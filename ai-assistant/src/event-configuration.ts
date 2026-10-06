/** Human template revisions and immutable conversation configuration pins.
 * Read in order: validate native shape → restrict deployment authority → warn
 * about reaction topology → preview canonical content → save with revision CAS.
 * Template text is configuration data; prompt edits cannot create capabilities. */
import { createHash, randomUUID } from "node:crypto";
import type { DatabaseSync } from "node:sqlite";
import { validateDefinition } from "@deepseek-ai/dsh-event-system";
import type { EventSystemDefinition, EventAgentDefinition, ExecutionLimits } from "@deepseek-ai/dsh-event-system";
import { executionLimits } from "./execution-policy.js";
import { isRecord } from "./types.js";

export interface EventConfiguration {
  schemaVersion: 1;
  domain: "spec" | "circuit";
  preset: "goal" | "orchestrated";
  definition: EventSystemDefinition;
  limits: ExecutionLimits;
}
export interface EventTemplate { key: string; name: string; revision: number; text: string; builtin: boolean }
// Canonicalize object keys while preserving array order: agent/subscription and
// prompt order are authored content and must not be rearranged during review.
function sorted(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sorted);
  if (isRecord(value)) return Object.fromEntries(Object.keys(value).sort().map(key => [key, sorted(value[key])]));
  return value;
}
export const configurationText = (document: EventConfiguration): string => JSON.stringify(sorted(document), null, 2) + "\n";
const digest = (text: string): string => createHash("sha256").update(text).digest("hex");

export class EventConfigurations {
  private readonly builtins = new Map<string, EventTemplate>();
  constructor(private readonly database: DatabaseSync, private readonly route: { provider: string; model: string }) {
    database.exec(`CREATE TABLE IF NOT EXISTS event_templates (key TEXT PRIMARY KEY, name TEXT NOT NULL, revision INTEGER NOT NULL, text TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS binding_event_configuration (session_id TEXT PRIMARY KEY REFERENCES bindings(session_id) ON DELETE CASCADE, template_key TEXT NOT NULL, template_revision INTEGER NOT NULL, text TEXT NOT NULL);`);
  }
  addBuiltin(domain: EventConfiguration["domain"], preset: EventConfiguration["preset"], definition: EventSystemDefinition, limits: ExecutionLimits): void {
    const document: EventConfiguration = { schemaVersion: 1, domain, preset, definition, limits };
    this.builtins.set(`${domain}.${preset}`, { key: `${domain}.${preset}`, name: `${domain} · ${preset}`, revision: 0, builtin: true, text: configurationText(document) });
  }
  list(): EventTemplate[] {
    return [...this.builtins.values(), ...(this.database.prepare("SELECT * FROM event_templates ORDER BY name,key").all() as unknown as Omit<EventTemplate, "builtin">[]).map(row => ({ ...row, builtin: false }))];
  }
  get(key: string): EventTemplate {
    const value = this.list().find(item => item.key === key);
    if (!value) throw new Error("Unknown event template.");
    return value;
  }
  validate(text: unknown): { document: EventConfiguration; text: string; warnings: string[] } {
    if (typeof text !== "string" || Buffer.byteLength(text) > 60_000) throw new Error("Configuration text must be at most 60 KB.");
    const input: unknown = JSON.parse(text);
    if (!isRecord(input) || input.schemaVersion !== 1 || !["spec", "circuit"].includes(String(input.domain)) || !["goal", "orchestrated"].includes(String(input.preset))) throw new Error("Choose a supported domain, preset, and configuration schemaVersion 1.");
    if (Object.keys(input).some(key => !["schemaVersion", "domain", "preset", "definition", "limits"].includes(key))) throw new Error("Unknown configuration field.");
    const domain = input.domain as EventConfiguration["domain"], preset = input.preset as EventConfiguration["preset"];
    const definition = validateDefinition(input.definition);
    // Native shape validation is necessary but insufficient: an otherwise valid
    // roster may request capabilities this deployment never authorized.
    const base = JSON.parse(this.get(`${domain}.${preset}`).text) as EventConfiguration;
    if (definition.primary !== "primary" || definition.id !== base.definition.id || definition.version !== base.definition.version) throw new Error("Keep the trusted preset identity and primary member.");
    if (!isRecord(input.limits)) throw new Error("Explicit resource limits are required.");
    const { maxOutputTokens, ...rest } = input.limits;
    if (maxOutputTokens !== base.limits.maxOutputTokens) throw new Error("The deployment owns the output token limit.");
    const limits = executionLimits(preset, rest, base.limits.maxOutputTokens);
    for (const [name, value] of Object.entries(limits)) if (value > base.limits[name as keyof ExecutionLimits]) throw new Error(`${name} exceeds the deployment allowance.`);
    if (definition.agents.length > limits.maxMembers) throw new Error("Roster exceeds member capacity.");
    for (const member of definition.agents) {
      if (!/^[a-z][a-z0-9_-]{0,47}$/.test(member.id)) throw new Error("Agent IDs must be short lowercase identifiers.");
      if (Buffer.byteLength(member.prompt) > 16_384) throw new Error(`Prompt too large for ${member.id}.`);
      const authority: EventAgentDefinition | undefined = base.definition.agents.find(agent => agent.id === member.id) ?? (preset === "orchestrated" ? { id: member.id, prompt: member.prompt, tools: ["get_bound_context", "publish_event", "get_event_system", "wait_for_event"], publishes: [], agentPreset: undefined } : undefined);
      // Deployment compositions are the capability ceiling. Prompts cannot grant permissions.
      if (!authority || member.agentPreset !== authority.agentPreset || member.tools.some(tool => !authority.tools.includes(tool)) || member.publishes.some(event => event in base.definition.events && !authority.publishes.includes(event))) throw new Error(`Unapproved composition, tools, or publications for ${member.id}.`);
      if (member.id === "primary" && member.publishes.length) throw new Error("Primary cannot publish domain results.");
      if ((member.provider !== undefined || member.model !== undefined) && (member.provider !== this.route.provider || member.model !== this.route.model)) throw new Error("Choose the deployment-approved provider and model together, or inherit the native route.");
    }
    for (const [event, schema] of Object.entries(base.definition.events)) if (JSON.stringify(sorted(definition.events[event])) !== JSON.stringify(sorted(schema))) throw new Error(`Keep the host payload contract for ${event}.`);
    for (const edge of definition.subscriptions) if (edge.retry && (edge.target === "primary" || edge.retry.maxAttempts > limits.maxRequests)) throw new Error("Automatic retry requires a read-only specialist and available request bounds.");
    if (preset === "goal" && (definition.agents.length !== 1 || definition.subscriptions.some(edge => edge.target !== "primary"))) throw new Error("Goal uses its one native primary.");
    if (preset === "orchestrated") {
      for (const role of ["analyst", "reviewer"]) if (!definition.agents.some(agent => agent.id === role)) throw new Error(`Orchestrated requires the approved ${role} role.`);
      for (const [event, target] of [["user.requested", "analyst"], ["analysis.ready", "reviewer"], ["review.ready", "primary"], ["source.changed", "analyst"]]) if (!definition.subscriptions.some(edge => edge.event === event && edge.target === target)) throw new Error(`Orchestrated requires ${event} → ${target}.`);
    } else if (!definition.subscriptions.some(edge => edge.event === "source.changed" && edge.target === "primary")) throw new Error("Goal requires source.changed → primary.");
    for (const event of Object.keys(definition.events)) if (!/^[a-z][a-z0-9_.-]{0,79}$/.test(event)) throw new Error("Event types must be short lowercase identifiers.");
    const warnings: string[] = [];
    const host = new Set(["user.requested", "source.changed", "review.prepared", "review.applied", "review.discarded", "architecture.prepared", "architecture.decided"]);
    for (const event of Object.keys(definition.events)) {
      if (!definition.subscriptions.some(edge => edge.event === event)) warnings.push(`${event} has no subscription; it can still resolve a correlated wait or appear in inspection.`);
      if (!host.has(event) && !definition.agents.some(agent => agent.publishes.includes(event))) warnings.push(`${event} has no configured publisher.`);
    }
    // Reaction cycles are a review warning, not a DAG validation error. The native
    // runtime bounds causal depth, event growth, model requests and active time.
    const adjacency = new Map(definition.agents.map(agent => [agent.id, definition.subscriptions.filter(edge => agent.publishes.includes(edge.event)).map(edge => edge.target)]));
    const visited = new Set<string>(), visiting = new Set<string>();
    function cycle(id: string): boolean { if (visiting.has(id)) return true; if (visited.has(id)) return false; visiting.add(id); const found = (adjacency.get(id) ?? []).some(target => cycle(target)); visiting.delete(id); visited.add(id); return found; }
    if (definition.agents.some(agent => cycle(agent.id))) warnings.push("Reaction cycle detected. Depth, events, requests, and time bounds still apply; review the cycle before saving.");
    const document: EventConfiguration = { schemaVersion: 1, domain, preset, definition, limits };
    return { document, text: configurationText(document), warnings };
  }
  preview(key: string, revision: number, text: unknown) {
    const current = this.get(key);
    if (current.revision !== revision) throw new Error("Template changed; reload before reviewing.");
    const valid = this.validate(text);
    const previous = JSON.parse(current.text) as EventConfiguration;
    if (valid.document.domain !== previous.domain || valid.document.preset !== previous.preset) throw new Error("Template domain and preset are immutable.");
    // Bind acknowledgement to the exact canonical text and observed revision.
    // A later UI edit cannot reuse the token for previously reviewed content.
    const reviewDigest = digest(JSON.stringify([key, revision, valid.text]));
    return { before: current.text, after: valid.text, warnings: valid.warnings, reviewDigest };
  }
  save(key: string, revision: number, text: unknown, reviewed: unknown, name: unknown): EventTemplate {
    const preview = this.preview(key, revision, text);
    if (reviewed !== preview.reviewDigest) throw new Error("Review the current text diff and validation before saving.");
    if (typeof name !== "string" || !name.trim() || name.length > 80) throw new Error("Template name must contain 1–80 characters.");
    const current = this.get(key);
    if (current.builtin) {
      const created = { key: randomUUID(), name: name.trim(), revision: 1, text: preview.after, builtin: false };
      this.database.prepare("INSERT INTO event_templates VALUES(?,?,?,?)").run(created.key, created.name, created.revision, created.text);
      return created;
    }
    const result = this.database.prepare("UPDATE event_templates SET name=?,revision=revision+1,text=? WHERE key=? AND revision=?").run(name.trim(), preview.after, key, revision);
    if (result.changes !== 1) throw new Error("Template changed; reload before saving.");
    return this.get(key);
  }
  selection(domain: EventConfiguration["domain"], preset: EventConfiguration["preset"], key?: string, revision?: number) {
    const template = this.get(key ?? `${domain}.${preset}`);
    if (key && revision !== template.revision) throw new Error("Selected template changed; reload before starting.");
    const validated = this.validate(template.text);
    if (validated.document.domain !== domain || validated.document.preset !== preset) throw new Error("Template does not match the bound domain and preset.");
    return { template, ...validated };
  }
  pin(sessionId: string, domain: EventConfiguration["domain"], preset: EventConfiguration["preset"], key?: string, revision?: number): void {
    const selected = this.selection(domain, preset, key, revision);
    // Store resolved text, not a pointer to mutable catalog state. Existing chats
    // keep their prompt, routing, permission and resource identity after edits.
    this.database.prepare("INSERT INTO binding_event_configuration VALUES(?,?,?,?)").run(sessionId, selected.template.key, selected.template.revision, selected.text);
  }
  pinInstructions(sessionId: string, domain: EventConfiguration["domain"], preset: EventConfiguration["preset"],
    definition: EventSystemDefinition, limits: ExecutionLimits, sourceSessionId?: string): void {
    if (this.pinned(sessionId)) return;
    const source = sourceSessionId ? this.pinned(sourceSessionId) : undefined;
    const document = source?.document.domain === domain && source.document.preset === preset
      ? source.document : { schemaVersion: 1 as const, domain, preset, definition: validateDefinition(definition), limits };
    this.database.prepare("INSERT OR IGNORE INTO binding_event_configuration VALUES(?,?,?,?)")
      .run(sessionId, source?.key ?? `${domain}.${preset}`, source?.revision ?? 0, configurationText(document));
  }
  pinned(sessionId: string): { key: string; revision: number; document: EventConfiguration } | undefined {
    const row = this.database.prepare("SELECT * FROM binding_event_configuration WHERE session_id=?").get(sessionId) as { template_key: string; template_revision: number; text: string } | undefined;
    return row ? { key: row.template_key, revision: row.template_revision, document: JSON.parse(row.text) as EventConfiguration } : undefined;
  }
}

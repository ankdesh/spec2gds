/** Immutable static instructions. Service facts and permissions stay live. */
import { readFileSync, readdirSync } from "node:fs";
import { resolve, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import type { DatabaseSync } from "node:sqlite";
import { parsePromptBundleYaml } from "@deepseek-ai/dsh-prompt-catalog-yaml";
import { assertObjectJsonSchema, assertSupportedJsonSchema, type JsonSchemaNode } from "@deepseek-ai/dsh-tools";
import type { ToolName } from "./tool-arguments.js";

export const handlerCompatibilityVersion = 2;
export const toolNames: readonly ToolName[] = ["get_bound_context", "prepare_circuit_proposal"];
export interface ToolContract {
  name: ToolName; version: string; handler_key: ToolName; instruction_ref: string;
  availability: string; input_schema: JsonSchemaNode; output_schema: JsonSchemaNode;
  timeout_ms?: number; service_schema_slot?: string;
  unavailable?: { instruction_ref: string; input_schema: JsonSchemaNode };
}
export interface InstructionSnapshot {
  version: string; hash: string; handler_compatibility_version: number;
  files: Record<string, string>;
}
export const contentHash = (value: unknown): string => `sha256:${createHash("sha256").update(JSON.stringify(value)).digest("hex")}`;

export class InstructionBundle {
  readonly contracts: Record<ToolName, ToolContract>;
  private readonly texts: Record<string, string>;
  constructor(readonly snapshot: InstructionSnapshot) {
    this.snapshot = structuredClone(snapshot);
    const files = Object.fromEntries(Object.entries(snapshot.files).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0));
    if (contentHash(files) !== snapshot.hash) throw new Error("Instruction snapshot content hash does not match.");
    if (snapshot.handler_compatibility_version !== handlerCompatibilityVersion) throw new Error("Pinned instructions require incompatible handlers. Start a new conversation.");
    const release = JSON.parse(files["release.json"] ?? "null");
    if (release?.version !== snapshot.version || release?.handler_compatibility_version !== snapshot.handler_compatibility_version
      || !/^\d+\.\d+\.\d+$/.test(snapshot.version)) throw new Error("Invalid instruction release manifest.");
    this.texts = JSON.parse(files["instructions.json"] ?? "null");
    if (!this.texts || Object.values(this.texts).some(text => typeof text !== "string")) throw new Error("Invalid instruction catalogue.");
    const contractFiles = Object.keys(files).filter(path => path.startsWith("tools/"));
    if (contractFiles.length !== toolNames.length || contractFiles.some(path => !toolNames.some(name => path === `tools/${name}.json`))) {
      throw new Error("Instruction release contains unregistered tool contracts.");
    }
    this.contracts = Object.fromEntries(toolNames.map(name => {
      const contract: ToolContract = JSON.parse(files[`tools/${name}.json`] ?? "null");
      if (!contract || contract.name !== name || contract.handler_key !== name || contract.version !== "1.0.0"
        || contract.availability !== availability[name] || contract.instruction_ref !== `tool.${name}`
        || contract.service_schema_slot !== (name.endsWith("_proposal") ? "operations.items" : undefined)) throw new Error(`Unsupported tool contract: ${name}`);
      if (contract.unavailable) {
        assertObjectJsonSchema(contract.unavailable.input_schema);
        this.text(contract.unavailable.instruction_ref);
      }
      assertObjectJsonSchema(contract.input_schema);
      assertSupportedJsonSchema(contract.output_schema);
      this.text(contract.instruction_ref);
      return [name, contract];
    })) as Record<ToolName, ToolContract>;
    for (const domain of ["spec", "circuit"]) this.bind({ id: `spec2gds.${domain}`, version: "1.0.0" }, {
      "binding.owner": "", "binding.document_id": "", "binding.scope": "", "binding.target": "",
    });
    for (const preset of ["goal", "orchestrated"]) for (const domain of ["spec", "circuit"]) this.eventDefinition(domain, preset);
    freeze(this.snapshot);
    freeze(this.contracts);
    freeze(this.texts);
  }
  text(key: string, values: Record<string, string> = {}): string {
    const text = this.texts[key];
    if (typeof text !== "string") throw new Error(`Missing instruction reference: ${key}`);
    return render(text, values);
  }
  bind(ref: { id: string; version: string }, variables: Readonly<Record<string, string>>) {
    const domain = ref.id === "spec2gds.spec" ? "spec" : ref.id === "spec2gds.circuit" ? "circuit" : null;
    if (!domain || ref.version !== "1.0.0") throw new Error("Unsupported domain instruction reference.");
    const bundle = parsePromptBundleYaml(this.snapshot.files[`prompts/${domain}.yaml`] ?? "");
    if (bundle.metadata.id !== ref.id || bundle.metadata.version !== ref.version) throw new Error("Domain instruction identity mismatch.");
    return { sections: bundle.sections.map(section => ({ ...section, text: render(section.text, variables) })) };
  }
  eventDefinition(domain: string, preset: string): any {
    const definition = JSON.parse(this.snapshot.files[`event-systems/${domain}-${preset}.yaml`] ?? "null");
    if (!definition || definition.id !== `spec2gds.${domain}.${preset}`) throw new Error("Missing pinned event definition.");
    for (const member of definition.agents) {
      const prompt = this.snapshot.files[`event-systems/${member.prompt}`];
      if (typeof prompt !== "string") throw new Error("Missing pinned event-member instructions.");
      member.prompt = prompt;
    }
    return definition;
  }
}
const availability: Record<ToolName, string> = {
  get_bound_context: "bound", prepare_circuit_proposal: "circuit-primary",
};
function freeze(value: unknown): void {
  if (value && typeof value === "object") {
    for (const child of Object.values(value)) freeze(child);
    Object.freeze(value);
  }
}
function render(text: string, variables: Readonly<Record<string, string>>): string {
  return text.replace(/\{\{([^{}]+)\}\}/g, (_whole, key: string) => {
    const value = variables[key.trim()];
    if (value === undefined) throw new Error(`Unresolved instruction variable: ${key}`);
    return value;
  });
}
export function loadInstructions(root: string): InstructionBundle {
  const files: Record<string, string> = {};
  const visit = (directory: string) => {
    for (const entry of readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name < b.name ? -1 : a.name > b.name ? 1 : 0)) {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) visit(path);
      else if (entry.isFile()) files[relative(root, path).replaceAll("\\", "/")] = readFileSync(path, "utf8");
    }
  };
  visit(root);
  const sorted = Object.fromEntries(Object.entries(files).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0));
  const release = JSON.parse(files["release.json"]!);
  return new InstructionBundle({ ...release, hash: contentHash(sorted), files: sorted });
}
export const defaultInstructions = loadInstructions(process.env.SPEC2GDS_CATALOG_ROOT
  ?? fileURLToPath(new URL("../profile/catalog", import.meta.url)));

/** No binding foreign key: an unbound conversation also has a durable pin. */
export class InstructionSnapshots {
  constructor(private readonly database: DatabaseSync, readonly current = defaultInstructions) {
    database.exec(`CREATE TABLE IF NOT EXISTS instruction_releases(version TEXT PRIMARY KEY, hash TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS instruction_snapshots(session_id TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL);`);
    const release = database.prepare("SELECT hash FROM instruction_releases WHERE version=?").get(current.snapshot.version) as { hash: string } | undefined;
    if (release && release.hash !== current.snapshot.hash) throw new Error("Instruction release version was reused with changed content.");
    database.prepare("INSERT OR IGNORE INTO instruction_releases VALUES(?,?)").run(current.snapshot.version, current.snapshot.hash);
  }
  has(id: string): boolean {
    return !!this.database.prepare("SELECT 1 FROM instruction_snapshots WHERE session_id=?").get(id);
  }
  get(id: string): InstructionBundle | null {
    const row = this.database.prepare("SELECT snapshot_json FROM instruction_snapshots WHERE session_id=?").get(id) as { snapshot_json: string } | undefined;
    return row ? new InstructionBundle(JSON.parse(row.snapshot_json)) : null;
  }
  pin(id: string, source?: string): InstructionBundle {
    const old = this.get(id);
    if (old) return old;
    const bundle = source ? this.get(source) : this.current;
    if (!bundle) throw new Error("Source conversation has no instruction snapshot. Start a new conversation.");
    this.database.prepare("INSERT OR IGNORE INTO instruction_snapshots VALUES(?,?)").run(id, JSON.stringify(bundle.snapshot));
    return this.get(id)!;
  }
}

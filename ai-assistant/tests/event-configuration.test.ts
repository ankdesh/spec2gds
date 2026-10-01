import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";
import { EventConfigurations } from "../src/event-configuration.js";

function fixture() {
  const database = new DatabaseSync(":memory:");
  database.exec("CREATE TABLE bindings (session_id TEXT PRIMARY KEY)");
  const service = new EventConfigurations(database, { provider: "mock", model: "mock" });
  for (const domain of ["spec", "circuit"] as const) for (const preset of ["goal", "orchestrated"] as const) {
    const source = new URL(`../profile/catalog/event-systems/${domain}-${preset}.yaml`, import.meta.url);
    const definition = JSON.parse(readFileSync(source, "utf8"));
    definition.agents = definition.agents.map((agent: any) => ({ ...agent, prompt: readFileSync(new URL(agent.prompt, source), "utf8") }));
    service.addBuiltin(domain, preset, definition, { maxRounds: 8, maxRequests: 48, maxTokens: 500000, maxActiveMillis: 60000, maxMembers: preset === "goal" ? 1 : 7, maxConcurrency: preset === "goal" ? 1 : 3, maxPending: 100, maxEvents: 100, maxPayloadBytes: 8192, maxDepth: 8, maxOutputTokens: 1200 });
  }
  return { database, service };
}

test("reviewed configuration revisions pin exact text and reject stale or unreviewed changes", () => {
  const { database, service } = fixture();
  try {
    for (const preset of ["goal", "orchestrated"]) {
      const initial = service.get(`spec.${preset}`), document = JSON.parse(initial.text);
      document.definition.agents[0].prompt += "\nA human edit.";
      const text = JSON.stringify(document), preview = service.preview(initial.key, 0, text);
      assert.throws(() => service.save(initial.key, 0, text, "old review", "Custom"), /Review the current/);
      const saved = service.save(initial.key, 0, text, preview.reviewDigest, "Custom");
      database.prepare("INSERT INTO bindings VALUES(?)").run(preset);
      service.pin(preset, "spec", preset as "goal" | "orchestrated", saved.key, 1);
      const original = service.pinned(preset);
      document.definition.agents[0].prompt += "\nAnother edit.";
      const next = service.preview(saved.key, 1, JSON.stringify(document));
      service.save(saved.key, 1, next.after, next.reviewDigest, "Custom");
      assert.deepEqual(service.pinned(preset), original);
      assert.throws(() => service.preview(saved.key, 1, next.after), /Template changed/);
      assert.throws(() => service.pin(preset, "circuit", preset as "goal" | "orchestrated", saved.key, 2), /does not match/);
      assert.equal(service.validate(next.after).text, next.after);
      const restored = new EventConfigurations(database, { provider: "mock", model: "mock" });
      assert.deepEqual(restored.pinned(preset), original);
      assert.equal(restored.get(saved.key).revision, 2);
    }
  } finally { database.close(); }
});

test("preflight enforces host schemas, references, review roles, native routes and deployment budgets", () => {
  const { database, service } = fixture();
  try {
    const original = JSON.parse(service.get("spec.orchestrated").text);
    for (const [edit, expected] of [
      [(doc: any) => doc.definition.agents[0].tools.push("run_shell"), /Unapproved/],
      [(doc: any) => doc.definition.agents[1].publishes.push("review.ready"), /Unapproved/],
      [(doc: any) => doc.definition.agents[0].provider = "foreign", /approved provider/],
      [(doc: any) => doc.limits.maxRequests = 49, /deployment allowance/],
      [(doc: any) => doc.definition.subscriptions[0].target = "missing", /Invalid subscription/],
      [(doc: any) => delete doc.definition.events["source.changed"], /subscription|payload contract/],
      [(doc: any) => doc.definition.events["analysis.ready"].required = [], /host payload contract/],
      [(doc: any) => doc.definition.subscriptions = doc.definition.subscriptions.slice(1), /requires user.requested/],
      [(doc: any) => doc.definition.subscriptions[2].retry = { replaySafe: true, maxAttempts: 3, initialBackoffMillis: 1, maxBackoffMillis: 10 }, /read-only specialist/],
    ] as const) {
      const document = structuredClone(original); edit(document);
      assert.throws(() => service.validate(JSON.stringify(document)), expected);
    }
    assert.throws(() => service.validate('{"schemaVersion":1}'), /supported domain/);
    assert.throws(() => service.validate(" ".repeat(60001)), /60 KB/);
  } finally { database.close(); }
});

test("approved read-only observers, custom contracts and bounded reaction cycles round-trip", () => {
  const { database, service } = fixture();
  try {
    const doc = JSON.parse(service.get("spec.orchestrated").text);
    doc.definition.events["observation.ready"] = { type: "object", properties: { text: { type: "string" } }, required: ["text"], additionalProperties: false };
    doc.definition.agents.push({ id: "observer", prompt: "Observe read-only context.", tools: ["get_bound_context", "publish_event"], publishes: ["observation.ready"] });
    doc.definition.subscriptions.push({ id: "observe", event: "observation.ready", target: "observer" });
    const valid = service.validate(JSON.stringify(doc));
    assert.ok(valid.warnings.some(warning => warning.includes("Reaction cycle")));
    assert.deepEqual(service.validate(valid.text).document, valid.document);
    doc.definition.agents.at(-1).tools.push("prepare_spec_proposal");
    assert.throws(() => service.validate(JSON.stringify(doc)), /Unapproved/);
  } finally { database.close(); }
});

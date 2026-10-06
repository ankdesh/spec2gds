import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ProductState } from "../src/state.js";
import { InstructionBundle, InstructionSnapshots, defaultInstructions, contentHash, toolNames } from "../src/instructions.js";
import { nativeTool } from "../src/tool-registry.js";
import { registerDomainTools } from "../src/tools.js";
import { registerArchitectureTool } from "../src/architecture-review.js";
import { registerSourceCreationTool } from "../src/source-creation.js";
import { specAdapter } from "../src/service-adapters/spec.js";
import { circuitAdapter } from "../src/service-adapters/circuit.js";
import { metadataDigest } from "../src/service-adapters/metadata.js";
import { assertObjectJsonSchema } from "@deepseek-ai/dsh-tools";
import { EventConfigurations } from "../src/event-configuration.js";

function modified(version: string, change: (files: Record<string, string>) => void = () => {}) {
  const snapshot = structuredClone(defaultInstructions.snapshot);
  snapshot.version = version;
  snapshot.files["release.json"] = JSON.stringify({ version, handler_compatibility_version: 1 });
  change(snapshot.files);
  snapshot.files = Object.fromEntries(Object.entries(snapshot.files).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0));
  snapshot.hash = contentHash(snapshot.files);
  return new InstructionBundle(snapshot);
}

test("the registry exposes the five JSON contracts with unchanged native schemas", () => {
  const found = new Map<string, any>();
  const ctx: any = { tools: { register(tool: any) { found.set(tool.name, tool); return () => {}; } } };
  const contract: any = { tool_schema: { type: "json" } };
  for (const domain of ["spec", "circuit"]) registerDomainTools(ctx, { domain, scope: "document", documentId: "d" } as any,
    {} as any, {} as any, undefined, undefined, undefined, false, contract);
  registerArchitectureTool({ id: "x", ctx }, {} as any, {} as any, () => "");
  registerSourceCreationTool({ ctx }, {} as any, () => ({}) as any);
  assert.deepEqual([...found.keys()].sort(), [...toolNames].sort());
  const baseline = JSON.parse(readFileSync(new URL("./fixtures/native-tool-schemas.json", import.meta.url), "utf8"));
  for (const name of toolNames) {
    assert.deepEqual(found.get(name).parameters, baseline[name].input_schema);
    assert.deepEqual(found.get(name).output.schema, baseline[name].output_schema);
  }
});

test("contract admission rejects unsupported schema keywords, references and handler declarations", () => {
  for (const edit of [
    (contract: any) => { contract.input_schema.properties.cursor.pattern = "a"; },
    (contract: any) => { contract.input_schema.properties.cursor.$ref = "#/$defs/x"; },
    (contract: any) => { contract.handler_key = "untrusted_handler"; },
    (contract: any) => { contract.instruction_ref = "missing"; },
    (contract: any) => { contract.availability = "all"; },
  ]) assert.throws(() => modified("2.0.0", files => {
    const contract = JSON.parse(files["tools/get_bound_context.json"]!); edit(contract);
    files["tools/get_bound_context.json"] = JSON.stringify(contract);
  }));
  assert.throws(() => modified("2.0.0", files => {
    files["prompts/spec.yaml"] = files["prompts/spec.yaml"]!.replace("{{binding.target}}", "{{unknown}} ");
  }), /Unresolved instruction variable/);
  assert.throws(() => modified("2.0.0", files => { delete files["event-systems/prompts/primary.md"]; }), /Missing pinned event-member/);
  assert.throws(() => modified("2.0.0", files => {
    files["tools/unregistered.json"] = files["tools/get_bound_context.json"]!;
  }), /unregistered tool contracts/);
  assert.throws(() => nativeTool("prepare_spec_proposal"), /Live service operation schema/);
});

test("unbound snapshots survive restart and new releases without instruction replacement", () => {
  const root = mkdtempSync(join(tmpdir(), "instructions-")); const path = join(root, "state.sqlite3");
  let state = new ProductState(path);
  try {
    let snapshots = new InstructionSnapshots(state.database);
    const old = snapshots.pin("unbound");
    assert.equal(state.getBinding("unbound"), null);
    assert.throws(() => { old.snapshot.files["instructions.json"] = "changed"; }, TypeError);
    state.close(); state = new ProductState(path);
    const newer = modified("1.1.0", files => {
      const texts = JSON.parse(files["instructions.json"]!); texts.architecture += "\nNew release.";
      files["instructions.json"] = JSON.stringify(texts);
    });
    snapshots = new InstructionSnapshots(state.database, newer);
    assert.equal(snapshots.get("unbound")!.text("architecture"), old.text("architecture"));
    assert.equal(snapshots.pin("new").snapshot.version, "1.1.0");
    assert.equal(snapshots.pin("continuation", "unbound").snapshot.hash, old.snapshot.hash);
    assert.equal(snapshots.pin("reviewer", "continuation").snapshot.hash, old.snapshot.hash);
    assert.throws(() => snapshots.pin("missing-child", "missing-parent"), /no instruction snapshot/);
    assert.throws(() => new InstructionSnapshots(state.database, modified("1.0.0", files => {
      files["instructions.json"] += "\n";
    })), /version was reused/);
  } finally { state.close(); rmSync(root, { recursive: true, force: true }); }
});

test("changed or incompatible stored snapshots block execution without deleting design records", () => {
  const state = new ProductState(":memory:");
  try {
    const pins = new InstructionSnapshots(state.database); pins.pin("old");
    const snapshot = structuredClone(defaultInstructions.snapshot); snapshot.handler_compatibility_version = 2;
    state.database.prepare("UPDATE instruction_snapshots SET snapshot_json=? WHERE session_id=?").run(JSON.stringify(snapshot), "old");
    assert.equal(pins.has("old"), true);
    assert.throws(() => pins.get("old"), /incompatible handlers/);
    assert.equal(pins.has("legacy"), false);
    assert.equal(pins.get("legacy"), null);
  } finally { state.close(); }
});

test("separate adapters accept their own metadata and reject routing or identity changes", () => {
  for (const [domain, adapter] of [["spec", specAdapter], ["circuit", circuitAdapter]] as const) {
    const value = JSON.parse(readFileSync(new URL(`./fixtures/${domain}-integration-metadata.json`, import.meta.url), "utf8"));
    adapter.validate(value);
    for (const edit of [
      (v: any) => { v.service_kind = "other"; }, (v: any) => { v.format_version = 2; },
      (v: any) => { v.interface_version = "2.0.0"; },
      (v: any) => { v.actions.operation_schema.path = "https://other.example/write"; },
      (v: any) => { v.actions.extra = v.actions.operation_schema; },
    ]) {
      const bad = structuredClone(value); edit(bad); const { digest: _, ...content } = bad;
      bad.digest = metadataDigest(content); assert.throws(() => adapter.validate(bad), /Incompatible/);
    }
    assert.throws(() => adapter.requestUrl("http://service", "unknown"), /Unknown/);
  }
  assert.equal(circuitAdapter.requestUrl("http://service/api/circuit-designer/v1", "context_document", { document_id: "a/b" }),
    "http://service/api/circuit-designer/v1/documents/a%2Fb");
});

test("event-member instructions resolve from the pinned release and retain capability boundaries", () => {
  const state = new ProductState(":memory:");
  try {
    const config = new EventConfigurations(state.database, { provider: "openai", model: "fixture" });
    const definition = defaultInstructions.eventDefinition("spec", "orchestrated");
    assert.match(definition.agents[0].prompt, /./);
    assert.ok(definition.agents.find((m: any) => m.id === "reviewer").tools.every((name: string) => !name.startsWith("prepare_")));
    const input: any = { domain: "spec", serviceUrl: "http://service", serviceBaseUrl: "http://service", documentId: "d", scope: "document",
      workspaceKey: "w", workspaceTitle: "w", workspacePath: "/tmp/w", workspaceDomain: "spec", workspaceServiceUrl: "http://service", workspaceDocumentId: "d" };
    state.createBinding("source", input); state.createBinding("destination", input);
    config.pinInstructions("source", "spec", "orchestrated", definition, {} as any);
    const changed = structuredClone(definition); changed.agents[0].prompt = "Changed catalogue.";
    config.pinInstructions("destination", "spec", "orchestrated", changed, {} as any, "source");
    assert.deepEqual(config.pinned("destination")!.document, config.pinned("source")!.document);
  } finally { state.close(); }
});


test("schema outages retain a valid native unavailable tool without granting operations", async () => {
  for (const domain of ["spec", "circuit"] as const) {
    const tools = new Map<string, any>();
    registerDomainTools({ tools: { register(value: any) { assertObjectJsonSchema(value.parameters); tools.set(value.name, value); return () => {}; } } },
      { domain, scope: "document", documentId: "d", sessionId: "x" } as any, {} as any, {} as any);
    const tool = tools.get(`prepare_${domain}_proposal`);
    assert.deepEqual(tool.parameters, { type: "object", properties: {} });
    const result = await tool.execute({}, { callId: "unavailable" });
    assert.equal(result.success, false);
    assert.equal(result.error.error_code, "SERVICE_CONTRACT_ERROR");
  }
});

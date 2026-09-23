import assert from "node:assert/strict";
import test from "node:test";
import { validateArgs } from "@deepseek-ai/dsh-tools";
import { promptSectionsFor, shapeBoundContext } from "../src/domain-context.js";
import { CIRCUIT_OPERATION_SCHEMA, SPEC_OPERATION_SCHEMA, validateProposalSemantics } from "../src/operation-schemas.js";
import type { SessionBinding } from "../src/types.js";

const binding = (domain: "spec" | "circuit", scope: "document" | "entity" = "document"): SessionBinding => ({
  sessionId: "session-1", status: "active", preset: "focused", domain, ownerUrl: "http://owner", documentId: "doc-1", scope,
  entityKind: scope === "entity" ? "component" : null, entityId: scope === "entity" ? "component-1" : null,
  title: "Test", archived: false, createdAt: "", updatedAt: "",
  workspaceKey: "test", workspaceTitle: "Test", workspacePath: "/tmp/test",
  workspaceDomain: domain, workspaceOwnerUrl: "http://owner", workspaceDocumentId: "doc-1",
});

const sectionText = (domain: "spec" | "circuit", scope: "document" | "entity" = "document"): string =>
  promptSectionsFor(binding(domain, scope)).map(section => section.text).join("\n\n");

test("bound domain prompts use four typed composable sections", () => {
  const expectedNames = [
    "spec2gds:domain-persona",
    "spec2gds:binding-context",
    "spec2gds:operation-constraints",
    "spec2gds:output-contract",
  ];
  for (const domain of ["spec", "circuit"] as const) {
    const sections = promptSectionsFor(binding(domain));
    assert.deepEqual(sections.map(section => section.name), expectedNames);
    assert.deepEqual(sections.map(section => section.order), [100, 150, 200, 300]);
    assert.equal(new Set(sections.map(section => section.name)).size, sections.length);
    assert.ok(sections.every(section => typeof section.text === "string" && section.text.length > 0));
    assert.ok(sections.every(section => !Object.hasOwn(section, "complete")));
  }
});

test("composed domain prompts retain proposal and safety rules", () => {
  const spec = sectionText("spec", "entity");
  for (const phrase of [
    "WRITABLE BOUNDARY", "exact entity IDs", "supported=false", "SystemVerilog", "component_vlnv",
    "List every material assumption", "Do not emit XML", "claim that a change was applied",
  ]) assert.match(spec, new RegExp(phrase));
  const circuit = sectionText("circuit");
  for (const phrase of [
    "complete replacements", "VALID ENDPOINT CATALOG", "cascade=false", "supported=false",
    "List every material assumption", "Never claim a proposal was applied or sent",
  ]) assert.match(circuit, new RegExp(phrase));
});

test("binding section names immutable entity and document targets and requires fresh context", () => {
  const entity = sectionText("spec", "entity");
  assert.match(entity, /Owner: Spec Editor/);
  assert.match(entity, /Document ID: doc-1/);
  assert.match(entity, /Scope: entity/);
  assert.match(entity, /Selected target: component component-1/);
  assert.match(entity, /MUST call get_bound_context before answering/);
  assert.match(entity, /Never ask the user which document or design they mean/);

  const document = sectionText("circuit");
  assert.match(document, /Owner: Circuit Designer/);
  assert.match(document, /Scope: document/);
  assert.match(document, /Selected target: the complete document/);
});

test("deterministic Spec context checks identity and exposes boundaries", () => {
  const context = shapeBoundContext(binding("spec", "entity"), {
    document_id: "doc-1", source_revision_hash: "sha256:one", scope: "entity",
    target: { document_id: "doc-1", entity_kind: "component", entity_id: "component-1" },
    writable: { entity_refs: [{ entity_id: "component-1" }], entity: { name: "alu" }, sections: [] },
    read_only: { neighbors: [] }, available_references: { components: [{ vlnv: "acme:lib:alu:1.0" }] }, diagnostics: [],
  });
  assert.match(context.text, /WRITABLE SEMANTIC IR/);
  assert.match(context.text, /READ-ONLY SURROUNDING CONTEXT/);
  assert.match(context.text, /acme:lib:alu:1.0/);
  assert.throws(() => shapeBoundContext(binding("spec", "entity"), {
    document_id: "other", source_revision_hash: "sha256:one", scope: "entity",
  }), /bound document/);
});

test("deterministic Circuit context lists exact endpoints and complete values", () => {
  const context = shapeBoundContext(binding("circuit"), {
    revision: "rev-1", document: { document_id: "doc-1", label: "Demo", components: [{
      id: "alu", label: "ALU", origin: "local", editable: true,
      terminals: [{ id: "sum", label: "sum", direction: "output", width: 8, category: "port" }],
      parameters: [], appearance: { renderer_key: "default", properties: { color: "blue" } },
    }], design: { id: "top", instances: [{ id: "u1", label: "u1", component_id: "alu", parameter_values: { WIDTH: 8 } }], boundary_terminals: [], nets: [] } },
  }, '<svg viewBox="0 0 100 80"><g data-instance-id="u1"/><path data-net-id="n1"/></svg>');
  assert.match(context.text, /VALID ENDPOINT CATALOG/);
  assert.match(context.text, /u1\.sum/);
  assert.match(context.text, /model-output parameter_values/);
  assert.match(context.text, /"name":"color"/);
  assert.match(context.text, /viewBox=0 0 100 80/);
  assert.match(context.text, /net ids=\["n1"\]/);
});

test("operation schemas reject unknown fields and wrong discriminated payloads", () => {
  const circuitParameters = { operations: { type: "array", items: CIRCUIT_OPERATION_SCHEMA, required: true } } as const;
  assert.deepEqual(validateArgs(circuitParameters, { operations: [{ operation_id: "delete", type: "delete_net", net_id: "n1" }] }), []);
  assert.ok(validateArgs(circuitParameters, { operations: [{ operation_id: "delete", type: "delete_net", net_id: "n1", surprise: true }] }).length);
  assert.ok(validateArgs(circuitParameters, { operations: [{ operation_id: "bad", type: "delete_net", component_id: "c1" }] }).length);

  const specParameters = { operations: { type: "array", items: SPEC_OPERATION_SCHEMA, required: true } } as const;
  assert.deepEqual(validateArgs(specParameters, { operations: [{ operation_id: "create", type: "create_entity", kind: "component", name: "timer", instances: [] }] }), []);
  assert.ok(validateArgs(specParameters, { operations: [{ operation_id: "create", type: "create_entity", kind: "component", name: "timer", instances: [], entity_id: "model-owned" }] }).length);
});

test("operation unions retain the complete former assistant vocabulary", () => {
  const discriminators = (schema: unknown): string[] => {
    const branches = (schema as { oneOf: Array<{ properties?: Record<string, { const?: string }> }> }).oneOf;
    return branches.map(branch => String(branch.properties?.type?.const)).sort();
  };
  assert.deepEqual(discriminators(CIRCUIT_OPERATION_SCHEMA), [
    "add_boundary_terminal", "add_component", "add_instance", "connect_endpoint", "create_net", "delete_net", "disconnect_endpoint",
    "remove_boundary_terminal", "remove_component", "remove_instance", "update_boundary_terminal", "update_component", "update_instance", "update_net",
  ].sort());
  assert.deepEqual(discriminators(SPEC_OPERATION_SCHEMA), [
    "clear_internal_design", "create_entity", "delete_abstraction_port", "delete_bus_interface", "delete_channel", "delete_component_port",
    "delete_connection", "delete_entity_section", "delete_instance", "delete_narrative_block", "delete_parameter", "reorder_connections",
    "reorder_instances", "reorder_narrative_blocks", "set_abstraction_bus_type", "set_entity_metadata", "set_internal_design",
    "set_narrative_entity_links", "update_bus_definition", "upsert_abstraction_port", "upsert_bus_interface", "upsert_channel",
    "upsert_component_port", "upsert_connection", "upsert_entity_section", "upsert_instance", "upsert_narrative_block", "upsert_parameter",
  ].sort());
});

test("proposal semantic guards enforce unsupported and domain invariants", () => {
  assert.doesNotThrow(() => validateProposalSemantics("spec", false, "Outside the writable boundary.", []));
  assert.throws(() => validateProposalSemantics("spec", false, null, []), /unsupported_reason/);
  assert.throws(() => validateProposalSemantics("circuit", true, null, [{ operation_id: "n", type: "create_net", net: { endpoints: [] } }]), /at least one endpoint/);
  assert.throws(() => validateProposalSemantics("spec", true, null, [{ operation_id: "c", type: "create_entity", kind: "component", name: "bad name", instances: [] }]), /XML-compatible/);
  assert.throws(() => validateProposalSemantics("spec", true, null, [{ operation_id: "same", type: "delete_parameter" }, { operation_id: "same", type: "delete_parameter" }]), /Duplicate/);
  assert.throws(() => validateProposalSemantics("spec", true, null, [{ operation_id: "block", type: "upsert_narrative_block", block: {
    block_id: "intro", type: "paragraph", text: "Hello", inlines: [], children: [], ordered: false, rows: [], asset_id: "", alt_text: "", caption: "", entity_refs: [], renderer_id: "", options: [], unexpected: true,
  } }]), /fields mismatch/);
});

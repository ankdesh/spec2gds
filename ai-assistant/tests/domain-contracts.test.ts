import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { UNBOUND_SOURCE_PROMPT } from "../src/index.js";
import { promptSectionsFor, shapeBoundContext } from "../src/domain-context.js";
import { validateProposalEnvelope } from "../src/operation-schemas.js";
import { parseOwnerOperationContract, validateOwnerOperations, verifyOwnerOperationContract } from "../src/owner-operation-schema.js";
import { proposalInputRequest, proposedComponentFields, structuredQuestionPrompt } from "../src/tools.js";
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

test("structured-question policy is conditional and requires the interactive tool", () => {
  assert.equal(structuredQuestionPrompt(false), null);
  const section = structuredQuestionPrompt(true);
  assert.ok(section);
  assert.equal(section.name, "spec2gds:interactive-clarification");
  assert.equal(section.order, 250);
  assert.equal(Object.hasOwn(section, "complete"), false);
  assert.match(section.text, /MUST call ask_user_question/);
  assert.match(section.text, /every missing value in required_fields/);
  assert.match(section.text, /LLM-suggested default_value for every field/);
  assert.match(section.text, /Do not list missing proposal fields in an ordinary assistant response/);
  assert.match(section.text, /cannot be derived from bound context/);
  assert.match(section.text, /durable event waiting is not available/);
});

test("missing details use model-suggested defaults in both domains", () => {
  const fields = [{ name: "width", label: "Terminal width", description: "Width in bits.", default_value: "8" }];
  for (const domain of ["spec", "circuit"] as const) {
    const request = proposalInputRequest(binding(domain), "The width is required.", fields);
    assert.equal(request?.fields[0]?.default_value, "8");
    assert.equal(proposalInputRequest(binding(domain), "Unsupported operation.", []), null);
  }
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

test("owner schema converts to a tool schema and validates operations", () => {
  const contract = parseOwnerOperationContract({
    schema_version: 1, digest: `sha256:${"a".repeat(64)}`,
    operation_schema: {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      oneOf: [{ type: "object", additionalProperties: false, required: ["operation_id", "type"],
        properties: { operation_id: { type: "string", minLength: 1 }, type: { const: "delete_net", type: "string" },
          net_id: { type: "string", pattern: "^[a-z]+$" } } }],
    },
  });
  assert.doesNotThrow(() => validateOwnerOperations(contract, [{ operation_id: "delete", type: "delete_net", net_id: "n" }]));
  assert.throws(() => validateOwnerOperations(contract, [{ operation_id: "delete", type: "delete_net", net_id: "BAD" }]), /owner's published schema/);
  assert.throws(() => parseOwnerOperationContract({ schema_version: 1, digest: contract.digest,
    operation_schema: { $schema: "https://json-schema.org/draft/2020-12/schema", anyOf: [] } }), /Unsupported owner schema keyword/);
});

test("proposal envelope checks remain independent of owner semantics", () => {
  assert.doesNotThrow(() => validateProposalEnvelope(false, "Outside the writable boundary.", []));
  assert.throws(() => validateProposalEnvelope(false, null, []), /unsupported_reason/);
  assert.throws(() => validateProposalEnvelope(true, null, [{ operation_id: "same" }, { operation_id: "same" }]), /Duplicate/);
});


test("canonical Circuit protocol assistant subset converts and rejects invalid operations", () => {
  const protocol = JSON.parse(readFileSync(new URL("../../circuit-designer/packages/core/src/protocol.schema.json", import.meta.url), "utf8"));
  const allowed = new Set([
    "AddComponentOperation", "UpdateComponentOperation", "RemoveComponentOperation",
    "AddInstanceOperation", "UpdateInstanceOperation", "RemoveInstanceOperation",
    "AddBoundaryTerminalOperation", "UpdateBoundaryTerminalOperation", "RemoveBoundaryTerminalOperation",
    "CreateNetOperation", "UpdateNetOperation", "DeleteNetOperation",
    "ConnectEndpointOperation", "DisconnectEndpointOperation",
  ]);
  const contract = parseOwnerOperationContract({
    schema_version: 1, digest: `sha256:${"b".repeat(64)}`,
    operation_schema: {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      oneOf: protocol.$defs.CircuitOperation.oneOf.filter((branch: { $ref: string }) => allowed.has(branch.$ref.split("/").at(-1)!)),
      $defs: protocol.$defs,
    },
  });
  assert.equal((contract.operation_schema.oneOf as unknown[]).length, 14);
  assert.doesNotThrow(() => validateOwnerOperations(contract, [{ operation_id: "delete", type: "delete_net", net_id: "n1" }]));
  assert.throws(() => validateOwnerOperations(contract, [{ operation_id: "delete", type: "set_instance_geometry", instance_id: "u1" }]), /owner's published schema/);
});


test("published Spec document and entity schemas convert without fallback", () => {
  const source = JSON.parse(readFileSync(new URL("../../spec2gds/agent_spec/spec_format/assistant_operation_schema.json", import.meta.url), "utf8"));
  for (const scope of ["document", "entity"] as const) {
    const branches = scope === "document" ? source.oneOf : source.oneOf.filter((branch: { properties: { type: { const: string } } }) =>
      branch.properties.type.const !== "create_entity");
    const contract = parseOwnerOperationContract({ schema_version: 1, digest: `sha256:${"c".repeat(64)}`,
      operation_schema: { $schema: source.$schema, oneOf: branches } });
    assert.ok(contract.tool_schema);
    if (scope === "document") {
      assert.doesNotThrow(() => validateOwnerOperations(contract, [{ operation_id: "create", type: "create_entity", kind: "component", name: "gate" }]));
      assert.doesNotThrow(() => validateOwnerOperations(contract, [{ operation_id: "edit", type: "set_entity_metadata",
        entity: { document_id: "doc-1", entity_kind: "component", entity_id: "component-1" }, description: "Refined" }]));
      assert.throws(() => validateOwnerOperations(contract, [{ operation_id: "edit", type: "set_entity_metadata" }]), /owner's published schema/);
    }
  }
});


test("changed owner schema digest requires fresh tool registration", () => {
  const current = parseOwnerOperationContract({ schema_version: 1, digest: `sha256:${"a".repeat(64)}`,
    operation_schema: { $schema: "https://json-schema.org/draft/2020-12/schema", type: "object", properties: {}, additionalProperties: false } });
  assert.doesNotThrow(() => verifyOwnerOperationContract(current, { ...current }));
  assert.throws(() => verifyOwnerOperationContract(current, { ...current, digest: `sha256:${"b".repeat(64)}` }), /Read get_bound_context again/);
  assert.throws(() => verifyOwnerOperationContract(current, { ...current, schema_version: 2 }), /invalid operation schema contract/);
});


test("Spec component details card uses proposed values without gate lookup defaults", () => {
  const fields = proposedComponentFields({ name: "custom_gate", ports: [
    { name: "left", direction: "in", range: "7:0" },
    { name: "right", direction: "in", range: "7:0" },
    { name: "result", direction: "out", range: "7:0" },
  ], systemverilog: "assign result = left ^ right;" });
  const defaults = Object.fromEntries(fields.map(field => [field.name, field.default_value]));
  assert.deepEqual(defaults, {
    component_name: "custom_gate", input_ports: "left, right", output_ports: "result",
    port_width: "8", behavior: "assign result = left ^ right;",
  });
});

test("comparator details keep 3-bit inputs and 1-bit result signals", () => {
  const fields = proposedComponentFields({ name: "comparator_3bit", ports: [
    { name: "A", direction: "in", range: "[2:0]" },
    { name: "B", direction: "in", range: "2:0" },
    { name: "A_greater", direction: "out" },
    { name: "A_equal", direction: "out" },
    { name: "A_less", direction: "out" },
  ] });
  const defaults = Object.fromEntries(fields.map(field => [field.label, field.default_value]));
  assert.equal(defaults["A width"], "3");
  assert.equal(defaults["B width"], "3");
  for (const output of ["A_greater", "A_equal", "A_less"]) assert.equal(defaults[`${output} width`], "1");
});


test("unbound prompt names both supported owner bindings", () => {
  assert.match(UNBOUND_SOURCE_PROMPT, /Spec Editor document or entity/);
  assert.match(UNBOUND_SOURCE_PROMPT, /Circuit Designer document/);
});

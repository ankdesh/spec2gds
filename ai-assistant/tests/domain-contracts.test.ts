import assert from "node:assert/strict";
import test from "node:test";
import { validateArgs } from "@deepseek-ai/dsh-tools";
import { promptSectionsFor, shapeBoundContext } from "../src/domain-context.js";
import { CIRCUIT_OPERATION_SCHEMA, SPEC_OPERATION_SCHEMA, validateProposalSemantics } from "../src/operation-schemas.js";
import { applyConfirmedComponentDetails, proposalInputRequest, registerDomainTools, structuredQuestionPrompt, type ProposalInputRequest } from "../src/tools.js";
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
  assert.match(section.text, /sensible default_value for every field/);
  assert.match(section.text, /Do not list missing proposal fields in an ordinary assistant response/);
  assert.match(section.text, /cannot be derived from bound context/);
  assert.match(section.text, /workflow input request capability/);
});

test("missing component details produce a defaulted form while genuinely unsupported requests remain errors", () => {
  const request = proposalInputRequest(
    binding("spec"),
    "The request does not provide a component name.",
    undefined,
    "Add a component with AND-gate semantics.",
  );
  assert.ok(request);
  assert.equal(request.title, "Complete the proposal details");
  assert.deepEqual(request.fields.map(field => [field.name, field.default_value]), [
    ["component_name", "AndGate"],
    ["input_ports", "A, B"],
    ["output_ports", "Y"],
    ["port_width", "1"],
    ["behavior", "Y = A & B"],
  ]);
  const requestDerived = proposalInputRequest(
    binding("spec"),
    "Review the component details before the proposal is prepared.",
    [{ name: "component_name", label: "Component name", description: "", default_value: "OrGate" }],
    "Create an 8-bit AND gate with sensible defaults, or let me edit them.",
    "OrGate",
  );
  assert.deepEqual(requestDerived?.fields.map(field => [field.name, field.default_value]), [
    ["component_name", "AndGate"],
    ["input_ports", "A, B"],
    ["output_ports", "Y"],
    ["port_width", "8"],
    ["behavior", "Y = A & B"],
  ]);
  const explicitlyNamed = proposalInputRequest(binding("spec"), "Review component details.", [],
    "Create an OR gate called StatusCombiner.", "AndGate");
  assert.equal(explicitlyNamed?.fields[0]?.default_value, "StatusCombiner");
  assert.equal(explicitlyNamed?.fields.at(-1)?.default_value, "Y = A | B");
  assert.equal(proposalInputRequest(binding("spec"), "Renaming entity identity is outside the writable boundary.", undefined), null);

  const explicit = proposalInputRequest(binding("circuit"), "A terminal width is required.", [{
    name: "width", label: "Terminal width", description: "Width in bits.", default_value: "1",
  }]);
  assert.equal(explicit?.fields[0]?.default_value, "1");
});

test("confirmed component form values become atomic initial ports and behavior", () => {
  const [operation] = applyConfirmedComponentDetails(
    [{ operation_id: "create", type: "create_entity", kind: "component", name: "placeholder", instances: [] }],
    [
      "Continue the pending design proposal using these user-confirmed values:",
      "- Component name: AndGate",
      "- Input ports: A, B",
      "- Output ports: Y",
      "- Port width: 1",
      "- Behavior: Y = A & B",
      "Prepare the proposal now.",
    ].join("\n"),
  ) as Array<Record<string, unknown>>;
  assert.equal(operation?.name, "AndGate");
  assert.deepEqual(operation?.ports, [
    { name: "A", family: "wire", display_name: null, description: null, direction: "in", range: null },
    { name: "B", family: "wire", display_name: null, description: null, direction: "in", range: null },
    { name: "Y", family: "wire", display_name: null, description: null, direction: "out", range: null },
  ]);
  assert.equal(operation?.systemverilog, "assign Y = A & B;");
});

test("the Spec proposal tool returns required input instead of an unsupported error for missing details", async () => {
  const registered: Array<{ name: string; execute(args: unknown, context: unknown): Promise<unknown> }> = [];
  registerDomainTools({
    tools: {
      register(tool) { registered.push(tool as typeof registered[number]); return () => undefined; },
      get() { return undefined; },
    },
  }, binding("spec"), {} as never, {} as never, undefined, undefined, undefined, true);
  const tool = registered.find(item => item.name === "prepare_spec_proposal");
  assert.ok(tool);
  const result = await tool.execute({
    supported: false,
    unsupported_reason: "The request does not provide a component name.",
    title: "Add an AND gate",
    summary: "Create a two-input AND gate.",
    rationale: "Requested by the user.",
    assumptions: ["Inputs A and B drive output Y."],
    operations: [],
  }, { callId: "call-1", signal: new AbortController().signal });
  assert.equal((result as { error?: unknown }).error, undefined);
  assert.equal((result as { required_input: ProposalInputRequest }).required_input.fields[0]?.default_value, "AndGate");

  const guessedProposal = await tool.execute({
    supported: true,
    unsupported_reason: null,
    title: "Create an AND-gate component",
    summary: "Create a two-input AND gate.",
    rationale: "Requested by the user.",
    assumptions: ["Inputs A and B drive output Y."],
    operations: [{ operation_id: "create", type: "create_entity", kind: "component", name: "Or", instances: [] }],
  }, { callId: "call-form", signal: new AbortController().signal });
  assert.equal((guessedProposal as { review?: unknown }).review, undefined);
  assert.equal((guessedProposal as { required_input: ProposalInputRequest }).required_input.fields[0]?.default_value, "AndGate");

  const confirmedTools: typeof registered = [];
  registerDomainTools({
    tools: {
      register(registeredTool) { confirmedTools.push(registeredTool as typeof registered[number]); return () => undefined; },
      get() { return undefined; },
    },
  }, binding("spec"), {} as never, {} as never, undefined, undefined,
  () => [
    "Continue the pending design proposal using these user-confirmed values:",
    "- Component name: AndGate",
    "- Input ports: A, B",
    "- Output ports: Y",
    "- Port width: 1",
    "- Behavior: Y = A & B",
  ].join("\n"), true);
  const confirmedTool = confirmedTools.find(item => item.name === "prepare_spec_proposal");
  assert.ok(confirmedTool);
  const afterConfirmation = await confirmedTool.execute({
    supported: true,
    unsupported_reason: null,
    title: "Create an AND-gate component",
    summary: "Create a two-input AND gate.",
    rationale: "Confirmed by the user.",
    assumptions: [],
    operations: [{ operation_id: "create", type: "create_entity", kind: "component", name: "AndGate", instances: [] }],
  }, { callId: "call-confirmed", signal: new AbortController().signal });
  assert.equal((afterConfirmation as { required_input?: unknown }).required_input, undefined, "confirmed details must not reopen the form");

  const unsupported = await tool.execute({
    supported: false,
    unsupported_reason: "Renaming entity identity is outside the writable boundary.",
    title: "Rename identity",
    summary: "Rename an immutable identity.",
    rationale: "Requested by the user.",
    assumptions: [],
    operations: [],
  }, { callId: "call-2", signal: new AbortController().signal });
  assert.equal((unsupported as { required_input?: unknown }).required_input, undefined);
  assert.equal((unsupported as { error: { error_code: string } }).error.error_code, "UNSUPPORTED_REQUEST");
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

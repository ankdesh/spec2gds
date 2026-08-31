import { describe, expect, it } from "vitest";
import {
  applyOperations,
  CircuitDraft,
  compileConstruction,
  connectedInstanceIds,
  createOperationBatch,
  documentFixtures,
  isCircuitSourceBindingV1,
  projectDocument,
  simpleDocumentFixture,
  terminalDefaultPlacement,
  uniqueSlug,
  validateCircuitDocument,
  validateComponentDesignBoundary,
  validateContractDefinition,
  resolveHierarchy,
  analyzeCircuitTiming,
  effectiveCircuitTiming,
  renderCircuitSvg,
  type CircuitConstruction,
} from "../src/index";

describe("independent circuit core", () => {
  it("validates every deterministic canonical fixture", () => {
    for (const build of Object.values(documentFixtures)) {
      const result = validateCircuitDocument(build());
      expect(result.errors, JSON.stringify(result.errors, null, 2)).toEqual([]);
      expect(result.diagnostics.filter((item) => item.severity === "error")).toEqual([]);
      expect(result.valid).toBe(true);
    }
  });

  it("validates public source-binding metadata at trust boundaries", () => {
    const binding = {
      schema_version: 1,
      binding_id: "binding_top",
      source_document_id: "spec_top",
      source_entity: { document_id: "spec_top", entity_id: "design_top", entity_kind: "design" },
      editable_design_id: "design_top",
      base_source_revision_hash: "sha256:base",
      writable: true,
      capabilities: ["topology", "layout"],
      omitted_bus_items: [],
      omitted_ports: [],
    };
    expect(isCircuitSourceBindingV1(binding)).toBe(true);
    expect(isCircuitSourceBindingV1({ ...binding, source_entity: { ...binding.source_entity, entity_kind: "asset" } })).toBe(false);
    expect(isCircuitSourceBindingV1({ ...binding, capabilities: "topology" })).toBe(false);
  });

  it("preserves inout direction and opaque symbolic widths", () => {
    const document = documentFixtures.bidirectional();
    const checked = validateCircuitDocument(document);
    expect(checked.valid).toBe(true);
    expect(checked.diagnostics.map((item) => item.code)).toContain("multiple_net_sources");

    const graph = projectDocument(document);
    expect(graph.terminals.map((terminal) => ({
      direction: terminal.direction,
      width: terminal.width,
    }))).toEqual([
      { direction: "inout", width: "[DATA_WIDTH-1:0]" },
      { direction: "inout", width: "[DATA_WIDTH-1:0]" },
    ]);
    expect(terminalDefaultPlacement("inout", 0).side).toBe("SOUTH");
  });

  it("allows whole symbolic terminals but rejects numeric slices on them", () => {
    const document = simpleDocumentFixture();
    document.components[0].terminals[0].width = "[SOURCE_WIDTH-1:0]";
    document.components[1].terminals[0].width = "[TARGET_WIDTH-1:0]";

    const unresolved = validateCircuitDocument(document);
    expect(unresolved.valid).toBe(true);
    expect(unresolved.diagnostics.map((item) => item.code)).toContain("width_unresolved");

    document.design.nets[0].endpoints[0] = {
      kind: "instance",
      instance_id: "producer_0",
      terminal_id: "data",
      slice: { lsb: 0, width: 4 },
    };
    const sliced = validateCircuitDocument(document);
    expect(sliced.valid).toBe(false);
    expect(sliced.diagnostics.map((item) => item.code)).toContain("slice_requires_numeric_width");
  });

  it("queries connected instances without provider or source-format knowledge", () => {
    expect(connectedInstanceIds(documentFixtures.hyperedge(), "source_0"))
      .toEqual(["sink_0", "sink_1", "sink_2"]);
  });

  it("creates deterministic readable collision suffixes", () => {
    expect(uniqueSlug("A useful Block", [])).toBe("a_useful_block");
    expect(uniqueSlug("A useful Block", ["a_useful_block", "a_useful_block_2"]))
      .toBe("a_useful_block_3");
  });

  it("rejects destructive instance removal unless cascade is explicit", () => {
    const document = simpleDocumentFixture();
    const rejected = applyOperations(document, [{
      operation_id: "remove_1",
      type: "remove_instance",
      instance_id: "producer_0",
    }]);
    expect(rejected.status).toBe("rejected");
    expect(rejected.diagnostics.map((item) => item.code)).toContain("cascade_required");

    const accepted = applyOperations(document, [{
      operation_id: "remove_2",
      type: "remove_instance",
      instance_id: "producer_0",
      cascade: true,
    }]);
    expect(accepted.status).toBe("accepted");
    expect(accepted.candidate?.design.nets[0].endpoints).toHaveLength(1);
    expect(accepted.diagnostics.map((item) => item.code)).toContain("incomplete_net");
  });

  it("builds operation batches and coalesces private draft moves", () => {
    const document = simpleDocumentFixture();
    const draft = new CircuitDraft(document, "7");
    draft.apply({
      operation_id: "move_1",
      type: "set_instance_geometry",
      instance_id: "producer_0",
      geometry: { x: 20, y: 20, width: 180, height: 100 },
    });
    draft.apply({
      operation_id: "move_2",
      type: "set_instance_geometry",
      instance_id: "producer_0",
      geometry: { x: 40, y: 60, width: 180, height: 100 },
    });
    expect(draft.operations).toHaveLength(1);
    expect(draft.toBatch("save_1").expected_revision).toBe("7");
    expect(createOperationBatch("batch_1", "7", draft.operations).operations).toHaveLength(1);
    draft.undo();
    expect(draft.document.layout.instance_geometry.producer_0?.x).toBe(20);
    draft.cancel();
    expect(draft.dirty).toBe(false);
  });

  it("applies compound draft commands atomically as one undo step", () => {
    const document = simpleDocumentFixture();
    const draft = new CircuitDraft(document, "7");
    const diagnostics = draft.applyBatch([
      { operation_id: "delete_net", type: "delete_net", net_id: "data" },
      { operation_id: "remove_producer", type: "remove_instance", instance_id: "producer_0", cascade: true },
    ]);
    expect(diagnostics.some((item) => item.severity === "error")).toBe(false);
    expect(draft.document.design.nets).toHaveLength(0);
    expect(draft.document.design.instances.map((item) => item.id)).not.toContain("producer_0");
    draft.undo();
    expect(draft.document).toEqual(document);

    const beforeRejected = draft.document;
    expect(draft.applyBatch([
      { operation_id: "move", type: "set_instance_geometry", instance_id: "producer_0", geometry: { x: 20, y: 20, width: 180, height: 100 } },
      { operation_id: "missing", type: "delete_net", net_id: "missing" },
    ]).some((item) => item.severity === "error")).toBe(true);
    expect(draft.document).toEqual(beforeRejected);
  });

  it("uses an implicit default clock and counts every crossed marker as one cycle", () => {
    const document = simpleDocumentFixture();
    document.layout.instance_geometry.producer_0 = { x: 80, y: 80, width: 180, height: 100 };
    document.layout.instance_geometry.consumer_0 = { x: 420, y: 80, width: 180, height: 100 };
    expect(effectiveCircuitTiming(document).clock_domains[0]).toEqual({ id: "default", label: "clk" });
    document.timing = {
      schema_version: 1,
      clock_domains: [{ id: "default", label: "clk" }],
      cycle_edges: [{ id: "cycle_edge_1", x: 320, locked: false }],
      subject_domain_overrides: {},
    };
    const analysis = analyzeCircuitTiming(document);
    expect(analysis.paths).toEqual([expect.objectContaining({ status: "ready", cycles: 1, source_stage: 0, target_stage: 1 })]);
    expect(validateCircuitDocument(document).valid).toBe(true);
    expect(renderCircuitSvg(document)).toContain("CYCLE EDGE 1");
    expect(renderCircuitSvg(document)).toContain("+1 cycle");
  });

  it("rejects markers that bisect an instance and reports advanced-domain CDCs", () => {
    const document = simpleDocumentFixture();
    document.layout.instance_geometry.producer_0 = { x: 80, y: 80, width: 180, height: 100 };
    document.layout.instance_geometry.consumer_0 = { x: 420, y: 80, width: 180, height: 100 };
    document.timing = {
      schema_version: 1,
      clock_domains: [{ id: "default", label: "clk" }, { id: "io", label: "io_clk" }],
      cycle_edges: [{ id: "cycle_edge_1", x: 320, locked: false }],
      subject_domain_overrides: { "instance:consumer_0": "io" },
    };
    const cdc = analyzeCircuitTiming(document).paths[0];
    expect(cdc).toEqual(expect.objectContaining({ status: "cdc", source_domain_id: "default", target_domain_id: "io" }));
    expect(cdc).not.toHaveProperty("cycles");
    expect(renderCircuitSvg(document)).toContain(">CDC<");
    document.timing.cycle_edges[0].x = 100;
    expect(validateCircuitDocument(document).diagnostics.map((item) => item.code)).toContain("cycle_edge_intersects_instance");
  });

  it("applies cycle-edge edits through one undoable draft operation", () => {
    const document = simpleDocumentFixture();
    const draft = new CircuitDraft(document, "1");
    expect(draft.apply({ operation_id: "edge", type: "add_cycle_edge", edge: { id: "cycle_edge_1", x: 360, locked: false } }).some((item) => item.severity === "error")).toBe(false);
    expect(draft.document.timing?.cycle_edges).toHaveLength(1);
    draft.undo();
    expect(draft.document.timing).toBeUndefined();
  });

  it("compiles aliases and primitive templates into a normalized document", () => {
    const construction: CircuitConstruction = {
      mode: "create",
      document_id: "demo",
      label: "Demo",
      design_id: "top",
      design_label: "Top",
      components: [
        { alias: "inv", name: "Inverter", template: "not", template_parameters: { width: 8 } },
      ],
      instances: [
        { alias: "u0", name: "First Inverter", component: "inv", parameter_values: {} },
      ],
      boundary_terminals: [
        { alias: "input", name: "Input", direction: "input", width: 8 },
      ],
      nets: [
        { name: "input net", endpoints: ["boundary.input", "u0.in"] },
      ],
    };
    expect(validateContractDefinition("CircuitConstruction", construction).valid).toBe(true);
    const result = compileConstruction(construction);
    expect(result.document?.components[0].terminals.map((item) => item.width)).toEqual([8, 8]);
    expect(result.alias_map.u0).toBe("u0");
    expect(result.diagnostics.filter((item) => item.severity === "error")).toEqual([]);
  });

  it("validates the client-authored portion of an external proposal", () => {
    const request = {
      proposal_id: "assistant_proposal",
      document_id: "fixture_simple",
      base_revision: "1",
      title: "Add a consumer",
      summary: "Add and connect one consumer instance.",
      assumptions: ["The producer output can fan out."],
      batch: {
        request_id: "assistant_batch",
        expected_revision: "1",
        operations: [{
          operation_id: "add_consumer",
          type: "add_instance",
          instance: {
            id: "consumer_1",
            label: "Consumer 1",
            component_id: "consumer",
            parameter_values: {},
          },
        }],
      },
    };
    expect(validateContractDefinition("CircuitProposalCreateRequest", request).valid)
      .toBe(true);
    expect(validateContractDefinition("CircuitProposalCreateRequest", {
      ...request,
      status: "pending",
    }).valid).toBe(false);
  });

  it("enforces provider child boundaries and rejects hierarchy cycles", async () => {
    const parent = simpleDocumentFixture();
    const component = parent.components[0];
    const incompatible = simpleDocumentFixture();
    incompatible.design.boundary_terminals = [];
    expect(validateComponentDesignBoundary(component, incompatible).map((item) => item.code))
      .toContain("missing_child_boundary");

    const child = simpleDocumentFixture();
    child.design.boundary_terminals = component.terminals.map((terminal) => ({
      id: terminal.id,
      label: terminal.label,
      direction: terminal.direction,
      width: terminal.width,
      category: terminal.category,
    }));
    child.design.instances[0].component_id = component.id;
    const resolved = await resolveHierarchy({
      resolveComponentDesign: async () => ({
        status: "available",
        document: child,
        provider_revision: "provider-1",
        writable: false,
      }),
    }, parent, component);
    expect(resolved.diagnostics.map((item) => item.code)).toContain("hierarchy_cycle");
    expect(resolved.result.status).toBe("unavailable");
  });

  it("rejects overlapping bus slices and treats width compatibility as a warning", () => {
    const document = simpleDocumentFixture();
    document.components[0].terminals[0].width = 8;
    document.components[1].terminals[0].width = 4;
    document.design.nets[0].endpoints = [
      { kind: "instance", instance_id: "producer_0", terminal_id: "data", slice: { lsb: 0, width: 4 } },
      { kind: "instance", instance_id: "consumer_0", terminal_id: "data" },
    ];
    document.design.nets.push({
      id: "overlap",
      label: "overlap",
      endpoints: [
        { kind: "instance", instance_id: "producer_0", terminal_id: "data", slice: { lsb: 2, width: 4 } },
      ],
    });
    const checked = validateCircuitDocument(document);
    expect(checked.diagnostics.map((item) => item.code)).toContain("terminal_slice_in_multiple_nets");
    expect(checked.valid).toBe(false);

    document.design.nets.pop();
    document.design.nets[0].endpoints[0] = {
      kind: "instance",
      instance_id: "producer_0",
      terminal_id: "data",
      slice: { lsb: 0, width: 8 },
    };
    const warning = validateCircuitDocument(document);
    expect(warning.diagnostics.map((item) => item.code)).toContain("width_mismatch");
    expect(warning.valid).toBe(true);
  });

  it("keeps built-in definitions read-only and rejects an atomic batch as a whole", () => {
    const document = simpleDocumentFixture();
    document.components[0].origin = "builtin";
    document.components[0].editable = false;
    const result = applyOperations(document, [
      {
        operation_id: "move_first",
        type: "set_instance_geometry",
        instance_id: "producer_0",
        geometry: { x: 20, y: 20, width: 180, height: 100 },
      },
      {
        operation_id: "remove_builtin",
        type: "remove_component",
        component_id: "producer",
        cascade: true,
      },
    ]);
    expect(result.status).toBe("rejected");
    expect(result.candidate).toBeUndefined();
    expect(result.diagnostics.map((item) => item.code)).toContain("component_read_only");
    expect(document.layout.instance_geometry.producer_0).toBeUndefined();
  });
});

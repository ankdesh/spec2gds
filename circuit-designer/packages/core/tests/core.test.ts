import { describe, expect, it } from "vitest";
import {
  applyOperations,
  CircuitDraft,
  compileConstruction,
  connectedInstanceIds,
  createOperationBatch,
  documentFixtures,
  simpleDocumentFixture,
  uniqueSlug,
  validateCircuitDocument,
  validateComponentDesignBoundary,
  validateContractDefinition,
  resolveHierarchy,
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

import { resolveConfig, endpointUrl } from "../../../../runtime/service-config.mjs";
import { expect, test, type Locator, type Page, type Route } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const documentId = "editor_test";
const revision = "sha256:editor-test";

const designRef = { document_id: documentId, entity_id: "design_top", entity_kind: "design" };
const internalDesignRef = { document_id: documentId, entity_id: "design_internal", entity_kind: "design" };
const componentRef = { document_id: documentId, entity_id: "component_timer", entity_kind: "component" };
const compositeRef = { document_id: documentId, entity_id: "component_subsystem", entity_kind: "component" };
const busRef = { document_id: documentId, entity_id: "bus_control", entity_kind: "bus_definition" };

const snapshot = {
  owner_document_key: "package-editor-test",
  edit_access: { mode: "edit", context_id: "fixture-context", participant_id: "fixture-tab", expires_at: 4102444800 },
  schema_version: "spec2gds.snapshot.v2",
  document_id: documentId,
  source_revision_hash: revision,
  components: [
    { ref: componentRef, vlnv: "acme:blocks:Timer:1.0" },
    { ref: compositeRef, vlnv: "acme:blocks:Subsystem:1.0" },
  ],
  designs: [{ ref: designRef, vlnv: "acme:systems:Processor:1.0" }, { ref: internalDesignRef, vlnv: "acme:systems:SubsystemImplementation:1.0" }],
  entry_designs: [{ ref: designRef, vlnv: "acme:systems:Processor:1.0" }],
  bus_definitions: [],
  abstraction_definitions: [],
  component_compositions: [{ component: compositeRef, internal_design: internalDesignRef }],
  narrative: { title: "Editor Test", blocks: [] },
  diagnostics: { source: [], artifacts: [] },
  entity_sections: [],
  section_validation: [],
  // These tests exercise commands on a previously checked source fixture.
  verifications: [{ target: designRef, source_revision_hash: revision, status: "passed", tool_version: "fixture", diagnostics: [], functional_simulation: "unverified" }],
};

function section(
  id: string,
  title: string,
  level: number,
  entityRef: object | null,
  options: {
    eyebrow?: string;
    facts?: object[];
    tables?: object[];
    children?: string[];
    availableSectionTypes?: object[];
  } = {},
) {
  return {
    id: `section-${id}`,
    component: "SpecSection",
    section: {
      section_id: id,
      title,
      level,
      eyebrow: options.eyebrow ?? (level === 1 ? "Document section" : "Hardware entity"),
      entity_ref: entityRef,
      facts: options.facts ?? [],
      tables: options.tables ?? [],
      narrative: [],
      content_sections: [],
      available_section_types: options.availableSectionTypes ?? (
        entityRef && ["component", "design"].includes((entityRef as { entity_kind?: string }).entity_kind ?? "")
          ? [{ section_type: "sv", type_version: 1, title: "SystemVerilog" }]
          : []
      ),
    },
    children: options.children ?? [],
  };
}

function cell(value: string, schemaPath: string) {
  return { kind: "text", value, presence: value ? "explicit" : "absent", schema_path: schemaPath, reference_anchor: "" };
}

const portTable = {
  table_id: "component-component_timer-port-irq",
  kind: "component_port",
  title: "irq",
  columns: [
    { key: "family", label: "Family", schema_path: "/model/ports/port" },
    { key: "display_name", label: "Display name", schema_path: "/model/ports/port/displayName" },
    { key: "direction", label: "Direction", schema_path: "/model/ports/port/wire/direction" },
    { key: "range", label: "Range", schema_path: "/model/ports/port/wire/vectors/vector" },
    { key: "description", label: "Description", schema_path: "/model/ports/port/description" },
  ],
  rows: [{
    row_id: "port-irq",
    cells: {
      name: cell("irq", "/model/ports/port/name"),
      family: cell("wire", "/model/ports/port/wire"),
      display_name: cell("Interrupt request", "/model/ports/port/displayName"),
      direction: cell("out", "/model/ports/port/wire/direction"),
      range: cell("", "/model/ports/port/wire/vectors/vector"),
      left: cell("", "/model/ports/port/wire/vectors/vector/left"),
      right: cell("", "/model/ports/port/wire/vectors/vector/right"),
      initiative: cell("", "/model/ports/port/transactional/initiative"),
      transaction_kind: cell("", "/model/ports/port/transactional/kind"),
      custom_kind: cell("", "/model/ports/port/transactional/kind/@custom"),
      bus_width: cell("", "/model/ports/port/transactional/busWidth"),
      structure: cell("", "/model/ports/port/structured"),
      description: cell("Interrupt", "/model/ports/port/description"),
    },
  }],
};

const transactionalPortTable = {
  table_id: "component-component_timer-port-request_stream",
  kind: "component_port",
  title: "request_stream",
  columns: portTable.columns,
  rows: [{
    row_id: "port-request_stream",
    cells: {
      name: cell("request_stream", "/model/ports/port/name"),
      family: cell("transactional", "/model/ports/port/transactional"),
      display_name: cell("Request stream", "/model/ports/port/displayName"),
      direction: cell("", "/model/ports/port/wire/direction"),
      range: cell("", "/model/ports/port/wire/vectors/vector"),
      left: cell("", "/model/ports/port/wire/vectors/vector/left"),
      right: cell("", "/model/ports/port/wire/vectors/vector/right"),
      initiative: cell("provides", "/model/ports/port/transactional/initiative"),
      transaction_kind: cell("custom", "/model/ports/port/transactional/kind"),
      custom_kind: cell("timer_service", "/model/ports/port/transactional/kind/@custom"),
      bus_width: cell("DATA_WIDTH", "/model/ports/port/transactional/busWidth"),
      structure: cell("", "/model/ports/port/structured"),
      description: cell("Streams timer requests", "/model/ports/port/description"),
    },
  }],
};

const structuredPortTable = {
  table_id: "component-component_timer-port-status_bundle",
  kind: "component_port",
  title: "status_bundle",
  columns: portTable.columns,
  rows: [{
    row_id: "port-status_bundle",
    cells: {
      name: cell("status_bundle", "/model/ports/port/name"),
      family: cell("structured", "/model/ports/port/structured"),
      display_name: cell("Status bundle", "/model/ports/port/displayName"),
      direction: cell("out", "/model/ports/port/structured/struct/@direction"),
      range: cell("", "/model/ports/port/wire/vectors/vector"),
      left: cell("", "/model/ports/port/wire/vectors/vector/left"),
      right: cell("", "/model/ports/port/wire/vectors/vector/right"),
      initiative: cell("", "/model/ports/port/transactional/initiative"),
      transaction_kind: cell("", "/model/ports/port/transactional/kind"),
      custom_kind: cell("", "/model/ports/port/transactional/kind/@custom"),
      bus_width: cell("", "/model/ports/port/transactional/busWidth"),
      structure: cell("Packed struct", "/model/ports/port/structured"),
      description: cell("Packed status fields", "/model/ports/port/description"),
    },
  }],
};

const allPortsTable = {
  ...portTable,
  table_id: "component-component_timer-ports",
  kind: "component_ports",
  title: "Ports",
  rows: [portTable.rows[0], transactionalPortTable.rows[0], structuredPortTable.rows[0]],
};

const componentFacts = [
  { label: "VLNV", value: "acme:blocks:Timer:1.0", schema_path: "/vendor | /library | /name | /version", reference_anchor: "" },
  { label: "Name", value: "Timer", schema_path: "/name", reference_anchor: "" },
  { label: "Display name", value: "", schema_path: "/displayName", reference_anchor: "" },
  { label: "Short description", value: "", schema_path: "/shortDescription", reference_anchor: "" },
  { label: "Description", value: "Counts time", schema_path: "/description", reference_anchor: "" },
];

const compositePortTable = {
  table_id: "component-component_subsystem-ports",
  kind: "component_ports",
  title: "Ports",
  columns: [],
  rows: [],
};

const designInstancesTable = {
  table_id: "design-design_top-instances",
  kind: "design_instances",
  title: "Component instances",
  columns: [
    { key: "name", label: "Instance", schema_path: "/componentInstances/componentInstance/instanceName" },
    { key: "component", label: "Component VLNV", schema_path: "/componentInstances/componentInstance/componentRef" },
  ],
  rows: [
    { row_id: "producer_0", cells: { name: cell("producer_0", "/componentInstances/componentInstance/instanceName"), component: cell("acme:blocks:Producer:1.0", "/componentInstances/componentInstance/componentRef") } },
    { row_id: "consumer_0", cells: { name: cell("consumer_0", "/componentInstances/componentInstance/instanceName"), component: cell("acme:blocks:Consumer:1.0", "/componentInstances/componentInstance/componentRef") } },
  ],
};

const topologyCircuitDocument = {
  protocol_version: "circuit-designer.v1",
  document_id: "editor_test_design_top_editor_test_v2",
  label: "Processor",
  components: [
    {
      id: "producer",
      label: "Producer",
      origin: "provider",
      editable: false,
      terminals: [{ id: "data", label: "data", direction: "output", width: 1, category: "port" }],
      parameters: [],
      appearance: { renderer_key: "generic", properties: {} },
    },
    {
      id: "consumer",
      label: "Consumer",
      origin: "provider",
      editable: false,
      terminals: [{ id: "data", label: "data", direction: "input", width: 1, category: "port" }],
      parameters: [],
      appearance: { renderer_key: "generic", properties: {} },
    },
  ],
  design: {
    id: "design_top",
    label: "Processor",
    boundary_terminals: [],
    instances: [
      { id: "producer_0", label: "producer_0", component_id: "producer", parameter_values: {} },
      { id: "consumer_0", label: "consumer_0", component_id: "consumer", parameter_values: {} },
    ],
    nets: [{
      id: "data_link",
      label: "data_link",
      endpoints: [
        { kind: "instance", instance_id: "producer_0", terminal_id: "data" },
        { kind: "instance", instance_id: "consumer_0", terminal_id: "data" },
      ],
    }],
  },
  layout: {
    grid_size: 20,
    direction: "RIGHT",
    instance_geometry: {},
    terminal_placements: {},
    net_routes: {},
    label_geometry: {},
  },
  timing: {
    schema_version: 1,
    clock_domains: [{ id: "default", label: "clk" }],
    cycle_edges: [{ id: "edge_1", x: 320, label: "Execute edge", next_stage_label: "Writeback", locked: false }],
    subject_domain_overrides: {},
    leading_stage_label: "Decode",
  },
};

const topologyBlock = {
  block_id: "derived_topology_design_top",
  type: "live_view",
  text: "Circuit topology",
  inlines: [],
  children: [],
  ordered: false,
  rows: [],
  asset_id: "",
  alt_text: "",
  caption: "",
  entity_refs: [designRef],
  renderer_id: "design.topology",
  options: {
    schema_version: 1,
    status: "ready",
    circuit_document: topologyCircuitDocument,
    omitted_bus_items: ["control_bus"],
    omitted_ports: [],
  },
};

const batch = {
  protocol_version: "v0.9",
  catalog_id: "urn:spec2gds:a2ui:document:v2",
  surface_id: "spec-document-editor-test",
  source_revision_hash: revision,
  messages: [
    {
      version: "v0.9",
      createSurface: {
        surfaceId: "spec-document-editor-test",
        catalogId: "urn:spec2gds:a2ui:document:v2",
      },
    },
    {
      version: "v0.9",
      updateComponents: {
        surfaceId: "spec-document-editor-test",
        components: [
          section("overview", "Overview", 1, null),
          section("designs", "Top-level Designs", 1, null),
          section("design-design_top", "Processor", 2, designRef, {
            eyebrow: "Entry design",
            tables: [designInstancesTable],
            children: ["narrative-design-design-top-0", "table-design-design-top-instances", "entity-section-design-top-sv"],
            availableSectionTypes: [],
          }),
          {
            id: "narrative-design-design-top-0",
            component: "LiveView",
            block: topologyBlock,
            documentId,
          },
          {
            id: "table-design-design-top-instances",
            component: "SpecTable",
            table: designInstancesTable,
          },
          {
            id: "entity-section-design-top-sv",
            component: "SpecEntitySection",
            section: {
              section_id: "section_sv_design_top",
              section_type: "sv",
              type_version: 1,
              title: "SystemVerilog",
              parent: designRef,
              payload: { content: "logic saved_marker;\n", media_type: "text/x-systemverilog" },
              editable: true,
              deletable: true,
              validation_status: "verified",
              diagnostics: [],
            },
          },
          section("components", "Components", 1, null),
          section("component-component_timer", "Timer", 2, componentRef, {
            facts: componentFacts,
            tables: [allPortsTable],
            children: ["narrative-component-timer-desc", "preview-component-timer", "table-component-component_timer-ports"],
          }),
          {
            id: "preview-component-timer",
            component: "LiveView",
            block: { ...topologyBlock, block_id: "derived_topology_component_timer", entity_refs: [componentRef],
              options: { ...topologyBlock.options, read_only: true } },
            documentId,
          },
          {
            id: "narrative-component-timer-desc",
            component: "NarrativeBlock",
            block: {
              block_id: "block_timer_desc",
              type: "paragraph",
              text: "The timer module generates periodic interrupts and tracks real-time intervals using a configurable 32-bit prescaler.",
              inlines: [],
              children: [],
              ordered: false,
              rows: [],
              asset_id: "",
              alt_text: "",
              caption: "",
              entity_refs: [],
              renderer_id: "",
              options: {},
            },
            documentId,
          },
          {
            id: "table-component-component_timer-ports",
            component: "SpecTable",
            table: allPortsTable,
          },
          section("component-component_subsystem", "Subsystem", 2, compositeRef, {
            facts: componentFacts.map((fact) => fact.label === "Name"
              ? { ...fact, value: "Subsystem" }
              : fact.label === "VLNV"
                ? { ...fact, value: "acme:blocks:Subsystem:1.0" }
                : { ...fact, value: "" }),
            tables: [compositePortTable],
            children: ["table-component-component_subsystem-ports"],
          }),
          section("design-design_internal", "Subsystem implementation", 3, internalDesignRef, { eyebrow: "Internal Design" }),
          {
            id: "table-component-component_subsystem-ports",
            component: "SpecTable",
            table: compositePortTable,
          },
          section("bus-definition-bus_control", "Control Bus", 2, busRef),
          {
            id: "root",
            component: "SpecDocument",
            title: "Editor Test",
            summary: "One design · one component · one protocol",
            documentId,
            sourceRevisionHash: revision,
            toc: [
              { section_id: "overview", title: "Overview", level: 1 },
              { section_id: "designs", title: "Top-level Designs", level: 1 },
              { section_id: "design-design_top", title: "Processor", level: 2 },
              { section_id: "components", title: "Components", level: 1 },
              { section_id: "component-component_timer", title: "Timer", level: 2 },
              { section_id: "component-component_subsystem", title: "Subsystem", level: 2 },
              { section_id: "design-design_internal", title: "Subsystem implementation", level: 3 },
              { section_id: "bus-definition-bus_control", title: "Control Bus", level: 2 },
            ],
            children: [
              "section-overview",
              "section-designs",
              "section-design-design_top",
              "section-components",
              "section-component-component_timer",
              "section-component-component_subsystem",
              "section-design-design_internal",
              "section-bus-definition-bus_control",
            ],
          },
        ],
      },
    },
    {
      version: "v0.9",
      updateDataModel: {
        surfaceId: "spec-document-editor-test",
        path: "/",
        value: { documentId, sourceRevisionHash: revision, schemaVersion: "1.0" },
      },
    },
  ],
};

type ApiState = {
  activityExecutions: Array<Record<string, unknown>>;
  circuits: Array<{ entity_kind: string; entity_id: string }>;
  createdPaths: string[];
  createdTitles: string[];
  copiedPaths: string[];
  openedPaths: string[];
  generatedTargets: Array<{ entity_kind: string; entity_id: string }>;
  transactions: Array<{ expected_source_revision_hash: string; operations: object[] }>;
  currentRevision: string;
  currentTitle: string;
  currentSummary?: string;
  staleNextTransaction: boolean;
};

async function mockEditorApi(page: Page, options: { topologyUnavailable?: boolean; topologyState?: "empty" | "render-error" | "unsupported" } = {}): Promise<ApiState> {
  const state: ApiState = {
    activityExecutions: [],
    generatedTargets: [],
    circuits: [],
    createdPaths: [],
    artifacts: [] as Array<Record<string, unknown>>,
    proposals: [] as Array<Record<string, unknown>>,
    createdTitles: [],
    copiedPaths: [],
    openedPaths: [],
    transactions: [],
    currentRevision: revision,
    currentTitle: snapshot.narrative.title,
    currentSummary: undefined,
    staleNextTransaction: false,
  };
  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const requestUrl = new URL(request.url());
    const path = requestUrl.pathname.replace(/^\/api/, "");
    const json = (value: unknown) => route.fulfill({ json: value, status: 200 });

    if (path.startsWith("/documents/edit-access/")) return json(snapshot.edit_access);

    if (path === "/services") {
      return json({
        schema_version: 2,
        services: {
          spec_editor: { service_url: "http://127.0.0.1:6010", ui_url: "http://127.0.0.1:6010/editor" },
          circuit_designer: { service_url: "http://127.0.0.1:6011/api/circuit-designer/v1", ui_url: "http://127.0.0.1:6012" },
          ai_assistant: { service_url: "http://127.0.0.1:6013", ui_url: "http://127.0.0.1:6013" },
        },
        logging: { enabled: false, level: "info" },
      });
    }

    if (path === "/filesystem/directories") {
      const body = request.method() === "POST"
        ? request.postDataJSON() as { parent: string; name: string }
        : null;
      const requestedPath = body
        ? `${body.parent}/${body.name}`
        : requestUrl.searchParams.get("path") ?? "/home/designer";
      return json({
        path: requestedPath,
        parent: requestedPath === "/home/designer" ? null : requestedPath.split("/").slice(0, -1).join("/") || "/home/designer",
        home: "/home/designer",
        separator: "/",
        roots: ["/home/designer"],
        directories: requestedPath === "/home/designer"
          ? [{ name: "specifications", path: "/home/designer/specifications" }]
          : [],
        specifications: requestedPath === "/home/designer/specifications"
          ? [{ name: "existing.spec", path: "/home/designer/specifications/existing.spec" }]
          : [],
      });
    }

    if (path === "/documents/copy-suggestion") return json({ path: "/home/designer/specifications/existing-copy.spec", title: `${state.currentTitle} copy` });

    if (path === "/documents/create" || path === "/documents/open" || path === "/documents/copy") {
      const body = request.postDataJSON() as { path: string; title?: string };
      (path.endsWith("copy") ? state.copiedPaths : path.endsWith("create") ? state.createdPaths : state.openedPaths).push(body.path);
      if (path.endsWith("create")) state.createdTitles.push(body.title ?? "");
      if (body.path === "/tmp/missing.spec") {
        return route.fulfill({ json: { detail: "Specification package was not found." }, status: 422 });
      }
      state.currentRevision = revision;
      state.currentTitle = !path.endsWith("open") ? body.title ?? "" : snapshot.narrative.title;
      return json(!path.endsWith("open")
        ? { ...snapshot, narrative: { ...snapshot.narrative, title: body.title ?? "" } }
        : snapshot);
    }
    if (path === "/documents/snapshot") {
      return json({ ...snapshot, source_revision_hash: state.currentRevision });
    }
    if (path === "/assistant/history") return json({ items: [], next_cursor: null });
    if (path === "/documents/a2ui" || path === "/documents/view") {
      const currentBatch = structuredClone(batch);
      const components = currentBatch.messages[1].updateComponents.components as Array<Record<string, any>>;
      const doc = components.find(component => component.component === "SpecDocument");
      doc.title = state.currentTitle;
      if (state.currentSummary !== undefined) {
        doc.summary = state.currentSummary;
      }
      const liveView = components.find((component) => component.component === "LiveView");
      if (options.topologyUnavailable) {
        liveView.block.options = {
          schema_version: 1,
          status: "unavailable",
          omitted_bus_items: [],
          omitted_ports: [],
          message: "connected structured endpoint cannot be represented",
        };
      }
      if (options.topologyState === "empty") {
        liveView.block.options.status = "empty";
        delete liveView.block.options.circuit_document;
      } else if (options.topologyState === "render-error") {
        liveView.block.options.circuit_document.protocol_version = "invalid";
      } else if (options.topologyState === "unsupported") {
        liveView.block.options.schema_version = 99;
      }
      if (state.transactions.length) {
        if (liveView.block.options.circuit_document) {
          liveView.block.options.circuit_document.design.instances[0].label = "producer_updated";
        }
        currentBatch.source_revision_hash = state.currentRevision;
      }
      currentBatch.source_revision_hash = state.currentRevision;
      return json(path === "/documents/view" ? {
        snapshot: { ...snapshot, source_revision_hash: state.currentRevision, narrative: { ...snapshot.narrative, title: state.currentTitle } },
        a2ui: currentBatch, activity: { executions: state.activityExecutions, artifacts: state.artifacts, proposals: state.proposals, assistant_changes: [] },
        approval_policy: "automatic", event_cursor: state.transactions.length, source_revision_hash: state.currentRevision,
      } : currentBatch);
    }
    if (path === "/transactions") {
      const body = request.postDataJSON() as { expected_source_revision_hash: string; operations: object[] };
      state.transactions.push(body);
      if (state.staleNextTransaction) {
        state.staleNextTransaction = false;
        state.currentRevision = "sha256:external-change";
        return route.fulfill({
          json: { detail: { diagnostics: ["Stale base revision."] } },
          status: 409,
        });
      }
      state.currentRevision = `sha256:edited-${state.transactions.length}`;
      return json({ committed: true, snapshot: { ...snapshot, source_revision_hash: state.currentRevision } });
    }
    if (path === "/executions") return json({ executions: state.activityExecutions });
    if (path === "/artifacts") return json({ artifacts: state.artifacts });
    if (path === "/proposals") return json({ proposals: state.proposals });
    if (path === "/proposals/proposal_draft_review/accept") {
      state.currentRevision = "sha256:reviewed-source";
      state.proposals[0].review_status = "accepted";
      return json({ snapshot: { ...snapshot, source_revision_hash: state.currentRevision } });
    }
    if (path === "/assistant/changes") return json({ assistant_changes: [] });
    if (path === "/assistant/launch/document") {
      const body = request.postDataJSON() as { attach_active_document: boolean };
      if (!body.attach_active_document) {
        return json({
          assistant_url: "http://127.0.0.1:6013/launch",
          document_id: null,
          source_revision_hash: null,
          scope: "unbound",
        });
      }
      return json({
        assistant_url: "http://127.0.0.1:6013/launch/spec-document?document_id=editor_test",
        document_id: documentId,
        source_revision_hash: state.currentRevision,
        scope: "document",
      });
    }
    if (path === "/circuit-designer/launch") {
      const body = request.postDataJSON() as { entity_kind: string; entity_id: string };
      state.circuits.push(body);
      return json({
        document_id: "circuit-test",
        entity_id: body.entity_id,
        entity_kind: body.entity_kind,
        editor_url: "http://127.0.0.1:6012/?document_id=circuit-test",
        reused_session: false,
        omitted_bus_items: [],
        omitted_ports: [],
      });
    }
    if (/^\/entities\/[^/]+\/[^/]+\/activities$/.test(path)) {
      return json({ activities: [{
        definition: {
          activity_id: "rtl.generate",
          version: "1.1.0",
          title: "Generate RTL",
          description: "Generate deterministic structural SystemVerilog modules and direct wiring.",
          requires_workspace_output: true,
          artifact_roles: ["rtl.generation_report"],
        },
        availability: { available: true, diagnostics: ["Warning: dut.clk is unconnected."] },
      }] });
    }
    if (/^\/entities\/[^/]+\/[^/]+\/activities\/rtl.generate\/executions$/.test(path)) {
      const [, , entityKind, entityId] = path.split("/");
      state.generatedTargets.push({ entity_kind: entityKind, entity_id: entityId });
      const execution = {
        execution_type: "activity",
        title: "Generate RTL",
        target_name: "Processor",
        execution_id: "activity_execution_test",
        activity_id: "rtl.generate",
        activity_version: "1.1.0",
        status: "queued",
        cancel_requested: false,
        report: {},
        diagnostics: [],
      };
      state.activityExecutions.push(execution);
      return json(execution);
    }
    if (/^\/executions\/[^/]+\/cancel$/.test(path)) {
      state.activityExecutions = state.activityExecutions.map((item) => ({
        ...item,
        cancel_requested: true,
      }));
      return json(state.activityExecutions[0]);
    }
    if (/^\/entities\/[^/]+\/[^/]+\/actions$/.test(path)) {
      return json({ actions: [] });
    }
    if (path === "/events" || path === "/activity-events") {
      return route.fulfill({
        body: "",
        contentType: "text/event-stream",
        headers: { "cache-control": "no-cache" },
        status: 200,
      });
    }
    return route.fulfill({ json: { detail: `Unexpected test route: ${path}` }, status: 404 });
  });
  await page.addInitScript(() => {
    Object.defineProperty(window, "open", {
      configurable: true,
      value: () => ({
        close() {},
        document: { body: { textContent: "" }, title: "" },
        location: { replace() {} },
        opener: null,
      }),
    });
  });
  return state;
}

async function openCircuitPreview(card: Locator): Promise<void> {
  await card.getByRole("button", { name: "Options for circuit preview", exact: true }).click();
  await card.getByRole("menuitem", { name: "Open in Circuit Designer", exact: true }).click();
}

async function openSample(page: Page): Promise<void> {
  await page.goto("/");
  const menu = page.getByRole("button", { name: "Menu", exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /Open Spec/ }).click();
  await page.getByText("More options", { exact: true }).click();
  await page.getByLabel("File path", { exact: true }).fill("/home/designer/specifications/existing.spec");
  await page.getByRole("button", { name: "Open Spec", exact: true }).click();
  await expect(page.locator(".spec-paper")).toBeVisible();
}

test("creates a Spec from its name in Spec root and refreshes the saved file", async ({ page }) => {
  const state = await mockEditorApi(page);
  await page.goto("/");
  await expect(page).toHaveTitle("spec2hw · Spec Editor");
  await expect(page.locator(".app-header")).toBeVisible();
  await page.keyboard.press("Control+n");
  const dialog = page.getByRole("dialog", { name: "New Spec", exact: true });
  await expect(dialog.getByLabel("Spec name")).toBeFocused();
  await expect(dialog.getByLabel("File path", { exact: true })).toBeHidden();
  await expect(dialog.getByRole("button", { name: "Create Spec", exact: true })).toBeDisabled();
  await dialog.getByLabel("Spec name").fill("Single cycle.spec");
  await expect(dialog.locator(".spec-filename")).toHaveText("File: single-cycle.spec");
  await dialog.getByLabel("Spec name").fill("Single cycle");
  await expect(dialog.locator(".spec-filename")).toHaveText("File: single-cycle.spec");
  await expect(dialog.locator(".spec-location strong")).toHaveText("Spec root");
  await dialog.getByLabel("Spec name").press("Enter");
  await expect(page.getByRole("heading", { name: "Single cycle", exact: true })).toBeVisible();
  expect(state.createdPaths).toEqual(["/home/designer/single-cycle.spec"]);
  expect(state.createdTitles).toEqual(["Single cycle"]);
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: /Save Automatic/ })).toHaveCount(0);
  await page.getByRole("menuitem", { name: "Refresh From Disk" }).click();
  await expect.poll(() => state.openedPaths).toEqual(["/home/designer/single-cycle.spec"]);
});

test("chooses a folder with one click, cancels location changes, and adds a folder", async ({ page }) => {
  const state = await mockEditorApi(page);
  await page.goto("/");
  await expect(page.locator(".app-header")).toBeVisible();
  await page.keyboard.press("Control+n");
  await page.getByLabel("Spec name").fill("New editor specification");
  await page.getByRole("button", { name: "Change location" }).click();
  await expect(page.getByLabel("Spec name")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Spec root", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: /^specifications$/ }).click();
  await page.getByRole("button", { name: "Back", exact: true }).click();
  await expect(page.locator(".spec-location strong")).toHaveText("Spec root");
  await expect(page.getByLabel("Spec name")).toHaveValue("New editor specification");
  await expect(page.getByLabel("Spec name")).toBeFocused();
  await page.getByRole("button", { name: "Change location" }).click();
  await page.getByRole("button", { name: /^specifications$/ }).click();
  await page.getByRole("button", { name: /New folder/ }).click();
  await page.getByLabel("New folder name").fill("Project Alpha");
  await page.getByLabel("New folder name").press("Enter");
  await expect(page.getByRole("button", { name: "Project Alpha", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Use this folder" }).click();
  await expect(page.locator(".spec-location strong")).toHaveText("Spec root / specifications / Project Alpha");
  await page.getByRole("button", { name: "Create Spec", exact: true }).click();
  await expect(page.getByRole("heading", { name: "New editor specification", exact: true })).toBeVisible();
  expect(state.createdPaths).toEqual(["/home/designer/specifications/Project Alpha/new-editor-specification.spec"]);
});

test("Open Spec starts at Spec root, filters names, and opens a file by double-click", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  await page.keyboard.press("Control+o");
  const dialog = page.getByRole("dialog", { name: "Open Spec", exact: true });
  await expect(dialog.getByRole("button", { name: "Spec root", exact: true })).toBeDisabled();
  await expect(dialog.getByLabel("File path", { exact: true })).toBeHidden();
  await dialog.getByLabel("Filter folders and Specs").fill("does-not-exist");
  await expect(dialog.getByText("No matching names")).toBeVisible();
  await dialog.getByLabel("Filter folders and Specs").fill("SPECIF");
  await dialog.getByRole("button", { name: /^specifications$/ }).click();
  await expect(dialog.getByLabel("Filter folders and Specs")).toHaveValue("");
  await dialog.getByRole("button", { name: /^existing\.spec$/ }).click();
  await expect(dialog.getByRole("button", { name: "Open Spec", exact: true })).toBeEnabled();
  await dialog.getByLabel("Filter folders and Specs").fill("missing");
  await expect(dialog.getByRole("button", { name: "Open Spec", exact: true })).toBeDisabled();
  await dialog.getByLabel("Filter folders and Specs").fill("");
  await dialog.getByRole("button", { name: /^existing\.spec$/ }).dblclick();
  await expect(dialog).toHaveCount(0);
  expect(state.openedPaths.at(-1)).toBe("/home/designer/specifications/existing.spec");
  await page.keyboard.press("Control+o");
  await page.getByText("More options", { exact: true }).click();
  await page.getByLabel("File path", { exact: true }).fill("/tmp/missing.spec");
  await page.getByRole("button", { name: "Open Spec", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Specification package was not found");
  await expect(dialog).toBeVisible();
  await expect(page.getByLabel("File path", { exact: true })).toHaveValue("/tmp/missing.spec");
});

test("manual paths survive name and folder changes until reset to automatic", async ({ page }) => {
  const state = await mockEditorApi(page);
  await page.goto("/");
  await expect(page.locator(".app-header")).toBeVisible();
  await page.keyboard.press("Control+n");
  await page.getByLabel("Spec name").fill("First name");
  await page.getByText("More options", { exact: true }).click();
  const path = page.getByLabel("File path", { exact: true });
  await path.fill("/home/designer/exact.spec");
  await page.getByLabel("Spec name").fill("Renamed Spec");
  await expect(path).toHaveValue("/home/designer/exact.spec");
  await page.getByRole("button", { name: "Change location" }).click();
  await page.getByRole("button", { name: /^specifications$/ }).click();
  await page.getByRole("button", { name: "Use this folder" }).click();
  await expect(page.locator(".spec-filename")).toHaveText("File: exact.spec");
  await page.getByText("More options", { exact: true }).click();
  await expect(path).toHaveValue("/home/designer/specifications/exact.spec");
  await page.getByRole("button", { name: "Reset to automatic" }).click();
  await expect(path).toHaveValue("/home/designer/specifications/renamed-spec.spec");
  await page.getByRole("button", { name: "Create Spec", exact: true }).click();
  await expect.poll(() => state.createdPaths).toEqual(["/home/designer/specifications/renamed-spec.spec"]);
});

test("retries a failed location load without losing the entered name", async ({ page }) => {
  await mockEditorApi(page);
  let failListing = true;
  await page.route("**/api/filesystem/directories*", async route => {
    if (failListing) return route.fulfill({ status: 503, json: { detail: "Folders are unavailable. Try again." } });
    return route.fallback();
  });
  await page.goto("/");
  await expect(page.locator(".app-header")).toBeVisible();
  await page.keyboard.press("Control+n");
  await page.getByLabel("Spec name").fill("Keep this name");
  await expect(page.getByRole("alert")).toHaveText("Folders are unavailable. Try again.");
  await expect(page.getByRole("button", { name: "Create Spec", exact: true })).toBeDisabled();
  failListing = false;
  await page.getByRole("button", { name: "Retry loading folders" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByLabel("Spec name")).toHaveValue("Keep this name");
  await expect(page.getByRole("button", { name: "Create Spec", exact: true })).toBeEnabled();
});

test("opens the configured AI Assistant from the top bar", async ({ page }) => {
  await mockEditorApi(page);
  await openSample(page);
  await page.evaluate(() => {
    (window as Window & { openedAssistantUrl?: string }).open = ((url?: string | URL) => {
      (window as Window & { openedAssistantUrl?: string }).openedAssistantUrl = String(url);
      return null;
    }) as typeof window.open;
  });

  await page.getByRole("button", { name: "AI Assistant", exact: true }).click();
  await expect.poll(() => page.evaluate(
    () => (window as Window & { openedAssistantUrl?: string }).openedAssistantUrl,
  )).toBe("http://127.0.0.1:6013/launch/spec-document?document_id=editor_test");
});

test("opens an unbound AI Assistant when no specification is open", async ({ page }) => {
  await mockEditorApi(page);
  await page.goto("/");
  await page.evaluate(() => {
    (window as Window & { openedAssistantUrl?: string }).open = ((url?: string | URL) => {
      (window as Window & { openedAssistantUrl?: string }).openedAssistantUrl = String(url);
      return null;
    }) as typeof window.open;
  });

  const assistant = page.getByRole("button", { name: /AI Assistant/ });
  await expect(assistant).toBeEnabled();
  await assistant.click();
  await expect.poll(() => page.evaluate(
    () => (window as Window & { openedAssistantUrl?: string }).openedAssistantUrl,
  )).toBe("http://127.0.0.1:6013/launch");
});

test("supports keyboard menu navigation and restores trigger focus", async ({ page }) => {
  await mockEditorApi(page);
  await page.goto("/");
  const file = page.getByRole("menuitem", { name: "File", exact: true });
  await file.focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("menu", { name: "File" })).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("menu", { name: "Edit" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu", { name: "Edit" })).toBeHidden();
  await expect(page.getByRole("menuitem", { name: "Edit", exact: true })).toBeFocused();
});

test("adds, edits, and deletes SystemVerilog sections with preserved typed operations", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);

  const timer = page.locator("#component-component_timer");
  await timer.getByRole("button", { name: "Options", exact: true }).click();
  await page.getByRole("menuitem", { name: "Add SystemVerilog section…" }).click();
  const newEditor = timer.locator(".cm-content");
  await expect(newEditor).toBeVisible();
  await newEditor.fill("assign irq = 1'b0;\n");
  await timer.getByRole("button", { name: "Add section", exact: true }).click();
  await expect.poll(() => state.transactions.length).toBe(1);
  expect(state.transactions[0]?.operations).toEqual([{
    type: "upsert_entity_section",
    parent: componentRef,
    section_type: "sv",
    type_version: 1,
    payload: { content: "assign irq = 1'b0;\n" },
  }]);

  const design = page.locator("#design-design_top");
  await design.getByRole("button", { name: "Options for SystemVerilog", exact: true }).click();
  await design.getByRole("menuitem", { name: "Edit", exact: true }).click();
  const savedEditor = design.locator(".cm-content");
  await savedEditor.fill("logic edited_marker;\n");
  await design.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect.poll(() => state.transactions.length).toBe(2);
  expect(state.transactions[1]?.operations).toEqual([{
    type: "upsert_entity_section",
    parent: designRef,
    section_type: "sv",
    type_version: 1,
    section_id: "section_sv_design_top",
    payload: { content: "logic edited_marker;\n" },
  }]);

  page.once("dialog", (dialog) => dialog.accept());
  await design.getByRole("button", { name: "Options for SystemVerilog", exact: true }).click();
  await design.getByRole("menuitem", { name: "Delete", exact: true }).click();
  await expect.poll(() => state.transactions.length).toBe(3);
  expect(state.transactions[2]?.operations).toEqual([{
    type: "delete_entity_section",
    parent: designRef,
    section_type: "sv",
    section_id: "section_sv_design_top",
  }]);
});

test("edits the persisted specification name without changing the stable identity", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);

  await page.locator(".spec-cover").getByRole("button", { name: "Options", exact: true }).click();
  await page.locator(".spec-cover").getByRole("menuitem", { name: "Edit name", exact: true }).click();
  await page.getByLabel("Spec name").fill("Timer Platform Specification");
  await page.getByRole("button", { name: "Save to Spec" }).click();
  await expect.poll(() => state.transactions.length).toBe(1);
  expect(state.transactions[0]?.operations).toEqual([
    { type: "set_document_title", title: "Timer Platform Specification" },
  ]);

  const component = page.locator("#component-component_timer");
  const options = component.getByRole("button", { name: "Options", exact: true });
  await options.click();
  await expect(component.getByRole("menuitem", { name: "Edit text…" })).toBeVisible();
  await component.getByRole("menuitem", { name: "Rename", exact: true }).click();
  await expect(component.getByLabel("Name", { exact: true })).toBeFocused();
  await component.getByLabel("Name", { exact: true }).fill("Programmable Timer");
  await component.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect.poll(() => state.transactions.length).toBe(2);
  expect(state.transactions[1]?.operations).toEqual([{
    type: "set_entity_metadata", entity: componentRef,
    display_name: "Programmable Timer", short_description: "", description: "Counts time",
  }]);
  await expect(options).toBeFocused();

  const design = page.locator("#design-design_top");
  const designOptions = design.getByRole("button", { name: "Options", exact: true });
  await designOptions.click();
  await design.getByRole("menuitem", { name: "Rename", exact: true }).click();
  await design.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(designOptions).toBeFocused();
  expect(state.transactions.length).toBe(2);
});

test("renders, expands, downloads, and refreshes the derived circuit SVG", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  const design = page.locator("#design-design_top");
  const card = design.locator(".spec-topology-card");
  const table = design.getByRole("region", { name: "Component instances" });
  const image = card.getByRole("img", { name: "Circuit topology circuit diagram" });
  await expect(image).toBeVisible();
  const cardBox = await card.boundingBox();
  const tableBox = await table.boundingBox();
  expect(cardBox?.y).toBeLessThan(tableBox?.y ?? 0);
  await card.getByText("1 unsupported item omitted from this preview").click();
  await expect(card.getByText("Interface connection: control_bus")).toBeVisible();

  await expect(card.getByRole("button", { name: "Open in Circuit Designer", exact: true })).toHaveCount(0);
  await openCircuitPreview(card);
  await expect.poll(() => state.circuits).toEqual([{ entity_kind: "design", entity_id: "design_top" }]);

  const firstImageUrl = await image.getAttribute("src");
  await card.getByRole("button", { name: "Options for circuit preview", exact: true }).click();
  const expand = card.getByRole("menuitem", { name: "Expand", exact: true });
  await expand.click();
  const dialog = page.getByRole("dialog", { name: "Circuit topology" });
  await expect(dialog.getByRole("img", { name: "Circuit topology circuit diagram" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Close circuit preview" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(card.getByRole("button", { name: "Options for circuit preview", exact: true })).toBeFocused();

  const downloadPromise = page.waitForEvent("download");
  await card.getByRole("button", { name: "Options for circuit preview", exact: true }).click();
  await card.getByRole("menuitem", { name: "Download SVG" }).click();
  const downloadPath = await (await downloadPromise).path();
  expect(downloadPath).not.toBeNull();
  const svg = await readFile(downloadPath!, "utf8");
  expect(svg).toContain('data-instance-id="producer_0"');
  expect(svg).toContain('data-terminal-id="producer_0:data"');
  expect(svg).toContain('fill="url(#canvas-grid)"');
  expect(svg).toContain('class="net"');
  expect(svg).toContain('class="cycle-edge"');
  expect(svg).toContain("Execute edge");
  expect(svg).toContain("WRITEBACK");

  await page.locator(".spec-cover").getByRole("button", { name: "Options", exact: true }).click();
  await page.locator(".spec-cover").getByRole("menuitem", { name: "Edit name", exact: true }).click();
  await page.getByLabel("Spec name").fill("Updated topology source");
  await page.getByRole("button", { name: "Save to Spec" }).click();
  await expect.poll(async () => image.getAttribute("src")).not.toBe(firstImageUrl);
});

test("keeps design tables and launch access available when a circuit preview is unsafe", async ({ page }) => {
  const state = await mockEditorApi(page, { topologyUnavailable: true });
  await openSample(page);
  const design = page.locator("#design-design_top");

  await expect(design.getByText("Preview unavailable: connected structured endpoint cannot be represented")).toBeVisible();
  await expect(design.getByRole("region", { name: "Component instances" })).toBeVisible();
  await expect(design.getByRole("img", { name: "Circuit topology circuit diagram" })).toHaveCount(0);
  await openCircuitPreview(design.locator(".spec-topology-card"));
  await expect.poll(() => state.circuits).toEqual([{ entity_kind: "design", entity_id: "design_top" }]);
});

for (const topologyState of ["empty", "render-error", "unsupported"] as const) {
  test(`opens the same Design when its preview is ${topologyState}`, async ({ page }) => {
    const state = await mockEditorApi(page, { topologyState });
    await openSample(page);
    const card = page.locator("#design-design_top .spec-topology-card");
    await expect(card.getByRole("status")).toContainText(topologyState === "empty"
      ? "No instances" : topologyState === "render-error" ? "Preview unavailable" : "unsupported renderer options");
    await openCircuitPreview(card);
    await expect.poll(() => state.circuits).toEqual([{ entity_kind: "design", entity_id: "design_top" }]);
    expect(state.transactions).toHaveLength(0);
  });
}

test("opens leaf and composite Components from the menu and leaf previews with the keyboard", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  for (const [name, id] of [[/Timer.*Read-only preview/, "component_timer"], [/Subsystem.*Open assigned Design/, "component_subsystem"]] as const) {
    const trigger = page.getByRole("menuitem", { name: "Circuit Designer", exact: true });
    await trigger.focus();
    await page.keyboard.press("ArrowDown");
    const item = page.getByRole("menu", { name: "Circuit Designer", exact: true }).getByRole("menuitem", { name });
    await item.focus();
    await page.keyboard.press("Enter");
    await expect.poll(() => state.circuits.at(-1)).toEqual({ entity_kind: "component", entity_id: id });
  }
  const component = page.locator("#component-component_timer");
  await component.getByRole("button", { name: "Options", exact: true }).click();
  await component.getByRole("menuitem", { name: "Edit text…", exact: true }).click();
  const draft = component.getByLabel("Component explanation");
  await draft.fill("Private explanation, not saved to Spec.");
  const leaf = component.locator(".spec-topology-card");
  await expect(leaf).toContainText("Interface preview (read-only)");
  const button = leaf.getByRole("button", { name: "Options for circuit preview", exact: true });
  await button.focus();
  await page.keyboard.press("ArrowDown");
  await expect(leaf.getByRole("menuitem", { name: "Open in Circuit Designer", exact: true })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect.poll(() => state.circuits).toEqual([
    { entity_kind: "component", entity_id: "component_timer" },
    { entity_kind: "component", entity_id: "component_subsystem" },
    { entity_kind: "component", entity_id: "component_timer" },
  ]);
  await expect(draft).toHaveValue("Private explanation, not saved to Spec.");
  expect(state.transactions).toHaveLength(0);
});

test("reports launch errors, closes the pending tab, and permits retry", async ({ page, context }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  await page.route("**/circuit-designer/launch*", route => route.fulfill({ status: 503, json: { detail: "Circuit Designer is unavailable." } }), { times: 1 });
  const pagesBefore = context.pages().length;
  const card = page.locator("#design-design_top .spec-topology-card");
  await openCircuitPreview(card);
  await expect(page.getByRole("alert")).toContainText("Circuit Designer is unavailable.");
  await expect.poll(() => context.pages().length).toBe(pagesBefore);
  await openCircuitPreview(card);
  await expect.poll(() => state.circuits).toEqual([{ entity_kind: "design", entity_id: "design_top" }]);
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(state.transactions).toHaveLength(0);
});

test("keeps Circuit Designer visible with no circuit sources", async ({ page }) => {
  await mockEditorApi(page);
  await page.goto("/");
  await page.getByRole("menuitem", { name: "Circuit Designer", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: "No circuit sources", exact: true })).toBeDisabled();
});

test("adds an available top-level component instance to the entry design", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  const design = page.locator("#design-design_top");
  const options = design.getByRole("button", { name: "Options", exact: true });

  await options.click();
  await design.getByRole("menuitem", { name: "Add component instance…" }).click();
  await design.getByLabel("Instance ID").fill("timer0");
  await expect(design.getByLabel("Component", { exact: true })).toContainText("Timer");
  await design.getByLabel("Component", { exact: true }).selectOption("acme:blocks:Timer:1.0");
  await design.getByRole("button", { name: "Add instance" }).click();

  await expect.poll(() => state.transactions.length).toBe(1);
  expect(state.transactions[0]?.operations).toEqual([{
    type: "upsert_instance",
    design: designRef,
    instance: {
      name: "timer0",
      component_vlnv: "acme:blocks:Timer:1.0",
    },
  }]);
  await expect(options).toBeFocused();
});

test("keeps Edit state-aware and provides working Copy and Select All", async ({ context, page }) => {
  const editorOrigin = new URL(endpointUrl(resolveConfig(process.env.SPEC2GDS_TEST_SERVICE_CONFIG).spec_editor.dev_ui, "127.0.0.1", { local: true })).origin;
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: editorOrigin });
  await mockEditorApi(page);
  await openSample(page);

  await page.evaluate(() => {
    const textNode = document.querySelector(".spec-cover h1")?.firstChild;
    if (!textNode) throw new Error("Missing cover title");
    const range = document.createRange();
    range.selectNodeContents(textNode);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    document.dispatchEvent(new Event("selectionchange"));
  });
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: "Undo" })).toHaveCount(0);
  await expect(page.getByRole("menuitem", { name: "Cut", exact: true })).toBeDisabled();
  await expect(page.getByRole("menuitem", { name: "Find" })).toHaveCount(0);
  await page.getByRole("menuitem", { name: "Copy", exact: true }).click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe("Editor Test");

  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Select All" }).click();
  await expect.poll(() => page.evaluate(() => window.getSelection()?.toString() ?? "")).toContain("Processor");
});

test("launches circuits and queues a compatible design Activity", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);

  await page.getByRole("menuitem", { name: "Circuit Designer", exact: true }).click();
  const circuitMenu = page.getByRole("menu", { name: "Circuit Designer" });
  await expect(circuitMenu.getByText("Top-level Designs", { exact: true })).toBeVisible();
  await expect(circuitMenu.getByText("Components", { exact: true })).toBeVisible();
  await page.getByRole("menuitem", { name: /Processor Entry/ }).click();
  await expect.poll(() => state.circuits).toEqual([{ entity_kind: "design", entity_id: "design_top" }]);

  const overview = page.locator("#overview");
  await expect(overview.getByText("Document ID", { exact: true })).toHaveCount(0);
  await expect(overview.getByText("Source revision", { exact: true })).toHaveCount(0);
  await overview.getByRole("button", { name: "Options", exact: true }).click();
  await expect(overview.getByRole("menuitem", { name: /Launch activity/ })).toHaveCount(0);
  await expect(overview.getByRole("menuitem", { name: "Open in Circuit Designer" })).toHaveCount(0);
  await expect(overview.getByRole("menuitem", { name: /More actions/ })).toHaveCount(0);
  await expect(overview.getByRole("menuitem", { name: "Edit overview text…" })).toBeVisible();
  await overview.getByRole("menuitem", { name: "Edit overview text…" }).click();
  await expect(overview.getByLabel("Overview text")).toBeVisible();
  await overview.getByLabel("Overview text").fill("Top-level processor architecture overview.");
  await overview.getByRole("button", { name: "Save to Spec" }).click();
  await expect.poll(() => state.transactions.length).toBe(1);
  expect(state.transactions[0].operations).toEqual([
    expect.objectContaining({ type: "upsert_narrative_block" }),
  ]);
  await expect(page.locator(".spec-paper summary").filter({ hasText: "Technical details" })).toHaveCount(0);

  const design = page.locator("#design-design_top");
  await design.getByRole("button", { name: "Options", exact: true }).click();
  await expect(design.getByRole("menuitem", { name: /Generate RTL/ })).toBeVisible();
  await expect(design.getByText(/dut.clk is unconnected/)).toBeVisible();
  await design.getByRole("menuitem", { name: /Generate RTL/ }).click();
  await expect.poll(() => state.activityExecutions.length).toBe(1);
  expect(state.generatedTargets).toEqual([{ entity_kind: "design", entity_id: designRef.entity_id }]);
  await expect(page.locator(".utility-sidebar")).toHaveCount(0);
  await page.locator("#editor-activity-trigger").click();
  await expect(page.getByText("Generate RTL", { exact: true })).toBeVisible();
  if (await page.getByRole("button", { name: "Close side panel", exact: true }).isVisible()) await page.getByRole("button", { name: "Close side panel", exact: true }).click();

  await design.getByRole("button", { name: "Options", exact: true }).click();
  await expect(design.getByRole("menuitem", { name: /More actions|Launch activity/ })).toHaveCount(0);
  await expect(design.getByRole("menuitem", { name: "Explore with AI Assistant" })).toBeVisible();
  await design.getByRole("menuitem", { name: "Open in Circuit Designer" }).click();
  await expect.poll(() => state.circuits.length).toBe(2);

  const bus = page.locator("#bus-definition-bus_control");
  await bus.getByRole("button", { name: "Options", exact: true }).click();
  await expect(bus.getByRole("menuitem", { name: "Open in Circuit Designer" })).toHaveCount(0);
  await expect(bus.getByRole("menuitem", { name: "Explore with AI Assistant" })).toBeVisible();
});

test("creates entities, edits wire ports, and keeps other port families read-only", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);

  const composite = page.locator("#component-component_subsystem");
  await composite.getByRole("button", { name: "Options", exact: true }).click();
  await expect(composite.getByRole("menuitem", { name: /Add wire port.*Composite/ })).toBeDisabled();
  await expect(composite.getByRole("menuitem", { name: /Add transactional port/ })).toHaveCount(0);
  await expect(composite.getByRole("menuitem", { name: /Add structured port/ })).toHaveCount(0);

  const components = page.locator("#components");
  await components.getByRole("button", { name: "Options", exact: true }).click();
  await components.getByRole("menuitem", { name: "Add component…" }).click();
  await page.getByLabel("Component name").fill("counter");
  await page.getByRole("button", { name: "Create component" }).click();
  await expect.poll(() => state.transactions.length).toBe(1);
  expect(state.transactions[0]?.operations).toEqual([
    { type: "create_entity", kind: "component", name: "counter" },
  ]);

  const component = page.locator("#component-component_timer");
  await expect(component.getByRole("button", { name: "Rename", exact: true })).toHaveCount(0);
  await expect(component.getByRole("button", { name: "Edit text…", exact: true })).toHaveCount(0);
  await expect(component.getByText("Counts time", { exact: true })).toHaveClass(/spec-section-text/);
  await expect(component.getByText("acme:blocks:Timer:1.0", { exact: true })).toHaveCount(0);
  await expect(component.locator(".spec-ports-table")).toHaveCount(1);
  await expect(component.locator(".spec-port-row")).toHaveCount(3);
  await expect(component.locator(".spec-port-row", { hasText: "irq" })).toBeVisible();
  const transactionalRow = component.locator(".spec-port-row", { hasText: "request_stream" });
  await expect(transactionalRow).toContainText("Transactional");
  await expect(transactionalRow).toContainText("request_stream");
  await expect(transactionalRow).toContainText("provides");
  await expect(transactionalRow).toContainText("timer_service");
  await expect(transactionalRow).toContainText("DATA_WIDTH");
  await expect(transactionalRow).toContainText("Streams timer requests");
  const structuredRow = component.locator(".spec-port-row", { hasText: "status_bundle" });
  await expect(structuredRow).toContainText("Structured");
  await expect(structuredRow).toContainText("status_bundle");
  await expect(structuredRow).toContainText("Packed struct");
  await expect(structuredRow).toContainText("Packed status fields");
  await component.getByRole("button", { name: "Options", exact: true }).click();
  await component.getByRole("menuitem", { name: "Edit text…" }).click();
  await component.getByLabel("Component explanation").fill("A programmable timer.");
  await component.getByRole("button", { name: "Save to Spec" }).click();
  await expect.poll(() => state.transactions.length).toBe(2);
  expect(state.transactions[1]?.operations[0]).toEqual({
    type: "set_entity_metadata",
    entity: componentRef,
    display_name: "Timer",
    short_description: "",
    description: "A programmable timer.",
  });

  await component.getByRole("button", { name: "Options", exact: true }).click();
  await component.getByRole("menuitem", { name: "Add wire port…" }).click();
  const draftCard = component.locator(".spec-port-editor");
  await draftCard.getByLabel("Port ID").fill("count");
  await expect(draftCard.getByLabel("Port name (optional)")).toHaveCount(0);
  await draftCard.getByLabel("Direction").selectOption("out");
  await draftCard.getByLabel("Range").fill("31:0");
  await draftCard.getByLabel("Description").fill("Current counter value");
  await draftCard.getByRole("button", { name: "Save to Spec" }).click();
  await expect.poll(() => state.transactions.length).toBe(3);
  expect(state.transactions[2]?.operations[0]).toEqual({
    type: "add_component_port",
    component: componentRef,
    port: {
      name: "count",
      family: "wire",
      direction: "out",
      range: "31:0",
      description: "Current counter value",
    },
  });

  const existingCard = component.locator(".spec-port-row", { hasText: "irq" });
  await existingCard.getByRole("button", { name: /^Options for port/ }).click();
  await existingCard.getByRole("menuitem", { name: "Edit", exact: true }).click();
  const editCard = component.locator(".spec-port-editor");
  await expect(editCard.getByLabel("Port ID")).toHaveCount(0);
  await expect(editCard.getByLabel("Port name (optional)")).toHaveCount(0);
  await editCard.getByLabel("Direction").selectOption("inout");
  await editCard.getByLabel("Description").fill("Bidirectional interrupt");
  await editCard.getByRole("button", { name: "Save to Spec" }).click();
  await expect.poll(() => state.transactions.length).toBe(4);
  expect(state.transactions[3]?.operations[0]).toEqual({
    type: "update_component_port",
    component: componentRef,
    name: "irq",
    port: {
      family: "wire",
      direction: "inout",
      range: null,
      description: "Bidirectional interrupt",
    },
  });

  await expect(transactionalRow.getByRole("button", { name: /^Options for port/ })).toHaveCount(0);
  await expect(transactionalRow).toContainText("Read-only");
  await expect(structuredRow.getByRole("button", { name: /^Options for port/ })).toHaveCount(0);
  await expect(structuredRow).toContainText("Read-only");

});

test("validates port drafts, enforces one active editor, and restores focus", async ({ page }) => {
  await mockEditorApi(page);
  await openSample(page);
  const component = page.locator("#component-component_timer");
  const options = component.getByRole("button", { name: "Options", exact: true });

  await options.click();
  await component.getByRole("menuitem", { name: "Add wire port…" }).click();
  const draft = component.locator(".spec-port-editor");
  await draft.getByLabel("Port ID").fill("invalid_range");
  await draft.getByLabel("Range").fill("31::0");
  await draft.getByRole("button", { name: "Save to Spec" }).click();
  await expect(draft.getByRole("alert")).toContainText("left:right expression pair");

  await component.locator(".spec-port-row", { hasText: "irq" }).getByRole("button", { name: /^Options for port/ }).click();
  await component.locator(".spec-port-row", { hasText: "irq" }).getByRole("menuitem", { name: "Edit", exact: true }).click();
  await expect(page.getByText("Save or cancel the current edit before starting another one.")).toBeVisible();
  await expect(draft).toBeVisible();

  await draft.getByRole("button", { name: "Cancel" }).click();
  await expect(options).toBeFocused();
  await expect(draft).toHaveCount(0);
});

test("preserves an inline draft when the optimistic revision is stale", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  const component = page.locator("#component-component_timer");
  await component.getByRole("button", { name: "Options", exact: true }).click();
  await component.getByRole("menuitem", { name: "Edit text…" }).click();
  await component.getByLabel("Component explanation").fill("Keep this draft after refresh.");
  state.staleNextTransaction = true;
  await component.getByRole("button", { name: "Save to Spec" }).click();

  await expect(component.getByLabel("Component explanation")).toHaveValue("Keep this draft after refresh.");
  await expect(component.getByRole("alert")).toContainText("preserved draft");
  await page.getByRole("button", { name: "Use reviewed revision for next save" }).click();
  await component.getByRole("button", { name: "Save to Spec" }).click();
  await expect.poll(() => state.transactions.length).toBe(2);
  expect(state.transactions[1]?.expected_source_revision_hash).toBe("sha256:external-change");
});

test("offers Help content and remains usable at a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 560, height: 760 });
  await mockEditorApi(page);
  await openSample(page);

  await page.getByRole("button", { name: "Menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Help", exact: true }).click();
  await page.getByRole("menuitem", { name: "Getting Started" }).click();
  await expect(page.getByRole("dialog", { name: "Getting started" })).toContainText("Use Save to Spec");
  await page.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("button", { name: "Menu", exact: true })).toBeFocused();
  await page.getByRole("button", { name: "Menu", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: "File", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("#editor-diagnostics-trigger")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("opens the assigned Design for boundary edits and identifies launch modes", async ({ page }, testInfo) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  const composite = page.locator("#component-component_subsystem");
  const edit = composite.getByRole("button", { name: "Edit boundary ports in Circuit Designer", exact: true });
  await edit.click();
  await expect.poll(() => state.circuits).toEqual([{ entity_kind: "design", entity_id: "design_internal" }]);
  expect(state.transactions).toHaveLength(0);
  await page.getByRole("menuitem", { name: "Circuit Designer", exact: true }).click();
  const menu = page.getByRole("menu", { name: "Circuit Designer" });
  await expect(menu.getByRole("menuitem", { name: /Processor.*Edit Design/ })).toBeVisible();
  await expect(menu.getByRole("menuitem", { name: /Subsystem.*Open assigned Design/ })).toBeVisible();
  await page.keyboard.press("Escape");
  for (const theme of ["clean", "obsidian"]) {
    if (await page.locator("html").getAttribute("data-theme") !== theme) await page.locator(".theme-quick-toggle").click();
    for (const size of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 560, height: 760 }]) {
      await page.setViewportSize(size);
      const preview = page.locator("#design-design_top .spec-topology-card__preview");
      await preview.scrollIntoViewIfNeeded();
      await expect(preview).toHaveCSS("background-color", theme === "clean" ? "rgb(247, 249, 252)" : "rgb(9, 9, 11)");
      await expect(preview.locator("img")).toBeVisible();
      for (const card of [page.locator("#design-design_top .spec-topology-card"), page.locator("#component-component_timer .spec-topology-card")]) {
        const options = card.getByRole("button", { name: "Options for circuit preview", exact: true });
        await options.scrollIntoViewIfNeeded();
        await expect(options).toBeVisible();
        await expect(card.getByRole("button", { name: "Open in Circuit Designer", exact: true })).toHaveCount(0);
        const widths = await card.evaluate(element => {
          const parent = element.parentElement!;
          const style = getComputedStyle(parent);
          return { card: element.getBoundingClientRect().width,
            available: parent.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) };
        });
        expect(Math.abs(widths.card - widths.available)).toBeLessThanOrEqual(1);
        const optionsBox = await options.boundingBox();
        expect(optionsBox!.x).toBeGreaterThanOrEqual(0);
        expect(optionsBox!.x + optionsBox!.width).toBeLessThanOrEqual(size.width);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      if (size.width === 560) await page.getByRole("button", { name: "Menu", exact: true }).click();
      await page.getByRole("menuitem", { name: "Circuit Designer", exact: true }).click();
      await expect(page.getByRole("menu", { name: "Circuit Designer", exact: true })).toBeVisible();
      await page.keyboard.press("Escape");
      if (size.width === 560) await page.keyboard.press("Escape");
      await page.screenshot({ path: testInfo.outputPath(`preview-${theme}-${size.width}.png`) });
    }
  }
});

test("shows generated RTL diagnostics on the checked target with their file location", async ({ page }) => {
  await mockEditorApi(page);
  await page.route("**/documents/view*", async route => {
    // The existing fixture supplies the document projection; replace only its verification result.
    const currentBatch = structuredClone(batch);
    const checked = { ...snapshot, verifications: [{ target: designRef, source_revision_hash: revision, status: "failed", tool_version: "Verilator fixture", diagnostics: [{ code: "VERILATOR_ERROR", message: "Invalid parent connection", blocking: true, file_path: "designs/processor.sv", source_kind: "generated", line: 31, column: 45 }], functional_simulation: "unverified" }] };
    await route.fulfill({ json: { snapshot: checked, a2ui: currentBatch, activity: { executions: [], artifacts: [], proposals: [], assistant_changes: [] }, approval_policy: "automatic", event_cursor: 0, source_revision_hash: revision } });
  });
  await openSample(page);
  const design = page.locator("#design-design_top");
  await expect(design.locator(".spec-hardware-controls [role=status]")).toHaveCount(0);
  await expect(page.locator(".utility-sidebar")).toHaveCount(0);
  await page.locator("#editor-diagnostics-trigger").click();
  await expect(page.locator(".utility-sidebar")).toContainText("Generated RTL: designs/processor.sv:31:45");
  await expect(page.locator(".spec-section-diagnostics")).toHaveCount(0);
  await page.getByRole("button", { name: "Go to source", exact: true }).click();
  await expect(design).toBeInViewport();
  await expect(design.locator("h3")).toBeFocused();
  await expect(page.locator(".spec-source-highlight")).toHaveCount(0);
});

test("keeps port actions compact and keyboard accessible in both themes", async ({ page }, testInfo) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  const row = page.locator("#component-component_timer .spec-port-row").first();
  for (const theme of ["obsidian", "clean"]) {
    if (await page.locator("html").getAttribute("data-theme") !== theme) await page.locator(".theme-quick-toggle").click();
    for (const size of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 560, height: 760 }]) {
      await page.setViewportSize(size);
      await row.getByRole("button", { name: /^Options for port/ }).scrollIntoViewIfNeeded();
      const rowBox = await row.boundingBox();
      expect(rowBox!.height).toBeLessThan(90);
      await expect(page.getByRole("menuitem", { name: "Duplicate", exact: true })).toBeHidden();
      const more = row.getByLabel("Options for port irq", { exact: true });
      await more.focus();
      await page.keyboard.press("Enter");
      await expect(page.getByRole("menuitem", { name: "Duplicate", exact: true })).toBeVisible();
      await expect(page.getByRole("menuitem", { name: "Delete port", exact: true })).toBeVisible();
      await page.screenshot({ path: testInfo.outputPath(`ports-${theme}-${size.width}.png`) });
      await page.keyboard.press("Escape");
      await expect(more).toBeFocused();
      await expect(page.getByRole("menuitem", { name: "Duplicate", exact: true })).toBeHidden();
    }
  }
  await row.getByLabel("Options for port irq", { exact: true }).click();
  await page.getByRole("menuitem", { name: "Duplicate", exact: true }).click();
  const draft = page.locator("#component-component_timer .spec-port-editor");
  await expect(draft.getByLabel("Port ID", { exact: true })).toHaveValue("irq_2");
  await draft.getByRole("button", { name: "Cancel", exact: true }).click();
  expect(state.transactions).toHaveLength(0);
});

test("keeps mixed-family tables contained, IDs exact, and row actions readable", async ({ page }) => {
  await mockEditorApi(page);
  await openSample(page);
  const component = page.locator("#component-component_timer");
  for (const width of [390, 620, 800, 1024, 1100, 1440, 1728]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    const id = component.locator(".spec-port-row").first().locator("th");
    await expect(id).toHaveText("irq");
    await expect(id).toHaveCSS("text-transform", "none");
    const button = component.locator(".spec-port-row").first().getByRole("button", { name: /^Options for port/ });
    await expect(button).toHaveCSS("white-space", "nowrap");
    const scroll = component.getByRole("group", { name: "Ports", exact: true });
    await expect(scroll).toHaveAttribute("tabindex", "0");
    const box = await scroll.boundingBox();
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await component.locator(".spec-port-row").first().getByRole("button", { name: /^Options for port/ }).click();
  await component.locator(".spec-port-row").first().getByRole("menuitem", { name: "Edit", exact: true }).click();
  const draft = component.locator(".spec-port-editor");
  await expect(draft).toBeVisible();
  for (const control of [draft.getByLabel("Description"), draft.getByLabel("Direction"), draft.getByRole("button", { name: "Save to Spec", exact: true })]) {
    const box = await control.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  }
  await draft.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(component.locator(".spec-port-row").first().getByRole("button", { name: /^Options for port/ })).toBeFocused();
});

test("tracks the visible Section and keeps Contents and anchor targets below the toolbar", async ({ page }) => {
  await mockEditorApi(page);
  await openSample(page);
  const section = page.locator("#component-component_timer");
  await section.evaluate(el => el.scrollIntoView({ behavior: "instant", block: "start" }));
  await expect(page.locator('.spec-toc a[aria-current="location"]')).toHaveText("Timer");
  const header = await page.locator(".app-header").boundingBox();
  const contents = await page.locator(".spec-toc__sticky").boundingBox();
  const target = await section.boundingBox();
  expect(contents!.y).toBeGreaterThanOrEqual(header!.height);
  expect(target!.y).toBeGreaterThanOrEqual(header!.height);
  await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
  await expect(page.locator('.spec-toc a[aria-current="location"]')).toHaveText("Overview");
});

test("provides narrow Contents navigation, focus restoration, and unobstructed status", async ({ page }) => {
  await mockEditorApi(page);
  await openSample(page);
  await page.setViewportSize({ width: 390, height: 844 });
  const trigger = page.getByRole("button", { name: "Contents", exact: true });
  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("navigation", { name: "Spec Sections" }).getByRole("link", { name: "Timer", exact: true }).focus();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await trigger.click();
  await page.getByRole("navigation", { name: "Spec Sections" }).getByRole("link", { name: "Timer", exact: true }).click();
  await expect(page.locator("#component-component_timer h3")).toBeFocused();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  const header = await page.locator(".app-header").boundingBox();
  expect(header!.height).toBeLessThanOrEqual(120);
  await expect(page.locator(".spec-status-bar")).toHaveCSS("position", "static");
  await expect(page.locator(".spec-status-bar")).toContainText("Up to date");
  await expect(page.locator(".assistant-launch")).toBeVisible();
});

test("keeps a long Spec name and its edit action reachable at narrow widths", async ({ page }) => {
  await mockEditorApi(page);
  const name = "Timing interface specification ".repeat(6).trim();
  await page.goto("/");
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /New Spec/ }).click();
  await page.getByLabel("Spec name").fill(name);
  await page.getByText("More options", { exact: true }).click();
  await page.getByLabel("File path", { exact: true }).fill("/tmp/long-name.spec");
  await page.getByRole("button", { name: "Create Spec", exact: true }).click();
  await expect(page.locator(".spec-cover h1")).toHaveText(name);
  for (const width of [390, 720, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    const action = page.locator(".spec-cover").getByRole("button", { name: "Options", exact: true });
    await expect(action).toBeVisible();
    const box = await action.boundingBox();
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);
  }
});

test("Cut and Paste retain input and textarea selections and save their results", async ({ context, page }) => {
  const origin = new URL(endpointUrl(resolveConfig(process.env.SPEC2GDS_TEST_SERVICE_CONFIG).spec_editor.dev_ui, "127.0.0.1", { local: true })).origin;
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin });
  const state = await mockEditorApi(page);
  await openSample(page);
  const component = page.locator("#component-component_timer");
  await component.getByRole("button", { name: "Options", exact: true }).click();
  await component.getByRole("menuitem", { name: "Add wire port…" }).click();
  const field = component.getByLabel("Port ID", { exact: true });
  await field.fill("abcdef");
  await field.evaluate((input: HTMLInputElement) => { input.setSelectionRange(3, 6); document.dispatchEvent(new Event("selectionchange")); });
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Cut", exact: true }).click();
  await expect(field).toHaveValue("abc");
  await expect(field).toBeFocused();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe("def");
  await page.evaluate(() => navigator.clipboard.writeText("xyz"));
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Paste", exact: true }).click();
  await expect(field).toHaveValue("abcxyz");
  await component.getByRole("button", { name: "Save to Spec" }).click();
  expect(state.transactions[0]?.operations[0].port.name).toBe("abcxyz");

  await component.getByRole("button", { name: "Options", exact: true }).click();
  await component.getByRole("menuitem", { name: "Edit text…" }).click();
  const text = component.getByLabel("Component explanation");
  await text.fill("one two");
  await text.evaluate((input: HTMLTextAreaElement) => { input.setSelectionRange(4, 7); document.dispatchEvent(new Event("selectionchange")); });
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Cut", exact: true }).click();
  await expect(text).toHaveValue("one ");
  await page.evaluate(() => navigator.clipboard.writeText("three\nfour"));
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Paste", exact: true }).click();
  await expect(text).toHaveValue("one three\nfour");
  await text.evaluate((input: HTMLTextAreaElement) => { input.setSelectionRange(0, input.value.length); document.dispatchEvent(new Event("selectionchange")); });
  await page.evaluate(() => navigator.clipboard.writeText(""));
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Paste", exact: true }).click();
  await expect(text).toHaveValue("one three\nfour");
  await component.getByRole("button", { name: "Save to Spec" }).click();
  expect(state.transactions[1]?.operations[0].description).toBe("one three\nfour");
});

test("clipboard denial preserves a draft and SystemVerilog uses its editor model", async ({ context, page }) => {
  const origin = new URL(endpointUrl(resolveConfig(process.env.SPEC2GDS_TEST_SERVICE_CONFIG).spec_editor.dev_ui, "127.0.0.1", { local: true })).origin;
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin });
  const state = await mockEditorApi(page);
  await openSample(page);
  const component = page.locator("#component-component_timer");
  await component.getByRole("button", { name: "Options", exact: true }).click();
  await component.getByRole("menuitem", { name: "Add SystemVerilog section…" }).click();
  const code = component.locator(".cm-content");
  await code.fill("// first\n// second");
  await code.press("ControlOrMeta+a");
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Cut", exact: true }).click();
  await expect(code).toHaveText("");
  await page.evaluate(() => navigator.clipboard.writeText("// replacement\n// saved"));
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Paste", exact: true }).click();
  await expect(code).toContainText("// replacement");
  await expect(code).toContainText("// saved");
  await code.press("ControlOrMeta+a");
  await page.evaluate(() => Object.defineProperty(navigator.clipboard, "writeText", { value: async () => { throw new DOMException("Denied", "NotAllowedError"); } }));
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Cut", exact: true }).click();
  await expect(page.getByRole("alert").first()).toContainText("Could not cut text");
  await expect(code).toContainText("// replacement");
  await expect(code).toBeFocused();
  await page.evaluate(() => Object.defineProperty(navigator.clipboard, "readText", { value: async () => { throw new DOMException("Denied", "NotAllowedError"); } }));
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Paste", exact: true }).click();
  await expect(page.getByRole("alert").first()).toContainText("Could not paste text");
  await expect(code).toContainText("// saved");
  await component.getByRole("button", { name: "Add section", exact: true }).click();
  expect(state.transactions[0]?.operations[0].payload.content).toBe("// replacement\n// saved");
});

test("does not reuse late commands from a closed menu and shows unavailable Activity reasons", async ({ page }) => {
  await mockEditorApi(page);
  let release: () => void = () => {};
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/entities/design/design_top/activities**", async route => {
    await held;
    await route.fulfill({ json: { activities: [{
      definition: { activity_id: "test.old", title: "Old target Activity", description: "Old response", version: "1.0.0" },
      availability: { available: true, diagnostics: [] },
    }] } });
  });
  await page.route("**/entities/component/component_timer/activities**", route => route.fulfill({ json: { activities: [{
    definition: { activity_id: "test.unavailable", title: "Unavailable Activity", description: "Needs a source section", version: "1.0.0" },
    availability: { available: false, diagnostics: ["Add a SystemVerilog section first."] },
  }] } }));
  await openSample(page);
  const design = page.locator("#design-design_top");
  await design.getByRole("button", { name: "Options", exact: true }).click();
  await expect(design.getByRole("menuitem", { name: "Checking available commands…" })).toBeVisible();
  const component = page.locator("#component-component_timer");
  await component.getByRole("button", { name: "Options", exact: true }).click();
  release();
  const unavailable = component.getByRole("menuitem", { name: /Unavailable Activity/ });
  await expect(unavailable).toBeDisabled();
  await expect(unavailable).toContainText("Add a SystemVerilog section first.");
  await expect(page.getByRole("menuitem", { name: "Old target Activity" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(component.getByRole("button", { name: "Options", exact: true })).toBeFocused();
});

test("ignores a command catalogue response from an earlier source revision", async ({ page }) => {
  const state = await mockEditorApi(page);
  let release: () => void = () => {};
  const oldResponse = new Promise<void>(resolve => { release = resolve; });
  let requests = 0;
  await page.route("**/entities/design/design_top/activities**", async route => {
    const first = ++requests === 1;
    if (first) await oldResponse;
    await route.fulfill({ json: { activities: [{
      definition: { activity_id: first ? "test.old_revision" : "test.current_revision", title: first ? "Earlier revision Activity" : "Current revision Activity", description: "Source revision check", version: "1.0.0" },
      availability: { available: true, diagnostics: [] },
    }] } });
  });
  await openSample(page);
  const design = page.locator("#design-design_top");
  await design.getByRole("button", { name: "Options", exact: true }).click();
  await expect(design.getByRole("menuitem", { name: "Checking available commands…" })).toBeVisible();
  await page.keyboard.press("Escape");
  state.currentRevision = `sha256:${"9".repeat(64)}`;
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: "Refresh From Disk", exact: true }).click();
  await expect.poll(() => state.openedPaths.length).toBe(2);
  await design.getByRole("button", { name: "Options", exact: true }).click();
  await expect(design.getByRole("menuitem", { name: "Current revision Activity", exact: true })).toBeVisible();
  release();
  await expect(page.getByRole("menuitem", { name: "Earlier revision Activity", exact: true })).toHaveCount(0);
  await expect(design.getByRole("menuitem", { name: "Current revision Activity", exact: true })).toBeVisible();
});

test("preserves an unsaved draft and selection while inspecting an Activity", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  const design = page.locator("#design-design_top");
  await design.getByRole("button", { name: "Options", exact: true }).click();
  await design.getByRole("menuitem", { name: "Edit text…", exact: true }).click();
  await design.getByLabel("Design explanation").fill("Keep this private draft.");
  await design.getByRole("button", { name: "Options", exact: true }).click();
  await design.getByRole("menuitem", { name: /Generate RTL/ }).click();
  await expect.poll(() => state.activityExecutions.length).toBe(1);
  await expect(page.locator(".utility-sidebar")).toHaveCount(0);
  await page.locator("#editor-activity-trigger").click();
  await expect(page.getByRole("heading", { name: "Activity", exact: true })).toBeVisible();
  if (await page.getByRole("button", { name: "Close side panel", exact: true }).isVisible()) await page.getByRole("button", { name: "Close side panel", exact: true }).click();
  const draft = design.getByLabel("Design explanation");
  await expect(draft).toHaveValue("Keep this private draft.");
  await draft.click();
  await draft.evaluate((input: HTMLTextAreaElement) => { input.setSelectionRange(0, input.value.length); document.dispatchEvent(new Event("selectionchange")); });
  if (await page.locator("#editor-activity-trigger").getAttribute("aria-expanded") !== "true") await page.locator("#editor-activity-trigger").click();
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: "Cut", exact: true })).toBeDisabled();
  await expect(page.getByRole("menuitem", { name: "Paste", exact: true })).toBeDisabled();
  await expect(page.getByRole("menuitem", { name: "Copy", exact: true })).toBeDisabled();
  await page.keyboard.press("Escape");
  if (await page.getByRole("button", { name: "Close side panel", exact: true }).isVisible()) await page.getByRole("button", { name: "Close side panel", exact: true }).click();
  await expect(design.getByLabel("Design explanation")).toHaveValue("Keep this private draft.");
  expect(await draft.evaluate((input: HTMLTextAreaElement) => [input.selectionStart, input.selectionEnd])).toEqual([0, "Keep this private draft.".length]);
  expect(state.transactions).toHaveLength(0);
});

test("refreshes artifacts after completion without requiring a source change or reconnect", async ({ page }) => {
  await page.addInitScript(() => {
    const sources: TestSource[] = [];
    class TestSource extends EventTarget {
      url: string;
      constructor(url: string) { super(); this.url = url; sources.push(this); }
      close() { sources.splice(sources.indexOf(this), 1); }
    }
    Object.defineProperty(window, "EventSource", { value: TestSource });
    (window as unknown as { emitActivity: (record: object) => void }).emitActivity = record => {
      sources.filter(source => source.url.includes("/activity-events")).forEach(source => {
        source.dispatchEvent(new MessageEvent("activity.execution.changed", { data: JSON.stringify(record) }));
      });
    };
  });
  const state = await mockEditorApi(page);
  await page.clock.install();
  await openSample(page);
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: "Refresh From Disk", exact: true }).click();
  await expect.poll(() => state.openedPaths.length).toBe(2);
  const design = page.locator("#design-design_top");
  await design.getByRole("button", { name: "Options", exact: true }).click();
  await design.getByRole("menuitem", { name: /Generate RTL/ }).click();
  await expect(page.locator(".utility-sidebar")).toHaveCount(0);
  await page.locator("#editor-activity-trigger").click();
  await expect(page.getByRole("heading", { name: "Activity", exact: true })).toBeVisible();
  await page.getByText("Artifacts", { exact: true }).click();
  await expect(page.getByText("No generated artifacts.")).toBeVisible();
  state.artifacts.push({ artifact_id: "artifact_summary", role: "spec.summary", media_type: "application/json", size: 42, source_entities: [designRef] });
  const finished = { ...state.activityExecutions[0], status: "succeeded", artifact_ids: ["artifact_summary"] };
  state.activityExecutions[0] = finished;
  await page.evaluate(record => (window as unknown as { emitActivity: (record: object) => void }).emitActivity(record), finished);
  await expect(page.getByRole("link", { name: "Download JSON" })).toBeVisible();
  await expect(page.getByText("Target Section details", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Download JSON" })).toHaveAttribute("href", /owner_document_key=/);
  await page.mouse.move(0, 0);
  await page.clock.fastForward(5100);
  await expect(page.locator(".app-toast")).toHaveCount(0);
  await page.evaluate(record => (window as unknown as { emitActivity: (record: object) => void }).emitActivity(record), finished);
  await expect(page.locator(".app-toast")).toHaveCount(0);
  await expect(page.locator("#utility-tab-activity")).toHaveAttribute("aria-selected", "true");
});

test("proposal review preserves a private draft and its authored revision", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  const authoredRevision = state.currentRevision;
  const design = page.locator("#design-design_top");
  await design.getByRole("button", { name: "Options", exact: true }).click();
  await design.getByRole("menuitem", { name: "Edit text…", exact: true }).click();
  await design.getByLabel("Design explanation").fill("Keep the authored draft.");
  state.proposals.push({ proposal_id: "proposal_draft_review", review_status: "pending", rationale: "Add a saved note", operations: [{ type: "upsert_narrative_block", block: { block_id: "review_note", type: "paragraph", text: "Saved source note" } }] });
  if (await page.locator("#editor-activity-trigger").getAttribute("aria-expanded") !== "true") await page.locator("#editor-activity-trigger").click();
  await page.locator(".utility-heading").getByRole("button", { name: "Options", exact: true }).click();
  await page.getByRole("menuitem", { name: "Refresh", exact: true }).click();
  await page.locator(".activity-item").filter({ hasText: "Add a saved note" }).getByRole("button", { name: "Options", exact: true }).click();
  await page.getByRole("menuitem", { name: "Accept", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Proposal accepted." })).toBeVisible();
  if (await page.getByRole("button", { name: "Close side panel", exact: true }).isVisible()) await page.getByRole("button", { name: "Close side panel", exact: true }).click();
  await expect(design.getByLabel("Design explanation")).toHaveValue("Keep the authored draft.");
  state.staleNextTransaction = true;
  await design.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect.poll(() => state.transactions.length).toBe(1);
  expect(state.transactions[0].expected_source_revision_hash).toBe(authoredRevision);
  await expect(design.getByLabel("Design explanation")).toHaveValue("Keep the authored draft.");
});

test("toggles themes via quick toggle and Preferences dialog with persistence", async ({ page }) => {
  await mockEditorApi(page);
  await page.goto("/");

  // Default theme is obsidian
  await expect(page.locator("html")).toHaveAttribute("data-theme", "obsidian");
  await page.screenshot({ path: test.info().outputPath("spec_editor_obsidian.png") });

  // Click quick toggle in header
  const toggleButton = page.locator(".theme-quick-toggle");
  await expect(toggleButton).toBeVisible();
  await toggleButton.click();

  // Switched to clean (light)
  await expect(page.locator("html")).toHaveAttribute("data-theme", "clean");
  await page.screenshot({ path: test.info().outputPath("spec_editor_clean.png") });

  // Open Edit -> Preferences…
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: /Preferences/ }).click();

  const preferencesDialog = page.getByRole("dialog", { name: "Preferences" });
  await expect(preferencesDialog).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("spec_editor_preferences_dialog.png") });

  // Verify focus trap wraps between first and last focusable elements
  const closeButton = preferencesDialog.getByRole("button", { name: "Close" });
  const doneButton = preferencesDialog.getByRole("button", { name: "Done" });
  await doneButton.focus();
  await page.keyboard.press("Tab");
  await expect(closeButton).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(doneButton).toBeFocused();

  // Switch back to Obsidian in the dialog
  await preferencesDialog.getByRole("radio", { name: /Obsidian/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "obsidian");

  // Close dialog via Escape and verify focus restores to Edit menu trigger
  await page.keyboard.press("Escape");
  await expect(preferencesDialog).not.toBeVisible();
  await expect(page.locator("#editor-edit-menu-trigger")).toBeFocused();

  // Reload page to verify persistence in localStorage
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "obsidian");
});

test("renders SystemVerilog edit box with full width and aligns Section Options to right", async ({ page }) => {
  await mockEditorApi(page);
  await openSample(page);

  // Verify narrative block and Explore button alignment
  const narrativeBlock = page.locator(".spec-narrative-block");
  await expect(narrativeBlock).toBeVisible();
  const exploreButton = narrativeBlock.getByRole("button", { name: "Options for text Section", exact: true });
  await expect(exploreButton).toBeVisible();
  await expect(exploreButton).toHaveText(/Options/);

  // Verify exploreButton is aligned to the right edge of narrativeBlock
  const narrativeBox = await narrativeBlock.boundingBox();
  const buttonBox = await exploreButton.boundingBox();
  expect(narrativeBox).not.toBeNull();
  expect(buttonBox).not.toBeNull();
  expect(buttonBox!.x + buttonBox!.width).toBeGreaterThanOrEqual(narrativeBox!.x + narrativeBox!.width - 10);

  await page.locator("#component-component_timer").scrollIntoViewIfNeeded();
  await page.screenshot({ path: test.info().outputPath("spec_editor_narrative_action_right.png") });

  // Open SystemVerilog editor
  const timer = page.locator("#component-component_timer");
  await timer.getByRole("button", { name: "Options", exact: true }).click();
  await page.getByRole("menuitem", { name: "Add SystemVerilog section…" }).click();

  const svForm = timer.locator(".spec-sv-editor-form");
  await expect(svForm).toBeVisible();
  const codeEditor = svForm.locator(".spec-sv-code-editor");
  await expect(codeEditor).toBeVisible();

  // Verify that code editor width matches form width (full width available)
  const formBox = await svForm.boundingBox();
  const codeBox = await codeEditor.boundingBox();
  expect(formBox).not.toBeNull();
  expect(codeBox).not.toBeNull();
  expect(codeBox!.width).toBeGreaterThanOrEqual(formBox!.width - 36);

  await svForm.scrollIntoViewIfNeeded();
  await page.screenshot({ path: test.info().outputPath("spec_editor_sv_full_width.png") });
});

test("TS-UI-001 and TS-UI-002: renders canonical Spec Editor branding and inflects document entity counts", async ({ page }) => {
  const state = await mockEditorApi(page);
  // Set uninflected summary to verify formatDocumentSummary converts "1 components" -> "1 component"
  state.currentSummary = "1 components · 0 designs";

  await page.goto("/");
  await expect(page).toHaveTitle("spec2hw · Spec Editor");
  await expect(page.locator(".brand strong")).toHaveText("spec2hw");

  await openSample(page);
  await expect(page).toHaveTitle("spec2hw · Spec Editor");

  const summary = page.locator(".spec-cover p");
  await expect(summary).toBeVisible();
  await expect(summary).toHaveText("1 component · 0 designs");
});

test("TS-UI-004: dialogs enforce ARIA modal focus trapping, Escape dismissal, and return focus to trigger", async ({ page }) => {
  await mockEditorApi(page);
  await openSample(page);

  // Test Help -> About spec2hw dialog
  await page.getByRole("menuitem", { name: "Help", exact: true }).click();
  await page.getByRole("menuitem", { name: "About spec2hw", exact: true }).click();

  const aboutDialog = page.getByRole("dialog", { name: "About spec2hw" });
  await expect(aboutDialog).toBeVisible();
  await expect(aboutDialog).toHaveAttribute("aria-modal", "true");

  const closeButton = aboutDialog.getByRole("button", { name: "Close" });
  await expect(closeButton).toBeFocused();

  // Press Escape to dismiss and verify focus returns to Help menu trigger
  await page.keyboard.press("Escape");
  await expect(aboutDialog).not.toBeVisible();
  await expect(page.locator("#editor-help-menu-trigger")).toBeFocused();

  // Test Help -> Keyboard shortcuts dialog
  await page.getByRole("menuitem", { name: "Help", exact: true }).click();
  await page.getByRole("menuitem", { name: "Keyboard Shortcuts", exact: true }).click();

  const shortcutsDialog = page.getByRole("dialog", { name: "Keyboard shortcuts" });
  await expect(shortcutsDialog).toBeVisible();
  await expect(shortcutsDialog).toHaveAttribute("aria-modal", "true");

  await page.keyboard.press("Escape");
  await expect(shortcutsDialog).not.toBeVisible();
  await expect(page.locator("#editor-help-menu-trigger")).toBeFocused();
});

test("TS-UI-007: validates WCAG AA contrast ratio for table headers and menus across light and dark themes", async ({ page }) => {
  await mockEditorApi(page);
  await openSample(page);

  const getContrastRatio = async (fgSelector: string, bgSelector: string) => {
    return await page.evaluate(({ fgSel, bgSel }) => {
      const parseRgb = (color: string) => {
        const match = color.match(/\d+(\.\d+)?/g);
        return match ? match.slice(0, 3).map(Number) : [0, 0, 0];
      };
      const luminance = ([r, g, b]: number[]) => {
        const a = [r, g, b].map((v) => {
          const c = v / 255;
          return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        });
        return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
      };

      const fgEl = document.querySelector(fgSel);
      const bgEl = document.querySelector(bgSel);
      if (!fgEl || !bgEl) return 0;

      const fgColor = window.getComputedStyle(fgEl).color;
      let bgTarget: HTMLElement | null = bgEl as HTMLElement;
      let bgColor = window.getComputedStyle(bgTarget).backgroundColor;
      while (bgTarget && (bgColor === "transparent" || bgColor === "rgba(0, 0, 0, 0)")) {
        bgTarget = bgTarget.parentElement;
        if (bgTarget) bgColor = window.getComputedStyle(bgTarget).backgroundColor;
      }

      const l1 = luminance(parseRgb(fgColor));
      const l2 = luminance(parseRgb(bgColor));
      const brighter = Math.max(l1, l2);
      const darker = Math.min(l1, l2);
      return (brighter + 0.05) / (darker + 0.05);
    }, { fgSel: fgSelector, bgSel: bgSelector });
  };

  // Check Obsidian (dark theme) table header contrast
  const obsidianThRatio = await getContrastRatio(".spec-table-scroll th", ".spec-table-scroll th");
  expect(obsidianThRatio).toBeGreaterThanOrEqual(4.5);
  await page.setViewportSize({ width: 560, height: 760 });
  expect(await getContrastRatio(".editor-mobile-menu-trigger", ".editor-mobile-menu-trigger")).toBeGreaterThanOrEqual(4.5);

  // Switch to Clean (light theme)
  await page.locator(".theme-quick-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "clean");

  // Check Clean (light theme) table header contrast
  const cleanThRatio = await getContrastRatio(".spec-table-scroll th", ".spec-table-scroll th");
  expect(cleanThRatio).toBeGreaterThanOrEqual(4.5);
  expect(await getContrastRatio(".editor-mobile-menu-trigger", ".editor-mobile-menu-trigger")).toBeGreaterThanOrEqual(4.5);
});

test("captures Spec Editor visual baselines across themes, viewports, and dialogs", async ({ page }) => {
  const outputDir = process.env.UI_BASELINE_DIR || test.info().outputPath("visual-baselines");
  mkdirSync(outputDir, { recursive: true });
  const saveBaseline = async (filename: string) => {
    await page.screenshot({ path: join(outputDir, filename) });
  };

  await mockEditorApi(page);

  // 1. Desktop 1440x900 Obsidian (Dark)
  await page.setViewportSize({ width: 1440, height: 900 });
  await openSample(page);
  await saveBaseline("spec_editor_obsidian_1440x900.png");

  // 2. Desktop 1440x900 Clean (Light)
  await page.locator(".theme-quick-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "clean");
  await saveBaseline("spec_editor_clean_1440x900.png");

  // Switch back to dark for dialogs
  await page.locator(".theme-quick-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "obsidian");

  // 3. Compact 1024x768
  await page.setViewportSize({ width: 1024, height: 768 });
  await saveBaseline("spec_editor_compact_1024x768.png");

  // 4. Narrow 560x760
  await page.setViewportSize({ width: 560, height: 760 });
  await saveBaseline("spec_editor_narrow_560x760.png");

  // Restore desktop size
  await page.setViewportSize({ width: 1440, height: 900 });

  // 5. Preferences Dialog
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: /Preferences/ }).click();
  const preferencesDialog = page.getByRole("dialog", { name: "Preferences" });
  await expect(preferencesDialog).toBeVisible();
  await saveBaseline("spec_editor_preferences_dialog.png");
  await page.keyboard.press("Escape");
  await expect(preferencesDialog).not.toBeVisible();

  // 6. About Dialog
  await page.getByRole("menuitem", { name: "Help", exact: true }).click();
  await page.getByRole("menuitem", { name: "About spec2hw", exact: true }).click();
  const aboutDialog = page.getByRole("dialog", { name: "About spec2hw" });
  await expect(aboutDialog).toBeVisible();
  await saveBaseline("spec_editor_about_dialog.png");
  await page.keyboard.press("Escape");
  await expect(aboutDialog).not.toBeVisible();

  // 7. Topology Preview Dialog
  const design = page.locator("#design-design_top");
  const card = design.locator(".spec-topology-card");
  await card.getByRole("button", { name: "Options for circuit preview", exact: true }).click();
  const expand = card.getByRole("menuitem", { name: "Expand", exact: true });
  await expand.scrollIntoViewIfNeeded();
  await expand.click();
  const topologyDialog = page.getByRole("dialog", { name: "Circuit topology" });
  await expect(topologyDialog).toBeVisible();
  await saveBaseline("spec_editor_topology_dialog.png");
  await page.keyboard.press("Escape");
  await expect(topologyDialog).not.toBeVisible();
});


test("Copy uses the service suggestion beside the source", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /Create Copy/ }).click();
  await expect(page.getByLabel("Spec name", { exact: true })).toHaveValue("Editor Test copy");
  await expect(page.locator(".spec-filename")).toHaveText("File: existing-copy.spec");
  await expect(page.locator(".spec-location strong")).toHaveText("Spec root / specifications");
  await page.getByRole("button", { name: "Create Copy", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(state.copiedPaths).toEqual(["/home/designer/specifications/existing-copy.spec"]);
  expect(state.createdPaths).toEqual([]);
});

test("late copy suggestions preserve edits and a pending copy submits once", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  let releaseSuggestion!: () => void;
  const suggestionGate = new Promise<void>(resolve => { releaseSuggestion = resolve; });
  await page.route("**/api/documents/copy-suggestion*", async route => {
    await suggestionGate;
    return route.fulfill({ json: { path: "/home/designer/specifications/late.spec", title: "Late suggestion" } });
  });
  let releaseCopy!: () => void;
  const copyGate = new Promise<void>(resolve => { releaseCopy = resolve; });
  let requests = 0;
  await page.route("**/api/documents/copy", async route => { ++requests; await copyGate; return route.fallback(); });
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /Create Copy/ }).click();
  await page.getByLabel("Spec name", { exact: true }).fill("Chosen copy");
  await page.getByRole("button", { name: "Change location" }).click();
  await page.getByRole("button", { name: "Spec root", exact: true }).click();
  await page.getByRole("button", { name: "Use this folder" }).click();
  releaseSuggestion();
  await expect(page.getByLabel("Spec name", { exact: true })).toHaveValue("Chosen copy");
  await expect(page.locator(".spec-location strong")).toHaveText("Spec root");
  await expect(page.locator(".spec-filename")).toHaveText("File: chosen-copy.spec");
  await page.getByRole("button", { name: "Create Copy", exact: true }).click();
  await expect.poll(() => requests).toBe(1);
  await expect(page.getByRole("button", { name: "Creating…" })).toBeDisabled();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Escape");
  await expect(page.locator(".app-header")).toBeVisible();
  await page.keyboard.press("Control+n");
  await page.keyboard.press("Control+o");
  await expect(page.getByRole("dialog", { name: "Create Copy", exact: true })).toBeVisible();
  releaseCopy();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(requests).toBe(1);
  expect(state.copiedPaths).toEqual(["/home/designer/chosen-copy.spec"]);
});

test("file dialogs fit narrow screens in both themes and retain keyboard focus", async ({ page }, info) => {
  await mockEditorApi(page);
  for (const theme of ["obsidian", "clean"]) {
    await page.goto("/");
    await page.evaluate(themeId => localStorage.setItem("spec2gds:spec-editor:preferences", JSON.stringify({ schema_version: 1, theme_id: themeId })), theme);
    await page.reload();
    for (const width of [390, 1440]) {
      await page.setViewportSize({ width, height: 844 });
      await expect(page.locator(".app-header")).toBeVisible();
  await page.keyboard.press("Control+n");
      const dialog = page.getByRole("dialog", { name: "New Spec", exact: true });
      await page.getByLabel("Spec name", { exact: true }).fill("My registered adder");
      await expect(dialog.getByRole("button", { name: "Create Spec", exact: true })).toBeEnabled();
      const box = (await dialog.boundingBox())!;
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(width);
      await dialog.screenshot({ path: info.outputPath(`new-spec-${theme}-${width}.png`) });
      if (theme === "obsidian" && width === 1440) await dialog.screenshot({ path: info.outputPath("spec-new.jpg"), type: "jpeg", quality: 90 });
      await page.getByText("More options", { exact: true }).click();
      await expect(page.getByLabel("File path", { exact: true })).toHaveValue("/home/designer/my-registered-adder.spec");
      await page.getByText("More options", { exact: true }).click();
      await page.getByRole("button", { name: "Change location" }).click();
      await expect(page.getByLabel("Filter folders")).toBeFocused();
      await page.getByRole("dialog").screenshot({ path: info.outputPath(`choose-location-${theme}-${width}.png`) });
      await page.getByRole("button", { name: "Back", exact: true }).click();
      await expect(page.getByLabel("Spec name", { exact: true })).toBeFocused();
      await page.getByRole("button", { name: "Create Spec", exact: true }).focus();
      await page.keyboard.press("Tab");
      await expect(page.getByRole("button", { name: "Close", exact: true })).toBeFocused();
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
    }
  }
});


test("a late folder response cannot replace a later location choice", async ({ page }) => {
  await mockEditorApi(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/filesystem/directories?*", async route => {
    if (new URL(route.request().url()).searchParams.get("path") === "/home/designer/specifications") await gate;
    return route.fallback();
  });
  await page.goto("/");
  await expect(page.locator(".app-header")).toBeVisible();
  await page.keyboard.press("Control+n");
  await page.getByLabel("Spec name", { exact: true }).fill("Keep the root");
  await page.getByRole("button", { name: "Change location" }).click();
  const response = page.waitForResponse(response => new URL(response.url()).searchParams.get("path") === "/home/designer/specifications");
  await page.getByRole("button", { name: "specifications", exact: true }).click();
  await page.getByRole("button", { name: "Back", exact: true }).click();
  await page.getByRole("button", { name: "Change location" }).click();
  await expect(page.getByRole("button", { name: "Use this folder" })).toBeEnabled();
  release();
  await response;
  await expect(page.getByRole("button", { name: "Spec root", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Use this folder" }).click();
  await expect(page.locator(".spec-location strong")).toHaveText("Spec root");
});

async function openCatalogFixture(page: Page, options: { failResults?: boolean; failDetails?: boolean; conflict?: boolean } = {}) {
  await mockEditorApi(page);
  const components = Array.from({ length: 50 }, (_, index) => ({
    key: index === 0 ? "barrel-shift" : `component-${index}`,
    id: index === 0 ? "barrel_shift" : index === 1 ? "very_long_component_identifier_".repeat(4) : `component_${String(index).padStart(2, "0")}`,
    summary: index === 0 ? "Universal barrel shifter with direction and arithmetic mode controls." : "Reusable Component with a long description that must stay inside the result row without overlapping the selected Component details. ".repeat(3),
    version: "1.0.0", category: index % 2 ? "arithmetic" : "logic", package_sha256: `package-${index}`, functional_status: "reported_pass",
  }));
  const calls = { reviews: [] as any[], imports: [] as any[], lists: [] as URLSearchParams[] };
  await page.route("**/api/catalog/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api/, "");
    if (path === "/catalog/capabilities") return route.fulfill({ json: { categories: ["logic", "arithmetic"] } });
    if (path === "/catalog/components") {
      calls.lists.push(url.searchParams);
      if (options.failResults) return route.fulfill({ status: 503, json: { detail: "Component library is unavailable." } });
      const query = url.searchParams.get("q")?.toLowerCase() ?? "";
      const category = url.searchParams.get("category");
      const items = components.filter(item => `${item.id} ${item.summary}`.toLowerCase().includes(query) && (!category || item.category === category));
      const offset = Number(url.searchParams.get("offset") ?? 0);
      return route.fulfill({ json: { items: items.slice(offset, offset + 25), total: items.length } });
    }
    if (path === "/catalog/imports/preview") {
      const body = route.request().postDataJSON(); calls.reviews.push(body);
      const conflict = options.conflict && !body.renamed_copy;
      return route.fulfill({ json: { can_import: !conflict, reused: false, root: componentRef,
        definitions: [{ source_id: "source-shifter", name: body.renames["source-shifter"] || "Barrel shifter", vlnv: "acme:logic:barrel_shift:1.0", reused: false }],
        conflicts: conflict ? [{ source_id: "source-shifter", name: "Barrel shifter", reason: "A local definition has this name.", suggested_name: "Barrel shifter copy" }] : [],
      } });
    }
    if (path === "/catalog/imports") { calls.imports.push(route.request().postDataJSON()); return route.fulfill({ json: { root: componentRef, reused: false } }); }
    const match = path.match(/^\/catalog\/components\/([^/]+)(?:\/versions\/([^/]+))?$/);
    if (match) {
      if (options.failDetails) return route.fulfill({ status: 503, json: { detail: "Component details are unavailable." } });
      const item = components.find(item => item.key === match[1])!;
      if (!match[2]) return route.fulfill({ json: { versions: [{ ...item, version: "1.0.0" }, { ...item, version: "0.9.0" }] } });
      return route.fulfill({ json: { ...item, version: match[2],
        ports: Array.from({ length: 18 }, (_, index) => ({ name: index === 0 ? "clk_i" : `data_${index}`, direction: index % 2 ? "out" : "in", width: index ? "[(W*ORDER*$clog2(R))-1:0]".repeat(3) : "1" })),
        parameters: [{ name: "W", rtl_type: "int", value: "32", description: "Data width in bits." }, { name: "ORDER", rtl_type: "int", value: "4", description: "Pipeline stage count." }],
        metadata: { summary: "Parameterized shifter", presets: { default: { W: "32" } }, timing: { latency: "1 cycle" }, licence: "Apache-2.0", limitations: ["Use a positive data width."] },
        usage_markdown: "# Usage\nSet W to the required data width.\n".repeat(20),
        evidence: [{ received_at: "2026-11-10", report: { checks: [{ kind: "lint", status: "passed", summary: "Published source passed its recorded lint check." }], tools: { verilator: "5" } } }],
      } });
    }
    return route.fallback();
  });
  await openSample(page);
  await page.locator("#components").getByRole("button", { name: "Options", exact: true }).click();
  await page.getByRole("menuitem", { name: "Import from catalog…", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Component library", exact: true });
  await expect(dialog).toBeVisible();
  return { dialog, calls, options };
}

test("Component library contains long content and keeps its header and action visible", async ({ page }, info) => {
  const { dialog } = await openCatalogFixture(page);
  for (const theme of ["obsidian", "clean"]) {
    await page.evaluate(themeId => {
      localStorage.setItem("spec2gds:spec-editor:preferences", JSON.stringify({ schema_version: 1, theme_id: themeId }));
      document.documentElement.dataset.theme = themeId;
      document.querySelector<HTMLElement>(".app-shell")!.dataset.theme = themeId;
    }, theme);
    for (const width of [390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: width === 1440 ? 470 : 844 });
      if (width < 900 && await dialog.getByRole("button", { name: "Back to results", exact: false }).isVisible()) await dialog.getByRole("button", { name: "Back to results", exact: false }).click();
      const result = dialog.locator(".spec-catalog-result").first();
      await expect(result).toBeEnabled();
      const resultBox = (await result.boundingBox())!;
      const descriptionBox = (await result.locator(".spec-catalog-result-summary").boundingBox())!;
      expect(descriptionBox.x + descriptionBox.width).toBeLessThanOrEqual(resultBox.x + resultBox.width);
      await result.click();
      await expect(dialog.getByRole("heading", { name: "barrel_shift", exact: true })).toBeVisible();
      await expect(dialog.getByRole("button", { name: "Review import", exact: true })).toBeEnabled();
      const contrast = await dialog.evaluate(element => {
        const luminance = (color: string) => {
          const rgb = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map(value => value / 255)
            .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
          return .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2];
        };
        const text = luminance(getComputedStyle(element.querySelector(".spec-catalog-notice")!).color);
        const background = luminance(getComputedStyle(element).backgroundColor);
        const primary = getComputedStyle(element.querySelector(".spec-catalog-primary")!);
        const buttonText = luminance(primary.color), buttonBackground = luminance(primary.backgroundColor);
        return Math.min((Math.max(text, background) + .05) / (Math.min(text, background) + .05),
          (Math.max(buttonText, buttonBackground) + .05) / (Math.min(buttonText, buttonBackground) + .05));
      });
      expect(contrast).toBeGreaterThanOrEqual(4.5);
      const footerBefore = (await dialog.locator(".spec-catalog-footer").boundingBox())!;
      await dialog.locator(".spec-catalog-detail-scroll").evaluate(element => { element.scrollTop = element.scrollHeight; });
      await expect(dialog.getByRole("heading", { name: "Component library", exact: true })).toBeInViewport();
      await expect(dialog.getByRole("button", { name: "Review import", exact: true })).toBeInViewport();
      expect((await dialog.locator(".spec-catalog-footer").boundingBox())!.y).toBe(footerBefore.y);
      const box = (await dialog.boundingBox())!;
      expect(box.x).toBeGreaterThanOrEqual(0); expect(box.y).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(width); expect(box.y + box.height).toBeLessThanOrEqual(width === 1440 ? 470 : 844);
      expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
      await dialog.locator(".spec-catalog-detail-scroll").evaluate(element => { element.scrollTop = 0; });
      await dialog.screenshot({ path: info.outputPath(`component-library-${theme}-${width}.png`) });
    }
  }
});

test("Component library filters, paginates, and preserves results on narrow screens", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { dialog, calls } = await openCatalogFixture(page);
  await expect(dialog.getByLabel("Search Components")).toBeFocused();
  await dialog.getByLabel("Search Components").fill("no-such-component");
  await expect(dialog.getByText("No matching Components", { exact: true })).toBeVisible();
  await dialog.getByLabel("Search Components").fill("");
  await expect(dialog.getByRole("navigation", { name: "Catalog pages" })).toContainText("1–25 of 50");
  await dialog.getByRole("button", { name: "Next", exact: true }).click();
  await expect(dialog.getByRole("navigation", { name: "Catalog pages" })).toContainText("26–50 of 50");
  await dialog.locator(".spec-catalog-results-scroll").evaluate(element => { element.scrollTop = 250; });
  const before = await dialog.locator(".spec-catalog-results-scroll").evaluate(element => element.scrollTop);
  const chosen = dialog.locator(".spec-catalog-result").nth(3);
  await expect(chosen).toBeEnabled();
  await expect(chosen.locator("strong")).toHaveText("component_28");
  await chosen.focus();
  const position = await dialog.locator(".spec-catalog-results-scroll").evaluate(element => element.scrollTop);
  await chosen.press("Enter");
  await expect(dialog.getByRole("heading", { name: "component_28", exact: true })).toBeFocused();
  await dialog.getByRole("button", { name: "Back to results", exact: false }).click();
  await expect(chosen).toBeFocused();
  expect(await dialog.locator(".spec-catalog-results-scroll").evaluate(element => element.scrollTop)).toBe(position);
  expect(before).toBeGreaterThanOrEqual(0);
  await dialog.getByRole("button", { name: "Previous", exact: true }).click();
  const longResult = dialog.locator(".spec-catalog-result").nth(1);
  await expect(longResult).toBeEnabled();
  await expect(longResult.locator("strong")).toContainText("very_long_component_identifier_");
  await longResult.click();
  await expect(dialog.getByRole("button", { name: "Review import", exact: true })).toBeEnabled();
  expect((await dialog.locator(".spec-catalog-detail-scroll").boundingBox())!.height).toBeGreaterThan(100);
  await dialog.getByRole("button", { name: "Back to results", exact: false }).click();
  await dialog.getByRole("button", { name: "Filters", exact: true }).click();
  await dialog.getByRole("combobox", { name: "Category", exact: true }).selectOption("logic");
  await expect(dialog.getByRole("button", { name: "Filters (1)", exact: true })).toBeVisible();
  await expect.poll(() => calls.lists.at(-1)?.get("category")).toBe("logic");
  await dialog.getByRole("button", { name: "Clear filters", exact: true }).click();
  await expect(dialog.getByRole("button", { name: "Filters", exact: true })).toBeVisible();
});

test("Component library reviews conflicts and invalidates import after edits or a version change", async ({ page }) => {
  const { dialog, calls } = await openCatalogFixture(page, { conflict: true });
  await dialog.locator(".spec-catalog-result").first().click();
  await dialog.getByRole("button", { name: "Review import", exact: true }).click();
  await expect(dialog.getByRole("heading", { name: "Import preview", exact: true })).toBeFocused();
  await expect(dialog.getByText(/A local definition has this name/)).toBeVisible();
  await dialog.getByLabel("Import as a renamed copy").check();
  await dialog.getByRole("button", { name: "Review import", exact: true }).click();
  await expect(dialog.getByRole("button", { name: "Import into Spec", exact: true })).toBeEnabled();
  await dialog.getByLabel("Local name for source-shifter").fill("Local shifter");
  await expect(dialog.getByRole("button", { name: "Import into Spec", exact: true })).toHaveCount(0);
  await dialog.getByLabel("Local name for source-shifter").fill("Barrel shifter");
  await expect(dialog.getByRole("button", { name: "Import into Spec", exact: true })).toHaveCount(0);
  await dialog.getByLabel("Local name for source-shifter").fill("Local shifter");
  await dialog.getByRole("button", { name: "Review import", exact: true }).click();
  await dialog.getByRole("combobox", { name: "Version", exact: true }).selectOption("0.9.0");
  await expect(dialog.getByRole("button", { name: "Import into Spec", exact: true })).toHaveCount(0);
  await expect(dialog.getByRole("region", { name: "Import preview", exact: true })).toHaveCount(0);
  await dialog.getByRole("button", { name: "Review import", exact: true }).click();
  await dialog.getByLabel("Import as a renamed copy").check();
  await dialog.getByRole("button", { name: "Review import", exact: true }).click();
  await dialog.getByRole("button", { name: "Import into Spec", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(calls.imports).toHaveLength(1);
  expect(calls.imports[0]).toMatchObject({ version: "0.9.0", renamed_copy: true, expected_source_revision_hash: revision });
});

test("Component library recovers list and detail failures and restores focus on close", async ({ page }) => {
  const { dialog, options } = await openCatalogFixture(page, { failResults: true });
  await expect(dialog.getByRole("alert")).toContainText("Component library is unavailable.");
  options.failResults = false;
  await dialog.getByRole("button", { name: "Retry catalog request", exact: true }).click();
  await expect(dialog.locator(".spec-catalog-result").first()).toBeEnabled();
  options.failDetails = true;
  await dialog.locator(".spec-catalog-result").first().click();
  await expect(dialog.getByRole("alert")).toContainText("Component details are unavailable.");
  options.failDetails = false;
  await dialog.getByRole("button", { name: "Retry Component details", exact: true }).click();
  await expect(dialog.getByRole("button", { name: "Review import", exact: true })).toBeEnabled();
  await dialog.getByRole("button", { name: "Cancel", exact: true }).focus();
  await page.keyboard.press("Tab"); await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "Close Component library", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(page.locator("#components").getByRole("button", { name: "Options", exact: true })).toBeFocused();
});

test("Component library keeps an import pending and prevents duplicate actions", async ({ page }) => {
  const { dialog, calls } = await openCatalogFixture(page);
  await dialog.locator(".spec-catalog-result").first().click();
  await dialog.getByRole("button", { name: "Review import", exact: true }).click();
  await expect(dialog.getByRole("button", { name: "Import into Spec", exact: true })).toBeEnabled();
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let requests = 0;
  await page.route("**/api/catalog/imports**", async route => {
    if (new URL(route.request().url()).pathname === "/api/catalog/imports") { ++requests; await gate; }
    return route.fallback();
  });
  try {
    await dialog.getByRole("button", { name: "Import into Spec", exact: true }).click();
    await expect(dialog.getByRole("button", { name: "Importing…", exact: true })).toBeDisabled();
    await expect(dialog.getByRole("button", { name: "Close Component library", exact: true })).toBeDisabled();
    await expect(dialog.getByLabel("Import as a renamed copy")).toBeDisabled();
    await page.keyboard.press("Enter"); await page.keyboard.press("Escape"); await expect(page.locator(".app-header")).toBeVisible();
  await page.keyboard.press("Control+n");
    await expect(dialog).toBeVisible();
    expect(requests).toBe(1);
  } finally { release(); }
  await expect(dialog).toHaveCount(0);
  expect(calls.imports).toHaveLength(1);
});

for (const status of ["passed", "failed", "unverified", "stale"] as const) {
  test(`side panel: ${status} verification uses a short manual notification`, async ({ page }) => {
    await mockEditorApi(page);
    let verified = false;
    const result = { target: designRef, source_revision_hash: status === "stale" ? "old" : revision,
      status, tool_version: "Verilator fixture", functional_simulation: "unverified",
      diagnostics: status === "failed" ? [{ code: "WIDTH", message: "Width mismatch", blocking: true, file_path: "rtl/top.sv", source_kind: "generated", line: 3 }] : [] };
    await page.route("**/entities/design/design_top/verify*", async route => { verified = true; await route.fulfill({ json: result }); });
    await page.route("**/documents/view*", route => route.fulfill({ json: {
      snapshot: { ...snapshot, verifications: verified ? [result] : [] }, a2ui: batch,
      activity: { executions: [], artifacts: [], proposals: [], assistant_changes: [], pending_review_count: 27 },
      approval_policy: "review", event_cursor: 0, source_revision_hash: revision,
    } }));
    await openSample(page);
    await page.clock.install();
    const design = page.locator("#design-design_top");
    await design.getByRole("button", { name: "Options", exact: true }).click();
    await design.getByRole("menuitem", { name: "Verify Design", exact: true }).click();
    const label = { passed: "Lint passed", failed: "Lint failed", unverified: "Not verified", stale: "out of date" }[status];
    await expect(page.locator(".app-toast")).toContainText(label);
    await expect(page.locator(".utility-sidebar")).toHaveCount(0);
    await expect(design.locator(".spec-verification-details, .spec-validation-badge")).toHaveCount(0);
    await expect(page.locator("#editor-activity-trigger")).toHaveText("Activity27");
    const details = page.locator(".app-toast").getByRole("button", { name: "View details" });
    await details.focus();
    await page.clock.fastForward(6000);
    await expect(page.locator(".app-toast")).toBeVisible();
    await details.click();
    await expect(page.locator(".utility-sidebar")).toContainText(status === "stale" ? "Out of date" : label);
    await expect(page.locator(".spec-paper")).toBeVisible();
    if (status === "failed") await expect(page.locator("#editor-diagnostics-trigger span")).toHaveText("1");
    await page.getByRole("button", { name: "Close side panel" }).click();
    await expect(page.locator("#editor-diagnostics-trigger")).toBeFocused();
    // A second result expires without removing the persistent report or attention count.
    await design.getByRole("button", { name: "Options", exact: true }).click();
    await design.getByRole("menuitem", { name: "Verify Design", exact: true }).click();
    await page.mouse.move(0, 0);
    await expect(page.locator(".app-toast")).toBeVisible();
    await page.clock.fastForward(5100);
    await expect(page.locator(".app-toast")).toHaveCount(0);
    await page.locator("#editor-diagnostics-trigger").click();
    await expect(page.locator(".utility-sidebar")).toContainText(status === "stale" ? "Out of date" : label);
  });
}

test("side panel: responsive dock, keyboard resizing, themes and overlay focus", async ({ page }, testInfo) => {
  await mockEditorApi(page);
  await openSample(page);
  for (const theme of ["clean", "obsidian"]) {
    if (await page.locator("html").getAttribute("data-theme") !== theme) await page.locator(".theme-quick-toggle").click();
    for (const width of [1440, 1280, 1024, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await page.locator("#editor-diagnostics-trigger").click();
      const sidebar = page.locator(".utility-sidebar");
      await expect(sidebar).toBeVisible();
      if (width >= 1280) {
        const resizer = sidebar.getByRole("separator", { name: "Resize side panel" });
        await resizer.focus(); await page.keyboard.press("End");
        await expect(resizer).toHaveAttribute("aria-valuenow", String(Math.min(560, width - 800)));
        expect((await page.locator(".editor-document").boundingBox())!.width).toBeGreaterThanOrEqual(800);
        const box = (await sidebar.boundingBox())!;
        expect(box.x + box.width).toBe(width);
      } else {
        await expect(sidebar).toHaveAttribute("role", "dialog");
        await expect(page.locator("body")).toHaveCSS("overflow", "hidden");
        expect(await page.locator(".editor-document").evaluate(element => (element as HTMLElement).inert)).toBe(true);
        await sidebar.getByRole("button", { name: "Close side panel" }).focus();
        await page.keyboard.press("Tab");
        expect(await sidebar.evaluate(element => element.contains(document.activeElement))).toBe(true);
        if (width === 390) expect((await sidebar.boundingBox())!.width).toBe(390);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: testInfo.outputPath(`panel-${theme}-${width}.png`) });
      await page.keyboard.press("Escape");
      await expect(sidebar).toHaveCount(0);
      await expect(page.locator("#editor-diagnostics-trigger")).toBeFocused();
    }
    await page.setViewportSize({ width: 1440, height: 900 });
  }
});

test("side panel: saved source navigation, duplicate findings and separate Catalog evidence", async ({ page }) => {
  await mockEditorApi(page);
  const diagnostic = { code: "WIDTH", message: "Width mismatch", blocking: true, file_path: "sections/top.sv", source_kind: "section", line: 1, column: 1 };
  const checked = { ...snapshot,
    entity_sections: [{ section_id: "section_sv_design_top", parent: designRef, section_type: "sv", type_version: 1, title: "SystemVerilog", media_type: "text/x-systemverilog", source_path: "sections/top.sv", source_sha256: "hash", content: "logic saved_marker;\n" }],
    section_validation: [{ section_id: "section_sv_design_top", status: "errors", diagnostics: [diagnostic] }],
    verifications: [{ target: designRef, status: "failed", source_revision_hash: revision, tool_version: "fixture", functional_simulation: "unverified", diagnostics: [diagnostic] }],
    catalog_origins: [{ component_key: "published", version: "1", package_sha256: "release", source_vlnv: "vendor:lib:Published:1", root: designRef,
      evidence: [{ evidence_sha256: "evidence", report: { checks: [{ kind: "lint", status: "passed", summary: "Published check" }] } }] }],
  };
  await page.route("**/documents/view*", route => route.fulfill({ json: { snapshot: checked, a2ui: batch,
    activity: { executions: [], artifacts: [], proposals: [], assistant_changes: [] }, approval_policy: "automatic", event_cursor: 0, source_revision_hash: revision } }));
  await openSample(page);
  await expect(page.locator("#editor-diagnostics-trigger span")).toHaveText("1");
  await expect(page.locator(".spec-paper")).not.toContainText("Catalog origin");
  await page.locator("#editor-diagnostics-trigger").click();
  await expect(page.locator(".diagnostic-finding")).toHaveCount(1);
  await page.locator(".diagnostic-finding").getByRole("button", { name: "Go to source" }).click();
  await expect(page.locator(".spec-source-highlight")).toHaveText("logic saved_marker;");
  await page.locator(".utility-sidebar").getByText("Catalog evidence", { exact: true }).click();
  await expect(page.locator(".utility-sidebar")).toContainText("Published release evidence is separate");
  await expect(page.locator(".utility-sidebar")).toContainText("Published check");
  await page.getByRole("button", { name: "Close side panel" }).click();
  const section = page.locator(".spec-sv-section");
  await section.getByRole("button", { name: "Options for SystemVerilog" }).click();
  await section.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await section.locator(".cm-content").fill("logic private_draft;\n");
  await page.locator("#editor-diagnostics-trigger").click();
  await page.locator(".diagnostic-finding").getByRole("button", { name: "Go to source" }).click();
  await expect(page.locator(".spec-source-highlight")).toHaveCount(0);
  await expect(section.locator(".cm-content")).toContainText("private_draft");
});

test("side panel: existing Activity links open the panel beside the bound document", async ({ page }) => {
  await mockEditorApi(page);
  await page.goto(`/?owner_document_key=${snapshot.owner_document_key}&view=activity`);
  await expect(page.locator(".spec-paper")).toBeVisible();
  await expect(page.locator("#utility-tab-activity")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#editor-activity-trigger span")).toHaveCount(0);
  await page.getByText("Review policy", { exact: true }).click();
  await expect(page.locator(".utility-sidebar")).toContainText("Automatic submission");
});

test("side panel: a late job response cannot reopen tools or notify for another Spec", async ({ page }) => {
  await mockEditorApi(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let launched = false;
  await page.route("**/activities/rtl.generate/executions*", async route => {
    launched = true; await gate;
    await route.fulfill({ json: { execution_id: "old-job", status: "queued" } });
  });
  const other = { ...snapshot, owner_document_key: "another-spec", narrative: { title: "Other Spec", blocks: [] }, verifications: [] };
  await page.route("**/documents/open", async route => {
    if (route.request().postDataJSON().path.endsWith("other.spec")) return route.fulfill({ json: other });
    return route.fallback();
  });
  await page.route("**/documents/view*", route => {
    const selected = new URL(route.request().url()).searchParams.get("owner_document_key") === other.owner_document_key ? other : snapshot;
    const projection = structuredClone(batch);
    projection.messages[1].updateComponents.components.find((item: any) => item.component === "SpecDocument")!.title = selected.narrative.title;
    return route.fulfill({ json: { snapshot: selected, a2ui: projection,
      activity: { executions: [], artifacts: [], proposals: [], assistant_changes: [], pending_review_count: 0 },
      approval_policy: "automatic", event_cursor: 0, source_revision_hash: revision } });
  });
  await openSample(page);
  await page.locator("#editor-diagnostics-trigger").click();
  const design = page.locator("#design-design_top");
  await design.getByRole("button", { name: "Options", exact: true }).click();
  await design.getByRole("menuitem", { name: /^Generate RTL/ }).click();
  await expect.poll(() => launched).toBe(true);
  await expect(page.locator("#utility-tab-diagnostics")).toHaveAttribute("aria-selected", "true");
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /Open Spec/ }).click();
  await page.getByText("More options", { exact: true }).click();
  await page.getByLabel("File path", { exact: true }).fill("/home/designer/other.spec");
  await page.getByRole("button", { name: "Open Spec", exact: true }).click();
  await expect(page.locator(".spec-paper h1")).toHaveText("Other Spec");
  const completed = page.waitForResponse(response => response.url().includes("activities/rtl.generate/executions"));
  release(); await completed;
  await expect(page.locator(".utility-sidebar")).toHaveCount(0);
  await expect(page.locator(".app-toast")).toHaveCount(0);
  await expect(page.locator("#editor-diagnostics-trigger span")).toHaveCount(0);
});

test("side panel: pointer resizing persists and scrollbar space preserves the document width", async ({ page }) => {
  await mockEditorApi(page);
  await openSample(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.addStyleTag({ content: "html { scrollbar-gutter: stable; }" });
  await page.locator("#editor-diagnostics-trigger").click();
  const separator = page.getByRole("separator", { name: "Resize side panel" });
  await separator.focus(); await page.keyboard.press("End");
  const maximum = Math.min(560, await page.locator(".app-shell").evaluate(element => element.clientWidth) - 800);
  await expect(separator).toHaveAttribute("aria-valuenow", String(maximum));
  expect((await page.locator(".editor-document").boundingBox())!.width).toBeGreaterThanOrEqual(800);
  const handle = (await separator.boundingBox())!;
  await page.mouse.move(handle.x + handle.width / 2, handle.y + 100);
  await page.mouse.down(); await page.mouse.move(handle.x + handle.width / 2 + 40, handle.y + 100); await page.mouse.up();
  await expect(separator).toHaveAttribute("aria-valuenow", String(maximum - 40));
  await page.getByRole("button", { name: "Close side panel" }).click();
  await page.locator("#editor-diagnostics-trigger").click();
  await expect(separator).toHaveAttribute("aria-valuenow", String(maximum - 40));
});

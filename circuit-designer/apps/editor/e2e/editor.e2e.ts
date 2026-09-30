import { expect, test, type Page, type Route } from "@playwright/test";
import { readFile } from "node:fs/promises";

const documentId = "editor_test";
const revision = "sha256:editor-test";

const designRef = { document_id: documentId, entity_id: "design_top", entity_kind: "design" };
const componentRef = { document_id: documentId, entity_id: "component_timer", entity_kind: "component" };
const compositeRef = { document_id: documentId, entity_id: "component_subsystem", entity_kind: "component" };
const busRef = { document_id: documentId, entity_id: "bus_control", entity_kind: "bus_definition" };

const snapshot = {
  owner_document_key: "package-editor-test",
  schema_version: "spec2gds.snapshot.v2",
  document_id: documentId,
  source_revision_hash: revision,
  components: [
    { ref: componentRef, vlnv: "acme:blocks:Timer:1.0" },
    { ref: compositeRef, vlnv: "acme:blocks:Subsystem:1.0" },
  ],
  designs: [{ ref: designRef, vlnv: "acme:systems:Processor:1.0" }],
  entry_designs: [{ ref: designRef, vlnv: "acme:systems:Processor:1.0" }],
  bus_definitions: [],
  abstraction_definitions: [],
  component_compositions: [{ component: compositeRef, internal_design: designRef }],
  narrative: { title: "Editor Test", blocks: [] },
  diagnostics: { source: [], artifacts: [] },
  entity_sections: [],
  section_validation: [],
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
          section("designs", "Designs", 1, null),
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
              owner: designRef,
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
            children: ["table-component-component_timer-ports"],
          }),
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
              { section_id: "designs", title: "Designs", level: 1 },
              { section_id: "design-design_top", title: "Processor", level: 2 },
              { section_id: "components", title: "Components", level: 1 },
              { section_id: "component-component_timer", title: "Timer", level: 2 },
              { section_id: "component-component_subsystem", title: "Subsystem", level: 2 },
              { section_id: "bus-definition-bus_control", title: "Control Bus", level: 2 },
            ],
            children: [
              "section-overview",
              "section-designs",
              "section-design-design_top",
              "section-components",
              "section-component-component_timer",
              "section-component-component_subsystem",
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
  openedPaths: string[];
  transactions: Array<{ expected_source_revision_hash: string; operations: object[] }>;
  currentRevision: string;
  currentTitle: string;
  staleNextTransaction: boolean;
};

async function mockEditorApi(page: Page, options: { topologyUnavailable?: boolean } = {}): Promise<ApiState> {
  const state: ApiState = {
    activityExecutions: [],
    circuits: [],
    createdPaths: [],
    createdTitles: [],
    openedPaths: [],
    transactions: [],
    currentRevision: revision,
    currentTitle: snapshot.narrative.title,
    staleNextTransaction: false,
  };
  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const requestUrl = new URL(request.url());
    const path = requestUrl.pathname.replace(/^\/api/, "");
    const json = (value: unknown) => route.fulfill({ json: value, status: 200 });

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
        parent: requestedPath === "/" ? null : requestedPath.split("/").slice(0, -1).join("/") || "/",
        home: "/home/designer",
        separator: "/",
        roots: ["/"],
        directories: requestedPath === "/home/designer"
          ? [{ name: "specifications", path: "/home/designer/specifications" }]
          : [],
        specifications: requestedPath === "/home/designer/specifications"
          ? [{ name: "existing.spec", path: "/home/designer/specifications/existing.spec" }]
          : [],
      });
    }

    if (path === "/documents/create" || path === "/documents/open") {
      const body = request.postDataJSON() as { path: string; title?: string };
      (path.endsWith("create") ? state.createdPaths : state.openedPaths).push(body.path);
      if (path.endsWith("create")) state.createdTitles.push(body.title ?? "");
      if (body.path === "/tmp/missing.spec") {
        return route.fulfill({ json: { detail: "Specification package was not found." }, status: 422 });
      }
      state.currentRevision = revision;
      state.currentTitle = path.endsWith("create") ? body.title ?? "" : snapshot.narrative.title;
      return json(path.endsWith("create")
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
      components.find(component => component.component === "SpecDocument").title = state.currentTitle;
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
      if (state.transactions.length) {
        if (liveView.block.options.circuit_document) {
          liveView.block.options.circuit_document.design.instances[0].label = "producer_updated";
        }
        currentBatch.source_revision_hash = state.currentRevision;
      }
      currentBatch.source_revision_hash = state.currentRevision;
      return json(path === "/documents/view" ? {
        snapshot: { ...snapshot, source_revision_hash: state.currentRevision, narrative: { ...snapshot.narrative, title: state.currentTitle } },
        a2ui: currentBatch, activity: { executions: state.activityExecutions, artifacts: [], proposals: [], assistant_changes: [] },
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
    if (path === "/artifacts") return json({ artifacts: [] });
    if (path === "/proposals") return json({ proposals: [] });
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
      const execution = {
        execution_type: "activity",
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

async function openSample(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /Open Specification/ }).click();
  await page.getByLabel("Server-local package path").fill("/tmp/editor-test.spec");
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await expect(page.locator(".spec-paper")).toBeVisible();
}

test("creates, opens, refreshes, and exposes truthful File menu state", async ({ page }) => {
  const state = await mockEditorApi(page);
  await page.goto("/");

  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /New Specification/ }).click();
  await expect(page.getByText("visible to the server running spec2gds")).toBeVisible();
  await page.getByLabel("Specification name").fill("New editor specification");
  await page.getByRole("button", { name: "Browse…" }).click();
  const specificationsFolder = page.getByRole("button", { name: /specifications/ });
  await specificationsFolder.dblclick();
  await expect(page.getByText("/home/designer/specifications", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /New folder/ }).click();
  await page.getByLabel("New folder name").fill("Project Alpha");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByText("/home/designer/specifications/Project Alpha", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Select folder" }).click();
  await expect(page.getByLabel("Server-local package path"))
    .toHaveValue("/home/designer/specifications/Project Alpha/New editor specification.spec");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByText("New editor specification", { exact: true })).toBeVisible();
  expect(state.createdPaths).toEqual([
    "/home/designer/specifications/Project Alpha/New editor specification.spec",
  ]);
  expect(state.createdTitles).toEqual(["New editor specification"]);

  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: /Save Automatic/ })).toBeDisabled();
  await page.getByRole("menuitem", { name: "Refresh From Disk" }).click();
  await expect.poll(() => state.openedPaths).toEqual([
    "/home/designer/specifications/Project Alpha/New editor specification.spec",
  ]);

  await page.keyboard.press("Control+O");
  await expect(page.getByLabel("Server-local package path"))
    .toHaveValue("/home/designer/specifications/Project Alpha/New editor specification.spec");
  await page.getByRole("button", { name: "Browse…" }).click();
  await page.getByRole("button", { name: "Home" }).click();
  await page.getByRole("button", { name: /specifications/ }).dblclick();
  await page.getByRole("button", { name: /existing\.spec/ }).click();
  await page.getByRole("button", { name: "Select specification" }).click();
  await expect(page.getByLabel("Server-local package path"))
    .toHaveValue("/home/designer/specifications/existing.spec");
  await page.getByLabel("Server-local package path").fill("/tmp/missing.spec");
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Specification package was not found");
  await expect(page.getByRole("dialog", { name: "Open specification" })).toBeVisible();
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

  await page.getByRole("button", { name: /AI Assistant/ }).click();
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
  await timer.locator(".spec-options-trigger").click();
  await page.getByRole("menuitem", { name: "Add section → SystemVerilog" }).click();
  const newEditor = timer.locator(".cm-content");
  await expect(newEditor).toBeVisible();
  await newEditor.fill("assign irq = 1'b0;\n");
  await timer.getByRole("button", { name: "Add section", exact: true }).click();
  await expect.poll(() => state.transactions.length).toBe(1);
  expect(state.transactions[0]?.operations).toEqual([{
    type: "upsert_entity_section",
    owner: componentRef,
    section_type: "sv",
    type_version: 1,
    payload: { content: "assign irq = 1'b0;\n" },
  }]);

  const design = page.locator("#design-design_top");
  await design.getByRole("button", { name: "Edit", exact: true }).click();
  const savedEditor = design.locator(".cm-content");
  await savedEditor.fill("logic edited_marker;\n");
  await design.getByRole("button", { name: "Save", exact: true }).click();
  await expect.poll(() => state.transactions.length).toBe(2);
  expect(state.transactions[1]?.operations).toEqual([{
    type: "upsert_entity_section",
    owner: designRef,
    section_type: "sv",
    type_version: 1,
    section_id: "section_sv_design_top",
    payload: { content: "logic edited_marker;\n" },
  }]);

  page.once("dialog", (dialog) => dialog.accept());
  await design.getByRole("button", { name: "Delete", exact: true }).click();
  await expect.poll(() => state.transactions.length).toBe(3);
  expect(state.transactions[2]?.operations).toEqual([{
    type: "delete_entity_section",
    owner: designRef,
    section_type: "sv",
    section_id: "section_sv_design_top",
  }]);
});

test("edits the persisted specification name without changing the stable identity", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);

  await page.locator(".spec-cover").getByRole("button", { name: "Edit name" }).click();
  await page.getByLabel("Specification name").fill("Timer Platform Specification");
  await page.getByRole("button", { name: "Save name" }).click();
  await expect.poll(() => state.transactions.length).toBe(1);
  expect(state.transactions[0]?.operations).toEqual([
    { type: "set_document_title", title: "Timer Platform Specification" },
  ]);
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

  await card.getByRole("button", { name: "Open Circuit Designer" }).click();
  await expect.poll(() => state.circuits).toEqual([{ entity_kind: "design", entity_id: "design_top" }]);

  const firstImageUrl = await image.getAttribute("src");
  const expand = card.getByRole("button", { name: "Expand" });
  await expand.click();
  const dialog = page.getByRole("dialog", { name: "Circuit topology" });
  await expect(dialog.getByRole("img", { name: "Circuit topology circuit diagram" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Close circuit preview" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(expand).toBeFocused();

  const downloadPromise = page.waitForEvent("download");
  await card.getByRole("link", { name: "Download SVG" }).click();
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

  await page.locator(".spec-cover").getByRole("button", { name: "Edit name" }).click();
  await page.getByLabel("Specification name").fill("Updated topology source");
  await page.getByRole("button", { name: "Save name" }).click();
  await expect.poll(async () => image.getAttribute("src")).not.toBe(firstImageUrl);
});

test("keeps design tables available when a circuit preview is unsafe", async ({ page }) => {
  await mockEditorApi(page, { topologyUnavailable: true });
  await openSample(page);
  const design = page.locator("#design-design_top");

  await expect(design.getByText("Preview unavailable: connected structured endpoint cannot be represented")).toBeVisible();
  await expect(design.getByRole("region", { name: "Component instances" })).toBeVisible();
  await expect(design.getByRole("img", { name: "Circuit topology circuit diagram" })).toHaveCount(0);
});

test("adds an available top-level component instance to the entry design", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  const design = page.locator("#design-design_top");
  const options = design.getByRole("button", { name: "Options" });

  await options.click();
  await design.getByRole("menuitem", { name: "Add component instance…" }).click();
  await design.getByLabel("Instance name").fill("timer0");
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
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: "http://127.0.0.1:6015" });
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
  await expect(page.getByRole("menuitem", { name: "Undo Coming later" })).toBeDisabled();
  await expect(page.getByRole("menuitem", { name: /Cut Use keyboard in fields/ })).toBeDisabled();
  await expect(page.getByRole("menuitem", { name: "Find Coming soon" })).toBeDisabled();
  await page.getByRole("menuitem", { name: "Copy", exact: true }).click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe("Editor Test");

  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Select All" }).click();
  await expect.poll(() => page.evaluate(() => window.getSelection()?.toString() ?? "")).toContain("Processor");
});

test("launches circuits and queues a compatible design Activity", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);

  await page.getByRole("menuitem", { name: "Circuit", exact: true }).click();
  const circuitMenu = page.getByRole("menu", { name: "Circuit" });
  await expect(circuitMenu.getByText("Designs", { exact: true })).toBeVisible();
  await expect(circuitMenu.getByText("Components", { exact: true })).toBeVisible();
  await page.getByRole("menuitem", { name: /Processor Entry/ }).click();
  await expect.poll(() => state.circuits).toEqual([{ entity_kind: "design", entity_id: "design_top" }]);

  const overview = page.locator("#overview");
  await expect(overview.getByText("Document ID", { exact: true })).toHaveCount(0);
  await expect(overview.getByText("Source revision", { exact: true })).toHaveCount(0);
  await overview.getByRole("button", { name: "Options" }).click();
  await expect(overview.getByRole("menuitem", { name: /Launch activity/ })).toHaveCount(0);
  await expect(overview.getByRole("menuitem", { name: "Open circuit" })).toHaveCount(0);
  await expect(overview.getByRole("menuitem", { name: /More actions/ })).toHaveCount(0);

  const design = page.locator("#design-design_top");
  await design.getByRole("button", { name: "Options" }).click();
  await design.getByRole("menuitem", { name: "Launch activity…" }).click();
  const activityDialog = page.getByRole("dialog", { name: "Launch activity" });
  await expect(activityDialog.getByText("Generate RTL", { exact: true })).toBeVisible();
  await expect(activityDialog.getByText(/dut.clk is unconnected/)).toBeVisible();
  await activityDialog.getByRole("button", { name: "Run" }).click();
  await expect.poll(() => state.activityExecutions.length).toBe(1);
  await expect(page.getByText("rtl.generate", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Document", exact: true }).click();

  await design.getByRole("button", { name: "Options" }).click();
  await design.getByRole("menuitem", { name: /More actions/ }).click();
  const actionDialog = page.getByRole("dialog", { name: /Actions for design_top/ });
  await expect(actionDialog).toBeVisible();
  await expect(actionDialog.getByText("Explore with AI Assistant", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
  await design.getByRole("button", { name: "Options" }).click();
  await design.getByRole("menuitem", { name: "Open circuit" }).click();
  await expect.poll(() => state.circuits.length).toBe(2);

  const bus = page.locator("#bus-definition-bus_control");
  await bus.getByRole("button", { name: "Options" }).click();
  await expect(bus.getByRole("menuitem", { name: "Open circuit" })).toHaveCount(0);
  await expect(bus.getByRole("menuitem", { name: /More actions/ })).toBeVisible();
});

test("creates entities and edits all three port families inline", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);

  const composite = page.locator("#component-component_subsystem");
  await composite.getByRole("button", { name: "Options" }).click();
  await expect(composite.getByRole("menuitem", { name: /Add wire port.*Composite/ })).toBeDisabled();
  await expect(composite.getByRole("menuitem", { name: /Add transactional port.*Composite/ })).toBeDisabled();
  await expect(composite.getByRole("menuitem", { name: /Add structured port.*Composite/ })).toBeDisabled();

  const components = page.locator("#components");
  await components.getByRole("button", { name: "Options" }).click();
  await components.getByRole("menuitem", { name: "Add component…" }).click();
  await page.getByLabel("Component name").fill("counter");
  await page.getByRole("button", { name: "Create component" }).click();
  await expect.poll(() => state.transactions.length).toBe(1);
  expect(state.transactions[0]?.operations).toEqual([
    { type: "create_entity", kind: "component", name: "counter" },
  ]);

  const component = page.locator("#component-component_timer");
  await expect(component.getByText("Counts time", { exact: true })).toHaveClass(/spec-section-text/);
  await expect(component.getByText("acme:blocks:Timer:1.0", { exact: true })).toHaveCount(0);
  await expect(component.locator(".spec-ports-table")).toHaveCount(1);
  await expect(component.locator(".spec-port-row")).toHaveCount(3);
  await expect(component.locator(".spec-port-row", { hasText: "irq" })).toBeVisible();
  const transactionalRow = component.locator(".spec-port-row", { hasText: "request_stream" });
  await expect(transactionalRow).toContainText("Transactional");
  await expect(transactionalRow).toContainText("Request stream");
  await expect(transactionalRow).toContainText("provides");
  await expect(transactionalRow).toContainText("timer_service");
  await expect(transactionalRow).toContainText("DATA_WIDTH");
  await expect(transactionalRow).toContainText("Streams timer requests");
  const structuredRow = component.locator(".spec-port-row", { hasText: "status_bundle" });
  await expect(structuredRow).toContainText("Structured");
  await expect(structuredRow).toContainText("Status bundle");
  await expect(structuredRow).toContainText("Packed struct");
  await expect(structuredRow).toContainText("Packed status fields");
  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Edit text…" }).click();
  await component.getByLabel("Specification text").fill("A programmable timer.");
  await component.getByRole("button", { name: "Save changes" }).click();
  await expect.poll(() => state.transactions.length).toBe(2);
  expect(state.transactions[1]?.operations[0]).toEqual({
    type: "set_entity_metadata",
    entity: componentRef,
    display_name: "",
    short_description: "",
    description: "A programmable timer.",
  });

  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Add wire port…" }).click();
  const draftCard = component.locator(".spec-port-editor");
  await draftCard.getByLabel("Port name").fill("count");
  await draftCard.getByLabel("Display name").fill("Current count");
  await draftCard.getByLabel("Direction").selectOption("out");
  await draftCard.getByLabel("Range").fill("31:0");
  await draftCard.getByLabel("Description").fill("Current counter value");
  await draftCard.getByRole("button", { name: "Save" }).click();
  await expect.poll(() => state.transactions.length).toBe(3);
  expect(state.transactions[2]?.operations[0]).toEqual({
    type: "add_component_port",
    component: componentRef,
    port: {
      name: "count",
      family: "wire",
      display_name: "Current count",
      direction: "out",
      range: "31:0",
      description: "Current counter value",
    },
  });

  const existingCard = component.locator(".spec-port-row", { hasText: "irq" });
  await existingCard.getByRole("button", { name: "Edit" }).click();
  const editCard = component.locator(".spec-port-editor");
  await expect(editCard.getByLabel("Port name")).toHaveCount(0);
  await editCard.getByLabel("Display name").fill("Interrupt request line");
  await editCard.getByLabel("Direction").selectOption("inout");
  await editCard.getByLabel("Description").fill("Bidirectional interrupt");
  await editCard.getByRole("button", { name: "Save" }).click();
  await expect.poll(() => state.transactions.length).toBe(4);
  expect(state.transactions[3]?.operations[0]).toEqual({
    type: "update_component_port",
    component: componentRef,
    name: "irq",
    port: {
      family: "wire",
      display_name: "Interrupt request line",
      direction: "inout",
      range: null,
      description: "Bidirectional interrupt",
    },
  });

  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Add transactional port…" }).click();
  const transactionalDraft = component.locator(".spec-port-editor");
  await transactionalDraft.getByLabel("Port name").fill("service");
  await transactionalDraft.getByLabel("Display name").fill("Timer service");
  await transactionalDraft.getByLabel("Initiative").selectOption("provides");
  await transactionalDraft.getByLabel("Kind").selectOption("custom");
  await transactionalDraft.getByLabel("Custom kind name").fill("timer_service");
  await transactionalDraft.getByLabel("Bus width").fill("DATA_WIDTH");
  await transactionalDraft.getByLabel("Description").fill("Transaction-level timer service");
  await transactionalDraft.getByRole("button", { name: "Save" }).click();
  await expect.poll(() => state.transactions.length).toBe(5);
  expect(state.transactions[4]?.operations[0]).toEqual({
    type: "add_component_port",
    component: componentRef,
    port: {
      name: "service",
      family: "transactional",
      display_name: "Timer service",
      initiative: "provides",
      kind: "custom",
      custom_kind: "timer_service",
      bus_width: "DATA_WIDTH",
      description: "Transaction-level timer service",
    },
  });

  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Add structured port…" }).click();
  const structuredDraft = component.locator(".spec-port-editor");
  await structuredDraft.getByLabel("Port name").fill("response");
  await structuredDraft.getByLabel("Display name").fill("Response bundle");
  await structuredDraft.getByLabel("Direction").selectOption("out");
  await expect(structuredDraft).toContainText("Packed struct");
  await structuredDraft.getByLabel("Description").fill("Packed response fields");
  await structuredDraft.getByRole("button", { name: "Save" }).click();
  await expect.poll(() => state.transactions.length).toBe(6);
  expect(state.transactions[5]?.operations[0]).toEqual({
    type: "add_component_port",
    component: componentRef,
    port: {
      name: "response",
      family: "structured",
      display_name: "Response bundle",
      direction: "out",
      description: "Packed response fields",
    },
  });
});

test("validates port drafts, enforces one active editor, and restores focus", async ({ page }) => {
  await mockEditorApi(page);
  await openSample(page);
  const component = page.locator("#component-component_timer");
  const options = component.getByRole("button", { name: "Options" });

  await options.click();
  await component.getByRole("menuitem", { name: "Add wire port…" }).click();
  const draft = component.locator(".spec-port-editor");
  await draft.getByLabel("Port name").fill("invalid_range");
  await draft.getByLabel("Range").fill("31::0");
  await draft.getByRole("button", { name: "Save" }).click();
  await expect(draft.getByRole("alert")).toContainText("left:right expression pair");

  await component.locator(".spec-port-row", { hasText: "irq" }).getByRole("button", { name: "Edit" }).click();
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
  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Edit text…" }).click();
  await component.getByLabel("Specification text").fill("Keep this draft after refresh.");
  state.staleNextTransaction = true;
  await component.getByRole("button", { name: "Save changes" }).click();

  await expect(component.getByLabel("Specification text")).toHaveValue("Keep this draft after refresh.");
  await expect(component.getByRole("alert")).toContainText("preserved draft");
  await page.getByRole("button", { name: "Use reviewed revision for next save" }).click();
  await component.getByRole("button", { name: "Save changes" }).click();
  await expect.poll(() => state.transactions.length).toBe(2);
  expect(state.transactions[1]?.expected_source_revision_hash).toBe("sha256:external-change");
});

test("offers Help content and remains usable at a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 560, height: 760 });
  await mockEditorApi(page);
  await openSample(page);

  await page.getByRole("menuitem", { name: "Help", exact: true }).click();
  await page.getByRole("menuitem", { name: "Getting Started" }).click();
  await expect(page.getByRole("dialog", { name: "Getting started" })).toContainText("persisted automatically");
  await page.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("menuitem", { name: "File", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Document", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

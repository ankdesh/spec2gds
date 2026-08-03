import { expect, test, type Page, type Route } from "@playwright/test";

const documentId = "editor_test";
const revision = "sha256:editor-test";

const designRef = { document_id: documentId, entity_id: "design_top", entity_kind: "design" };
const componentRef = { document_id: documentId, entity_id: "component_timer", entity_kind: "component" };
const compositeRef = { document_id: documentId, entity_id: "component_subsystem", entity_kind: "component" };
const busRef = { document_id: documentId, entity_id: "bus_control", entity_kind: "bus_definition" };

const snapshot = {
  schema_version: "1.0",
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
  narrative: { blocks: [] },
  diagnostics: { source: [], artifacts: [] },
};

function section(
  id: string,
  title: string,
  level: number,
  entityRef: object | null,
  options: { facts?: object[]; tables?: object[]; children?: string[] } = {},
) {
  return {
    id: `section-${id}`,
    component: "SpecSection",
    section: {
      section_id: id,
      title,
      level,
      eyebrow: level === 1 ? "Document section" : "Hardware entity",
      entity_ref: entityRef,
      facts: options.facts ?? [],
      tables: options.tables ?? [],
      narrative: [],
    },
    children: options.children ?? [],
  };
}

function cell(value: string, schemaPath: string) {
  return { kind: "text", value, presence: value ? "explicit" : "absent", schema_path: schemaPath, reference_anchor: "" };
}

const portTable = {
  table_id: "component-component_timer-ports",
  kind: "component_ports",
  title: "Ports",
  columns: [
    { key: "name", label: "Name", schema_path: "/model/ports/port/name" },
    { key: "style", label: "Style", schema_path: "/model/ports/port/wire" },
    { key: "direction", label: "Direction / initiative", schema_path: "/model/ports/port/wire/direction" },
    { key: "left", label: "Left", schema_path: "/model/ports/port/wire/vectors/vector/left" },
    { key: "right", label: "Right", schema_path: "/model/ports/port/wire/vectors/vector/right" },
    { key: "width", label: "Bus width", schema_path: "/model/ports/port/transactional/busWidth" },
    { key: "qualifier", label: "Qualifier", schema_path: "/model/ports/port/wire/qualifier" },
    { key: "description", label: "Description", schema_path: "/model/ports/port/description" },
  ],
  rows: [{
    row_id: "port-irq",
    cells: {
      name: cell("irq", "/model/ports/port/name"),
      style: cell("wire", "/model/ports/port/wire"),
      direction: cell("out", "/model/ports/port/wire/direction"),
      left: cell("", "/model/ports/port/wire/vectors/vector/left"),
      right: cell("", "/model/ports/port/wire/vectors/vector/right"),
      width: cell("", "/model/ports/port/transactional/busWidth"),
      qualifier: cell("", "/model/ports/port/wire/qualifier"),
      description: cell("Interrupt", "/model/ports/port/description"),
    },
  }],
};

const componentFacts = [
  { label: "VLNV", value: "acme:blocks:Timer:1.0", schema_path: "/vendor | /library | /name | /version", reference_anchor: "" },
  { label: "Name", value: "Timer", schema_path: "/name", reference_anchor: "" },
  { label: "Display name", value: "", schema_path: "/displayName", reference_anchor: "" },
  { label: "Short description", value: "", schema_path: "/shortDescription", reference_anchor: "" },
  { label: "Description", value: "Counts time", schema_path: "/description", reference_anchor: "" },
];

const compositePortTable = {
  ...portTable,
  table_id: "component-component_subsystem-ports",
  rows: [],
};

const batch = {
  protocol_version: "v0.9",
  catalog_id: "urn:spec2gds:a2ui:document:v1",
  surface_id: "spec-document-editor-test",
  source_revision_hash: revision,
  messages: [
    {
      version: "v0.9",
      createSurface: {
        surfaceId: "spec-document-editor-test",
        catalogId: "urn:spec2gds:a2ui:document:v1",
      },
    },
    {
      version: "v0.9",
      updateComponents: {
        surfaceId: "spec-document-editor-test",
        components: [
          section("overview", "Overview", 1, null),
          section("designs", "Designs", 1, null),
          section("design-design_top", "Processor", 2, designRef),
          section("components", "Components", 1, null),
          section("component-component_timer", "Timer", 2, componentRef, {
            facts: componentFacts,
            tables: [portTable],
            children: ["table-component-component_timer-ports"],
          }),
          {
            id: "table-component-component_timer-ports",
            component: "SpecTable",
            table: portTable,
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
  circuits: Array<{ entity_kind: string; entity_id: string }>;
  createdPaths: string[];
  openedPaths: string[];
  transactions: Array<{ expected_source_revision_hash: string; operations: object[] }>;
  currentRevision: string;
  staleNextTransaction: boolean;
};

async function mockEditorApi(page: Page): Promise<ApiState> {
  const state: ApiState = {
    circuits: [],
    createdPaths: [],
    openedPaths: [],
    transactions: [],
    currentRevision: revision,
    staleNextTransaction: false,
  };
  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^\/api/, "");
    const json = (value: unknown) => route.fulfill({ json: value, status: 200 });

    if (path === "/documents/create" || path === "/documents/open") {
      const body = request.postDataJSON() as { path: string };
      (path.endsWith("create") ? state.createdPaths : state.openedPaths).push(body.path);
      if (body.path === "/tmp/missing.spec") {
        return route.fulfill({ json: { detail: "Specification package was not found." }, status: 422 });
      }
      state.currentRevision = revision;
      return json(snapshot);
    }
    if (path === "/documents/snapshot") {
      return json({ ...snapshot, source_revision_hash: state.currentRevision });
    }
    if (path === "/documents/a2ui") return json(batch);
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
    if (path === "/executions") return json({ executions: [] });
    if (path === "/artifacts") return json({ artifacts: [] });
    if (path === "/proposals") return json({ proposals: [] });
    if (path === "/assistant/changes") return json({ assistant_changes: [] });
    if (path === "/circuit-designer/launch") {
      const body = request.postDataJSON() as { entity_kind: string; entity_id: string };
      state.circuits.push(body);
      return json({
        document_id: "circuit-test",
        entity_id: body.entity_id,
        entity_kind: body.entity_kind,
        editor_url: "http://127.0.0.1:4180/?document_id=circuit-test",
        reused_session: false,
        omitted_bus_items: [],
      });
    }
    if (/^\/entities\/[^/]+\/[^/]+\/actions$/.test(path)) {
      return json({
        actions: [{
          action_id: "reference.snapshot_summary",
          title: "Snapshot summary",
          version: "1.0",
          produced_artifact_roles: ["summary"],
        }],
      });
    }
    if (path === "/events") {
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
  await page.getByLabel("Server-local package path").fill("/tmp/new-editor.spec");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByText("new-editor.spec", { exact: true })).toBeVisible();
  expect(state.createdPaths).toEqual(["/tmp/new-editor.spec"]);

  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: /Save Automatic/ })).toBeDisabled();
  await page.getByRole("menuitem", { name: "Refresh From Disk" }).click();
  await expect.poll(() => state.openedPaths).toEqual(["/tmp/new-editor.spec"]);

  await page.keyboard.press("Control+O");
  await expect(page.getByLabel("Server-local package path")).toHaveValue("/tmp/new-editor.spec");
  await page.getByLabel("Server-local package path").fill("/tmp/missing.spec");
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Specification package was not found");
  await expect(page.getByRole("dialog", { name: "Open specification" })).toBeVisible();
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

test("keeps Edit state-aware and provides working Copy and Select All", async ({ context, page }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: "http://127.0.0.1:4190" });
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

test("launches grouped and section circuits while preserving entity actions", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);

  await page.getByRole("menuitem", { name: "Circuit", exact: true }).click();
  await expect(page.getByText("Designs", { exact: true })).toBeVisible();
  await expect(page.getByText("Components", { exact: true })).toBeVisible();
  await page.getByRole("menuitem", { name: /Processor Entry/ }).click();
  await expect.poll(() => state.circuits).toEqual([{ entity_kind: "design", entity_id: "design_top" }]);

  const overview = page.locator("#overview");
  await overview.getByRole("button", { name: "Options" }).click();
  await expect(overview.getByRole("menuitem", { name: /Launch activity Coming soon/ })).toBeDisabled();
  await expect(overview.getByRole("menuitem", { name: "Open circuit" })).toHaveCount(0);
  await expect(overview.getByRole("menuitem", { name: /More actions/ })).toHaveCount(0);

  const design = page.locator("#design-design_top");
  await design.getByRole("button", { name: "Options" }).click();
  await design.getByRole("menuitem", { name: /More actions/ }).click();
  await expect(page.getByRole("dialog", { name: /Actions for design_top/ })).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
  await design.getByRole("button", { name: "Options" }).click();
  await design.getByRole("menuitem", { name: "Open circuit" }).click();
  await expect.poll(() => state.circuits.length).toBe(2);

  const bus = page.locator("#bus-definition-bus_control");
  await bus.getByRole("button", { name: "Options" }).click();
  await expect(bus.getByRole("menuitem", { name: "Open circuit" })).toHaveCount(0);
  await expect(bus.getByRole("menuitem", { name: /More actions/ })).toBeVisible();
});

test("creates entities and edits metadata and physical ports inline", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);

  const composite = page.locator("#component-component_subsystem");
  await composite.getByRole("button", { name: "Options" }).click();
  await expect(composite.getByRole("menuitem", { name: /Add port.*Composite/ })).toBeDisabled();

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
  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Edit details…" }).click();
  await component.getByLabel("Display name").fill("Friendly timer");
  await component.getByLabel("Short description").fill("Counts cycles");
  await component.getByLabel("Description").fill("A programmable timer.");
  await component.getByRole("button", { name: "Save changes" }).click();
  await expect.poll(() => state.transactions.length).toBe(2);
  expect(state.transactions[1]?.operations[0]).toEqual({
    type: "set_entity_metadata",
    entity: componentRef,
    display_name: "Friendly timer",
    short_description: "Counts cycles",
    description: "A programmable timer.",
  });

  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Add port…" }).click();
  await component.getByLabel("Port name").fill("count");
  await component.getByLabel("Direction for count").selectOption("out");
  await component.getByLabel("Left bound for count").fill("31");
  await component.getByLabel("Right bound for count").fill("0");
  await component.getByLabel("Description for count").fill("Current count");
  const draftRow = component.locator(".spec-port-edit-row");
  await draftRow.getByRole("button", { name: "Save" }).click();
  await expect.poll(() => state.transactions.length).toBe(3);
  expect(state.transactions[2]?.operations[0]).toEqual({
    type: "add_component_port",
    component: componentRef,
    port: {
      name: "count",
      direction: "out",
      left: "31",
      right: "0",
      description: "Current count",
    },
  });

  const existingRow = component.locator("tbody tr").filter({ hasText: "irq" });
  await existingRow.getByRole("button", { name: "Edit" }).click();
  await component.getByLabel("Direction for irq").selectOption("inout");
  await component.getByLabel("Description for irq").fill("Bidirectional interrupt");
  await component.locator(".spec-port-edit-row").getByRole("button", { name: "Save" }).click();
  await expect.poll(() => state.transactions.length).toBe(4);
  expect(state.transactions[3]?.operations[0]).toEqual({
    type: "update_component_port",
    component: componentRef,
    name: "irq",
    port: {
      direction: "inout",
      left: null,
      right: null,
      description: "Bidirectional interrupt",
    },
  });
});

test("preserves an inline draft when the optimistic revision is stale", async ({ page }) => {
  const state = await mockEditorApi(page);
  await openSample(page);
  const component = page.locator("#component-component_timer");
  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Edit details…" }).click();
  await component.getByLabel("Description").fill("Keep this draft after refresh.");
  state.staleNextTransaction = true;
  await component.getByRole("button", { name: "Save changes" }).click();

  await expect(component.getByLabel("Description")).toHaveValue("Keep this draft after refresh.");
  await expect(component.getByRole("alert")).toContainText("draft was preserved");
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
  await expect(page.getByRole("dialog", { name: "Getting started" })).toContainText("saved automatically");
  await page.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("menuitem", { name: "File", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Document", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

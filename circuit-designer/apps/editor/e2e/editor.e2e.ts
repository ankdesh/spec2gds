import { expect, test, type Page, type Route } from "@playwright/test";

const documentId = "editor_test";
const revision = "sha256:editor-test";

const designRef = { document_id: documentId, entity_id: "design_top", entity_kind: "design" };
const componentRef = { document_id: documentId, entity_id: "component_timer", entity_kind: "component" };
const busRef = { document_id: documentId, entity_id: "bus_control", entity_kind: "bus_definition" };

const snapshot = {
  schema_version: "1.0",
  document_id: documentId,
  source_revision_hash: revision,
  components: [{ ref: componentRef, vlnv: "acme:blocks:Timer:1.0" }],
  designs: [{ ref: designRef, vlnv: "acme:systems:Processor:1.0" }],
  entry_designs: [{ ref: designRef, vlnv: "acme:systems:Processor:1.0" }],
  bus_definitions: [],
  abstraction_definitions: [],
  component_compositions: [],
  narrative: { blocks: [] },
  diagnostics: { source: [], artifacts: [] },
};

function section(id: string, title: string, level: number, entityRef: object | null) {
  return {
    id: `section-${id}`,
    component: "SpecSection",
    section: {
      section_id: id,
      title,
      level,
      eyebrow: level === 1 ? "Document section" : "Hardware entity",
      entity_ref: entityRef,
      facts: [],
      tables: [],
      narrative: [],
    },
    children: [],
  };
}

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
          section("design-design_top", "Processor", 2, designRef),
          section("component-component_timer", "Timer", 2, componentRef),
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
              { section_id: "design-design_top", title: "Processor", level: 2 },
              { section_id: "component-component_timer", title: "Timer", level: 2 },
              { section_id: "bus-definition-bus_control", title: "Control Bus", level: 2 },
            ],
            children: [
              "section-overview",
              "section-design-design_top",
              "section-component-component_timer",
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
};

async function mockEditorApi(page: Page): Promise<ApiState> {
  const state: ApiState = { circuits: [], createdPaths: [], openedPaths: [] };
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
      return json(snapshot);
    }
    if (path === "/documents/snapshot") return json(snapshot);
    if (path === "/documents/a2ui") return json(batch);
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
  await expect(page.getByRole("menuitem", { name: "Cut Read-only" })).toBeDisabled();
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

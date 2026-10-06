import { readFile } from "node:fs/promises";
import { createServer, type Server } from "node:http";
import { expect, test, type Page } from "@playwright/test";
import { createDefaultCircuitDesignerPreferences, simpleDocumentFixture } from "@spec2gds/circuit-core";

const circuitApiUrl = process.env.CIRCUIT_DESIGNER_E2E_API_URL
  ?? "http://127.0.0.1:6011/api/circuit-designer/v1";

let sourceProvider: Server;
let sourceProviderPort = 0;
let sourceProviderCalls: string[] = [];

test.beforeAll(async () => {
  sourceProvider = createServer((request, response) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      sourceProviderCalls.push(request.url ?? "");
      const body = JSON.parse(Buffer.concat(chunks).toString()) as {
        candidate_document: ReturnType<typeof simpleDocumentFixture>;
      };
      response.setHeader("Content-Type", "application/json");
      response.end(JSON.stringify({
        accepted: true,
        source_revision_hash: "sha256:source-roundtrip-saved",
        document: body.candidate_document,
        diagnostics: [],
      }));
    });
  });
  await new Promise<void>((resolve) => sourceProvider.listen(0, "127.0.0.1", resolve));
  const address = sourceProvider.address();
  sourceProviderPort = typeof address === "object" && address ? address.port : 0;
});

test.afterAll(async () => {
  await new Promise<void>((resolve) => sourceProvider.close(() => resolve()));
});

async function menuAction(page: Page, menu: string, action: string | RegExp): Promise<void> {
  await page.getByRole("menuitem", { name: menu, exact: true }).click();
  await page.getByRole("menuitem", typeof action === "string" ? { name: action, exact: true } : { name: action }).click();
}

test.beforeEach(async ({ request }) => {
  const response = await request.put(`${circuitApiUrl}/preferences`, {
    data: createDefaultCircuitDesignerPreferences(),
  });
  expect(response.ok()).toBe(true);
});

test("uses a compact menubar and the reclaimed full-width canvas", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("circuit-canvas")).toBeVisible();
  const appBox = await page.locator(".cd-app").boundingBox();
  const canvasBox = await page.locator(".canvas-surface").boundingBox();
  expect(appBox?.height).toBeGreaterThan(500);
  expect(canvasBox?.height).toBeGreaterThan(400);
  await expect(page.locator(".notice")).toContainText("Untitled circuit");
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await expect(page.locator(".library")).toHaveCount(0);
  await expect(page.locator(".canvas-action-bar")).toHaveCount(0);
  await expect(page.locator(".inspector")).toHaveCount(0);
  for (const name of ["File", "Edit", "Components", "Selection", "Connect", "Route", "Timing", "View", "Tools", "Help"]) {
    await expect(page.getByRole("menuitem", { name, exact: true })).toBeVisible();
  }
  await page.getByRole("menuitem", { name: "Connect", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: "New connection", exact: true })).toBeDisabled();
});

test("supports keyboard navigation, nested submenus, dismissal, and focus restoration", async ({ page }) => {
  await page.goto("/");
  const file = page.getByRole("menuitem", { name: "File", exact: true });
  await file.focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("menu", { name: "File" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: /New circuit/ })).toBeFocused();
  await page.keyboard.press("End");
  await expect(page.getByRole("menuitem", { name: "Download", exact: true })).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("menu", { name: "Download" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: /Download Circuit JSON/ })).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("menu", { name: "Download" })).toHaveCount(0);
  await expect(page.getByRole("menuitem", { name: "Download", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu", { name: "File" })).toHaveCount(0);
  await expect(file).toBeFocused();

  await page.getByRole("menuitem", { name: "Selection", exact: true }).click();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("menu", { name: "Connect" })).toBeVisible();
  await page.locator(".canvas-surface").click({ position: { x: 10, y: 10 } });
  await expect(page.getByRole("menu", { name: "Connect" })).toHaveCount(0);

  const help = page.getByRole("menuitem", { name: "Help", exact: true });
  await help.focus();
  await page.keyboard.press("Space");
  await expect(page.getByRole("menu", { name: "Help" })).toBeVisible();
  await page.keyboard.press("Escape");
  const tools = page.getByRole("menuitem", { name: "Tools", exact: true });
  await tools.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menu", { name: "Tools" })).toBeVisible();
  await page.keyboard.press("Escape");
});

test("launches former sidebar and action-strip workflows from menus", async ({ page }) => {
  await page.goto("/");
  await menuAction(page, "Components", "Component catalog");
  await expect(page.getByRole("dialog", { name: "Component catalog" })).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  await menuAction(page, "Edit", "Begin editing");
  await expect(page.locator(".document-status")).toContainText("private draft");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Producer");
  await page.getByRole("button", { name: "Create definition + instance" }).click();
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Consumer");
  await page.getByRole("button", { name: "Create definition + instance" }).click();

  await menuAction(page, "Selection", /Select all/);
  await page.getByRole("menuitem", { name: "View", exact: true }).click();
  await page.getByRole("menuitemcheckbox", { name: /Show Inspector/ }).click();
  await expect(page.locator(".inspector")).toContainText("2 items selected");
  await menuAction(page, "Selection", /Clear selection/);

  const source = page.locator('.react-flow__handle[data-handleid="producer:output"]');
  const target = page.locator('.react-flow__handle[data-handleid="consumer:input"]');
  await source.dragTo(target);
  await expect(page.locator(".notice")).toContainText("Created net");

  await menuAction(page, "Connect", "New connection");
  await page.getByLabel("Endpoint A").selectOption("producer:input");
  await page.getByLabel("Endpoint B").selectOption("consumer:output");
  await page.getByRole("button", { name: "Create net" }).click();
  await expect(page.locator(".notice")).toContainText("Created net");
});

test("edits a writable specification binding and saves it through source preview and commit", async ({ page, request }) => {
  sourceProviderCalls = [];
  const document = simpleDocumentFixture();
  document.document_id = `source_roundtrip_${Date.now()}`;
  const created = await request.post(`${circuitApiUrl}/documents`, {
    data: { request_id: `create_${document.document_id}`, document },
  });
  expect(created.ok()).toBe(true);
  const registered = await request.put(`${circuitApiUrl}/documents/${document.document_id}/source-binding`, {
    data: {
      callback_url: `http://127.0.0.1:${sourceProviderPort}/source/`,
      token: "browser-source-token",
      binding: {
        schema_version: 1,
        binding_id: `binding_${document.document_id}`,
        source_document_id: "browser_spec",
        source_entity: { document_id: "browser_spec", entity_id: "design_top", entity_kind: "design" },
        editable_design_id: "design_top",
        base_source_revision_hash: "sha256:source-roundtrip-base",
        writable: true,
        capabilities: ["topology", "layout", "local-components"],
        omitted_bus_items: [],
        omitted_ports: [],
      },
    },
  });
  expect(registered.ok()).toBe(true);

  await page.goto(`/?document_id=${document.document_id}`);
  await expect(page.locator(".document-status")).toContainText("Specification bound");
  await menuAction(page, "Edit", "Begin editing");
  await expect(page.locator(".document-status")).toContainText("Specification draft");

  const pane = page.locator(".react-flow__pane");
  await pane.click({ button: "right", position: { x: 420, y: 260 } });
  const createLocal = page.getByRole("menuitem", { name: "New local component…", exact: true });
  await expect(createLocal).toBeEnabled();
  await createLocal.click();
  await page.getByLabel("Name", { exact: true }).fill("spec_block");
  await expect(page.getByText("VLNV: spec2gds.local:work:spec_block:1.0")).not.toBeVisible();
  await page.getByRole("button", { name: "Create definition + instance" }).click();

  const save = page.getByRole("button", { name: "Save to Spec", exact: true });
  await expect(save).toBeVisible();
  await save.click();
  await expect(page.locator(".document-status")).toContainText("Specification bound");
  await expect(page.locator(".notice")).toContainText("Changes saved to the source");
  expect(sourceProviderCalls).toEqual(["/source/preview", "/source/commit"]);
});

test("saves shared shortcuts and Inspector visibility through the preference endpoint", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Preferences", exact: true }).click();
  await page.getByRole("menuitem", { name: /Actions and shortcuts/ }).click();
  await expect(page.getByRole("heading", { name: "Circuit Designer preferences" })).toBeVisible();
  await expect(page.getByLabel("Select all keyboard shortcut")).toHaveText("Ctrl/⌘ A");
  await expect(page.getByLabel("Drag canvas mouse shortcut")).toHaveValue("primary-drag");

  const saved = page.waitForResponse((response) => response.url().endsWith("/preferences") && response.request().method() === "PUT");
  await page.getByLabel("Fit circuit keyboard shortcut").focus();
  await page.keyboard.press("f");
  await page.getByLabel("New connection keyboard shortcut").focus();
  await page.keyboard.press("c");
  await page.getByRole("checkbox", { name: /Show Inspector/ }).check();
  await saved;
  await expect(page.getByRole("status")).toContainText("Saved");
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.locator(".inspector")).toBeVisible();

  await page.reload();
  await expect(page.locator(".inspector")).toBeVisible();
  await menuAction(page, "Edit", "Begin editing");
  await expect(page.locator(".document-status")).toContainText("private draft");
  await page.keyboard.press("c");
  await expect(page.getByRole("dialog", { name: "Create connection" })).toBeVisible();

  const response = await request.get(`${circuitApiUrl}/preferences`);
  const profile = await response.json() as { preferences: { ui: { inspector_open: boolean }; action_bindings: Record<string, { keyboard: string }> } };
  expect(profile.preferences.ui.inspector_open).toBe(true);
  expect(profile.preferences.action_bindings["fit-circuit"].keyboard).toBe("F");
  expect(profile.preferences.action_bindings["open-connect"].keyboard).toBe("C");
});

test("pans with left drag while Shift+left-drag remains selection gesture", async ({ page }) => {
  await page.goto("/");
  const pane = page.locator(".react-flow__pane");
  const viewport = page.locator(".react-flow__viewport");
  const bounds = await pane.boundingBox();
  expect(bounds).not.toBeNull();
  const before = await viewport.getAttribute("style");
  await page.mouse.move(bounds!.x + bounds!.width / 2, bounds!.y + bounds!.height / 2);
  await page.mouse.down({ button: "left" });
  await page.mouse.move(bounds!.x + bounds!.width / 2 + 90, bounds!.y + bounds!.height / 2 + 45, { steps: 5 });
  await page.mouse.up({ button: "left" });
  await expect.poll(() => viewport.getAttribute("style")).not.toBe(before);

  const afterPan = await viewport.getAttribute("style");
  await page.keyboard.down("Shift");
  await page.mouse.move(bounds!.x + 100, bounds!.y + 100);
  await page.mouse.down({ button: "left" });
  await page.mouse.move(bounds!.x + 230, bounds!.y + 190, { steps: 4 });
  await page.mouse.up({ button: "left" });
  await page.keyboard.up("Shift");
  await expect(viewport).toHaveAttribute("style", afterPan ?? "");

  await menuAction(page, "Edit", "Begin editing");
  await expect(page.locator(".document-status")).toContainText("private draft");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Marquee target");
  await page.getByRole("button", { name: "Create definition + instance" }).click();
  const node = page.locator(".react-flow__node").first();
  await expect(node).toBeVisible();
  const nodeBounds = await node.boundingBox();
  expect(nodeBounds).not.toBeNull();
  await page.keyboard.down("Shift");
  await page.mouse.move(nodeBounds!.x - 12, nodeBounds!.y - 12);
  await page.mouse.down({ button: "left" });
  await page.mouse.move(nodeBounds!.x + nodeBounds!.width + 12, nodeBounds!.y + nodeBounds!.height + 12, { steps: 5 });
  await page.mouse.up({ button: "left" });
  await page.keyboard.up("Shift");
  await expect(node).toHaveClass(/selected/);
});

test("keeps controlled component selection stable after click and Escape", async ({ page }) => {
  await page.goto("/");
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Stable selection");
  await page.getByRole("button", { name: "Create definition + instance" }).click();
  const node = page.locator(".react-flow__node[data-id='stable_selection']");
  await expect(node).toHaveClass(/selected/);

  await page.keyboard.press("Escape");
  await expect(node).not.toHaveClass(/selected/);
  const changesAfterEscape = await node.evaluate((element) => new Promise<number>((resolve) => {
    let changes = 0;
    const observer = new MutationObserver(() => { changes += 1; });
    observer.observe(element, { attributes: true, attributeFilter: ["class"] });
    window.setTimeout(() => { observer.disconnect(); resolve(changes); }, 450);
  }));
  expect(changesAfterEscape).toBe(0);

  await node.click();
  await expect(node).toHaveClass(/selected/);
  const changesAfterClick = await node.evaluate((element) => new Promise<number>((resolve) => {
    let changes = 0;
    const observer = new MutationObserver(() => { changes += 1; });
    observer.observe(element, { attributes: true, attributeFilter: ["class"] });
    window.setTimeout(() => { observer.disconnect(); resolve(changes); }, 450);
  }));
  expect(changesAfterClick).toBe(0);
});

test("opens clamped semantic context menus from pointer and keyboard", async ({ page }) => {
  await page.goto("/");
  const pane = page.locator(".react-flow__pane");
  const paneBounds = await pane.boundingBox();
  expect(paneBounds).not.toBeNull();

  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await pane.click({ button: "right", position: { x: paneBounds!.width - 20, y: paneBounds!.height - 120 } });
  await expect(page.getByRole("menu", { name: "File" })).toHaveCount(0);
  const contextMenu = page.getByRole("menu", { name: "Circuit context menu" });
  await expect(contextMenu).toBeVisible();
  const menuBounds = await contextMenu.boundingBox();
  const viewport = page.viewportSize();
  expect(menuBounds).not.toBeNull();
  expect(viewport).not.toBeNull();
  expect(menuBounds!.x).toBeGreaterThanOrEqual(8);
  expect(menuBounds!.y).toBeGreaterThanOrEqual(8);
  expect(menuBounds!.x + menuBounds!.width).toBeLessThanOrEqual(viewport!.width - 8);
  expect(menuBounds!.y + menuBounds!.height).toBeLessThanOrEqual(viewport!.height - 8);
  await page.keyboard.press("Escape");
  await expect(contextMenu).toHaveCount(0);

  await menuAction(page, "Edit", "Begin editing");
  const createPoint = { x: 420, y: 280 };
  await pane.click({ button: "right", position: createPoint });
  await page.getByRole("menuitem", { name: "New local component…", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("Pointer block");
  await page.getByRole("button", { name: "Create definition + instance" }).click();
  const node = page.locator(".react-flow__node[data-id='pointer_block']");
  await expect(node).toBeVisible();
  const nodeBounds = await node.boundingBox();
  expect(nodeBounds).not.toBeNull();
  expect(Math.abs(nodeBounds!.x + nodeBounds!.width / 2 - (paneBounds!.x + createPoint.x))).toBeLessThanOrEqual(25);
  expect(Math.abs(nodeBounds!.y + nodeBounds!.height / 2 - (paneBounds!.y + createPoint.y))).toBeLessThanOrEqual(25);

  await node.click({ button: "right" });
  await expect(node).toHaveClass(/selected/);
  await expect(page.getByRole("menuitem", { name: "Open selected child design", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await node.focus();
  await page.keyboard.press("Shift+F10");
  await expect(page.getByRole("menuitem", { name: "Center selection", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");

  const port = page.locator('.react-flow__handle[data-handleid="pointer_block:input"]');
  await port.click({ button: "right", force: true });
  await expect(page.getByRole("menuitem", { name: "Placement", exact: true })).toBeVisible();
  await page.getByRole("menuitem", { name: "New connection…", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Create connection" })).toBeVisible();
  await expect(page.getByLabel("Endpoint A")).toHaveValue("pointer_block:input");
  await page.getByRole("button", { name: "Close" }).click();

  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Context sink");
  await page.getByRole("button", { name: "Create definition + instance" }).click();
  await menuAction(page, "Connect", "New connection");
  await page.getByLabel("Endpoint A").selectOption("pointer_block:output");
  await page.getByLabel("Endpoint B").selectOption("context_sink:input");
  await page.getByRole("button", { name: "Create net" }).click();
  const connectedPort = page.locator('.react-flow__handle[data-handleid="pointer_block:output"]');
  await connectedPort.click({ button: "right", force: true });
  await expect(page.getByRole("menuitem", { name: "Select connected net", exact: true })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "Disconnect port", exact: true })).toBeVisible();
});

test("places, edits, hides, and exports a cycle timing marker", async ({ page }) => {
  await page.goto("/");
  await menuAction(page, "Edit", "Begin editing");
  const pane = page.locator(".react-flow__pane");
  await pane.click({ button: "right", position: { x: 430, y: 260 } });
  await page.getByRole("menuitem", { name: "Add cycle edge here", exact: true }).click();

  const edge = page.locator(".cd-cycle-edge");
  await expect(edge).toHaveCount(1);
  await expect(edge).toContainText("Cycle edge 1");
  await expect(page.locator(".cd-cycle-edge__leading-stage")).toHaveText("Stage 0");

  await edge.click({ button: "right" });
  await page.getByRole("menuitem", { name: "Edit cycle edge…", exact: true }).click();
  await page.getByLabel("Edge label").fill("Execute edge");
  await page.getByLabel("Following stage label").fill("Writeback");
  await page.getByRole("button", { name: "Apply", exact: true }).click();
  await expect(edge).toContainText("Execute edge");
  await expect(edge).toContainText("Writeback");

  await page.getByRole("menuitem", { name: "View", exact: true }).click();
  await page.getByRole("menuitemcheckbox", { name: /Show timing overlay/ }).click();
  await expect(edge).toHaveCount(0);
  await page.getByRole("menuitem", { name: "View", exact: true }).click();
  await page.getByRole("menuitemcheckbox", { name: /Show timing overlay/ }).click();
  await expect(edge).toHaveCount(1);

  const saveDownload = page.waitForEvent("download");
  await menuAction(page, "File", /Save changes/);
  await saveDownload;
  const svgDownload = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: "Download", exact: true }).click();
  await page.getByRole("menuitem", { name: "Export SVG", exact: true }).click();
  const svgPath = await (await svgDownload).path();
  expect(svgPath).not.toBeNull();
  const svg = await readFile(svgPath!, "utf8");
  expect(svg).toContain('class="cycle-edge"');
  expect(svg).toContain("Execute edge");
  expect(svg).toContain("WRITEBACK");
  expect(svg).toContain("STAGE 0");
});

test("keeps right-drag panning without opening a context menu", async ({ page, request }) => {
  const preferences = createDefaultCircuitDesignerPreferences();
  preferences.action_bindings["pan-canvas"].mouse = "secondary-drag";
  expect((await request.put(`${circuitApiUrl}/preferences`, { data: preferences })).ok()).toBe(true);
  await page.goto("/");
  const pane = page.locator(".react-flow__pane");
  const viewport = page.locator(".react-flow__viewport");
  const bounds = await pane.boundingBox();
  expect(bounds).not.toBeNull();
  const before = await viewport.getAttribute("style");
  await page.mouse.move(bounds!.x + 250, bounds!.y + 180);
  await page.mouse.down({ button: "right" });
  await page.mouse.move(bounds!.x + 330, bounds!.y + 225, { steps: 5 });
  await page.mouse.up({ button: "right" });
  await expect.poll(() => viewport.getAttribute("style")).not.toBe(before);
  await expect(page.getByRole("menu", { name: "Circuit context menu" })).toHaveCount(0);

  await pane.click({ button: "right", position: { x: 200, y: 160 } });
  await expect(page.getByRole("menu", { name: "Circuit context menu" })).toBeVisible();
});

test("downloads and reopens a portable circuit file from File commands", async ({ page }) => {
  await page.goto("/");
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Inspection block");
  await page.getByRole("button", { name: "Create definition + instance" }).click();

  const downloadPromise = page.waitForEvent("download");
  await menuAction(page, "File", /Save changes/);
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^untitled-circuit(?:-\d+)?\.circuit\.json$/);
  const filePath = await download.path();
  expect(filePath).not.toBeNull();
  const saved = JSON.parse(await readFile(filePath!, "utf8")) as {
    components: Array<{ id: string }>;
    design: { instances: Array<{ component_id: string }> };
  };
  expect(saved.components.some((component) => component.id === "inspection_block")).toBe(true);

  await menuAction(page, "File", /New circuit/);
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  const chooserPromise = page.waitForEvent("filechooser");
  await menuAction(page, "File", /Open circuit/);
  await (await chooserPromise).setFiles(filePath!);
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await expect(page.locator(".notice")).toContainText("Untitled circuit");
});

test("exports the visible canvas layout consistently to SVG and PNG", async ({ page }) => {
  await page.goto("/");
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Visual export");
  await page.getByRole("button", { name: "Create definition + instance" }).click();
  const node = page.locator(".react-flow__node[data-id='visual_export']");
  await expect(node).toBeVisible();
  const nodeTransform = await node.evaluate((element) => (element as HTMLElement).style.transform);
  const canvasPosition = nodeTransform.match(/translate\(([-\d.]+)px,\s*([-\d.]+)px\)/);
  expect(canvasPosition).not.toBeNull();

  const saveDownload = page.waitForEvent("download");
  await menuAction(page, "File", /Save changes/);
  await saveDownload;

  const svgDownloadPromise = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: "Download", exact: true }).click();
  await page.getByRole("menuitem", { name: "Export SVG", exact: true }).click();
  const svgPath = await (await svgDownloadPromise).path();
  expect(svgPath).not.toBeNull();
  const svg = await readFile(svgPath!, "utf8");
  const svgBox = svg.match(/<svg[^>]+width="(\d+)"[^>]+height="(\d+)"/);
  const exportedPosition = svg.match(/data-instance-id="visual_export"><rect x="([\d.-]+)" y="([\d.-]+)"/);
  expect(svgBox).not.toBeNull();
  expect(exportedPosition?.slice(1)).toEqual(canvasPosition?.slice(1));
  expect(svg).toContain(".canvas-background{fill:#f7f9fc}");
  expect(svg).toContain('fill="url(#canvas-grid)"');
  expect(svg).toContain('data-terminal-id="visual_export:input"');
  expect(svg).toContain('data-terminal-id="visual_export:output"');

  const pngDownloadPromise = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: "Download", exact: true }).click();
  await page.getByRole("menuitem", { name: "Export PNG", exact: true }).click();
  const pngPath = await (await pngDownloadPromise).path();
  expect(pngPath).not.toBeNull();
  const png = await readFile(pngPath!);
  expect([...png.subarray(0, 8)]).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
  expect(png.readUInt32BE(16)).toBe(Number(svgBox![1]));
  expect(png.readUInt32BE(20)).toBe(Number(svgBox![2]));
});

test("rejects an invalid file without replacing the current circuit", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".notice")).toContainText("Untitled circuit");
  const nodeCount = await page.locator(".react-flow__node").count();
  const chooserPromise = page.waitForEvent("filechooser");
  await menuAction(page, "File", /Open circuit/);
  await (await chooserPromise).setFiles({
    name: "broken.circuit.json",
    mimeType: "application/json",
    buffer: Buffer.from("{"),
  });
  await expect(page.locator(".notice")).toContainText("Could not open broken.circuit.json");
  await expect(page.locator(".react-flow__node")).toHaveCount(nodeCount);
});

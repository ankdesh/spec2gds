import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";
import { createDefaultCircuitDesignerPreferences } from "@spec2gds/circuit-core";

const circuitApiUrl = process.env.CIRCUIT_DESIGNER_E2E_API_URL
  ?? "http://127.0.0.1:6011/api/circuit-designer/v1";

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
  await expect(page.locator(".notice")).toContainText("REST session");
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await expect(page.locator(".library")).toHaveCount(0);
  await expect(page.locator(".canvas-action-bar")).toHaveCount(0);
  await expect(page.locator(".inspector")).toHaveCount(0);
  for (const name of ["File", "Edit", "Components", "Selection", "Connect", "Route", "View", "Tools", "Help"]) {
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
  await expect(page.getByRole("menuitem", { name: /Download circuit JSON/ })).toBeFocused();
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

test("downloads and reopens a portable circuit file from File commands", async ({ page }) => {
  await page.goto("/");
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Inspection block");
  await page.getByRole("button", { name: "Create definition + instance" }).click();

  const downloadPromise = page.waitForEvent("download");
  await menuAction(page, "File", /Save changes/);
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^local_.*\.circuit\.json$/);
  const filePath = await download.path();
  expect(filePath).not.toBeNull();
  const saved = JSON.parse(await readFile(filePath!, "utf8")) as {
    components: Array<{ id: string }>;
    design: { instances: Array<{ component_id: string }> };
  };
  expect(saved.components.some((component) => component.id === "inspection_block")).toBe(true);

  await menuAction(page, "File", /New circuit/);
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await page.getByLabel("Circuit file").setInputFiles(filePath!);
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await expect(page.locator(".notice")).toContainText(".circuit.json");
});

test("rejects an invalid file without replacing the current circuit", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".notice")).toContainText("REST session");
  const nodeCount = await page.locator(".react-flow__node").count();
  await page.getByLabel("Circuit file").setInputFiles({
    name: "broken.circuit.json",
    mimeType: "application/json",
    buffer: Buffer.from("{"),
  });
  await expect(page.locator(".notice")).toContainText("Could not open broken.circuit.json");
  await expect(page.locator(".react-flow__node")).toHaveCount(nodeCount);
});

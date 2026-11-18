import { readFileSync } from "node:fs";
import { test, expect, openSpec, type Stack } from "./fixtures.js";
import type { Page } from "@playwright/test";

async function menu(page: Page, name: string, action: string | RegExp): Promise<void> {
  if (!await page.getByRole("menuitem", { name, exact: true }).isVisible()) await page.getByRole("menuitem", { name: "Commands", exact: true }).click();
  await page.getByRole("menuitem", { name, exact: true }).click();
  await page.getByRole("menuitem", typeof action === "string" ? { name: action, exact: true } : { name: action }).click();
}
async function localComponent(page: Page, name: string): Promise<void> {
  await menu(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Add to Design" }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
}
async function sourceDesign(stack: Stack): Promise<any> {
  const created = await stack.json("/documents/create", { path: stack.path(), document_id: "circuit_source", title: "Coverage authoring" });
  const snapshot = (await stack.commit([{ type: "create_entity", kind: "design", name: "top" }], created)).snapshot;
  return snapshot;
}
async function launch(page: Page, stack: Stack, kind: string, id: string): Promise<any> {
  const launched = await stack.json("/circuit-designer/launch", { entity_kind: kind, entity_id: id });
  await page.goto(launched.editor_url);
  await expect(page.getByTestId("circuit-canvas")).toBeVisible();
  return launched;
}

for (const theme of ["blueprint-slate", "obsidian"]) test(`visible Circuit actions connect, inspect timing and save in ${theme}`, async ({ page, stack }, info) => {
  await page.goto(stack.circuitUI);
  await expect(page.getByTestId("circuit-canvas")).toBeVisible();
  if (await page.locator(".cd-app").getAttribute("data-theme") !== theme) await page.getByRole("button", { name: /^Switch theme/ }).click();
  await expect(page.getByRole("status", { name: "Circuit save state" })).toHaveText("Viewing");
  await expect(page.getByRole("button", { name: "Save circuit", exact: true })).toBeDisabled();
  await page.screenshot({ path: info.outputPath(`ux-start-${theme}.png`) });
  await page.getByRole("button", { name: "Begin editing", exact: true }).click();
  await page.getByRole("button", { name: "Add component", exact: true }).click();
  await page.getByRole("button", { name: "Create local Component", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("Arithmetic unit");
  await page.getByLabel("Port width or range", { exact: true }).fill("16");
  await page.getByRole("button", { name: "Add to Design", exact: true }).click();
  await page.getByRole("button", { name: "Add port to Design", exact: true }).click();
  let dialog = page.getByRole("dialog", { name: "Add port", exact: true });
  await expect(dialog.getByLabel("Wire width or range", { exact: true })).toHaveValue("1");
  await dialog.getByLabel("Name", { exact: true }).fill("data_in");
  await dialog.getByLabel("Wire width or range", { exact: true }).fill("8");
  await dialog.getByRole("button", { name: "Add port", exact: true }).click();
  await page.getByRole("button", { name: "Connect ports", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Connect ports", exact: true });
  await expect(dialog.getByLabel("LSB for A")).toHaveCount(0);
  await dialog.getByLabel("From port", { exact: true }).selectOption("boundary:data_in");
  await dialog.getByLabel("To port", { exact: true }).selectOption("arithmetic_unit:input");
  await expect(dialog.getByRole("button", { name: "Connect", exact: true })).toBeDisabled();
  await expect(dialog.getByRole("status", { name: "Connection guidance" })).toContainText("8 bits → 16 bits");
  await page.screenshot({ path: info.outputPath(`ux-width-guidance-${theme}.png`) });
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.getByRole("button", { name: "Show Inspector", exact: true }).click();
  await page.getByRole("complementary", { name: "Inspector", exact: true }).getByLabel("Wire width or range").fill("16");
  await page.getByRole("button", { name: "Connect ports", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Connect ports", exact: true });
  await dialog.getByLabel("From port", { exact: true }).selectOption("boundary:data_in");
  await dialog.getByLabel("To port", { exact: true }).selectOption("arithmetic_unit:input");
  await dialog.getByLabel("Net label", { exact: true }).fill("operand");
  await expect(dialog.getByRole("status", { name: "Connection mapping" })).toContainText("16 bits");
  await dialog.getByRole("button", { name: "Connect", exact: true }).click();
  await menu(page, "Timing", "Timing analysis");
  const timing = page.getByRole("complementary", { name: "Timing analysis", exact: true });
  await expect(timing).toContainText("Arithmetic unit.input");
  await expect(timing.locator(".timing-path")).not.toContainText("instance:arithmetic_unit");
  await timing.getByRole("button", { name: /operand/ }).click();
  await expect(page.locator(".react-flow__edge")).toHaveClass(/selected/);
  await page.screenshot({ path: info.outputPath(`ux-timing-${theme}.png`) });
  await timing.getByRole("button", { name: "Close timing analysis", exact: true }).click();
  await expect(page.getByRole("status", { name: "Circuit save state" })).toHaveText("Unsaved changes");
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save circuit", exact: true }).click();
  const saved = JSON.parse(readFileSync((await (await downloading).path())!, "utf8"));
  expect(saved.design.nets[0]).toMatchObject({ label: "operand" });
  expect(saved.design.nets[0].endpoints.every((endpoint: any) => !endpoint.slice)).toBe(true);
  expect(saved.components[0].terminals.map((port: any) => port.width)).toEqual([16, 16]);
  await expect(page.getByRole("status", { name: "Circuit save state" })).toHaveText("Saved");
  for (const [width, height] of [[1440, 1000], [1024, 768], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await expect(page.locator(".document-status")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save circuit", exact: true })).toBeInViewport();
    await page.getByRole("button", { name: "Port list", exact: true }).click();
    await expect(page.getByRole("region", { name: "Circuit ports", exact: true })).toContainText("data_in");
    await expect(page.getByRole("button", { name: "Connect from port" }).first()).toBeDisabled();
    await page.getByRole("button", { name: "Close port list", exact: true }).click();
    const geometry = await page.locator(".canvas-actions button").evaluateAll(buttons => buttons.map(button => button.getBoundingClientRect().height));
    expect(Math.min(...geometry)).toBeGreaterThanOrEqual(44);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0);
    await page.screenshot({ path: info.outputPath(`ux-saved-${theme}-${width}.png`) });
  }
  await menu(page, "Help", "About Circuit Designer");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menuitem", { name: "Commands", exact: true })).toBeFocused();
});

test("Spec Editor launches expose direct actions for a Design and a blank Component", async ({ page: specPage, stack }, info) => {
  const created = await stack.json("/documents/create", { path: stack.path(), document_id: "ux_launch" });
  await stack.commit([{ type: "create_entity", kind: "design", name: "Visible Design" }, { type: "create_entity", kind: "component", name: "Visible Component" }], created);
  await specPage.goto(`${stack.spec}/editor?owner_document_key=${encodeURIComponent(created.owner_document_key)}&edit_context_id=${encodeURIComponent(created.edit_access.context_id)}`);
  await expect(specPage.locator(".spec-paper")).toBeVisible();
  for (const name of ["Visible Design", "Visible Component"]) {
    const popup = specPage.waitForEvent("popup");
    await specPage.getByRole("menuitem", { name: "Circuit Designer", exact: true }).click();
    await specPage.getByRole("menu", { name: "Circuit Designer", exact: true }).getByRole("menuitem").filter({ hasText: name }).click();
    const page = await popup;
    await expect(page.getByTestId("circuit-canvas")).toBeVisible();
    const before = stack.archive(stack.path());
    if (name === "Visible Component") {
      await page.getByRole("button", { name: "Create internal Design", exact: true }).click();
      await expect(page.getByRole("status", { name: "Circuit save state" })).toHaveText("Unsaved Design");
      await expect(page.getByRole("button", { name: "Save to Spec", exact: true })).toBeEnabled();
    } else await page.getByRole("button", { name: "Begin editing", exact: true }).click();
    await expect(page.getByRole("button", { name: "Add component", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add port to Design", exact: true })).toBeEnabled();
    await page.screenshot({ path: info.outputPath(`ux-spec-launch-${name.replaceAll(" ", "-")}.png`) });
    expect(stack.archive(stack.path())).toEqual(before);
    await page.getByRole("button", { name: "Cancel changes", exact: true }).click();
    expect(stack.archive(stack.path())).toEqual(before);
    if (name === "Visible Component") await expect(page.getByRole("button", { name: "Create internal Design", exact: true })).toBeVisible();
    await page.close();
  }
});

for (const mode of ["ports", "instances", "empty"] as const) test(`encloses ${mode} in a Design frame and adds ports without the Inspector`, async ({ page, stack, request }, testInfo) => {
  const documentId = `frame_${mode}_${Date.now()}`;
  const terminal = (id: string, direction: string, width = 16) => ({ id, label: id, direction, width, category: "port" });
  const document = {
    protocol_version: "circuit-designer.v1", document_id: documentId, label: "Frame check",
    components: [{ id: "adder", label: "16-bit modulo adder", origin: "local", editable: true, parameters: [], appearance: { renderer_key: "generic", properties: {} }, terminals: [terminal("a", "input"), terminal("b", "input"), terminal("y", "output")] }],
    design: { id: "top", label: "Frame check", nets: [],
      boundary_terminals: mode === "ports" ? [terminal("a", "input"), terminal("b", "input"), terminal("clk", "input", 1), terminal("enable", "input", 1), terminal("rst_n", "input", 1), terminal("y", "output")] : [],
      instances: mode === "instances" ? ["a1", "a2"].map(id => ({ id, label: id, component_id: "adder", parameter_values: {} })) : [],
    },
    layout: { grid_size: 20, direction: "RIGHT", instance_geometry: mode === "instances" ? { a1: { x: 80, y: 80, width: 180, height: 120 }, a2: { x: 80, y: 360, width: 180, height: 120 } } : {}, terminal_placements: {}, net_routes: {}, label_geometry: {} },
  };
  const api = `${stack.circuit}/api/circuit-designer/v1/documents`;
  expect((await request.post(api, { data: { request_id: documentId, document } })).ok()).toBe(true);
  await page.goto(`${stack.circuitUI}/?document_id=${documentId}`);
  const frame = page.getByTestId("circuit-design-frame");
  await expect(frame).toBeVisible();
  await expect(frame.getByRole("button", { name: "Add port", exact: true })).toBeDisabled();
  if (await page.getByRole("button", { name: "Hide Inspector", exact: true }).isVisible()) await page.getByRole("button", { name: "Hide Inspector", exact: true }).click();
  for (const appearance of ["initial", "alternate"]) {
    await page.getByRole("button", { name: "Fit circuit", exact: true }).click();
    await expect(frame).toBeInViewport({ ratio: .99 });
    await page.screenshot({ path: testInfo.outputPath(`frame-${mode}-${appearance}.png`) });
    if (appearance === "initial") await page.getByRole("button", { name: /^Switch theme/ }).click();
  }
  if (mode === "ports") {
    const bounds = (await frame.boundingBox())!;
    const a = (await page.locator('.react-flow__handle[data-terminal-id="boundary:a"]').boundingBox())!;
    const y = (await page.locator('.react-flow__handle[data-terminal-id="boundary:y"]').boundingBox())!;
    expect(Math.abs(a.x + a.width / 2 - bounds.x)).toBeLessThan(3);
    expect(Math.abs(y.x + y.width / 2 - bounds.x - bounds.width)).toBeLessThan(3);
    expect(await page.locator(".cd-node--boundary").first().evaluate(element => getComputedStyle(element).backgroundColor)).toBe("rgba(0, 0, 0, 0)");
  }
  await menu(page, "Edit", "Begin editing");
  await frame.getByRole("button", { name: "Add port", exact: true }).click();
  let dialog = page.getByRole("dialog", { name: "Add port", exact: true });
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.locator('.react-flow__handle[data-terminal-id="boundary:port"]')).toHaveCount(0);
  if (mode === "instances") {
    await frame.locator(".cd-design-frame__header").click({ button: "right" });
    await page.getByRole("menuitem", { name: "Add port…", exact: true }).click();
  } else await frame.getByRole("button", { name: "Add port", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Add port", exact: true });
  await dialog.getByLabel("Name", { exact: true }).fill("result");
  await dialog.getByRole("combobox", { name: "Direction", exact: true }).selectOption("output");
  await dialog.getByLabel("Wire width or range", { exact: true }).fill("0");
  await dialog.getByRole("button", { name: "Add port", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("positive whole number");
  await dialog.getByLabel("Wire width or range", { exact: true }).fill("16");
  await dialog.getByRole("button", { name: "Add port", exact: true }).click();
  await expect(dialog).toBeHidden();
  const result = page.locator('.react-flow__handle[data-terminal-id="boundary:result"]');
  await expect(result).toBeVisible();
  await menu(page, "Edit", /Undo/);
  await expect(result).toHaveCount(0);
  await menu(page, "Edit", /Redo/);
  await expect(result).toBeVisible();
  if (mode === "empty") {
    await result.click({ button: "right" });
    await page.getByRole("menuitem", { name: "Placement", exact: true }).click();
    await page.getByRole("menuitem", { name: "Side", exact: true }).click();
    await page.getByRole("menuitemradio", { name: "South", exact: true }).click();
    await expect(result).toHaveClass(/react-flow__handle-top/);
    const bounds = (await frame.boundingBox())!, pin = (await result.boundingBox())!;
    expect(Math.abs(pin.y + pin.height / 2 - bounds.y - bounds.height)).toBeLessThan(3);
  }
  if (mode === "instances") {
    await page.locator('.react-flow__handle[data-terminal-id="a1:y"]').dragTo(result);
    await expect(page.locator(".react-flow__edge")).toHaveCount(1);
  }
  await menu(page, "File", /^Save changes/);
  await expect(page.locator(".notice")).toContainText(/saved/i);
  const saved = await (await request.get(`${api}/${documentId}`)).json();
  expect(saved.document.design.boundary_terminals.at(-1)).toMatchObject({ label: "result", direction: "output", width: 16 });
  expect(saved.document.layout.instance_geometry).toEqual(document.layout.instance_geometry);
  await page.reload();
  await expect(frame).toBeVisible();
  await expect(result).toBeVisible();
  if (mode === "instances") {
    await expect(page.locator(".react-flow__edge")).toHaveCount(1);
    const label = (await page.locator('.react-flow__node[data-id="boundary:result"] .cd-node__port-label').boundingBox())!;
    const pin = (await result.boundingBox())!;
    expect(label.y + label.height).toBeLessThanOrEqual(pin.y + 1);
  }
  if (mode === "empty") {
    expect(saved.document.layout.terminal_placements["boundary:result"].side).toBe("NORTH");
    await page.setViewportSize({ width: 1000, height: 740 });
    await page.getByRole("button", { name: "Fit circuit", exact: true }).click();
    await expect(frame).toBeInViewport({ ratio: .99 });
  }
  if (mode === "ports") for (const format of ["SVG", "PNG"]) {
    const downloading = page.waitForEvent("download");
    await menu(page, "File", "Download");
    await page.getByRole("menuitem", { name: new RegExp(format) }).click();
    const downloaded = await downloading;
    const path = testInfo.outputPath(`frame.${format.toLowerCase()}`);
    await downloaded.saveAs(path);
    const bytes = readFileSync(path);
    if (format === "SVG") {
      expect(bytes.toString()).toContain('data-design-frame="top"');
      expect(bytes.toString()).toContain('data-terminal-id="boundary:result"');
      expect(bytes.toString()).not.toMatch(/<g data-boundary-id="[^"]+"><rect/);
    } else expect([...bytes.subarray(0, 8)]).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
  }
  await page.screenshot({ path: testInfo.outputPath(`frame-${mode}-saved.png`) });
});

test("opens exact Spec targets from the Circuit Designer menu and embedded previews without changing the Spec", async ({ page, stack }) => {
  stack.seedSample();
  await openSpec(page, stack);
  const snapshot = await stack.snapshot();
  const before = stack.archive(stack.path());
  const composite = snapshot.component_compositions[0];
  const leaf = snapshot.components.find((item: any) => !snapshot.component_compositions.some((mapping: any) => mapping.component.entity_id === item.ref.entity_id));
  const design = snapshot.entry_designs[0];
  const component = snapshot.components.find((item: any) => item.ref.entity_id === composite.component.entity_id);
  const targets = [design, component, leaf];
  for (const target of targets) {
    const ref = target.ref;
    const routes = ref.entity_id === component.ref.entity_id ? ["menu"] : ["menu", "preview"];
    for (const route of routes) {
      const launched = page.waitForEvent("popup");
      if (route === "menu") {
        await page.getByRole("menuitem", { name: "Circuit Designer", exact: true }).click();
        const name = target.display_name || target.vlnv.split(":")[2];
        const status = target === leaf ? "Read-only preview" : target === component ? "Open assigned Design" : "Edit Design";
        await page.getByRole("menu", { name: "Circuit Designer", exact: true }).getByRole("menuitem")
          .filter({ hasText: name }).filter({ hasText: status }).click();
      } else {
        const anchor = `${ref.entity_kind}-${ref.entity_id.replaceAll("_", "-")}`;
        const preview = page.locator(`#${anchor} .spec-topology-card`);
        await preview.getByRole("button", { name: "Options for circuit preview", exact: true }).click();
        await preview.page().getByRole("menu", { name: /^Options for / }).getByRole("menuitem", { name: "Open in Circuit Designer", exact: true }).click();
      }
      const circuit = await launched;
      await expect(circuit.getByTestId("circuit-canvas")).toBeVisible();
      const documentId = new URL(circuit.url()).searchParams.get("document_id");
      expect(documentId).toBeTruthy();
      const response = await fetch(`${stack.circuit}/api/circuit-designer/v1/documents/${documentId}/source-binding`);
      expect(response.ok).toBe(true);
      const binding = await response.json();
      expect(binding.source_entity).toEqual(ref);
      expect(binding.base_source_revision_hash).toBe(snapshot.source_revision_hash);
      expect(binding.source_owner_document_key).toBe(snapshot.owner_document_key);
      expect(binding.writable).toBe(target !== leaf);
      if (target === component) {
        expect(binding.editable_design_id).toBe(composite.internal_design.entity_id);
        await expect(circuit.getByTestId("circuit-design-frame")).toContainText(component.display_name || component.vlnv.split(":")[2]);
      }
      if (target === leaf) await expect(circuit.getByTestId("circuit-design-frame")).toHaveCount(0);
      if (target === leaf) {
        await circuit.getByRole("menuitem", { name: "Edit", exact: true }).click();
        await expect(circuit.getByRole("menuitem", { name: "Begin editing", exact: true })).toBeEnabled();
      }
      expect((await stack.snapshot()).source_revision_hash).toBe(snapshot.source_revision_hash);
      expect(stack.archive(stack.path())).toEqual(before);
      await circuit.close();
    }
  }
});

test("@smoke saves Circuit topology to real Spec source and reopens both applications", async ({ page, stack }) => {
  const snapshot = await sourceDesign(stack);
  const ref = snapshot.designs[0].ref;
  await launch(page, stack, "design", ref.entity_id);
  await menu(page, "Edit", "Begin editing");
  await localComponent(page, "Circuit child");
  await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(page.locator(".notice")).toContainText("Changes saved to the source");
  const saved = await stack.snapshot();
  expect(saved.source_revision_hash).not.toBe(snapshot.source_revision_hash);
  expect(saved.components).toHaveLength(1);
  expect(saved.designs[0].instances).toHaveLength(1);
  expect(Object.values(stack.archive(stack.path())).join("\n")).toContain("Circuit child");
  await stack.restart("spec");
  await stack.json("/documents/open", { path: stack.path() });
  expect((await stack.snapshot()).source_revision_hash).toBe(saved.source_revision_hash);
  await launch(page, stack, "design", ref.entity_id);
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
});

test("cancel discards a Circuit draft without changing the Spec", async ({ page, stack }) => {
  const snapshot = await sourceDesign(stack);
  await launch(page, stack, "design", snapshot.designs[0].ref.entity_id);
  const source = stack.archive(stack.path());
  await menu(page, "Edit", "Begin editing");
  await localComponent(page, "Cancelled child");
  await menu(page, "File", "Cancel changes");
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  expect(stack.archive(stack.path())).toEqual(source);
  expect((await stack.snapshot()).source_revision_hash).toBe(snapshot.source_revision_hash);
});

test("replaces a deleted instance with another definition using the same name", async ({ page, stack }) => {
  let snapshot = await sourceDesign(stack);
  snapshot = (await stack.commit([
    { type: "create_entity", kind: "component", name: "Two input selector" },
    { type: "create_entity", kind: "component", name: "Four input selector" },
  ], snapshot)).snapshot;
  const first = snapshot.components.find((item: any) => item.display_name === "Two input selector");
  const replacement = snapshot.components.find((item: any) => item.display_name === "Four input selector");
  snapshot = (await stack.commit([{ type: "upsert_instance", design: snapshot.designs[0].ref,
    instance: { name: "u_read", component_vlnv: first.vlnv } }], snapshot)).snapshot;
  await launch(page, stack, "design", snapshot.designs[0].ref.entity_id);
  await menu(page, "Edit", "Begin editing");
  await page.locator('.react-flow__node[data-id="u_read"]').click();
  await menu(page, "Edit", /Delete selected/);
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await menu(page, "Components", "Component catalog");
  const dialog = page.getByRole("dialog");
  await dialog.locator(".catalog-list button").filter({ hasText: "Four input selector" }).click();
  await dialog.getByLabel("Instance name").fill("u_read");
  await dialog.getByRole("button", { name: "Place instance", exact: true }).click();
  await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(page.locator(".notice")).toContainText("Changes saved to the source");
  await expect(page.locator(".save-error")).toHaveCount(0);
  const saved = await stack.snapshot();
  expect(saved.designs[0].instances).toEqual([{ name: "u_read", component_vlnv: replacement.vlnv, parameter_values: [] }]);
  await launch(page, stack, "design", snapshot.designs[0].ref.entity_id);
  await expect(page.locator('.react-flow__node[data-id="u_read"]')).toContainText("Four input selector");
});

test("confirmed source takeover preserves the displaced draft and blocks its saves", async ({ page, context, stack }) => {
  const snapshot = await sourceDesign(stack);
  const launched = await launch(page, stack, "design", snapshot.designs[0].ref.entity_id);
  await menu(page, "Edit", "Begin editing");
  await localComponent(page, "First tab private child");
  const before = stack.archive(stack.path());
  const second = await context.newPage();
  await second.goto(launched.editor_url);
  await expect(second.getByRole("button", { name: "Take over editing", exact: true })).toBeVisible();
  await second.getByRole("button", { name: "Take over editing", exact: true }).click();
  await second.getByRole("dialog").getByRole("button", { name: "Cancel", exact: true }).click();
  expect(stack.archive(stack.path())).toEqual(before);
  await second.getByRole("button", { name: "Take over editing", exact: true }).click();
  await second.getByRole("dialog").getByRole("button", { name: "Take over editing", exact: true }).click();
  await expect(second.locator(".notice")).toContainText("Editing taken over");
  await expect(second.locator(".react-flow__node")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Discard preserved draft" })).toBeVisible();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  expect(stack.archive(stack.path())).toEqual(before);
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: /Undo/ })).toBeDisabled();
  await page.keyboard.press("Escape");
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Draft JSON", exact: true }).click();
  const file = await (await downloaded).path();
  expect(file).not.toBeNull();
  expect(JSON.parse(readFileSync(file!, "utf8")).components[0].label).toBe("First tab private child");
  await page.getByRole("button", { name: "Discard preserved draft" }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await localComponent(second, "Second tab accepted child");
  await second.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(second.locator(".notice")).toContainText("Changes saved to the source");
  const saved = await stack.snapshot();
  expect(saved.components).toHaveLength(1);
  expect(saved.components[0].display_name).toBe("Second tab accepted child");
});

test("Cancel remains usable when a private draft lease has expired", async ({ page, stack }) => {
  const snapshot = await sourceDesign(stack);
  const launched = await launch(page, stack, "design", snapshot.designs[0].ref.entity_id);
  const before = stack.archive(stack.path());
  await menu(page, "Edit", "Begin editing");
  await localComponent(page, "Expired private child");
  const base = `${stack.circuit}/api/circuit-designer/v1/documents/${launched.document_id}`;
  const lease = (await (await fetch(`${base}/lock`)).json()).lease;
  // Shorten only the expiry prerequisite; Cancel is performed through the UI.
  expect((await fetch(`${base}/lock/${lease.lease_id}`, { method: "PUT",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ttl_seconds: 0.001 }) })).ok).toBe(true);
  await expect.poll(async () => (await (await fetch(`${base}/lock`)).json()).lease).toBeNull();
  await menu(page, "File", "Cancel changes");
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  expect(stack.archive(stack.path())).toEqual(before);
});

test("a stale Circuit save cannot replace a later Spec edit", async ({ page, stack }) => {
  const snapshot = await sourceDesign(stack);
  await launch(page, stack, "design", snapshot.designs[0].ref.entity_id);
  await menu(page, "Edit", "Begin editing");
  await localComponent(page, "Stale child");
  await stack.commit([{ type: "create_entity", kind: "component", name: "later_source" }]);
  const saved = await stack.snapshot();
  const source = stack.archive(stack.path());
  await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(page.locator(".notice")).toContainText("Review the save conflict");
  await expect(page.locator(".save-error")).toContainText("The Spec changed. Your draft is safe.");
  await expect(page.locator(".save-error")).toContainText("before exporting");
  await page.screenshot({ path: test.info().outputPath("save-rejected.png") });
  expect((await stack.snapshot()).source_revision_hash).toBe(saved.source_revision_hash);
  expect(stack.archive(stack.path())).toEqual(source);
  await expect(page.getByRole("button", { name: "Save to Spec", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Open latest Spec", exact: true }).click();
  await page.getByRole("dialog", { name: "Open the latest Spec?", exact: true }).getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await page.route("**/source/reload", route => route.abort("failed"), { times: 1 });
  await page.getByRole("button", { name: "Open latest Spec", exact: true }).click();
  await page.getByRole("button", { name: "Discard draft and open latest", exact: true }).click();
  await expect(page.locator(".save-error")).toContainText("Could not open the latest Spec. Your draft is preserved");
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download draft", exact: true }).click();
  const preserved = JSON.parse(readFileSync((await (await downloading).path())!, "utf8"));
  expect(preserved.design.instances).toHaveLength(1);
  expect(stack.archive(stack.path())).toEqual(source);
  await menu(page, "File", "Cancel changes");
  await expect(page.locator(".save-error")).toHaveCount(0);
});

for (const theme of ["blueprint-slate", "obsidian"]) {
  test(`creates a blank Component internal Design with an empty first save in ${theme}`, async ({ page: specPage, stack }) => {
    const created = await stack.json("/documents/create", { path: stack.path(), document_id: "blank_source" });
    const snapshot = (await stack.commit([{ type: "create_entity", kind: "component", name: "Blank Component" }], created)).snapshot;
    const ref = snapshot.components[0].ref;
    await specPage.goto(`${stack.spec}/editor?owner_document_key=${encodeURIComponent(created.owner_document_key)}&edit_context_id=${encodeURIComponent(created.edit_access.context_id)}`);
    await expect(specPage.locator(".spec-paper")).toBeVisible();
    const opened = specPage.waitForEvent("popup");
    if (theme === "blueprint-slate") {
      await specPage.getByRole("menuitem", { name: "Circuit Designer", exact: true }).click();
      await specPage.getByRole("menu", { name: "Circuit Designer", exact: true }).getByRole("menuitem").filter({ hasText: "Blank Component" }).click();
    } else {
      const preview = specPage.locator(".spec-topology-card");
      await preview.getByRole("button", { name: "Options for circuit preview", exact: true }).click();
      await preview.page().getByRole("menu", { name: /^Options for / }).getByRole("menuitem", { name: "Open in Circuit Designer", exact: true }).click();
    }
    const page = await opened;
    await expect(page.getByTestId("circuit-canvas")).toBeVisible();
    if (await page.locator(".cd-app").getAttribute("data-theme") !== theme) await page.getByRole("button", { name: /^Switch theme/ }).click();
    await page.setViewportSize({ width: 540, height: 820 });
    if (!await page.getByRole("menuitem", { name: "Edit", exact: true }).isVisible()) await page.getByRole("menuitem", { name: "Commands", exact: true }).click();
    await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
    await expect(page.getByRole("menuitem", { name: "Create internal Design", exact: true })).toBeDisabled();
    await expect(page.getByRole("menuitem", { name: "Create internal Design", exact: true })).toHaveAttribute("title", "Select Begin editing first.");
    await page.getByRole("menuitem", { name: "Begin editing", exact: true }).click();
    if (!await page.getByRole("menuitem", { name: "Components", exact: true }).isVisible()) await page.getByRole("menuitem", { name: "Commands", exact: true }).click();
    await page.getByRole("menuitem", { name: "Components", exact: true }).click();
    await expect(page.getByRole("menuitem", { name: "New local component", exact: true })).toBeDisabled();
    await page.keyboard.press("Escape");
    const before = stack.archive(stack.path());
    if (!await page.getByRole("menuitem", { name: "Edit", exact: true }).isVisible()) await page.getByRole("menuitem", { name: "Commands", exact: true }).click();
    await page.getByRole("menuitem", { name: "Edit", exact: true }).focus();
    await page.keyboard.press("Enter");
    await page.getByRole("menuitem", { name: "Create internal Design", exact: true }).focus();
    if (theme === "obsidian") {
      await page.route("**/source/internal-design/prepare", async route => {
        await route.fetch();
        await route.abort("failed");
      }, { times: 1 });
    } else {
      await page.route("**/source/internal-design/prepare", route => route.fulfill({
        status: 200, contentType: "application/json", body: JSON.stringify({ accepted: false,
          source_revision_hash: snapshot.source_revision_hash,
          diagnostics: [{ severity: "error", code: "source_projection_failed", message: "Preparation rejected for this check." }] }),
      }), { times: 1 });
    }
    await page.keyboard.press("Enter");
    await expect(page.locator(".notice")).toContainText("Could not confirm Design preparation");
    await menu(page, "File", "Cancel changes");
    await expect(page.locator(".notice")).toContainText("Draft cancelled");
    expect(stack.archive(stack.path())).toEqual(before);
    await menu(page, "Edit", "Begin editing");
    await menu(page, "Edit", "Create internal Design");
    await expect(page.getByRole("button", { name: "Save to Spec", exact: true })).toBeEnabled();
    const saveBounds = await page.getByRole("button", { name: "Save to Spec", exact: true }).boundingBox();
    expect(saveBounds!.x + saveBounds!.width).toBeLessThanOrEqual(540);
    await page.screenshot({ path: test.info().outputPath(`pending-design-${theme}.png`) });
    expect(stack.archive(stack.path())).toEqual(before);
    await menu(page, "File", "Cancel changes");
    await expect(page.locator(".notice")).toContainText("Draft cancelled");
    expect(stack.archive(stack.path())).toEqual(before);
    await menu(page, "Edit", "Begin editing");
    await menu(page, "Edit", "Create internal Design");
    await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
    await expect(page.locator(".notice")).toContainText("Changes saved to the source");
    const saved = await stack.snapshot();
    expect(saved.designs).toHaveLength(1);
    expect(saved.designs[0].instances).toHaveLength(0);
    expect(saved.entry_designs).toHaveLength(0);
    expect(saved.component_compositions[0].component).toEqual(ref);
    expect(saved.component_compositions[0].internal_design).toEqual(saved.designs[0].ref);
    await expect(specPage.locator(".spec-topology-card")).not.toContainText("Interface preview (read-only)");
    await page.reload();
    await menu(page, "Edit", "Begin editing");
    if (!await page.getByRole("menuitem", { name: "Edit", exact: true }).isVisible()) await page.getByRole("menuitem", { name: "Commands", exact: true }).click();
    await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
    await expect(page.getByRole("menuitem", { name: "Create internal Design", exact: true })).toBeDisabled();
    await page.keyboard.press("Escape");
    await page.screenshot({ path: test.info().outputPath(`internal-design-${theme}.png`) });
  });
}

for (const choice of ["Retain SV", "Remove SV"]) {
  test(`creates an internal Design with ${choice}, cancelled saving, ports, and source-safe retries`, async ({ page, stack }) => {
    const created = await stack.json("/documents/create", { path: stack.path(), document_id: "sv_source" });
    let snapshot = (await stack.commit([{ type: "create_entity", kind: "component", name: "SV Component" }], created)).snapshot;
    const ref = snapshot.components[0].ref;
    snapshot = (await stack.json("/transactions", { expected_source_revision_hash: snapshot.source_revision_hash, validation_mode: "authoring", operations: [
      { type: "add_component_port", component: ref, port: { name: "a", family: "wire", direction: "in", range: "7:0" } },
      { type: "upsert_entity_section", parent: ref, section_type: "sv", type_version: 1, payload: { content: "assign retained_broken = ;" } },
    ] })).snapshot;
    await launch(page, stack, "component", ref.entity_id);
    await menu(page, "Edit", "Begin editing");
    await menu(page, "Edit", "Create internal Design");
    const before = stack.archive(stack.path());
    await page.getByRole("button", { name: "Show Inspector", exact: true }).click();
    await page.getByRole("button", { name: "Add port to Design", exact: true }).click();
    await page.getByRole("dialog", { name: "Add port", exact: true }).getByRole("button", { name: "Add port", exact: true }).click();
    await page.setViewportSize({ width: 540, height: 820 });
    if (choice === "Remove SV") await page.getByRole("button", { name: /^Switch theme/ }).click();
    await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Save the internal Design" })).toBeVisible();
    await expect(page.getByRole("button", { name: choice, exact: true })).toBeInViewport();
    await page.screenshot({ path: test.info().outputPath(`sv-choice-${choice.replaceAll(" ", "-")}.png`) });
    await page.getByRole("button", { name: "Cancel saving", exact: true }).click();
    expect(stack.archive(stack.path())).toEqual(before);
    await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
    // Let the real save finish, then withhold its response to exercise receipt retry.
    let requestId: string | undefined;
    await page.route("**/source/commit", async route => {
      requestId = route.request().postDataJSON().batch.request_id;
      await route.fetch();
      await route.abort("failed");
    }, { times: 1 });
    await page.getByRole("button", { name: choice, exact: true }).click();
    await expect(page.locator(".save-error")).toContainText("Retry Save to Spec");
    const committed = stack.archive(stack.path());
    const retry = page.waitForRequest(request => request.url().endsWith("/source/commit"));
    await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
    expect((await retry).postDataJSON().batch.request_id).toBe(requestId);
    await expect(page.locator(".notice")).toContainText("Changes saved to the source");
    expect(stack.archive(stack.path())).toEqual(committed);
    const saved = await stack.snapshot();
    expect(saved.designs).toHaveLength(1);
    expect(saved.components[0].ports).toHaveLength(2);
    if (choice === "Retain SV") {
      expect(saved.entity_sections[0].usage).toBe("reference");
      expect(saved.entity_sections[0].content).toBe("assign retained_broken = ;");
    } else expect(saved.entity_sections).toHaveLength(0);
    await openSpec(page, stack);
    if (choice === "Retain SV") await expect(page.getByText("Reference only · excluded from implementation", { exact: true })).toBeVisible();
  });
}

test("a displaced internal Design draft can be discarded without releasing the successor's lease", async ({ page, context, stack }) => {
  const created = await stack.json("/documents/create", { path: stack.path(), document_id: "pending_takeover" });
  const snapshot = (await stack.commit([{ type: "create_entity", kind: "component", name: "Pending Component" }], created)).snapshot;
  const launched = await launch(page, stack, "component", snapshot.components[0].ref.entity_id);
  const before = stack.archive(stack.path());
  await menu(page, "Edit", "Begin editing");
  await menu(page, "Edit", "Create internal Design");
  await expect(page.getByRole("button", { name: "Save to Spec", exact: true })).toBeEnabled();
  const second = await context.newPage();
  await second.goto(launched.editor_url);
  await second.getByRole("button", { name: "Take over editing", exact: true }).click();
  await second.getByRole("dialog").getByRole("button", { name: "Take over editing", exact: true }).click();
  await expect(second.locator(".notice")).toContainText("Editing taken over");
  const endpoint = `${stack.circuit}/api/circuit-designer/v1/documents/${launched.document_id}/lock`;
  const successor = (await (await fetch(endpoint)).json()).lease;
  await expect(page.locator(".notice")).toContainText("Editing permission was lost");
  await menu(page, "File", "Cancel changes");
  await expect(page.locator(".notice")).toContainText("Draft cancelled");
  expect((await (await fetch(endpoint)).json()).lease.lease_id).toBe(successor.lease_id);
  expect(stack.archive(stack.path())).toEqual(before);
  await menu(second, "Edit", "Create internal Design");
  await expect(second.getByRole("button", { name: "Save to Spec", exact: true })).toBeEnabled();
  await menu(second, "File", "Cancel changes");
  expect(stack.archive(stack.path())).toEqual(before);
});

test("standalone circuit roundtrip and malformed open preserve authoritative data", async ({ page, stack }) => {
  await page.goto(stack.circuitUI);
  await menu(page, "Edit", "Begin editing");
  await localComponent(page, "Portable child");
  const event = page.waitForEvent("download");
  await menu(page, "File", /Save changes/);
  const download = await event;
  const path = await download.path();
  expect(path).not.toBeNull();
  const saved = JSON.parse(readFileSync(path!, "utf8"));
  expect(saved.design.instances).toHaveLength(1);
  await menu(page, "File", /New circuit/);
  const chooser = page.waitForEvent("filechooser");
  await menu(page, "File", /Open circuit/);
  await (await chooser).setFiles(path!);
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  const invalid = page.waitForEvent("filechooser");
  await menu(page, "File", /Open circuit/);
  await (await invalid).setFiles({ name: "bad.circuit.json", mimeType: "application/json", buffer: Buffer.from('{"invalid":true}') });
  await expect(page.locator(".notice")).toContainText("Could not open circuit file");
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
});

test("dialogs trap focus and Escape returns focus to triggering menu", async ({ page, stack }) => {
  await page.goto(stack.circuitUI);
  await menu(page, "Help", "About Circuit Designer");
  const dialog = page.getByRole("dialog", { name: "About Circuit Designer" });
  await expect(dialog).toBeVisible();
  const closeButton = dialog.getByRole("button", { name: "Close" });
  await expect(closeButton).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  const trigger = page.locator("#circuit-help-menu-trigger");
  await expect(await trigger.isVisible() ? trigger : page.getByRole("menuitem", { name: "Commands", exact: true })).toBeFocused();
});

test("Circuit preferences stay in each browser and leave service defaults unchanged", async ({ page, browser, stack }) => {
  const snapshot = await sourceDesign(stack);
  const opened = await launch(page, stack, "design", snapshot.designs[0].ref.entity_id);
  const defaultsBefore = await (await fetch(`${stack.circuit}/api/circuit-designer/v1/preferences`)).json();
  const otherContext = await browser.newContext();
  const other = await otherContext.newPage();
  try {
    await other.goto(opened.editor_url);
    await expect(other.getByTestId("circuit-canvas")).toBeVisible();
    const previous = await page.locator(".cd-app").getAttribute("data-theme");
    await expect(other.locator(".cd-app")).toHaveAttribute("data-theme", previous!);
    await page.getByRole("button", { name: /^Switch theme/ }).click();
    await expect(page.locator(".cd-app")).not.toHaveAttribute("data-theme", previous!);
    await expect(other.locator(".cd-app")).toHaveAttribute("data-theme", previous!);
    await expect.poll(() => page.evaluate(() => localStorage.getItem("spec2gds.circuit.preferences.v1"))).not.toBeNull();
    const chosen = await page.locator(".cd-app").getAttribute("data-theme");
    await page.reload();
    await expect(page.locator(".cd-app")).toHaveAttribute("data-theme", chosen!);
    const defaultsAfter = await (await fetch(`${stack.circuit}/api/circuit-designer/v1/preferences`)).json();
    expect(defaultsAfter).toEqual(defaultsBefore);
  } finally { await otherContext.close(); }
});

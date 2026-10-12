import { writeFileSync, readFileSync, existsSync } from "node:fs";
import { test, expect, newSpec, openSpec, type Stack } from "./fixtures.js";
import type { Page, Locator } from "@playwright/test";
import { documentImports } from "./import_flow.js";

documentImports();

async function addComponent(page: Page, stack: Stack): Promise<Locator> {
  const section = page.locator("#components");
  await section.getByRole("button", { name: "Options" }).click();
  await section.getByRole("menuitem", { name: "Add component…" }).click();
  await page.getByLabel("Component name").fill("counter");
  await page.getByRole("button", { name: "Create component" }).click();
  await expect.poll(async () => (await stack.snapshot()).components.length).toBe(1);
  const ref = (await stack.snapshot()).components[0].ref;
  const component = page.locator(`#component-${ref.entity_id.replaceAll("_", "-")}`);
  await expect(component).toBeVisible();
  return component;
}
async function portDraft(component: Locator, family = "wire"): Promise<Locator> {
  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: `Add ${family} port…` }).click();
  return component.locator(".spec-port-editor");
}
async function editText(component: Locator, text: string): Promise<void> {
  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Edit text…" }).click();
  await component.getByLabel("Component explanation").fill(text);
}

test("@smoke creates a Component and wire port through the UI and reopens saved source", async ({ page, stack }) => {
  await newSpec(page, stack);
  const component = await addComponent(page, stack);
  const initial = await stack.snapshot();
  const draft = await portDraft(component);
  await draft.getByLabel("Port ID").fill("count");
  await draft.getByLabel("Direction").selectOption("out");
  await draft.getByLabel("Range").fill("31:0");
  await draft.getByLabel("Description").fill("Current count");
  await draft.getByRole("button", { name: "Save to Spec" }).click();
  await expect(component.locator(".spec-port-row")).toContainText("Current count");
  const saved = await stack.snapshot();
  expect(saved.components[0].ref).toEqual(initial.components[0].ref);
  expect(saved.components[0].ports[0]).toMatchObject({ name: "count", direction: "out", range: "31:0", width: "[31:0]" });
  expect(Object.values(stack.archive(stack.path())).join("\n")).toContain("Current count");
  await stack.restart("spec");
  await openSpec(page, stack);
  expect((await stack.snapshot()).source_revision_hash).toBe(saved.source_revision_hash);
  await expect(component.locator(".spec-port-row")).toContainText("count");
});

test("@smoke preserves an invalid draft, cancels it, and saves a corrected draft", async ({ page, stack }) => {
  await newSpec(page, stack);
  const component = await addComponent(page, stack);
  const before = await stack.snapshot();
  const source = stack.archive(stack.path());
  let draft = await portDraft(component);
  await draft.getByLabel("Port ID").fill("count");
  await draft.getByLabel("Range").fill("31::0");
  await draft.getByRole("button", { name: "Save to Spec" }).click();
  await expect(draft.getByRole("alert")).toContainText("left:right expression pair");
  await expect(draft.getByLabel("Range")).toHaveValue("31::0");
  expect((await stack.snapshot()).source_revision_hash).toBe(before.source_revision_hash);
  await draft.getByRole("button", { name: "Cancel" }).click();
  await expect(component.getByRole("button", { name: "Options" })).toBeFocused();
  expect(stack.archive(stack.path())).toEqual(source);
  draft = await portDraft(component);
  await draft.getByLabel("Port ID").fill("count");
  await draft.getByLabel("Range").fill("7:0");
  await draft.getByRole("button", { name: "Save to Spec" }).click();
  await openSpec(page, stack);
  expect((await stack.snapshot()).components[0].ports[0]).toMatchObject({ name: "count", range: "7:0", width: "[7:0]" });
  expect(Object.values(stack.archive(stack.path())).join("\n")).toContain("count");
});

for (const family of ["wire", "transactional", "structured"]) {
  test(`preserves saved ${family} ports with the release editing policy`, async ({ page, stack }) => {
    await newSpec(page, stack);
    const component = await addComponent(page, stack);
    const initial = await stack.snapshot();
    const port = family === "transactional"
      ? { name: "interface0", family, initiative: "provides", kind: "custom", custom_kind: "service0", bus_width: "DATA_WIDTH", description: "Interface contract" }
      : { name: "interface0", family, direction: "out", description: "Interface contract", ...(family === "wire" ? { range: "WIDTH-1:0" } : {}) };
    await stack.commit([{ type: "add_component_port", component: initial.components[0].ref, port }]);
    await openSpec(page, stack);
    const row = component.locator(".spec-port-row", { hasText: "interface0" });
    await expect(row).toContainText("Interface contract");
    if (family === "wire") {
      await row.getByRole("button", { name: "Edit", exact: true }).click();
      const draft = component.locator(".spec-port-editor");
      await expect(draft.getByLabel("Port ID")).toHaveCount(0);
      await draft.getByLabel("Description").fill("Updated interface contract");
      await draft.getByRole("button", { name: "Save to Spec" }).click();
    } else {
      await expect(row.getByRole("button", { name: "Edit", exact: true })).toHaveCount(0);
      await expect(row).toContainText("Read-only");
      const { name, ...update } = port;
      await stack.commit([{ type: "update_component_port", component: initial.components[0].ref, name, port: { ...update, description: "Updated interface contract" } }]);
    }
    await openSpec(page, stack);
    expect((await stack.snapshot()).components[0].ports[0]).toMatchObject({ name: "interface0", style: family, description: "Updated interface contract" });
    expect(Object.values(stack.archive(stack.path())).join("\n")).toContain("Updated interface contract");
  });
}

test("failed opens and an existing destination preserve the active Spec", async ({ page, stack }) => {
  await newSpec(page, stack);
  await addComponent(page, stack);
  const source = stack.archive(stack.path());
  writeFileSync(stack.path("malformed.spec"), "not an archive");
  for (const path of [stack.path("missing.spec"), stack.path("malformed.spec")]) {
    await page.getByRole("menuitem", { name: "File", exact: true }).click();
    await page.getByRole("menuitem", { name: /Open Spec/ }).click();
    await page.getByLabel("Server-local package path").fill(path);
    await page.getByRole("button", { name: "Open", exact: true }).click();
    await expect(page.getByRole("alert").first()).toBeVisible();
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Coverage authoring", exact: true })).toBeVisible();
  }
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /New Spec/ }).click();
  await page.getByLabel("Spec name").fill("Replacement");
  await page.getByLabel("Server-local package path").fill(stack.path());
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByRole("alert").first()).toBeVisible();
  expect(stack.archive(stack.path())).toEqual(source);
});

test("two writers preserve a stale draft until an explicit reviewed retry", async ({ page, context, stack }) => {
  await newSpec(page, stack);
  const component = await addComponent(page, stack);
  await editText(component, "Private draft from first writer");
  const second = await context.newPage();
  await openSpec(second, stack);
  const other = second.locator(`#${await component.getAttribute("id")}`);
  await editText(other, "Saved by second writer");
  await other.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(other).toContainText("Saved by second writer");
  const saved = await stack.snapshot();
  await expect(component.getByLabel("Component explanation")).toHaveValue("Private draft from first writer");
  await component.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(component.getByRole("alert")).toContainText("preserved draft");
  expect((await stack.snapshot()).source_revision_hash).toBe(saved.source_revision_hash);
  await page.getByRole("button", { name: "Use reviewed revision for next save" }).click();
  await component.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(component).toContainText("Private draft from first writer");
  await openSpec(page, stack);
  expect(Object.values(stack.archive(stack.path())).join("\n")).toContain("Private draft from first writer");
});

test("names retain identity and keyboard editing works at a narrow width", async ({ page, stack }) => {
  await page.setViewportSize({ width: 560, height: 760 });
  await newSpec(page, stack);
  const component = await addComponent(page, stack);
  const before = await stack.snapshot();
  await editText(component, "Keyboard-authored description");
  const save = component.getByRole("button", { name: "Save to Spec", exact: true });
  await save.focus(); await page.keyboard.press("Enter");
  await expect(component).toContainText("Keyboard-authored description");
  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Rename", exact: true }).click();
  await component.getByLabel("Name", { exact: true }).fill("Counter display name");
  await save.focus(); await page.keyboard.press("Enter");
  await expect(component.getByRole("heading", { name: "Counter display name", exact: true })).toBeVisible();
  await openSpec(page, stack);
  const saved = await stack.snapshot();
  expect(saved.document_id).toBe(before.document_id);
  expect(saved.components[0].ref).toEqual(before.components[0].ref);
  expect(Object.values(stack.archive(stack.path())).join("\n")).toContain("Counter display name");
});

test("creates an entry Design and Component instance through the UI and reopens it", async ({ page, stack }) => {
  await newSpec(page, stack);
  await addComponent(page, stack);
  const before = await stack.snapshot();
  const designs = page.locator("#designs");
  await designs.getByRole("button", { name: "Options" }).click();
  await designs.getByRole("menuitem", { name: "Add design…", exact: true }).click();
  await page.getByLabel("Design name").fill("top");
  await page.getByRole("button", { name: "Create design", exact: true }).click();
  await expect.poll(async () => (await stack.snapshot()).designs.length).toBe(1);
  const saved = await stack.snapshot();
  expect(saved.entry_designs).toHaveLength(1);
  const design = page.locator(`#design-${saved.designs[0].ref.entity_id.replaceAll("_", "-")}`);
  await design.getByRole("button", { name: "Options" }).click();
  await design.getByRole("menuitem", { name: "Add component instance…", exact: true }).click();
  await design.getByLabel("Instance ID").fill("counter0");
  await design.getByLabel("Component", { exact: true }).selectOption(before.components[0].vlnv);
  await design.getByRole("button", { name: "Add instance", exact: true }).click();
  await expect(design).toContainText("counter0");
  await openSpec(page, stack);
  const reopened = await stack.snapshot();
  expect(reopened.designs[0].instances[0]).toMatchObject({ name: "counter0", component_vlnv: before.components[0].vlnv });
  expect(reopened.components[0].ref).toEqual(before.components[0].ref);
  expect(Object.values(stack.archive(stack.path())).join("\n")).toContain("counter0");
});

test("SystemVerilog add, edit, delete and reopen use real source", async ({ page, stack }) => {
  await newSpec(page, stack);
  const component = await addComponent(page, stack);
  await component.getByRole("button", { name: "Options" }).click();
  await page.getByRole("menuitem", { name: "Add SystemVerilog section…" }).click();
  await component.locator(".cm-content").fill("logic saved_marker;\n");
  await component.getByRole("button", { name: "Add section", exact: true }).click();
  await expect(component.locator(".cm-content")).toHaveCount(0);
  expect(Object.values(stack.archive(stack.path())).join("\n")).toContain("saved_marker");
  await openSpec(page, stack);
  await component.getByRole("button", { name: "Edit", exact: true }).click();
  await component.locator(".cm-content").fill("logic edited_marker;\n");
  await component.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(component.locator(".cm-content")).toHaveCount(0);
  expect(Object.values(stack.archive(stack.path())).join("\n")).toContain("edited_marker");
  page.once("dialog", dialog => dialog.accept());
  await component.getByRole("button", { name: "Delete", exact: true }).click();
  await openSpec(page, stack);
  expect((await stack.snapshot()).entity_sections).toEqual([]);
  expect(Object.values(stack.archive(stack.path())).join("\n")).not.toContain("edited_marker");
});

test("editing visible text preserves hidden bus interfaces and other source members", async ({ page, stack }) => {
  stack.seedSample();
  await openSpec(page, stack);
  const source = stack.archive(stack.path());
  const component = page.locator("#component-component-leaf");
  await editText(component, "Updated explanation with hidden source retained");
  await component.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(component).toContainText("Updated explanation with hidden source retained");
  const saved = stack.archive(stack.path());
  for (const [name, content] of Object.entries(source)) {
    if (name.endsWith(".xml") && !name.includes("demo-leaf-")) expect(saved[name]).toBe(content);
    if (!name.endsWith(".xml") && name !== "manifest.json") expect(saved[name]).toBe(content);
    if (name.includes("demo-leaf-") && name.endsWith(".xml")) {
      const hidden = content.match(/<ipxact:busInterfaces>[\s\S]*?<\/ipxact:busInterfaces>/)?.[0];
      expect(hidden).toBeTruthy(); expect(saved[name]).toContain(hidden);
    }
  }
  await openSpec(page, stack);
  expect(stack.archive(stack.path())).toEqual(saved);
});

test("renders and downloads a source-derived SVG without a Circuit service", async ({ page, stack }) => {
  stack.seedSample();
  await openSpec(page, stack);
  const before = await stack.snapshot();
  const card = page.locator(".spec-topology-card").filter({ has: page.getByRole("img") }).first();
  await expect(card.getByRole("img")).toBeVisible();
  await card.getByRole("button", { name: "Expand", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Circuit topology", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  const event = page.waitForEvent("download");
  await card.getByRole("link", { name: "Download SVG" }).click();
  const path = await (await event).path();
  expect(readFileSync(path!, "utf8")).toContain("<svg");
  expect((await stack.snapshot()).source_revision_hash).toBe(before.source_revision_hash);
});

test("a delayed response cannot replace a newly selected Spec", async ({ page, stack }) => {
  await newSpec(page, stack);
  await addComponent(page, stack);
  const first = await stack.snapshot();
  const other = stack.path("second.spec");
  await stack.json("/documents/create", { path: other, document_id: "second", title: "Second source" });
  let release!: () => void, arrived!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const requested = new Promise<void>(resolve => { arrived = resolve; });
  let delayed = false;
  await page.route("**/documents/view?*", async route => {
    if (!delayed && route.request().url().includes(encodeURIComponent(first.owner_document_key))) {
      delayed = true;
      const response = await route.fetch();
      arrived(); await held;
      await route.fulfill({ response });
    } else await route.continue();
  });
  try {
    await stack.commit([{ type: "create_entity", kind: "component", name: "older_response" }], first);
    await expect.poll(() => delayed).toBe(true);
    await requested;
    await page.getByRole("menuitem", { name: "File", exact: true }).click();
    await page.getByRole("menuitem", { name: /Open Spec/ }).click();
    await page.getByLabel("Server-local package path").fill(other);
    await page.getByRole("button", { name: "Open", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Second source", exact: true })).toBeVisible();
    const response = page.waitForResponse(response => response.url().includes("/documents/view?") && response.url().includes(encodeURIComponent(first.owner_document_key)));
    release();
    await (await response).finished();
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => resolve())));
    await page.unroute("**/documents/view?*");
    await expect(page.getByRole("heading", { name: "Second source", exact: true })).toBeVisible();
    await expect(page.locator(".spec-port-row")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "older_response", exact: true })).toHaveCount(0);
  } finally { release(); }
});

test("source events reconnect after restart and show current saved source", async ({ page, stack }) => {
  await newSpec(page, stack);
  const component = await addComponent(page, stack);
  const ref = (await stack.snapshot()).components[0].ref;
  await stack.restart("spec");
  await stack.json("/documents/open", { path: stack.path() });
  await stack.commit([{ type: "set_entity_metadata", entity: ref, description: "Saved after service restart" }]);
  await expect(component).toContainText("Saved after service restart", { timeout: 30_000 });
  await expect(page.getByText("Up to date", { exact: true })).toBeVisible();
  expect(Object.values(stack.archive(stack.path())).join("\n")).toContain("Saved after service restart");
});

test("an Activity retains its enqueued source after source editing and service restart", async ({ page, stack }) => {
  await newSpec(page, stack);
  const component = await addComponent(page, stack);
  const baseline = await stack.snapshot();
  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Controlled barrier", exact: true }).click();
  await expect.poll(() => existsSync(`${stack.directory}/barrier/started`)).toBe(true);
  await stack.commit([{ type: "set_entity_metadata", entity: baseline.components[0].ref, description: "Later source description" }]);
  const current = await stack.snapshot();
  expect(current.source_revision_hash).not.toBe(baseline.source_revision_hash);
  await stack.restart("spec");
  await stack.json("/documents/open", { path: stack.path() });
  const reopened = await stack.snapshot();
  expect(Object.values(stack.archive(stack.path())).join("\n")).toContain("Later source description");
  writeFileSync(`${stack.directory}/barrier/release`, "continue");
  await expect.poll(async () => (await stack.json("/executions")).executions.at(-1)?.status).toBe("succeeded");
  const execution = (await stack.json("/executions")).executions.at(-1);
  expect(execution.source_revision_hash).toBe(baseline.source_revision_hash);
  expect(execution.report.source_revision).toBe(baseline.source_revision_hash);
  expect((await stack.snapshot()).source_revision_hash).toBe(reopened.source_revision_hash);
});

for (const [title, status] of [["Source proof", "succeeded"], ["Controlled failure", "failed"], ["Controlled barrier", "cancelled"]]) {
  test(`Activity ${title} reaches its real ${status} state`, async ({ page, stack }) => {
    await newSpec(page, stack);
    const component = await addComponent(page, stack);
    const before = await stack.snapshot();
    await component.getByRole("button", { name: "Options" }).click();
    await component.getByRole("menuitem", { name: title, exact: true }).click();
    if (status === "cancelled") {
      await expect.poll(() => existsSync(`${stack.directory}/barrier/started`)).toBe(true);
      await page.getByRole("button", { name: /^Activity \d/ }).click();
      const cancel = page.locator(".activity-item").filter({ hasText: title }).getByRole("button", { name: "Cancel", exact: true });
      await expect(cancel).toBeEnabled();
      await page.getByRole("button", { name: "Refresh", exact: true }).click();
      await expect(cancel).toBeEnabled();
      await page.reload();
      await openSpec(page, stack);
      await page.getByRole("button", { name: /^Activity \d/ }).click();
      await expect(cancel).toBeEnabled();
      await cancel.click();
    }
    await expect.poll(async () => (await stack.json("/executions")).executions.at(-1)?.status).toBe(status);
    if (!await page.getByRole("heading", { name: "Activity", exact: true }).isVisible()) {
      await page.getByRole("button", { name: /^Activity \d/ }).click();
    }
    await expect(page.locator(".activity-item").filter({ hasText: title }).first()).toContainText(status);
    const execution = (await stack.json("/executions")).executions.at(-1);
    expect(execution.source_revision_hash).toBe(before.source_revision_hash);
    if (status === "succeeded") {
      expect(execution.artifact_ids.length).toBe(1);
      const artifact = await fetch(`${stack.spec}/artifacts/${execution.artifact_ids.at(-1)}/content`);
      expect(artifact.ok).toBe(true);
      expect(await artifact.text()).toBe(before.source_revision_hash);
    }
    await stack.restart("spec");
    await openSpec(page, stack);
    expect((await stack.json("/executions")).executions.at(-1).status).toBe(status);
    expect((await stack.snapshot()).source_revision_hash).toBe(before.source_revision_hash);
  });
}

test("exports target Section details as a downloadable saved JSON artifact", async ({ page, stack }) => {
  await newSpec(page, stack);
  const component = await addComponent(page, stack);
  const initial = await stack.snapshot();
  const target = initial.components[0].ref;
  await stack.commit([{
    type: "set_entity_metadata", entity: target, description: "Saved diagnostic explanation",
  }]);
  await openSpec(page, stack);
  const before = await stack.snapshot();
  await component.getByRole("button", { name: "Options" }).click();
  await component.getByRole("menuitem", { name: "Export target details (JSON)", exact: true }).click();
  await expect.poll(async () => (await stack.json("/executions")).executions.at(-1)?.status).toBe("succeeded");
  await expect(page.getByRole("link", { name: "Download JSON" })).toBeVisible();
  const event = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download JSON" }).click();
  const download = await event;
  expect(download.suggestedFilename()).toMatch(/-section-details\.json$/);
  const value = JSON.parse(readFileSync((await download.path())!, "utf8"));
  expect(value).toMatchObject({ schema_version: "spec2gds.section-diagnostics.v1", target, source_revision_hash: before.source_revision_hash });
  expect(JSON.stringify(value.sections)).toContain("Saved diagnostic explanation");
  expect((await stack.snapshot()).source_revision_hash).toBe(before.source_revision_hash);
  await stack.restart("spec");
  await openSpec(page, stack);
  await page.getByRole("button", { name: /^Activity \d/ }).click();
  await expect(page.getByRole("link", { name: "Download JSON" })).toBeVisible();
});

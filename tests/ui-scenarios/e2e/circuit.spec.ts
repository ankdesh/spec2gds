import { readFileSync } from "node:fs";
import { test, expect, type Stack } from "./fixtures.js";
import type { Page } from "@playwright/test";

async function menu(page: Page, name: string, action: string | RegExp): Promise<void> {
  await page.getByRole("menuitem", { name, exact: true }).click();
  await page.getByRole("menuitem", typeof action === "string" ? { name: action, exact: true } : { name: action }).click();
}
async function localComponent(page: Page, name: string): Promise<void> {
  await menu(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Create definition + instance" }).click();
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

test("a stale Circuit save cannot replace a later Spec edit", async ({ page, stack }) => {
  const snapshot = await sourceDesign(stack);
  await launch(page, stack, "design", snapshot.designs[0].ref.entity_id);
  await menu(page, "Edit", "Begin editing");
  await localComponent(page, "Stale child");
  await stack.commit([{ type: "create_entity", kind: "component", name: "later_source" }]);
  const saved = await stack.snapshot();
  const source = stack.archive(stack.path());
  await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(page.locator(".notice")).toContainText(/stale|changed|revision/i);
  expect((await stack.snapshot()).source_revision_hash).toBe(saved.source_revision_hash);
  expect(stack.archive(stack.path())).toEqual(source);
});

test("leaf Component Circuit previews remain read-only", async ({ page, stack }) => {
  const created = await stack.json("/documents/create", { path: stack.path(), document_id: "leaf_source" });
  const snapshot = (await stack.commit([{ type: "create_entity", kind: "component", name: "leaf" }], created)).snapshot;
  const launched = await launch(page, stack, "component", snapshot.components[0].ref.entity_id);
  expect(launched.source_binding.writable).toBe(false);
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: "Begin editing", exact: true })).toBeDisabled();
  expect((await stack.snapshot()).source_revision_hash).toBe(snapshot.source_revision_hash);
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
  await expect(page.locator("#circuit-help-menu-trigger")).toBeFocused();
});


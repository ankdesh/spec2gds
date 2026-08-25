import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

test("starts an empty document through the REST service", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("circuit-canvas")).toBeVisible();
  await expect(page.locator(".notice")).toContainText("REST session");
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await expect(page.locator(".library")).toContainText("Empty local circuit");
});

test("uses one canvas interaction layer with discoverable command-bar actions", async ({ page }) => {
  await page.goto("/");
  const actions = page.getByLabel("Circuit canvas actions");

  await expect(page.locator(".mode-toolbar")).toHaveCount(0);
  await expect(actions.getByRole("button", { name: /Selection/ })).toBeVisible();
  await expect(actions.getByRole("button", { name: /Connect/ })).toBeDisabled();
  await actions.getByRole("button", { name: /View/ }).click();
  await expect(actions.getByRole("button", { name: "Pan left" })).toBeVisible();
  await actions.getByRole("menuitem", { name: "Zoom In" }).click();

  await page.getByRole("button", { name: "Unlock" }).click();
  await expect(page.getByRole("button", { name: "Save", exact: true })).toBeVisible();
  await page.getByLabel("Name", { exact: true }).fill("Producer");
  await page.getByRole("button", { name: "Create definition + instance" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Consumer");
  await page.getByRole("button", { name: "Create definition + instance" }).click();

  await actions.getByRole("button", { name: /Selection/ }).click();
  await actions.getByRole("menuitem", { name: /Select All/ }).click();
  await expect(page.locator(".inspector")).toContainText("2 items selected");
  await actions.getByRole("button", { name: /Selection/ }).click();
  await actions.getByRole("menuitem", { name: /Clear Selection/ }).click();

  const source = page.locator('.react-flow__handle[data-handleid="producer:output"]');
  const target = page.locator('.react-flow__handle[data-handleid="consumer:input"]');
  await expect(source).toBeVisible();
  await expect(target).toBeVisible();
  await source.dragTo(target);
  await expect(page.locator(".notice")).toContainText("Created net");

  await actions.getByRole("button", { name: /Connect/ }).click();
  await page.getByLabel("Endpoint A").selectOption("producer:input");
  await page.getByLabel("Endpoint B").selectOption("consumer:output");
  await page.getByRole("button", { name: "Create net" }).click();
  await expect(page.locator(".notice")).toContainText("Created net");
});

test("downloads and reopens a portable circuit file", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Unlock" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Producer");
  await page.getByRole("button", { name: "Create definition + instance" }).click();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^local_.*\.circuit\.json$/);
  const filePath = await download.path();
  expect(filePath).not.toBeNull();

  await page.getByRole("button", { name: "New", exact: true }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await page.getByLabel("Circuit file").setInputFiles(filePath!);

  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await expect(page.locator(".notice")).toContainText(".circuit.json");
  await expect(page.locator(".library")).toContainText("permanent changes are saved by downloading a new file");
});

test("rejects an invalid file without replacing the current circuit", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("circuit-canvas")).toBeVisible();
  const nodeCount = await page.locator(".react-flow__node").count();

  await page.getByLabel("Circuit file").setInputFiles({
    name: "broken.circuit.json",
    mimeType: "application/json",
    buffer: Buffer.from("{"),
  });

  await expect(page.locator(".notice")).toContainText("Could not open broken.circuit.json");
  await expect(page.locator(".react-flow__node")).toHaveCount(nodeCount);
});

test("commits a draft and downloads the accepted document", async ({ page }) => {
  await page.goto("/");
  const initialNodeCount = await page.locator(".react-flow__node").count();
  await page.getByRole("button", { name: "Unlock" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Inspection block");
  await page.getByRole("button", { name: "Create definition + instance" }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(initialNodeCount + 1);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^local_.*\.circuit\.json$/);
  const filePath = await download.path();
  expect(filePath).not.toBeNull();
  const saved = JSON.parse(await readFile(filePath!, "utf8")) as {
    components: Array<{ id: string }>;
    design: { instances: Array<{ component_id: string }> };
  };
  expect(saved.components.some((component) => component.id === "inspection_block")).toBe(true);
  expect(saved.design.instances.some((instance) => instance.component_id === "inspection_block")).toBe(true);
  await expect(page.locator(".notice")).toContainText("downloaded local_");
});

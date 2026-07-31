import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

test("loads examples through the REST service", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("circuit-canvas")).toBeVisible();
  await expect(page.locator(".notice")).toContainText("REST session");

  await page.getByLabel("Example").selectOption("datapath");
  await expect(page.locator(".react-flow__node")).toHaveCount(2);
  await expect(page.locator(".notice")).toContainText(/REST session|existing REST session/);
});

test("keeps select, connect, route, and pan modes mutually exclusive", async ({ page }) => {
  await page.goto("/");
  const modes = page.locator(".mode-toolbar");

  await expect(modes.getByRole("button", { name: "select" })).toHaveClass(/active/);
  await modes.getByRole("button", { name: "connect" }).click();
  await expect(modes.getByRole("button", { name: "connect" })).toHaveClass(/active/);
  await modes.getByRole("button", { name: "route" }).click();
  await expect(modes.getByRole("button", { name: "route" })).toHaveClass(/active/);
  await modes.getByRole("button", { name: "pan" }).click();
  await expect(modes.getByRole("button", { name: "pan" })).toHaveClass(/active/);

  await page.keyboard.press("Escape");
  await expect(modes.getByRole("button", { name: "select" })).toHaveClass(/active/);
});

test("downloads and reopens a portable circuit file", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Example").selectOption("datapath");
  await expect(page.locator(".react-flow__node")).toHaveCount(2);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download file" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("standalone_datapath.circuit.json");
  const filePath = await download.path();
  expect(filePath).not.toBeNull();

  await page.getByLabel("Example").selectOption("fanout");
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
  await page.getByLabel("Circuit file").setInputFiles(filePath!);

  await expect(page.locator(".react-flow__node")).toHaveCount(2);
  await expect(page.locator(".notice")).toContainText("standalone_datapath.circuit.json");
  await expect(page.locator(".library")).toContainText("permanent changes are saved by downloading a new file");
});

test("rejects an invalid file without replacing the current circuit", async ({ page }) => {
  await page.goto("/");
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
  expect(download.suggestedFilename()).toBe("standalone_subsystem.circuit.json");
  const filePath = await download.path();
  expect(filePath).not.toBeNull();
  const saved = JSON.parse(await readFile(filePath!, "utf8")) as {
    components: Array<{ id: string }>;
    design: { instances: Array<{ component_id: string }> };
  };
  expect(saved.components.some((component) => component.id === "inspection_block")).toBe(true);
  expect(saved.design.instances.some((instance) => instance.component_id === "inspection_block")).toBe(true);
  await expect(page.locator(".notice")).toContainText("downloaded standalone_subsystem.circuit.json");
});

test("distinguishes true junctions from geometric crossings", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Example").selectOption("fanout");
  await expect(page.locator(".cd-net__junction")).not.toHaveCount(0);
  await page.getByLabel("Example").selectOption("crossing");
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
  await expect(page.locator(".cd-net__junction")).toHaveCount(0);
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
});

import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { readFileSync } from "node:fs";
import type { Page } from "@playwright/test";
import { test, expect, root, type Stack } from "./fixtures.js";

const api = "/api/verification/v1";
function seed(stack: Stack, stage: string): any {
  const result = spawnSync(join(root, ".venv/bin/python"), [join(root, "tests/ui-scenarios/e2e/seed_planner.py"), stack.planner, stage], { env: stack.env, encoding: "utf8" });
  expect(result.status, result.stderr).toBe(0);
  return JSON.parse(result.stdout);
}
async function open(page: Page, stack: Stack, plan: string): Promise<void> {
  await page.goto(stack.planner);
  await page.locator("#planSelector").selectOption(plan);
  const selected = await get(stack, `/plans/${plan}`);
  await expect(page.locator("#breadcrumbPath")).toHaveText(selected.plan.name);
}
async function get(stack: Stack, path: string): Promise<any> {
  const response = await fetch(`${stack.planner}${api}${path}`);
  expect(response.ok).toBe(true); return response.json();
}

for (const [sample, button] of [["FIFO", "btnSampleFifo"], ["Two-FIFO", "btnSampleTwoFifo"]]) {
  test(`creates a Test Plan from the sample source through the UI (${sample})`, async ({ page, stack }) => {
    await page.goto(stack.planner);
    await page.locator("#btnNewPlan").click();
    const imported = page.waitForResponse(response => response.url().endsWith(`${api}/source-imports`) && response.request().method() === "POST");
    await page.locator(`#${button}`).click();
    const source = await (await imported).json();
    await expect(page.locator("#btnSubmitNewPlan")).toBeEnabled();
    const selectedScope = await page.locator("#newPlanScope").inputValue();
    await page.locator("#newPlanName").fill("Browser sample plan");
    const dialogs: string[] = [];
    page.on("dialog", async dialog => { dialogs.push(dialog.message()); await dialog.accept(); });
    await page.locator("#btnSubmitNewPlan").click();
    await expect(page.locator("#modalNewPlan")).not.toHaveClass(/open/);
    expect(dialogs).toEqual([]);
    const plans = await get(stack, "/plans");
    expect(plans).toHaveLength(1);
    expect(plans[0].name).toBe("Browser sample plan");
    expect(plans[0].snapshot_id).toBe(source.snapshot_id);
    expect(plans[0].root_scope_id).toBe(selectedScope);
  });
}

test("authors a Section and draft intent and preserves them across restart", async ({ page, stack }) => {
  const data = seed(stack, "draft");
  await open(page, stack, data.plan_id);
  await page.locator("#btnAddSection").click();
  await page.locator("#secFormTitle").fill("Reset review");
  await page.locator("#btnSaveSection").click();
  await expect(page.locator("#modalSection")).not.toHaveClass(/open/);
  await page.locator("#btnAddIntent").click();
  await page.locator("#intentFormTitle").fill("Reset clears state");
  const section = (await get(stack, `/plans/${data.plan_id}/records`)).find((record: any) => record.title === "Reset review");
  expect(section).toBeTruthy();
  await page.locator("#intentFormSection").selectOption(section.id);
  await page.locator("#btnSaveIntentDraft").click();
  await expect(page.locator("#modalIntent")).not.toHaveClass(/open/);
  const records = await get(stack, `/plans/${data.plan_id}/records`);
  expect(records.find((record: any) => record.record_type === "intent")).toMatchObject({ title: "Reset clears state", authoring_state: "draft" });
  await page.locator("#btnReviewPlanHeader").click();
  await expect(page.locator("#reviewBlockersList")).not.toBeEmpty();
  await expect(page.locator("#btnConfirmReviewCheckpoint")).toBeDisabled();
  await stack.restart("verification");
  await open(page, stack, data.plan_id);
  expect(await get(stack, `/plans/${data.plan_id}/records`)).toEqual(records);
});

test("rejects ready intent authoring with missing fields and preserves the draft", async ({ page, stack }) => {
  const data = seed(stack, "draft");
  await open(page, stack, data.plan_id);
  await page.locator("#btnAddIntent").click();
  await page.locator("#intentFormTitle").fill("Incomplete intent");
  const message = page.waitForEvent("dialog");
  await page.locator("#btnSaveIntentReady").click();
  const dialog = await message;
  expect(dialog.message()).toContain("Failed to save intent"); await dialog.accept();
  await expect(page.locator("#intentFormTitle")).toHaveValue("Incomplete intent");
  expect(await get(stack, `/plans/${data.plan_id}/records`)).toEqual([]);
  await page.locator("#btnSaveIntentDraft").click();
  await expect(page.locator("#modalIntent")).not.toHaveClass(/open/);
});

test("reviews a ready plan and freezes P1 across restart", async ({ page, stack }) => {
  const data = seed(stack, "authoring");
  await open(page, stack, data.plan_id);
  page.on("dialog", async dialog => await dialog.accept(dialog.type() === "prompt" ? "bundle" : undefined));
  await page.locator("#btnReviewPlanHeader").click();
  await expect(page.locator("#btnConfirmReviewCheckpoint")).toBeEnabled();
  await page.locator("#btnConfirmReviewCheckpoint").click();
  await expect(page.locator("#modalReview")).not.toHaveClass(/open/);
  const checkpoints = await get(stack, `/plans/${data.plan_id}/checkpoints`);
  expect(checkpoints).toHaveLength(1);
  expect(checkpoints[0].layer).toBe("plan");
  await stack.restart("verification");
  await open(page, stack, data.plan_id);
  expect(await get(stack, `/plans/${data.plan_id}/checkpoints`)).toEqual(checkpoints);
});

for (const [format, extension] of [["bundle", "vplan"], ["markdown", "md"], ["csv", "csv"]]) {
  test(`exports ${format === "bundle" ? "a bundle" : format} through the supported UI command`, async ({ page, context, stack }) => {
    const data = seed(stack, "draft");
    await open(page, stack, data.plan_id);
    page.on("dialog", dialog => dialog.accept(format));
    const responseEvent = context.waitForEvent("response", { predicate: response => response.url().includes(`/plans/${data.plan_id}/exports`) });
    const downloadEvent = page.waitForEvent("download");
    // Retain a caught promise if an HTTP contract failure occurs before a download.
    void downloadEvent.catch(() => {});
    await page.locator("#btnExportHeader").click();
    const response = await responseEvent;
    expect(response.ok(), `Export request failed with HTTP ${response.status()}`).toBe(true);
    expect(response.request().method()).toBe("POST");
    const download = await downloadEvent;
    const bundle = await download.path();
    expect(bundle).not.toBeNull();
    expect(download.suggestedFilename().endsWith("." + extension)).toBe(true);
    expect(readFileSync(bundle!).length).toBeGreaterThan(0);
    if (format === "bundle") expect(readFileSync(bundle!).subarray(0, 2).toString()).toBe("PK");
  });
}

test("imports a real exported bundle through the UI and reopens its copy", async ({ page, stack }) => {
  const data = seed(stack, "evidence");
  const exported = await fetch(`${stack.planner}${api}/plans/${data.plan_id}/exports`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ format: "bundle" }),
  });
  expect(exported.ok).toBe(true);
  const bundle = Buffer.from(await exported.arrayBuffer());
  const before = await get(stack, `/plans/${data.plan_id}/records`);
  await open(page, stack, data.plan_id);
  page.on("dialog", dialog => dialog.accept());
  const chooser = page.waitForEvent("filechooser");
  await page.locator("#btnImportBundle").click();
  await (await chooser).setFiles({ name: "roundtrip.vplan", mimeType: "application/zip", buffer: bundle });
  await expect.poll(async () => (await get(stack, "/plans")).length).toBe(2);
  const imported = (await get(stack, "/plans")).find((plan: any) => plan.id !== data.plan_id);
  expect(imported).toBeTruthy();
  await stack.restart("verification");
  await open(page, stack, imported.id);
  const records = await get(stack, `/plans/${imported.id}/records`);
  expect(records.map((record: any) => [record.record_type, record.title])).toEqual(before.map((record: any) => [record.record_type, record.title]));
});

test("reviews ready evidence coverage and freezes its next immutable C1 checkpoint", async ({ page, stack }) => {
  const data = seed(stack, "evidence");
  const before = await get(stack, `/plans/${data.plan_id}/checkpoints`);
  await open(page, stack, data.plan_id);
  await page.locator('.layer-tab[data-layer="coverage"]').click();
  await page.locator("#btnReviewCoverage").click();
  await expect(page.locator("#btnConfirmReviewCoverage")).toBeEnabled();
  page.once("dialog", dialog => dialog.accept());
  await page.locator("#btnConfirmReviewCoverage").click();
  await expect(page.locator("#modalReviewCoverage")).not.toHaveClass(/open/);
  const saved = await get(stack, `/plans/${data.plan_id}/checkpoints`);
  expect(saved).toHaveLength(before.length + 1);
  for (const checkpoint of before) expect(saved.find((item: any) => item.id === checkpoint.id)).toEqual(checkpoint);
  await stack.restart("verification");
  expect(await get(stack, `/plans/${data.plan_id}/checkpoints`)).toEqual(saved);
});

test("invalid result text cannot enable evidence commitment", async ({ page, stack }) => {
  const data = seed(stack, "evidence");
  await open(page, stack, data.plan_id);
  await page.locator('.layer-tab[data-layer="coverage"]').click();
  await page.locator("#btnImportResults").click();
  await page.locator("#importResultJson").fill("{invalid result JSON");
  const messages: string[] = [];
  page.once("dialog", async dialog => { messages.push(dialog.message()); await dialog.accept(); });
  await page.locator("#btnStageImportPreview").click();
  expect(messages).toEqual(["Invalid JSON format."]);
  await expect(page.locator("#btnCommitImport")).toBeDisabled();
  expect(await get(stack, `/plans/${data.plan_id}/runs`)).toEqual([]);
});

test("stages synthetic evidence before commit and reopens the committed run", async ({ page, stack }) => {
  const data = seed(stack, "evidence");
  await open(page, stack, data.plan_id);
  await page.locator('.layer-tab[data-layer="coverage"]').click();
  await page.locator("#btnImportResults").click();
  await expect(page.locator("#btnCommitImport")).toBeDisabled();
  await page.locator("#importResultJson").fill(JSON.stringify(data.results));
  await page.locator("#btnStageImportPreview").click();
  await expect(page.locator("#importPreviewBox")).toContainText("Validation Preview");
  await expect(page.locator("#btnCommitImport")).toBeEnabled();
  expect(await get(stack, `/plans/${data.plan_id}/runs`)).toEqual([]);
  page.once("dialog", dialog => dialog.accept());
  await page.locator("#btnCommitImport").click();
  await expect(page.locator("#modalImportResults")).not.toHaveClass(/open/);
  const runs = await get(stack, `/plans/${data.plan_id}/runs`);
  expect(runs).toHaveLength(1);
  await stack.restart("verification");
  await open(page, stack, data.plan_id);
  expect(await get(stack, `/plans/${data.plan_id}/runs`)).toEqual(runs);
});

test("preflights reference recipes, freezes I1, and produces labelled reference artifacts", async ({ page, stack }) => {
  const data = seed(stack, "implementation");
  await open(page, stack, data.plan_id);
  await page.locator('.layer-tab[data-layer="implementation"]').click();
  await expect(page.locator("#recipesTableBody")).toContainText("Browser reference recipe");
  page.on("dialog", dialog => dialog.accept());
  await page.locator("#btnReviewImplementation").click();
  await expect(page.locator("#btnConfirmReviewImplementation")).toBeEnabled();
  await page.locator("#btnConfirmReviewImplementation").click();
  await expect(page.locator("#modalReviewImplementation")).not.toHaveClass(/open/);
  await page.locator("#btnGenerateArtifacts").click();
  await page.locator("#btnRunGenPreview").click();
  await expect(page.locator("#genPreviewFeedback")).toContainText(/no executable|reference/i);
  await page.locator("#btnSubmitGeneration").click();
  await expect(page.locator("#genArtifactsList")).toContainText("synthetic-result-template.json");
  const document = page.locator("#genArtifactsList li").filter({ hasText: "recipe.md" });
  const event = page.waitForEvent("download");
  await document.getByRole("link", { name: "Download", exact: true }).click();
  const download = await event;
  const artifactPath = await download.path();
  const { readFileSync } = await import("node:fs");
  expect(readFileSync(artifactPath!, "utf8")).toContain("no executable tests");
  const generations = await get(stack, `/plans/${data.plan_id}/generations`);
  expect(generations).toHaveLength(1);
  expect(generations[0].status).toBe("succeeded");
  await stack.restart("verification");
  await open(page, stack, data.plan_id);
  expect(await get(stack, `/plans/${data.plan_id}/generations`)).toEqual(generations);
});

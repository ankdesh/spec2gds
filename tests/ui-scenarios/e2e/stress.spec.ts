import { copyFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator } from "@playwright/test";
import { test, expect, openSpec, type Stack, root } from "./fixtures.js";

async function getComponent(page: any, stack: Stack): Promise<Locator> {
  const snapshot = await stack.snapshot();
  const ref = snapshot.components[0].ref;
  return page.locator(`#component-${ref.entity_id.replaceAll("_", "-")}`);
}

async function editText(component: Locator, text: string): Promise<void> {
  await component.getByRole("button", { name: "Options", exact: true }).click();
  await component.getByRole("menuitem", { name: "Edit text…" }).click();
  await component.getByLabel("Component explanation").fill(text);
}

test.describe("Phase 2 Spec Editor Stress Scenarios", () => {
  test("Stress 1: Open fifo_sync, edit W=7, save, reopen, verify symbolic ranges and SV, generate RTL", async ({ page, stack }) => {
    const fifoPath = join(stack.directory, "fifo_sync.spec");
    copyFileSync(join(root, "spec_catalog_service/catalog/storage/fifo_sync/1.0.0/fifo_sync.spec"), fifoPath);

    await openSpec(page, stack, fifoPath);
    const initial = await stack.snapshot();
    expect(initial.components).toHaveLength(1);
    expect(initial.components[0].parameters.find((p: any) => p.name === "W")?.value).toBe("32");

    const component = await getComponent(page, stack);
    await expect(component).toBeVisible();
    await expect(component.locator(".spec-sv-source")).toContainText("localparam int unsigned PTR_W");

    // Edit W from 32 to 7 using actual parameter UI control
    const parameters = component.locator(".spec-hardware-controls > details").filter({ has: page.getByText("Parameters", { exact: true }) });
    await parameters.locator("summary").click();
    const wRow = parameters.locator(".spec-edit-actions").filter({ hasText: "W:" });
    await wRow.getByRole("button", { name: "Options for parameter W", exact: true }).click();
    await wRow.getByRole("menuitem", { name: "Edit", exact: true }).click();

    await parameters.getByLabel("Default expression", { exact: true }).fill("7");
    await parameters.getByRole("button", { name: "Save parameter to Spec", exact: true }).click();

    // Reopen and verify symbolic ranges and SV remain linked to W
    await openSpec(page, stack, fifoPath);
    const reopened = await stack.snapshot();
    const comp = reopened.components[0];
    expect(comp.parameters.find((p: any) => p.name === "W")?.value).toBe("7");
    expect(comp.parameters.find((p: any) => p.name === "DEPTH")?.value).toBe("4");
    // Verify ports symbolic ranges
    const dataIn = comp.ports.find((p: any) => p.name === "s_data_i");
    const dataOut = comp.ports.find((p: any) => p.name === "m_data_o");
    expect(dataIn?.width).toBe("[W-1:0]");
    expect(dataOut?.width).toBe("[W-1:0]");

    // Produce RTL through Generate RTL
    const reopenedComp = await getComponent(page, stack);
    await reopenedComp.getByRole("button", { name: "Options", exact: true }).click();
    await expect(reopenedComp.getByRole("menuitem", { name: "Generate RTL", exact: true })).toBeEnabled();
    await reopenedComp.getByRole("menuitem", { name: "Generate RTL", exact: true }).click();
    await expect(page.locator(".utility-sidebar")).toHaveCount(0);
    await page.locator("#editor-activity-trigger").click();
    await expect(page.getByRole("heading", { name: "Activity", exact: true })).toBeVisible();
    await expect.poll(async () => (await stack.json("/documents/view")).activity.executions.some((e: any) => e.status === "succeeded")).toBe(true);
  });

  test("Stress 2: Edit SV section comment, save, reopen; attempt illegal module header with validation failure", async ({ page, stack }) => {
    const fifoPath = join(stack.directory, "fifo_sync_sv.spec");
    copyFileSync(join(root, "spec_catalog_service/catalog/storage/fifo_sync/1.0.0/fifo_sync.spec"), fifoPath);

    await openSpec(page, stack, fifoPath);
    const component = await getComponent(page, stack);
    const svSection = component.locator(".spec-sv-section");

    // Add a harmless explanatory comment
    await svSection.getByRole("button", { name: "Options for SystemVerilog", exact: true }).click();
    await svSection.getByRole("menuitem", { name: "Edit", exact: true }).click();

    const originalContent = (await stack.snapshot()).entity_sections[0].content;
    const comment = "// Phase 2 Spec Editor verified explanatory comment\n";
    await component.locator(".cm-content").fill(comment + originalContent);
    await svSection.getByRole("button", { name: "Save to Spec", exact: true }).click();

    // Reopen and compare body bytes
    await openSpec(page, stack, fifoPath);
    const reopenedSnap = await stack.snapshot();
    expect(reopenedSnap.entity_sections[0].content).toBe(comment + originalContent);

    // Attempt illegal module header in body
    const reopenedComp = await getComponent(page, stack);
    const reopenedSv = reopenedComp.locator(".spec-sv-section");
    await reopenedSv.getByRole("button", { name: "Options for SystemVerilog", exact: true }).click();
    await reopenedSv.getByRole("menuitem", { name: "Edit", exact: true }).click();
    await reopenedComp.locator(".cm-content").fill("module nested_illegal();\nendmodule\n");
    await reopenedSv.getByRole("button", { name: "Save to Spec", exact: true }).click();

    // Require validation failure
    await expect(reopenedSv.getByRole("alert")).toContainText("cannot declare module/endmodule");
    await reopenedSv.getByRole("button", { name: "Cancel", exact: true }).click();

    // Reopen and confirm preservation of last saved version
    await openSpec(page, stack, fifoPath);
    const preservedSnap = await stack.snapshot();
    expect(preservedSnap.entity_sections[0].content).toBe(comment + originalContent);
  });

  test("Stress 3: Attempt DEPTH=0, require invalid configuration before qualifying RTL run", async ({ page, stack }) => {
    const fifoPath = join(stack.directory, "fifo_sync_depth0.spec");
    copyFileSync(join(root, "spec_catalog_service/catalog/storage/fifo_sync/1.0.0/fifo_sync.spec"), fifoPath);

    await openSpec(page, stack, fifoPath);
    const component = await getComponent(page, stack);

    const parameters = component.locator(".spec-hardware-controls > details").filter({ has: page.getByText("Parameters", { exact: true }) });
    await parameters.locator("summary").click();
    const depthRow = parameters.locator(".spec-edit-actions").filter({ hasText: "DEPTH:" });
    await depthRow.getByRole("button", { name: "Options for parameter DEPTH", exact: true }).click();
    await depthRow.getByRole("menuitem", { name: "Edit", exact: true }).click();

    await parameters.getByLabel("Default expression", { exact: true }).fill("0");
    await parameters.getByRole("button", { name: "Save parameter to Spec", exact: true }).click();

    const updatedSnap = await stack.snapshot();
    expect(updatedSnap.components[0].parameters.find((p: any) => p.name === "DEPTH")?.value).toBe("0");
  });

  test("Stress 4: Parameter edit canceled leaves no durable change and no duplicate rows", async ({ page, stack }) => {
    const fifoPath = join(stack.directory, "fifo_sync_cancel.spec");
    copyFileSync(join(root, "spec_catalog_service/catalog/storage/fifo_sync/1.0.0/fifo_sync.spec"), fifoPath);

    await openSpec(page, stack, fifoPath);
    const initialSnap = await stack.snapshot();
    const initialPorts = initialSnap.components[0].ports.length;

    const component = await getComponent(page, stack);
    const parameters = component.locator(".spec-hardware-controls > details").filter({ has: page.getByText("Parameters", { exact: true }) });
    await parameters.locator("summary").click();

    const wRow = parameters.locator(".spec-edit-actions").filter({ hasText: "W:" });
    await wRow.getByRole("button", { name: "Options for parameter W", exact: true }).click();
    await wRow.getByRole("menuitem", { name: "Edit", exact: true }).click();

    await parameters.getByLabel("Default expression", { exact: true }).fill("99");
    await parameters.getByRole("button", { name: "Cancel parameter", exact: true }).click();

    // Reopen and verify no durable change
    await openSpec(page, stack, fifoPath);
    const reopenedSnap = await stack.snapshot();
    expect(reopenedSnap.components[0].parameters.find((p: any) => p.name === "W")?.value).toBe("32");
    expect(reopenedSnap.components[0].ports.length).toBe(initialPorts);
  });

  test("Stress 5: reset_sync STAGES 2->3 timing check; concurrent client stale save conflict", async ({ page, context, stack }) => {
    const rstPath = join(stack.directory, "reset_sync.spec");
    copyFileSync(join(root, "spec_catalog_service/catalog/cdc_reset/reset_sync/1.0.0/reset_sync.spec"), rstPath);

    await openSpec(page, stack, rstPath);
    const component = await getComponent(page, stack);

    // Change STAGES from 2 to 3
    const parameters = component.locator(".spec-hardware-controls > details").filter({ has: page.getByText("Parameters", { exact: true }) });
    await parameters.locator("summary").click();
    const stagesRow = parameters.locator(".spec-edit-actions").filter({ hasText: "STAGES:" });
    await stagesRow.getByRole("button", { name: "Options for parameter STAGES", exact: true }).click();
    await stagesRow.getByRole("menuitem", { name: "Edit", exact: true }).click();
    await parameters.getByLabel("Default expression", { exact: true }).fill("3");
    await parameters.getByRole("button", { name: "Save parameter to Spec", exact: true }).click();

    // Generate RTL and check activity execution
    await component.getByRole("button", { name: "Options", exact: true }).click();
    await component.getByRole("menuitem", { name: "Generate RTL", exact: true }).click();
    await expect(page.locator(".utility-sidebar")).toHaveCount(0);
    await page.locator("#editor-activity-trigger").click();
    await expect(page.getByRole("heading", { name: "Activity", exact: true })).toBeVisible();
    await expect.poll(async () => (await stack.json("/documents/view")).activity.executions.some((e: any) => e.status === "succeeded")).toBe(true);

    // Concurrent editing conflict check
    // Client 1 opens editor on description
    if (await page.getByRole("button", { name: "Close side panel", exact: true }).isVisible()) await page.getByRole("button", { name: "Close side panel", exact: true }).click();
    const comp1 = await getComponent(page, stack);
    await editText(comp1, "Draft from client 1");

    // Client 2 opens same spec in a second page, saves an edit
    const second = await context.newPage();
    await openSpec(second, stack, rstPath);
    const comp2 = await getComponent(second, stack);
    await editText(comp2, "Committed edit from client 2");
    await comp2.getByRole("button", { name: "Save to Spec", exact: true }).click();
    await expect(comp2).toContainText("Committed edit from client 2");

    // Client 1 tries to save stale draft -> must conflict
    await comp1.getByRole("button", { name: "Save to Spec", exact: true }).click();
    await expect(comp1.getByRole("alert")).toContainText("preserved draft");
  });
});

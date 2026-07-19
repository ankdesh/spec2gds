import { expect, test } from "@playwright/test";

test("loads and edits an independent example", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("circuit-canvas")).toBeVisible();
  await expect(page.getByTestId("layout-time")).toContainText("ELK");
  await page.locator(".react-flow__node").first().click();
  await expect(page.getByTestId("inspector")).toContainText("node");
  await page.getByLabel("Example").selectOption("fanout");
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
  await page.locator(".react-flow__node").first().click();
  await page.getByRole("button", { name: "Duplicate block" }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(5);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
});

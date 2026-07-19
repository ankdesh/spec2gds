import { expect, test } from "@playwright/test";

test("loads fixtures and selects a component", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("circuit-canvas")).toBeVisible();
  await expect(page.getByTestId("layout-time")).toContainText("ELK");
  await page.locator(".react-flow__node").first().click();
  await expect(page.getByTestId("inspector")).toContainText("node");
  await page.getByLabel("Fixture").selectOption("hyperedge");
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
});

import { expect, test } from "@playwright/test";

test("loads and edits an independent example", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("circuit-canvas")).toBeVisible();
  await expect(page.getByTestId("layout-time")).toContainText("Grid router");
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

test("keeps select, connect, route, and pan gestures mutually exclusive", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Select" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".cd-net__hit-segment")).toHaveCount(0);

  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(page.getByRole("button", { name: "Connect", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".cd-net__hit-segment")).toHaveCount(0);

  await page.getByRole("button", { name: "Route", exact: true }).click();
  await expect(page.locator(".cd-net__hit-segment").first()).toBeVisible();
  await expect(page.locator(".cd-net__route-handle").first()).toBeVisible();

  await page.getByRole("button", { name: "Pan", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pan", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".cd-net__hit-segment")).toHaveCount(0);

  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Select" })).toHaveAttribute("aria-pressed", "true");
});

test("edits an orthogonal segment as one undoable route command", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Example").selectOption("datapath");
  await page.getByRole("button", { name: "Route", exact: true }).click();
  const segment = page.locator('.cd-net__hit-segment[data-movable="true"]').first();
  await expect(segment).toBeVisible();
  const visible = page.locator(".cd-net__segment").nth(await segment.evaluate((element) => [...element.parentElement!.querySelectorAll(".cd-net__hit-segment")].indexOf(element)));
  const before = await visible.getAttribute("d");
  const box = await segment.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.mouse.down();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2 + 40, { steps: 5 });
  await page.mouse.up();
  await expect(page.locator(".notice")).toContainText("Manual route saved");
  await expect(page.getByRole("button", { name: "Undo" })).toBeEnabled();
  expect(await visible.getAttribute("d")).not.toBe(before);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.locator(".notice")).toContainText("Undid");
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

test("moves and locks ports from the inspector", async ({ page }) => {
  await page.goto("/");
  await page.locator(".react-flow__node").first().click();
  const port = page.locator(".port-card").first();
  await expect(port).toBeVisible();
  const side = port.locator("select");
  await side.selectOption("NORTH");
  await expect(page.locator(".notice")).toContainText("Moved port");
  await expect(side).toHaveValue("NORTH");
  await expect(port.getByRole("button", { name: "Unlock" })).toBeVisible();
});

test("rerouting unlocked nets does not move component geometry", async ({ page }) => {
  await page.goto("/");
  const before = await page.locator(".react-flow__node").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("style")));
  await page.getByRole("button", { name: "Reroute unlocked nets" }).click();
  await expect(page.locator(".notice")).toContainText("Routes optimized without moving blocks");
  const after = await page.locator(".react-flow__node").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("style")));
  expect(after).toEqual(before);
});

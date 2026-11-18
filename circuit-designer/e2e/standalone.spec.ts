import { resolveConfig, endpointUrl } from "../../runtime/service-config.mjs";
import { mkdirSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { createServer, type Server } from "node:http";
import { join } from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createDefaultCircuitDesignerPreferences, simpleDocumentFixture } from "@spec2gds/circuit-core";

const registry = resolveConfig(process.env.SPEC2GDS_TEST_SERVICE_CONFIG);
const circuitApiUrl = endpointUrl(registry.circuit_designer.service, registry.public_host, { local: true });

test("extends one net by connected-pin drag and dialog with local recovery", async ({ page, request }) => {
  const document = simpleDocumentFixture();
  document.document_id = `fanout_${Date.now()}`;
  document.label = document.document_id;
  for (const component of document.components) component.terminals[0].width = 16;
  for (let index = 1; index <= 3; index += 1) document.design.instances.push({ ...document.design.instances[1], id: `consumer_${index}`, label: `Sink ${index}` });
  expect((await request.post(`${circuitApiUrl}/documents`, { data: { request_id: document.document_id, document } })).ok()).toBe(true);
  expect((await request.put(`${circuitApiUrl}/documents/${document.document_id}/source-binding`, { data: {
    callback_url: `http://127.0.0.1:${sourceProviderPort}/source/`, token: "fanout-test",
    binding: { schema_version: 1, binding_id: `binding_${document.document_id}`, source_document_id: "fanout_spec",
      source_entity: { document_id: "fanout_spec", entity_id: "top", entity_kind: "design" }, editable_design_id: "top",
      base_source_revision_hash: "base", writable: true, capabilities: ["topology", "layout"], omitted_bus_items: [], omitted_ports: [] },
  } })).ok()).toBe(true);
  await page.goto(`/?document_id=${document.document_id}`);
  await expect(page.locator('.react-flow__node[data-id="consumer_3"]')).toBeInViewport({ ratio: 0.999999 });
  await menuAction(page, "Edit", "Begin editing");
  await connectTerminals(page, "producer_0:data", "consumer_1:data");
  await expect(page.locator(".notice")).toContainText("Endpoint added");
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
  await menuAction(page, "Edit", /Undo/);
  await menuAction(page, "Edit", /Redo/);
  await menuAction(page, "Connect", "New connection");
  await page.getByLabel("Connection action").selectOption("existing");
  await page.getByLabel("Existing net", { exact: true }).selectOption("data");
  await page.getByLabel("To port", { exact: true }).selectOption("consumer_2:data");
  if (await page.locator(".connection-advanced").getAttribute("open") === null) await page.getByText("Advanced: connect selected bits", { exact: true }).click();
  await page.getByLabel("Width (0=full)").fill("17");
  await expect(page.getByRole("button", { name: "Add endpoint", exact: true })).toBeDisabled();
  await expect(page.getByRole("status", { name: "Connection guidance" })).toContainText(/width/i);
  await expect(page.getByLabel("To port", { exact: true })).toHaveValue("consumer_2:data");
  if (await page.locator(".connection-advanced").getAttribute("open") === null) await page.getByText("Advanced: connect selected bits", { exact: true }).click();
  await page.getByLabel("Width (0=full)").fill("16");
  await expect(page.getByLabel("Connection mapping")).toContainText("16 bits");
  await page.getByRole("button", { name: "Add endpoint", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(page.locator(".notice")).toContainText("Changes saved to the source");
  const saved = await (await request.get(`${circuitApiUrl}/documents/${document.document_id}`)).json();
  expect(saved.document.design.nets).toHaveLength(1);
  expect(saved.document.design.nets[0]).toMatchObject({ id: "data", label: "data" });
  expect(saved.document.design.nets[0].endpoints).toHaveLength(4);
  await page.reload();
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
  const svgDownload = page.waitForEvent("download");
  await menuAction(page, "File", "Download");
  await page.getByRole("menuitem", { name: /SVG/ }).click();
  const svg = await readFile((await (await svgDownload).path())!, "utf8");
  expect(svg).toContain("Sink 1");
  expect(svg).toContain("Sink 2");
});

test("previews a scalar to high bus bit and preserves independent endpoint mappings", async ({ page, request }) => {
  const document = simpleDocumentFixture();
  document.document_id = `scalar_mapping_${Date.now()}`;
  document.label = document.document_id;
  document.design.nets = [];
  document.design.boundary_terminals = [{ id: "cin", label: "cin", direction: "input", width: 1, category: "port" }];
  document.components[1].terminals[0].width = 65;
  await publishEditableFixture(request, document);
  await page.goto(`/?document_id=${document.document_id}`);
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Connect", "New connection");
  await page.getByLabel("From port", { exact: true }).selectOption("boundary:cin");
  await page.getByLabel("To port", { exact: true }).selectOption("consumer_0:data");
  if (await page.locator(".connection-advanced").getAttribute("open") === null) await page.getByText("Advanced: connect selected bits", { exact: true }).click();
  await page.getByLabel("LSB for B", { exact: true }).fill("64");
  if (await page.locator(".connection-advanced").getAttribute("open") === null) await page.getByText("Advanced: connect selected bits", { exact: true }).click();
  await page.getByLabel("Width (0=full)").fill("2");
  await expect(page.getByRole("button", { name: "Connect", exact: true })).toBeDisabled();
  await expect(page.getByRole("status", { name: "Connection guidance" })).toContainText(/width|range|slice/i);
  await expect(page.getByLabel("LSB for B", { exact: true })).toHaveValue("64");
  if (await page.locator(".connection-advanced").getAttribute("open") === null) await page.getByText("Advanced: connect selected bits", { exact: true }).click();
  await page.getByLabel("Width (0=full)").fill("1");
  await expect(page.getByLabel("Connection mapping")).toContainText(/cin.*→.*data\[64\].*1 bit/);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(page.locator(".notice")).toContainText("Changes saved to the source");
  const saved = await (await request.get(`${circuitApiUrl}/documents/${document.document_id}`)).json();
  expect(saved.document.design.nets[0].endpoints).toEqual([
    { kind: "boundary", terminal_id: "cin" },
    { kind: "instance", instance_id: "consumer_0", terminal_id: "data", slice: { lsb: 64, width: 1 } },
  ]);
  expect(saved.document.components[1].terminals[0].width).toBe(65);
});

test("prevents multiple drivers and out-of-bounds slices before submission without losing the draft", async ({ page, request }) => {
  const document = simpleDocumentFixture();
  document.document_id = `invalid_connection_${Date.now()}`;
  document.label = document.document_id;
  document.design.nets = [];
  document.design.instances.push({ ...document.design.instances[0], id: "producer_1", label: "Second producer" });
  await publishEditableFixture(request, document);
  await page.goto(`/?document_id=${document.document_id}`);
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Connect", "New connection");
  await page.getByLabel("Net label", { exact: true }).fill("invalid_drivers");
  await page.getByLabel("From port", { exact: true }).selectOption("producer_0:data");
  await page.getByLabel("To port", { exact: true }).selectOption("producer_1:data");
  await expect(page.getByRole("status", { name: "Connection guidance" })).toContainText(/source|driver/i);
  await expect(page.getByRole("button", { name: "Connect", exact: true })).toBeDisabled();
  await expect(page.getByLabel("Net label", { exact: true })).toHaveValue("invalid_drivers");
  await page.getByLabel("To port", { exact: true }).selectOption("consumer_0:data");
  if (await page.locator(".connection-advanced").getAttribute("open") === null) await page.getByText("Advanced: connect selected bits", { exact: true }).click();
  await page.getByLabel("LSB for B").fill("40");
  if (await page.locator(".connection-advanced").getAttribute("open") === null) await page.getByText("Advanced: connect selected bits", { exact: true }).click();
  await page.getByLabel("Width (0=full)").fill("1");
  await expect(page.getByRole("button", { name: "Connect", exact: true })).toBeDisabled();
  await expect(page.getByRole("status", { name: "Connection guidance" })).toContainText(/width|range|slice/i);
  await expect(page.getByLabel("LSB for B")).toHaveValue("40");
  for (const theme of ["blueprint-slate", "obsidian"]) {
    if (await page.locator(".cd-app").getAttribute("data-theme") !== theme) {
      // Reopen the dialog after changing the host theme.
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: /Switch theme/ }).click();
      await menuAction(page, "Connect", "New connection");
      await page.getByLabel("From port", { exact: true }).selectOption("producer_0:data");
      await page.getByLabel("To port", { exact: true }).selectOption("consumer_0:data");
    }
    await expect(page.locator(".cd-app")).toHaveAttribute("data-theme", theme);
    for (const [width, height] of [[1440, 900], [1024, 768], [560, 760]]) {
      await page.setViewportSize({ width, height });
      await expect(page.getByRole("dialog")).toBeInViewport();
      await expect(page.getByRole("dialog").getByRole("button", { name: "Connect", exact: true })).toBeInViewport();
      const colors = await page.locator(".circuit-dialog input").first().evaluate(element => ({
        background: getComputedStyle(element).backgroundColor,
        expected: getComputedStyle(element.closest(".cd-app")!).getPropertyValue("--cd-surface").trim(),
      }));
      expect(colors.background).toBe(theme === "obsidian" ? "rgb(24, 24, 27)" : "rgb(255, 255, 255)");
      await page.screenshot({ path: test.info().outputPath(`connection-${theme}-${width}.png`) });
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  const saved = await (await request.get(`${circuitApiUrl}/documents/${document.document_id}`)).json();
  expect(saved.document.design.nets).toEqual([]);
  if (await page.locator(".connection-advanced").getAttribute("open") === null) await page.getByText("Advanced: connect selected bits", { exact: true }).click();
  await page.getByLabel("LSB for B").fill("0");
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

let sourceProvider: Server;
let sourceProviderPort = 0;
let sourceProviderCalls: string[] = [];

test.beforeAll(async () => {
  sourceProvider = createServer((request, response) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      if (request.url === "/source/renew") {
        response.setHeader("Content-Type", "application/json");
        response.end(JSON.stringify({ mode: "edit" }));
        return;
      }
      sourceProviderCalls.push(request.url ?? "");
      const body = JSON.parse(Buffer.concat(chunks).toString()) as {
        candidate_document: ReturnType<typeof simpleDocumentFixture>;
      };
      response.setHeader("Content-Type", "application/json");
      response.end(JSON.stringify({
        accepted: true,
        source_revision_hash: "sha256:source-roundtrip-saved",
        document: body.candidate_document,
        diagnostics: [],
      }));
    });
  });
  await new Promise<void>((resolve) => sourceProvider.listen(0, "127.0.0.1", resolve));
  const address = sourceProvider.address();
  sourceProviderPort = typeof address === "object" && address ? address.port : 0;
});

test.afterAll(async () => {
  await new Promise<void>((resolve) => sourceProvider.close(() => resolve()));
});

async function menuAction(page: Page, menu: string, action: string | RegExp): Promise<void> {
  if (!await page.getByRole("menuitem", { name: menu, exact: true }).isVisible()) await page.getByRole("menuitem", { name: "Commands", exact: true }).click();
  await page.getByRole("menuitem", { name: menu, exact: true }).click();
  await page.getByRole("menuitem", typeof action === "string" ? { name: action, exact: true } : { name: action }).click();
}

async function connectTerminals(page: Page, sourceKey: string, targetKey: string) {
  const source = page.locator(`.react-flow__handle[data-handleid="${sourceKey}"]`);
  const target = page.locator(`.react-flow__handle[data-handleid="${targetKey}"]`);
  const before = (await source.boundingBox())!;
  await source.hover();
  const hovered = (await source.boundingBox())!;
  expect(hovered.x).toBeCloseTo(before.x, 1);
  expect(hovered.y).toBeCloseTo(before.y, 1);
  await page.mouse.move(hovered.x + hovered.width / 2, hovered.y + hovered.height / 2);
  expect(await source.evaluate(element => {
    const bounds = element.getBoundingClientRect();
    return document.elementFromPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)?.closest(".react-flow__handle")?.getAttribute("data-handleid");
  })).toBe(sourceKey);
  await page.mouse.down();
  try {
    const box = (await target.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 12 });
    await expect(source).toHaveClass(/connectingfrom/);
    await expect(target).toHaveClass(/valid/);
  } finally { await page.mouse.up(); }
}

async function publishEditableFixture(request: APIRequestContext, document: ReturnType<typeof simpleDocumentFixture>) {
  const created = await request.post(`${circuitApiUrl}/documents`, { data: { request_id: document.document_id, document } });
  expect(created.ok(), await created.text()).toBe(true);
  const binding = await request.put(`${circuitApiUrl}/documents/${document.document_id}/source-binding`, { data: {
    callback_url: `http://127.0.0.1:${sourceProviderPort}/source/`, token: "focused-fixture",
    binding: { schema_version: 1, binding_id: `binding_${document.document_id}`, source_document_id: document.document_id,
      source_entity: { document_id: document.document_id, entity_id: "top", entity_kind: "design" }, editable_design_id: "top",
      base_source_revision_hash: "base", writable: true, capabilities: ["topology", "layout", "local-components"], omitted_bus_items: [], omitted_ports: [] },
  } });
  expect(binding.ok(), await binding.text()).toBe(true);
}

test.beforeEach(async ({ request }) => {
  const response = await request.put(`${circuitApiUrl}/preferences`, {
    data: createDefaultCircuitDesignerPreferences(),
  });
  expect(response.ok()).toBe(true);
});

function stackedCircuitFixture() {
  const document = simpleDocumentFixture();
  document.document_id = `arrange_${Date.now()}`;
  document.label = document.document_id;
  for (const component of document.components) {
    component.terminals[0].width = 16;
    component.terminals.push({ id: "clk", label: "clk", direction: "input", width: 1, category: "port" });
  }
  document.design.boundary_terminals = [
    { id: "clk", label: "shared_clock", direction: "input", width: 1, category: "port" },
    { id: "result", label: "result", direction: "output", width: 16, category: "port" },
  ];
  document.design.nets[0].endpoints.push({ kind: "boundary", terminal_id: "result" });
  document.design.nets.push({ id: "clock", label: "clock", endpoints: [
    { kind: "instance", instance_id: "consumer_0", terminal_id: "clk" },
    { kind: "instance", instance_id: "producer_0", terminal_id: "clk" },
    { kind: "boundary", terminal_id: "clk" },
  ] });
  document.layout.instance_geometry = {
    producer_0: { x: 80, y: 80, width: 180, height: 140, pinned: false },
    consumer_0: { x: 80, y: 780, width: 180, height: 140, pinned: false },
  };
  document.layout.net_routes = {};
  document.layout.terminal_placements = {};
  return document;
}

test("fits loaded circuits in both themes and saves the accepted Arrange geometry", async ({ page, request }, testInfo) => {
  test.setTimeout(60_000);
  const document = stackedCircuitFixture();
  await publishEditableFixture(request, document);
  for (const theme of ["blueprint-slate", "obsidian"]) {
    const preferences = createDefaultCircuitDesignerPreferences();
    preferences.ui.theme_id = theme;
    expect((await request.put(`${circuitApiUrl}/preferences`, { data: preferences })).ok()).toBe(true);
    for (const size of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 560, height: 760 }]) {
      await page.setViewportSize(size);
      await page.goto(`/?document_id=${document.document_id}`);
      await expect(page.locator(".cd-app")).toHaveAttribute("data-theme", theme);
      await expect(page.locator(".react-flow__node")).toHaveCount(4);
      await expect.poll(async () => {
        const canvas = await page.getByTestId("circuit-canvas").boundingBox();
        const boxes = await page.locator(".react-flow__node, .cd-node__port-label").evaluateAll(elements => elements.map(element => {
          const box = element.getBoundingClientRect(); return { x: box.x, y: box.y, right: box.right, bottom: box.bottom };
        }));
        return !!canvas && boxes.every(box => box.x >= canvas.x && box.y >= canvas.y && box.right <= canvas.x + canvas.width && box.bottom <= canvas.y + canvas.height);
      }).toBe(true);
      const label = page.locator('.react-flow__node[data-id="producer_0"] .cd-node__port-label').filter({ hasText: "16b" });
      await label.focus();
      await expect(label).toHaveAttribute("title", "data · 16 bits");
      await page.screenshot({ path: testInfo.outputPath(`circuit-${theme}-${size.width}.png`) });
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await menuAction(page, "Edit", "Begin editing");
  // Arrange must replace an existing close-up view, not fit only on reopen.
  await page.locator(".react-flow__pane").hover({ position: { x: 500, y: 300 } });
  await page.mouse.wheel(0, -700);
  await menuAction(page, "Route", "Arrange and route all");
  await expect(page.locator(".notice")).toContainText("Automatic layout completed");
  await expect.poll(async () => {
    const bounds = await page.getByTestId("circuit-canvas").boundingBox();
    const boxes = await page.locator(".react-flow__node, .cd-node__port-label").evaluateAll(elements => elements.map(element => {
      const rect = element.getBoundingClientRect(); return { x: rect.x, y: rect.y, right: rect.right, bottom: rect.bottom };
    }));
    return !!bounds && boxes.every(box => box.x >= bounds.x && box.y >= bounds.y && box.right <= bounds.x + bounds.width && box.bottom <= bounds.y + bounds.height);
  }).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("immediate-arrange-fit.png") });
  const producer = page.locator('.react-flow__node[data-id="producer_0"]');
  const consumer = page.locator('.react-flow__node[data-id="consumer_0"]');
  await expect.poll(async () => (await producer.boundingBox())!.x < (await consumer.boundingBox())!.x).toBe(true);
  await menuAction(page, "Edit", /Undo/);
  await expect.poll(async () => Math.abs((await producer.boundingBox())!.x - (await consumer.boundingBox())!.x)).toBeLessThan(1);
  await menuAction(page, "Edit", /Redo/);
  await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(page.locator(".notice")).toContainText("Changes saved to the source");
  const saved = await (await request.get(`${circuitApiUrl}/documents/${document.document_id}`)).json();
  expect(saved.document.layout.instance_geometry.producer_0.x).toBeLessThan(saved.document.layout.instance_geometry.consumer_0.x);
  expect(saved.document.design.nets).toEqual(document.design.nets);
  await page.reload();
  await expect.poll(async () => (await producer.boundingBox())!.x < (await consumer.boundingBox())!.x).toBe(true);
  // Allow Chromium's subpixel rounding on scaled, fully visible labels.
  await expect(page.locator('.cd-node__port-label[aria-label="shared_clock"]')).toBeInViewport({ ratio: 0.999999 });
  for (const theme of ["obsidian", "blueprint-slate"]) {
    if (await page.locator(".cd-app").getAttribute("data-theme") !== theme) await page.locator(".topbar .theme-quick-toggle").click();
    await expect(page.locator(".cd-app")).toHaveAttribute("data-theme", theme);
    await page.screenshot({ path: testInfo.outputPath(`arranged-${theme}-1440.png`) });
  }
});

test("places named instances with local duplicate validation and preserves numbered labels", async ({ page, request }, testInfo) => {
  const document = stackedCircuitFixture();
  document.components[1].label = "Enabled eight-bit register";
  document.design.instances[1].label = "enabled_eight_bit_register_12";
  await publishEditableFixture(request, document);
  await page.goto(`/?document_id=${document.document_id}`);
  const node = page.locator('.react-flow__node[data-id="consumer_0"]');
  await expect(node.locator(".cd-node__eyebrow")).toHaveText("Enabled eight-bit register");
  await expect(node.locator(".cd-node__title")).toContainText(/…_12$/);
  await node.locator(".cd-node__title").focus();
  await expect(node.locator(".cd-node__title")).toHaveAttribute("title", "enabled_eight_bit_register_12");
  const titleBounds = (await node.locator(".cd-node__title").boundingBox())!;
  const suffixBounds = (await node.locator(".cd-node__instance-suffix").boundingBox())!;
  expect(suffixBounds.x + suffixBounds.width).toBeLessThanOrEqual(titleBounds.x + titleBounds.width + 0.5);
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Components", "Component catalog");
  await page.locator(".catalog-list").getByRole("button", { name: /Enabled eight-bit register/ }).click();
  const name = page.getByLabel("Instance name (optional)", { exact: true });
  await name.fill("enabled_eight_bit_register_12");
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText("already exists");
  await expect(page.getByRole("button", { name: "Place instance", exact: true })).toBeDisabled();
  await name.fill("u_lane4");
  await page.getByRole("button", { name: "Place instance", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator('.react-flow__node[data-id="u_lane4"] .cd-node__title')).toHaveText("u_lane4");
  await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(page.locator(".notice")).toContainText("Changes saved to the source");
  const saved = await (await request.get(`${circuitApiUrl}/documents/${document.document_id}`)).json();
  expect(saved.document.design.instances.at(-1)).toMatchObject({ id: "u_lane4", label: "u_lane4", component_id: document.components[1].id });
  await page.reload();
  await expect(page.locator('.react-flow__node[data-id="u_lane4"] .cd-node__title')).toHaveText("u_lane4");
  await expect(page.locator('.react-flow__node[data-id="consumer_0"]')).toBeInViewport({ ratio: 0.999999 });
  await expect(page.locator('.cd-node__port-label[aria-label="shared_clock"]')).toBeInViewport({ ratio: 0.999999 });
  await page.screenshot({ path: testInfo.outputPath("named-instances.png") });
});

test("places two distinct cycle markers through the UI and retains them after save", async ({ page, request }, testInfo) => {
  const document = stackedCircuitFixture();
  document.layout.instance_geometry.consumer_0 = { x: 800, y: 80, width: 180, height: 140, pinned: false };
  await publishEditableFixture(request, document);
  await page.goto(`/?document_id=${document.document_id}`);
  await expect(page.locator('.react-flow__node[data-id="consumer_0"]')).toBeInViewport({ ratio: 0.999999 });
  await menuAction(page, "Edit", "Begin editing");
  for (const x of [400, 640]) {
    await menuAction(page, "Timing", "Add cycle edge");
    const point = await page.evaluate(({ x, y }) => {
      const canvas = document.querySelector('[data-testid="circuit-canvas"]')!.getBoundingClientRect();
      const viewport = document.querySelector(".react-flow__viewport")!;
      const matrix = new DOMMatrix(getComputedStyle(viewport).transform);
      return { x: canvas.x + matrix.e + x * matrix.a, y: canvas.y + matrix.f + y * matrix.d };
    }, { x, y: 350 });
    await page.mouse.click(point.x, point.y);
    await expect(page.locator(".notice")).toContainText(`Added cycle edge at x=${x}`);
  }
  await expect(page.locator(".cd-cycle-edge")).toHaveCount(2);
  await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(page.locator(".notice")).toContainText("Changes saved to the source");
  const saved = await (await request.get(`${circuitApiUrl}/documents/${document.document_id}`)).json();
  expect(saved.document.timing.cycle_edges.map((edge: { x: number }) => edge.x)).toEqual([400, 640]);
  await page.reload();
  await expect(page.locator(".cd-cycle-edge")).toHaveCount(2);
  await page.screenshot({ path: testInfo.outputPath("two-cycle-markers.png") });
});

test("ignores an Arrange result after another draft edit", async ({ page, request }) => {
  await page.addInitScript(() => {
    const NativeWorker = window.Worker;
    window.Worker = class extends NativeWorker {
      postMessage(message: unknown, transfer?: Transferable[]) {
        if ((message as { type?: string }).type === "layout") {
          (window as Window & { releaseArrange?: () => void }).releaseArrange = () => super.postMessage(message, transfer ?? []);
        } else super.postMessage(message, transfer ?? []);
      }
    };
  });
  const document = stackedCircuitFixture();
  await publishEditableFixture(request, document);
  await page.goto(`/?document_id=${document.document_id}`);
  await expect(page.locator('.cd-node__port-label[aria-label="shared_clock"]')).toBeInViewport({ ratio: 0.999999 });
  const viewport = page.locator(".react-flow__viewport");
  const initialViewport = await viewport.getAttribute("style");
  const pane = (await page.locator(".react-flow__pane").boundingBox())!;
  await page.mouse.move(pane.x + pane.width - 140, pane.y + pane.height - 140);
  await page.mouse.down();
  await page.mouse.move(pane.x + pane.width - 100, pane.y + pane.height - 120, { steps: 6 });
  await page.mouse.up();
  await expect.poll(() => viewport.getAttribute("style")).not.toBe(initialViewport);
  const manualViewport = await viewport.getAttribute("style");
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Route", "Arrange and route all");
  await expect.poll(() => page.evaluate(() => !!(window as Window & { releaseArrange?: () => void }).releaseArrange)).toBe(true);
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Late edit");
  await page.getByRole("button", { name: "Add to Design", exact: true }).click();
  await expect(viewport).toHaveAttribute("style", manualViewport!);
  await page.evaluate(() => (window as Window & { releaseArrange?: () => void }).releaseArrange!());
  await expect(page.locator(".notice")).toContainText("Local component and first instance created");
  await expect(viewport).toHaveAttribute("style", manualViewport!);
  await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(page.locator(".notice")).toContainText("Changes saved to the source");
  const saved = await (await request.get(`${circuitApiUrl}/documents/${document.document_id}`)).json();
  expect(saved.document.design.instances).toHaveLength(3);
  expect(saved.document.layout.instance_geometry.producer_0.x).toBe(80);
  expect(saved.document.layout.instance_geometry.consumer_0.x).toBe(80);
});

test("uses a compact menubar and the reclaimed full-width canvas", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("circuit-canvas")).toBeVisible();
  const appBox = await page.locator(".cd-app").boundingBox();
  const canvasBox = await page.locator(".canvas-surface").boundingBox();
  expect(appBox?.height).toBeGreaterThan(500);
  expect(canvasBox?.height).toBeGreaterThan(400);
  await expect(page.locator(".notice")).toContainText("Untitled circuit");
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  await expect(page.locator(".library")).toHaveCount(0);
  await expect(page.locator(".canvas-action-bar")).toHaveCount(0);
  await expect(page.locator(".inspector")).toHaveCount(0);
  for (const name of ["File", "Edit", "Components", "Selection", "Connect", "Route", "Timing", "View", "Tools", "Help"]) {
    await expect(page.getByRole("menuitem", { name, exact: true })).toBeVisible();
  }
  await page.getByRole("menuitem", { name: "Connect", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: "New connection", exact: true })).toBeDisabled();
});

test("supports keyboard navigation, nested submenus, dismissal, and focus restoration", async ({ page }) => {
  await page.goto("/");
  const file = page.getByRole("menuitem", { name: "File", exact: true });
  await file.focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("menu", { name: "File" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: /New circuit/ })).toBeFocused();
  await page.keyboard.press("End");
  await expect(page.getByRole("menuitem", { name: "Download", exact: true })).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("menu", { name: "Download" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: /Download Circuit JSON/ })).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("menu", { name: "Download" })).toHaveCount(0);
  await expect(page.getByRole("menuitem", { name: "Download", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu", { name: "File" })).toHaveCount(0);
  await expect(file).toBeFocused();

  await page.getByRole("menuitem", { name: "Selection", exact: true }).click();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("menu", { name: "Connect" })).toBeVisible();
  await page.locator(".canvas-surface").click({ position: { x: 10, y: 10 } });
  await expect(page.getByRole("menu", { name: "Connect" })).toHaveCount(0);

  const help = page.getByRole("menuitem", { name: "Help", exact: true });
  await help.focus();
  await page.keyboard.press("Space");
  await expect(page.getByRole("menu", { name: "Help" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu", { name: "Help" })).toHaveCount(0);
  await expect(help).toBeFocused();
  const tools = page.getByRole("menuitem", { name: "Tools", exact: true });
  await tools.focus();
  await expect(tools).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("menu", { name: "Tools" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(tools).toBeFocused();
});

test("launches former sidebar and action-strip workflows from menus", async ({ page }) => {
  await page.goto("/");
  await menuAction(page, "Components", "Component catalog");
  await expect(page.getByRole("dialog", { name: "Component catalog" })).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  await menuAction(page, "Edit", "Begin editing");
  await expect(page.locator(".document-status")).toContainText("Editing · No changes");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Producer");
  await page.getByRole("button", { name: "Add to Design" }).click();
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Consumer");
  await page.getByRole("button", { name: "Add to Design" }).click();

  await menuAction(page, "Selection", /Select all/);
  await page.getByRole("menuitem", { name: "View", exact: true }).click();
  await page.getByRole("menuitemcheckbox", { name: /Show Inspector/ }).click();
  await expect(page.locator(".inspector")).toContainText("2 items selected");
  await menuAction(page, "Selection", /Clear selection/);
  // The automatic frame keeps the current viewport while content grows.
  await menuAction(page, "View", "Fit circuit");

  const source = page.locator('.react-flow__handle[data-handleid="producer:output"]');
  const target = page.locator('.react-flow__handle[data-handleid="consumer:input"]');
  await source.dragTo(target);
  await expect(page.locator(".notice")).toContainText("Created net");

  await menuAction(page, "Connect", "New connection");
  await page.getByLabel("From port").selectOption("producer:input");
  await page.getByLabel("To port").selectOption("consumer:output");
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(page.locator(".notice")).toContainText("Created net");
});

test("edits a writable specification binding and saves it through source preview and commit", async ({ page, request }) => {
  sourceProviderCalls = [];
  const document = simpleDocumentFixture();
  const uniqueId = `source_roundtrip_${Date.now()}`;
  document.document_id = uniqueId;
  document.label = uniqueId;
  const created = await request.post(`${circuitApiUrl}/documents`, {
    data: { request_id: `create_${document.document_id}`, document },
  });
  expect(created.ok()).toBe(true);
  const registered = await request.put(`${circuitApiUrl}/documents/${document.document_id}/source-binding`, {
    data: {
      callback_url: `http://127.0.0.1:${sourceProviderPort}/source/`,
      token: "browser-source-token",
      binding: {
        schema_version: 1,
        binding_id: `binding_${document.document_id}`,
        source_document_id: "browser_spec",
        source_entity: { document_id: "browser_spec", entity_id: "design_top", entity_kind: "design" },
        editable_design_id: "design_top",
        base_source_revision_hash: "sha256:source-roundtrip-base",
        writable: true,
        capabilities: ["topology", "layout", "local-components"],
        omitted_bus_items: [],
        omitted_ports: [],
      },
    },
  });
  expect(registered.ok()).toBe(true);

  await page.goto(`/?document_id=${document.document_id}`);
  await expect(page.locator(".document-status")).toContainText("Viewing");
  await menuAction(page, "Edit", "Begin editing");
  await expect(page.locator(".document-status")).toContainText("Editing · No changes");

  const pane = page.locator(".react-flow__pane");
  const emptyPoint = await pane.evaluate(element => {
    const box = element.getBoundingClientRect();
    for (const point of [{ x: box.width - 80, y: box.height - 80 }, { x: 80, y: 80 }, { x: box.width - 80, y: 80 }]) {
      if (document.elementFromPoint(box.x + point.x, box.y + point.y) === element) return point;
    }
    throw new Error("No empty canvas point is visible.");
  });
  await pane.click({ button: "right", position: emptyPoint });
  const createLocal = page.getByRole("menuitem", { name: "New local component…", exact: true });
  await expect(createLocal).toBeEnabled();
  await createLocal.click();
  await page.getByLabel("Name", { exact: true }).fill("spec_block");
  await expect(page.getByText("VLNV: spec2gds.local:work:spec_block:1.0")).not.toBeVisible();
  await page.getByRole("button", { name: "Add to Design" }).click();

  const save = page.getByRole("button", { name: "Save to Spec", exact: true });
  await expect(save).toBeVisible();
  await save.click();
  await expect(page.getByRole("status", { name: "Circuit save state" })).toHaveText("Saved");
  await expect(page.locator(".notice")).toContainText("Changes saved to the source");
  expect(sourceProviderCalls).toEqual(["/source/preview", "/source/commit"]);
});

test("preserves independent endpoint offsets when creating a bus connection", async ({ page, request }) => {
  const document = simpleDocumentFixture();
  document.document_id = `slice_offsets_${Date.now()}`;
  document.design.nets = [];
  for (const component of document.components) component.terminals[0].width = 16;
  const created = await request.post(`${circuitApiUrl}/documents`, { data: { request_id: document.document_id, document } });
  expect(created.ok()).toBe(true);
  const binding = await request.put(`${circuitApiUrl}/documents/${document.document_id}/source-binding`, { data: {
    callback_url: `http://127.0.0.1:${sourceProviderPort}/source/`, token: "browser-slice-token",
    binding: { schema_version: 1, binding_id: `binding_${document.document_id}`, source_document_id: "slice_spec",
      source_entity: { document_id: "slice_spec", entity_id: "design_top", entity_kind: "design" },
      editable_design_id: "design_top", base_source_revision_hash: "sha256:slice-base", writable: true,
      capabilities: ["topology", "layout"], omitted_bus_items: [], omitted_ports: [] },
  } });
  expect(binding.ok()).toBe(true);
  await page.goto(`/?document_id=${document.document_id}`);
  await expect(page.locator(".document-status")).toContainText("Viewing");
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Connect", "New connection");
  await page.getByLabel("Net label", { exact: true }).fill("upper_to_lower");
  await page.getByLabel("From port", { exact: true }).selectOption("producer_0:data");
  await page.getByLabel("To port", { exact: true }).selectOption("consumer_0:data");
  if (await page.locator(".connection-advanced").getAttribute("open") === null) await page.getByText("Advanced: connect selected bits", { exact: true }).click();
  await page.getByLabel("LSB for A", { exact: true }).fill("8");
  if (await page.locator(".connection-advanced").getAttribute("open") === null) await page.getByText("Advanced: connect selected bits", { exact: true }).click();
  await page.getByLabel("LSB for B", { exact: true }).fill("0");
  if (await page.locator(".connection-advanced").getAttribute("open") === null) await page.getByText("Advanced: connect selected bits", { exact: true }).click();
  await page.getByLabel("Width (0=full)", { exact: true }).fill("8");
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
  await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
  await expect(page.locator(".notice")).toContainText("Changes saved to the source");
  const saved = await request.get(`${circuitApiUrl}/documents/${document.document_id}`);
  const snapshot = await saved.json();
  expect(snapshot.document.design.nets[0].endpoints.map((item: any) => item.slice)).toEqual([{ lsb: 8, width: 8 }, { lsb: 0, width: 8 }]);
  await page.reload();
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
});

test("cancelling an unchanged draft preserves saved routes and source", async ({ page, request }) => {
  const document = simpleDocumentFixture();
  document.document_id = `cancel_routes_${Date.now()}`;
  document.label = document.document_id;
  const created = await request.post(`${circuitApiUrl}/documents`, { data: { request_id: document.document_id, document } });
  expect(created.ok()).toBe(true);
  const binding = await request.put(`${circuitApiUrl}/documents/${document.document_id}/source-binding`, { data: {
    callback_url: `http://127.0.0.1:${sourceProviderPort}/source/`, token: "browser-cancel-token",
    binding: { schema_version: 1, binding_id: `binding_${document.document_id}`, source_document_id: "cancel_spec",
      source_entity: { document_id: "cancel_spec", entity_id: "design_top", entity_kind: "design" },
      editable_design_id: "design_top", base_source_revision_hash: "sha256:cancel-base", writable: true,
      capabilities: ["topology", "layout"], omitted_bus_items: [], omitted_ports: [] },
  } });
  expect(binding.ok()).toBe(true);
  const before = await (await request.get(`${circuitApiUrl}/documents/${document.document_id}`)).json();
  await page.goto(`/?document_id=${document.document_id}`);
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
  await menuAction(page, "Edit", "Begin editing");
  await expect(page.locator(".notice")).toContainText("Private draft opened");
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
  await menuAction(page, "File", "Cancel changes");
  await expect(page.locator(".notice")).toContainText("Draft cancelled");
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
  const after = await (await request.get(`${circuitApiUrl}/documents/${document.document_id}`)).json();
  expect(after).toEqual(before);
});

test("saves shortcuts and Inspector visibility in the browser", async ({ page, request }) => {
  const defaults = await (await request.get(`${circuitApiUrl}/preferences`)).json();
  await page.goto("/");
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Preferences", exact: true }).click();
  await page.getByRole("menuitem", { name: /Actions and shortcuts/ }).click();
  await expect(page.getByRole("heading", { name: "Circuit Designer preferences" })).toBeVisible();
  await expect(page.getByLabel("Select all keyboard shortcut")).toHaveText("Ctrl/⌘ A");
  await expect(page.getByLabel("Drag canvas mouse shortcut")).toHaveValue("primary-drag");

  await page.getByLabel("Fit circuit keyboard shortcut").focus();
  await page.keyboard.press("f");
  await page.getByLabel("New connection keyboard shortcut").focus();
  await page.keyboard.press("c");
  await page.getByRole("checkbox", { name: /Show Inspector/ }).check();
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem("spec2gds.circuit.preferences.v1") || "null")?.ui.inspector_open)).toBe(true);
  await expect(page.locator(".action-settings").getByRole("status")).toContainText("Saved");
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.locator(".inspector")).toBeVisible();

  await page.reload();
  await expect(page.locator(".inspector")).toBeVisible();
  await menuAction(page, "Edit", "Begin editing");
  await expect(page.locator(".document-status")).toContainText("Editing · No changes");
  await page.keyboard.press("c");
  await expect(page.getByRole("dialog", { name: "Connect ports" })).toBeVisible();

  const preferences = await page.evaluate(() => JSON.parse(localStorage.getItem("spec2gds.circuit.preferences.v1")!));
  expect(preferences.ui.inspector_open).toBe(true);
  expect(preferences.action_bindings["fit-circuit"].keyboard).toBe("F");
  expect(preferences.action_bindings["open-connect"].keyboard).toBe("C");
  expect(await (await request.get(`${circuitApiUrl}/preferences`)).json()).toEqual(defaults);
});

test("pans with left drag while Shift+left-drag remains selection gesture", async ({ page }) => {
  await page.goto("/");
  const pane = page.locator(".react-flow__pane");
  const viewport = page.locator(".react-flow__viewport");
  const bounds = await pane.boundingBox();
  expect(bounds).not.toBeNull();
  const before = await viewport.getAttribute("style");
  await page.mouse.move(bounds!.x + bounds!.width / 2, bounds!.y + bounds!.height / 2);
  await page.mouse.down({ button: "left" });
  await page.mouse.move(bounds!.x + bounds!.width / 2 + 90, bounds!.y + bounds!.height / 2 + 45, { steps: 5 });
  await page.mouse.up({ button: "left" });
  await expect.poll(() => viewport.getAttribute("style")).not.toBe(before);

  const afterPan = await viewport.getAttribute("style");
  await page.keyboard.down("Shift");
  await page.mouse.move(bounds!.x + 100, bounds!.y + 100);
  await page.mouse.down({ button: "left" });
  await page.mouse.move(bounds!.x + 230, bounds!.y + 190, { steps: 4 });
  await page.mouse.up({ button: "left" });
  await page.keyboard.up("Shift");
  await expect(viewport).toHaveAttribute("style", afterPan ?? "");

  await menuAction(page, "Edit", "Begin editing");
  await expect(page.locator(".document-status")).toContainText("Editing · No changes");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Marquee target");
  await page.getByRole("button", { name: "Add to Design" }).click();
  const node = page.locator(".react-flow__node").first();
  await expect(node).toBeVisible();
  const nodeBounds = await node.boundingBox();
  expect(nodeBounds).not.toBeNull();
  await page.keyboard.down("Shift");
  await page.mouse.move(nodeBounds!.x - 12, nodeBounds!.y - 12);
  await page.mouse.down({ button: "left" });
  await page.mouse.move(nodeBounds!.x + nodeBounds!.width + 12, nodeBounds!.y + nodeBounds!.height + 12, { steps: 5 });
  await page.mouse.up({ button: "left" });
  await page.keyboard.up("Shift");
  await expect(node).toHaveClass(/selected/);
});

test("keeps controlled component selection stable after click and Escape", async ({ page }) => {
  await page.goto("/");
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Stable selection");
  await page.getByRole("button", { name: "Add to Design" }).click();
  const node = page.locator(".react-flow__node[data-id='stable_selection']");
  await expect(node).toHaveClass(/selected/);

  await page.keyboard.press("Escape");
  await expect(node).not.toHaveClass(/selected/);
  const changesAfterEscape = await node.evaluate((element) => new Promise<number>((resolve) => {
    let changes = 0;
    const observer = new MutationObserver(() => { changes += 1; });
    observer.observe(element, { attributes: true, attributeFilter: ["class"] });
    window.setTimeout(() => { observer.disconnect(); resolve(changes); }, 450);
  }));
  expect(changesAfterEscape).toBe(0);

  await node.click();
  await expect(node).toHaveClass(/selected/);
  const changesAfterClick = await node.evaluate((element) => new Promise<number>((resolve) => {
    let changes = 0;
    const observer = new MutationObserver(() => { changes += 1; });
    observer.observe(element, { attributes: true, attributeFilter: ["class"] });
    window.setTimeout(() => { observer.disconnect(); resolve(changes); }, 450);
  }));
  expect(changesAfterClick).toBe(0);
});

test("opens clamped semantic context menus from pointer and keyboard", async ({ page }) => {
  await page.goto("/");
  const pane = page.locator(".react-flow__pane");
  const paneBounds = await pane.boundingBox();
  expect(paneBounds).not.toBeNull();

  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await pane.click({ button: "right", position: { x: paneBounds!.width - 20, y: paneBounds!.height - 120 } });
  await expect(page.getByRole("menu", { name: "File" })).toHaveCount(0);
  const contextMenu = page.getByRole("menu", { name: "Circuit context menu" });
  await expect(contextMenu).toBeVisible();
  const menuBounds = await contextMenu.boundingBox();
  const viewport = page.viewportSize();
  expect(menuBounds).not.toBeNull();
  expect(viewport).not.toBeNull();
  expect(menuBounds!.x).toBeGreaterThanOrEqual(8);
  expect(menuBounds!.y).toBeGreaterThanOrEqual(8);
  expect(menuBounds!.x + menuBounds!.width).toBeLessThanOrEqual(viewport!.width - 8);
  expect(menuBounds!.y + menuBounds!.height).toBeLessThanOrEqual(viewport!.height - 8);
  await page.keyboard.press("Escape");
  await expect(contextMenu).toHaveCount(0);

  await menuAction(page, "Edit", "Begin editing");
  const createPoint = { x: 420, y: 280 };
  await pane.click({ button: "right", position: createPoint });
  await page.getByRole("menuitem", { name: "New local component…", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("Pointer block");
  await page.getByRole("button", { name: "Add to Design" }).click();
  const node = page.locator(".react-flow__node[data-id='pointer_block']");
  await expect(node).toBeVisible();
  const nodeBounds = await node.boundingBox();
  expect(nodeBounds).not.toBeNull();
  expect(Math.abs(nodeBounds!.x + nodeBounds!.width / 2 - (paneBounds!.x + createPoint.x))).toBeLessThanOrEqual(25);
  expect(Math.abs(nodeBounds!.y + nodeBounds!.height / 2 - (paneBounds!.y + createPoint.y))).toBeLessThanOrEqual(25);

  await node.click({ button: "right" });
  await expect(node).toHaveClass(/selected/);
  await expect(page.getByRole("menuitem", { name: "Open selected child design", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await node.focus();
  await page.keyboard.press("Shift+F10");
  await expect(page.getByRole("menuitem", { name: "Center selection", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");

  const port = page.locator('.react-flow__handle[data-handleid="pointer_block:input"]');
  await port.click({ button: "right", force: true });
  await expect(page.getByRole("menuitem", { name: "Placement", exact: true })).toBeVisible();
  await page.getByRole("menuitem", { name: "New connection…", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Connect ports" })).toBeVisible();
  await expect(page.getByLabel("From port")).toHaveValue("pointer_block:input");
  await page.getByRole("button", { name: "Close" }).click();

  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Context sink");
  await page.getByRole("button", { name: "Add to Design" }).click();
  await menuAction(page, "Connect", "New connection");
  await page.getByLabel("From port").selectOption("pointer_block:output");
  await page.getByLabel("To port").selectOption("context_sink:input");
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  const connectedPort = page.locator('.react-flow__handle[data-handleid="pointer_block:output"]');
  await connectedPort.click({ button: "right", force: true });
  await expect(page.getByRole("menuitem", { name: "Select connected net", exact: true })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "Disconnect port", exact: true })).toBeVisible();
});

test("places, edits, hides, and exports a cycle timing marker", async ({ page }) => {
  await page.goto("/");
  await menuAction(page, "Edit", "Begin editing");
  const pane = page.locator(".react-flow__pane");
  await pane.click({ button: "right", position: { x: 430, y: 260 } });
  await page.getByRole("menuitem", { name: "Add cycle edge here", exact: true }).click();

  const edge = page.locator(".cd-cycle-edge");
  await expect(edge).toHaveCount(1);
  await expect(edge).toContainText("Cycle edge 1");
  await expect(page.locator(".cd-cycle-edge__leading-stage")).toHaveText("Stage 0");

  await edge.click({ button: "right" });
  await page.getByRole("menuitem", { name: "Edit cycle edge…", exact: true }).click();
  await page.getByLabel("Edge label").fill("Execute edge");
  await page.getByLabel("Following stage label").fill("Writeback");
  await page.getByRole("button", { name: "Apply", exact: true }).click();
  await expect(edge).toContainText("Execute edge");
  await expect(edge).toContainText("Writeback");

  await page.getByRole("menuitem", { name: "View", exact: true }).click();
  await page.getByRole("menuitemcheckbox", { name: /Show timing overlay/ }).click();
  await expect(edge).toHaveCount(0);
  await page.getByRole("menuitem", { name: "View", exact: true }).click();
  await page.getByRole("menuitemcheckbox", { name: /Show timing overlay/ }).click();
  await expect(edge).toHaveCount(1);

  const saveDownload = page.waitForEvent("download");
  await menuAction(page, "File", /Save changes/);
  await saveDownload;
  const svgDownload = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: "Download", exact: true }).click();
  await page.getByRole("menuitem", { name: "Export SVG", exact: true }).click();
  const svgPath = await (await svgDownload).path();
  expect(svgPath).not.toBeNull();
  const svg = await readFile(svgPath!, "utf8");
  expect(svg).toContain('class="cycle-edge"');
  expect(svg).toContain("Execute edge");
  expect(svg).toContain("WRITEBACK");
  expect(svg).toContain("STAGE 0");
});

test("keeps right-drag panning without opening a context menu", async ({ page, request }) => {
  const preferences = createDefaultCircuitDesignerPreferences();
  preferences.action_bindings["pan-canvas"].mouse = "secondary-drag";
  expect((await request.put(`${circuitApiUrl}/preferences`, { data: preferences })).ok()).toBe(true);
  await page.goto("/");
  const pane = page.locator(".react-flow__pane");
  const viewport = page.locator(".react-flow__viewport");
  const bounds = await pane.boundingBox();
  expect(bounds).not.toBeNull();
  const before = await viewport.getAttribute("style");
  await page.mouse.move(bounds!.x + 250, bounds!.y + 180);
  await page.mouse.down({ button: "right" });
  await page.mouse.move(bounds!.x + 330, bounds!.y + 225, { steps: 5 });
  await page.mouse.up({ button: "right" });
  await expect.poll(() => viewport.getAttribute("style")).not.toBe(before);
  await expect(page.getByRole("menu", { name: "Circuit context menu" })).toHaveCount(0);

  await pane.click({ button: "right", position: { x: 200, y: 160 } });
  await expect(page.getByRole("menu", { name: "Circuit context menu" })).toBeVisible();
});

test("downloads and reopens a portable circuit file from File commands", async ({ page }) => {
  await page.goto("/");
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Inspection block");
  await page.getByRole("button", { name: "Add to Design" }).click();

  const downloadPromise = page.waitForEvent("download");
  await menuAction(page, "File", /Save changes/);
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^untitled-circuit(?:-\d+)?\.circuit\.json$/);
  const filePath = await download.path();
  expect(filePath).not.toBeNull();
  const saved = JSON.parse(await readFile(filePath!, "utf8")) as {
    components: Array<{ id: string }>;
    design: { instances: Array<{ component_id: string }> };
  };
  expect(saved.components.some((component) => component.id === "inspection_block")).toBe(true);

  await menuAction(page, "File", /New circuit/);
  await expect(page.locator(".react-flow__node")).toHaveCount(0);
  const chooserPromise = page.waitForEvent("filechooser");
  await menuAction(page, "File", /Open circuit/);
  await (await chooserPromise).setFiles(filePath!);
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await expect(page.locator(".notice")).toContainText("Untitled circuit");
});

test("exports the visible canvas layout consistently to SVG and PNG", async ({ page }) => {
  await page.goto("/");
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Visual export");
  await page.getByRole("button", { name: "Add to Design" }).click();
  const node = page.locator(".react-flow__node[data-id='visual_export']");
  await expect(node).toBeVisible();
  const nodeTransform = await node.evaluate((element) => (element as HTMLElement).style.transform);
  const canvasPosition = nodeTransform.match(/translate\(([-\d.]+)px,\s*([-\d.]+)px\)/);
  expect(canvasPosition).not.toBeNull();

  const saveDownload = page.waitForEvent("download");
  await menuAction(page, "File", /Save changes/);
  await saveDownload;

  const svgDownloadPromise = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: "Download", exact: true }).click();
  await page.getByRole("menuitem", { name: "Export SVG", exact: true }).click();
  const svgPath = await (await svgDownloadPromise).path();
  expect(svgPath).not.toBeNull();
  const svg = await readFile(svgPath!, "utf8");
  const svgBox = svg.match(/<svg[^>]+width="(\d+)"[^>]+height="(\d+)"/);
  const exportedPosition = svg.match(/data-instance-id="visual_export"><rect x="([\d.-]+)" y="([\d.-]+)"/);
  expect(svgBox).not.toBeNull();
  expect(exportedPosition?.slice(1)).toEqual(canvasPosition?.slice(1));
  expect(svg).toContain(".canvas-background{fill:#f7f9fc}");
  expect(svg).toContain('fill="url(#canvas-grid)"');
  expect(svg).toContain('data-terminal-id="visual_export:input"');
  expect(svg).toContain('data-terminal-id="visual_export:output"');

  const pngDownloadPromise = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: "Download", exact: true }).click();
  await page.getByRole("menuitem", { name: "Export PNG", exact: true }).click();
  const pngPath = await (await pngDownloadPromise).path();
  expect(pngPath).not.toBeNull();
  const png = await readFile(pngPath!);
  expect([...png.subarray(0, 8)]).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
  expect(png.readUInt32BE(16)).toBe(Number(svgBox![1]));
  expect(png.readUInt32BE(20)).toBe(Number(svgBox![2]));
  await page.getByRole("button", { name: /Switch theme/ }).click();
  await expect(page.locator(".cd-app")).toHaveAttribute("data-theme", "obsidian");
  const darkSvgDownload = page.waitForEvent("download");
  await menuAction(page, "File", "Download");
  await page.getByRole("menuitem", { name: "Export SVG", exact: true }).click();
  const darkSvg = await readFile((await (await darkSvgDownload).path())!, "utf8");
  expect(darkSvg).toContain(".canvas-background{fill:#09090b}");
  expect(darkSvg).not.toBe(svg);
  const darkPngDownload = page.waitForEvent("download");
  await menuAction(page, "File", "Download");
  await page.getByRole("menuitem", { name: "Export PNG", exact: true }).click();
  const darkPng = await readFile((await (await darkPngDownload).path())!);
  expect(darkPng.equals(png)).toBe(false);
  expect(darkPng.readUInt32BE(16)).toBe(png.readUInt32BE(16));
  expect(darkPng.readUInt32BE(20)).toBe(png.readUInt32BE(20));
});

test("rejects an invalid file without replacing the current circuit", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".notice")).toContainText("Untitled circuit");
  const nodeCount = await page.locator(".react-flow__node").count();
  const chooserPromise = page.waitForEvent("filechooser");
  await menuAction(page, "File", /Open circuit/);
  await (await chooserPromise).setFiles({
    name: "broken.circuit.json",
    mimeType: "application/json",
    buffer: Buffer.from("{"),
  });
  await expect(page.locator(".notice")).toContainText("Could not open broken.circuit.json");
  await expect(page.locator(".react-flow__node")).toHaveCount(nodeCount);
});

test("toggles visual theme via quick toggle and preferences page", async ({ page }) => {
  await page.goto("/");
  // Defaults to blueprint-slate (light canvas)
  await expect(page.locator(".cd-app")).toHaveAttribute("data-theme", "blueprint-slate");
  await page.screenshot({ path: test.info().outputPath("circuit_designer_blueprint_slate.png") });

  // Click topbar quick toggle
  const toggle = page.locator(".topbar .theme-quick-toggle");
  await expect(toggle).toBeVisible();
  await toggle.click();

  // Switched to obsidian
  await expect(page.locator(".cd-app")).toHaveAttribute("data-theme", "obsidian");
  await page.screenshot({ path: test.info().outputPath("circuit_designer_obsidian.png") });

  // Open preferences page
  await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
  await page.getByRole("menuitem", { name: "Preferences", exact: true }).click();
  await page.getByRole("menuitem", { name: /Actions and shortcuts/ }).click();
  await expect(page.locator(".action-settings")).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("circuit_designer_preferences.png") });

  // Switch back to Blueprint Slate in preferences
  await page.locator(".action-settings__theme-card").filter({ hasText: "Blueprint Slate" }).click();
  await expect(page.locator(".action-settings").getByRole("status")).toContainText("Saved");
  await expect(page.locator(".cd-app")).toHaveAttribute("data-theme", "blueprint-slate");

  // Done closes settings
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.locator(".action-settings")).not.toBeVisible();

  // Reload page to verify persistence
  await page.reload();
  await expect(page.locator(".cd-app")).toHaveAttribute("data-theme", "blueprint-slate");
});

test("captures Circuit Designer visual baselines across canvas, menus, dialogs, and viewports", async ({ page }) => {
  const outputDir = process.env.UI_BASELINE_DIR || join(process.cwd(), "tmp/visual-baselines");
  mkdirSync(outputDir, { recursive: true });
  const saveBaseline = async (filename: string) => {
    await page.screenshot({ path: join(outputDir, filename) });
  };

  // 1. Desktop 1440x900 Blueprint Slate
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await menuAction(page, "Edit", "Begin editing");
  await menuAction(page, "Components", "New local component");
  await page.getByLabel("Name", { exact: true }).fill("Baseline block");
  await page.getByRole("button", { name: "Add to Design" }).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await saveBaseline("circuit_designer_blueprint_slate_1440x900.png");

  // 2. Desktop 1440x900 Obsidian (Dark)
  const toggle = page.locator(".topbar .theme-quick-toggle");
  await toggle.click();
  await expect(page.locator(".cd-app")).toHaveAttribute("data-theme", "obsidian");
  await saveBaseline("circuit_designer_obsidian_1440x900.png");

  // 3. Compact 1024x768
  await page.setViewportSize({ width: 1024, height: 768 });
  await saveBaseline("circuit_designer_compact_1024x768.png");

  // Restore desktop size
  await page.setViewportSize({ width: 1440, height: 900 });

  // 4. Action Menubar open state
  await page.getByRole("menuitem", { name: "Components", exact: true }).click();
  await expect(page.getByRole("menu", { name: "Components" })).toBeVisible();
  await saveBaseline("circuit_designer_menu_open.png");

  // 5. About Circuit Designer Dialog
  await page.keyboard.press("Escape");
  await menuAction(page, "Help", "About Circuit Designer");
  const aboutDialog = page.getByRole("dialog", { name: "About Circuit Designer" });
  await expect(aboutDialog).toBeVisible();
  await saveBaseline("circuit_designer_about_dialog.png");
  await page.keyboard.press("Escape");
  await expect(aboutDialog).not.toBeVisible();
});

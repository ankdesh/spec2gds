import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import vm from "node:vm";
import { authenticatedLaunchLocation } from "../src/index.js";

const root = resolve(import.meta.dirname, "..");

test("editor launch uses a relative DSH authentication target and fragment payload", () => {
  const location = authenticatedLaunchLocation(
    { authenticatedUrl: base => `${base}/?token=one-time-secret` },
    "session/with spaces",
  );
  assert.equal(
    location,
    "/?token=one-time-secret#spec2gds_session=session%2Fwith+spaces",
  );
  assert.ok(!location.includes("127.0.0.1"), "redirect must stay on the browser's current authority");
});

test("focused web profile removes the generic DSH provider onboarding plugin", () => {
  const patch = readFileSync(resolve(root, "bundles/web/cordis.patch.yml"), "utf8");
  assert.match(patch, /- id: ui-settings-models\n  disabled: true/);
  assert.doesNotMatch(patch, /showTestingNotice|showDeepSeekOnboarding/);
});

test("product dialog preserves the HTML hidden contract over layout styles", () => {
  const source = readFileSync(resolve(root, "client/index.js"), "utf8");
  assert.match(source, /\.s2g-dialog \[hidden\]\{display:none!important\}/);
});

test("browser plugin owns New Session and consumes launch data from the fragment", async () => {
  let definition: { factory(require: (name: string) => unknown): { apply(ctx: unknown): void } } | undefined;
  let newSessionHandler: Record<string, unknown> | undefined;
  let replaced = "";
  const created: unknown[] = [];
  const opened: unknown[] = [];
  const microtasks: Array<() => unknown> = [];
  const source = readFileSync(resolve(root, "client/index.js"), "utf8");
  const context = {
    URLSearchParams,
    location: {
      pathname: "/",
      search: "",
      hash: "#spec2gds_session=bound-session",
    },
    history: { replaceState: (_state: unknown, _title: string, url: string) => { replaced = url; } },
    document: {
      title: "",
      createElement: () => ({ dataset: {}, textContent: "" }),
      head: { appendChild: () => undefined },
    },
    fetch: async (url: string) => ({ ok: true, json: async () => {
      if (url === "/spec2gds-api/workspaces") return { workspaces: [] };
      if (url === "/spec2gds-api/bindings/bound-session") return { session: {
        sessionId: "bound-session", workspaceKey: "workspace-1", workspaceTitle: "Bound design",
        workspacePath: "/tmp/bound-design", workspaceDomain: "spec",
        workspaceOwnerUrl: "http://127.0.0.1:6010", workspaceDocumentId: "doc-1",
      } };
      return {};
    } }),
    queueMicrotask: (callback: () => unknown) => { microtasks.push(callback); },
    window: {
      alert: (message: unknown) => { throw new Error(`unexpected alert: ${String(message)}`); },
      __ModuleLoader__: { load: (value: typeof definition) => { definition = value; } },
    },
  };
  vm.runInNewContext(source, context, { filename: "client/index.js" });
  assert.ok(definition);
  const plugin = definition.factory(name => {
    assert.equal(name, "react");
    return { createElement: () => null };
  });
  plugin.apply({
    uiSession: { registerNewSessionHandler: (handler: Record<string, unknown>) => { newSessionHandler = handler; } },
    slots: { inject: () => undefined },
    sessions: {
      create: async (value: unknown) => { created.push(value); },
      open: (value: unknown) => { opened.push(value); },
    },
    workspaces: {
      list: { getSnapshot: () => ({ items: [] }) },
      create: async () => ({ workspaceId: "workspace-1", title: "Bound design", path: "/tmp/bound-design" }),
      rename: async () => undefined,
    },
  });

  assert.equal(newSessionHandler?.id, "spec2gds");
  assert.equal(newSessionHandler?.priority, -100);
  assert.equal(context.document.title, "spec2gds Assistant");
  assert.equal(replaced, "/");
  assert.equal(microtasks.length, 2);
  for (const task of microtasks) await task();
  await new Promise(resolvePromise => setImmediate(resolvePromise));
  assert.equal(JSON.stringify(created), JSON.stringify([{ sessionId: "bound-session", workspaceId: "workspace-1" }]));
  assert.deepEqual(opened, ["bound-session"]);
});

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
    "/tmp/spec2gds work",
  );
  assert.equal(
    location,
    "/?token=one-time-secret#spec2gds_session=session%2Fwith+spaces&spec2gds_cwd=%2Ftmp%2Fspec2gds+work",
  );
  assert.ok(!location.includes("127.0.0.1"), "redirect must stay on the browser's current authority");
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
      hash: "#spec2gds_session=bound-session&spec2gds_cwd=%2Ftmp%2Fbound-session",
    },
    history: { replaceState: (_state: unknown, _title: string, url: string) => { replaced = url; } },
    document: {
      title: "",
      createElement: () => ({ dataset: {}, textContent: "" }),
      head: { appendChild: () => undefined },
    },
    fetch: async () => ({ ok: true, json: async () => ({}) }),
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
  });

  assert.equal(newSessionHandler?.id, "spec2gds");
  assert.equal(newSessionHandler?.priority, -100);
  assert.equal(replaced, "/");
  assert.equal(microtasks.length, 1);
  await microtasks[0]?.();
  await new Promise(resolvePromise => setImmediate(resolvePromise));
  assert.equal(JSON.stringify(created), JSON.stringify([{ sessionId: "bound-session", cwd: "/tmp/bound-session" }]));
  assert.deepEqual(opened, ["bound-session"]);
});

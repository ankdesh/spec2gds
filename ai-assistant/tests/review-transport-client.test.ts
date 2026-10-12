import assert from "node:assert/strict";
import test from "node:test";
import vm from "node:vm";
import { readFileSync } from "node:fs";

async function fixture(meta: any, text: string) {
  let definition: any, tracker: any, tail: any;
  let cursor = 0;
  const state: any[] = [], effects: any[] = [], deps = new Map<number, string>();
  const calls: string[] = [];
  let failed = true;
  const review = { proposalId: "proposal", sessionId: "conversation", callId: "call", state: "ready", domain: "circuit",
    artifact: { title: "Large proposal", operations: [] }, preview: { diff: [] }, changeSummary: {}, serviceResult: null };
  const React = {
    createElement: (type: any, props: any, ...children: any[]) => ({ type, props: props || {}, children: children.flat() }),
    useState: (initial: any) => { const i = cursor++; if (!(i in state)) state[i] = initial; return [state[i], (v: any) => { state[i] = typeof v === "function" ? v(state[i]) : v; }]; },
    useEffect: (effect: any, keys: any[]) => { const i = cursor++; const key = JSON.stringify(keys); if (deps.get(i) !== key) { deps.set(i, key); effects.push(effect); } },
  };
  vm.runInNewContext(readFileSync(new URL("../client/index.js", import.meta.url), "utf8"), {
    window: { __ModuleLoader__: { load: (v: any) => { definition = v; } } }, URL, URLSearchParams, setInterval: () => 0, clearInterval() {},
    location: { pathname: "/", search: "", hash: "" }, document: { title: "", createElement: () => ({ dataset: {} }), head: { appendChild() {} } }, queueMicrotask() {},
    fetch: async (path: string) => {
      calls.push(path);
      if (failed) return { ok: false, status: 503, json: async () => ({ error: "Service unavailable" }) };
      return { ok: true, json: async () => path.endsWith("/reviews") ? { reviews: [review] } : { review } };
    },
  });
  definition.factory(() => React).apply({ uiSession: { registerNewSessionHandler() {} },
    uiConversation: { events: { register(v: any) { tracker = v; } } }, sessions: {}, workspaces: {},
    slots: { inject: (_name: string, fn: any) => fn(), register: (options: any, component: any) => { if (options.name === "conversation.chat.turnTail") tail = { options, component }; } },
  });
  let tracking = tracker.start({}, { event: { type: "turn/start", data: { turn: 1 } } });
  tracking = tracker.update({ state: tracking }, { event: { type: "tool/call", data: { callId: "call", name: "prepare_circuit_proposal" } } });
  tracking = tracker.update({ state: tracking }, { event: { type: "tool/result", seq: 3, data: { meta,
    message: { source: { callId: "call" }, content: [{ content: [{ type: "text", text }] }] } } } });
  const location = tracker.buildLocationData({ state: tracking }, "turn", null);
  const matched = tail.options.select({ seq: 4, turn: { data: { get: () => location.value } } });
  const node = tail.component({ matched, sessionId: "conversation" });
  const card = node.type(node.props);
  const render = () => { cursor = 0; return card.type(card.props); };
  const settle = async () => { for (const effect of effects.splice(0)) effect(); await new Promise(resolve => setImmediate(resolve)); };
  return { calls, render, settle, fail(value: boolean) { failed = value; } };
}

for (const legacy of [false, true]) test(`${legacy ? "legacy truncated text" : "durable metadata"} recovers a stored review and gates approval on lookup`, async () => {
  const f = await fixture(legacy ? undefined : { kind: "spec2gds.review", version: 1, sessionId: "conversation", proposalId: "proposal" }, "broken spilled text");
  f.render(); await f.settle();
  let tree = f.render();
  assert.equal(tree.type, "article");
  const button = tree.children.find((node: any) => node?.type === "button");
  assert.equal(button.children[0], "Retry review lookup");
  assert.ok(!JSON.stringify(tree).includes("Save to Spec"));
  f.fail(false); button.props.onClick(); f.render(); await f.settle(); tree = f.render();
  assert.equal(tree.type.name, "ReviewCard");
  assert.equal(tree.props.review.proposalId, "proposal");
  assert.deepEqual(f.calls, [legacy ? "/spec2gds-api/bindings/conversation/reviews" : "/spec2gds-api/bindings/conversation/reviews/proposal",
    legacy ? "/spec2gds-api/bindings/conversation/reviews" : "/spec2gds-api/bindings/conversation/reviews/proposal"]);
});

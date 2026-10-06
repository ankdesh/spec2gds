import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

async function browserFixture(automatic = false) {
  let plugin: any; let events: any; let tail: any;
  const calls: Array<{ path: string; body?: any }> = [];
  const created: any[] = []; const opened: string[] = []; const prompts: any[] = [];
  const request: any = { requestId: "request-1", sourceSessionId: "origin", documentId: "comparator_3bit", title: "Comparator",
    serviceBaseUrl: "http://spec", status: "pending", destination: "/spec-documents/comparator_3bit.spec", specDocumentRoot: "/spec-documents",
    pathSeparator: "/", destinationSessionId: "destination", preset: "focused", error: null,
    services: [{ url: "http://spec", available: true }] };
  const continuation = { requestId: "stable-prompt-id", message: "The package exists. Original user request: A[2:0], B[2:0], A_greater, A_equal, A_less.", sent: false };
  const reservation = { session: { sessionId: "destination", preset: "focused" },
    workspace: { key: "workspace-key", title: "Comparator", path: "/workspace/comparator", domain: "spec", serviceUrl: "http://spec", documentId: "comparator_3bit" },
    creation_request: request, continuation };
  if (automatic) Object.assign(request, { automatic: true, status: "reserved", continuation,
    reservation: { session: reservation.session, workspace: reservation.workspace } });
  const microtasks: Array<() => any> = [];
  let hookCursor = 0; const state: any[] = []; const effects: Array<() => any> = []; const effectKeys = new Map<number, string>();
  const React = {
    createElement: (type: any, props: any, ...children: any[]) => ({ type, props: props ?? {}, children: children.flat() }),
    useState: (initial: any) => { const index = hookCursor++; if (!(index in state)) state[index] = typeof initial === "function" ? initial() : initial;
      return [state[index], (value: any) => { state[index] = typeof value === "function" ? value(state[index]) : value; }]; },
    useEffect: (effect: () => any, deps: any[]) => { const index = hookCursor++; const key = JSON.stringify(deps);
      if (effectKeys.get(index) !== key) { effectKeys.set(index, key); effects.push(effect); } },
  };
  let failPrompt = false;
  const sessionRows: Record<string, any> = {};
  const ctx = {
    uiSession: { registerNewSessionHandler: () => {} },
    uiConversation: { events: { register: (value: any) => { events = value; } } },
    slots: { inject: (_name: string, callback: () => any) => callback(), register: (options: any, component: any) => {
      if (options.name === "conversation.chat.turnTail") tail = { options, component };
    } },
    workspaces: { list: { getSnapshot: () => ({ items: [{ workspaceId: "workspace-1", path: "/workspace/comparator", title: "Comparator" }] }) } },
    sessions: { list: { getSnapshot: () => ({ byId: sessionRows }) },
      create: async (value: any) => { created.push(value); sessionRows[value.sessionId] = { id: value.sessionId }; return value.sessionId; },
      open: (id: string) => { opened.push(id); },
      binding: (id: string) => ({ session: { prompt: async (...args: any[]) => { prompts.push({ id, args }); return failPrompt ? { ok: false, error: { message: "Prompt admission failed" } } : { ok: true }; } } }),
    },
  };
  const context: any = {
    URL, URLSearchParams, location: { pathname: "/", search: "", hash: "" },
    document: { title: "", createElement: () => ({ dataset: {} }), head: { appendChild: () => {} } },
    window: { __ModuleLoader__: { load: (definition: any) => { plugin = definition.factory(() => React); } } },
    queueMicrotask: (callback: () => any) => microtasks.push(callback),
    fetch: async (path: string, options: any) => {
      const body = options.body ? JSON.parse(options.body) : undefined; calls.push({ path, body });
      let value: any;
      if (path.endsWith("/workspaces")) value = { workspaces: [] };
      else if (path.endsWith("/sources/create")) { request.status = "reserved"; value = reservation; }
      else if (path.endsWith("/activate")) value = { session: reservation.session };
      else if (path.endsWith("/continued")) { request.status = "continued"; continuation.sent = true; value = { creation_request: request }; }
      else if (path.endsWith("/cancel")) { request.status = "cancelled"; value = { creation_request: request }; }
      else value = { creation_request: request };
      return { ok: true, json: async () => JSON.parse(JSON.stringify(value)) };
    },
  };
  vm.runInNewContext(readFileSync(new URL("../client/index.js", import.meta.url), "utf8"), context);
  plugin.apply(ctx);
  for (const task of microtasks.splice(0)) await task();
  let tracking = events.start({}, { event: { type: "turn/start", data: { turn: 1 } } });
  tracking = events.update({ state: tracking }, { event: { type: "tool/call", data: { callId: "call", name: "prepare_spec_document_creation" } } });
  tracking = events.update({ state: tracking }, { event: { type: "tool/result", seq: 3, data: { message: { source: { callId: "call" }, content: [{ content: [{ type: "text", text: JSON.stringify({ source_creation: request }) }] }] } } } });
  const location = events.buildLocationData({ state: tracking }, "turn", null);
  const matched = tail.options.select({ seq: 4, turn: { data: { get: () => location.value } } });
  assert.equal(matched.sourceCreation.requestId, "request-1", "Creation cards survive the collapsed tool trace");
  const tailNode = tail.component({ matched }); const cardNode = tailNode.type(tailNode.props);
  const render = () => { hookCursor = 0; return cardNode.type(cardNode.props); };
  const settle = async () => { for (const effect of effects.splice(0)) effect(); await new Promise(resolve => setImmediate(resolve)); for (const task of microtasks.splice(0)) await task(); };
  render(); await settle();
  const nodes = (tree: any): any[] => [tree, ...(tree.children ?? []).filter((child: any) => child && typeof child === "object").flatMap(nodes)];
  return { render, settle, nodes, created, opened, prompts, calls, request, continuation, events, tracking, tail,
    set failPrompt(value: boolean) { failPrompt = value; },
    submit: async () => { const form = nodes(render()).find(node => node.type === "form"); await form.props.onSubmit({ preventDefault() {} }); await settle(); },
  };
}

test("creation footer creates the destination chat and submits the original description there", async () => {
  const f = await browserFixture();
  const tree = f.render();
  assert.ok(f.nodes(tree).some(node => node.type === "code" && node.children[0] === "/spec-documents"));
  await f.submit();
  assert.deepEqual(JSON.parse(JSON.stringify(f.created)), [{ sessionId: "destination", workspaceId: "workspace-1", agentPreset: "focused" }]);
  assert.deepEqual(f.opened, ["destination"]);
  assert.equal(f.prompts.length, 1);
  assert.equal(f.prompts[0].id, "destination");
  assert.equal(f.prompts[0].args[0][0].text, f.continuation.message);
  assert.equal(f.prompts[0].args[3], "stable-prompt-id");
  assert.ok(!f.calls.some(call => call.path.endsWith("/abandon")));
  assert.equal(f.render().props["data-s2g-source-creation"], "continued");
});

test("failed continuation preserves the package reservation and retries with the same prompt identity", async () => {
  const f = await browserFixture(); f.failPrompt = true;
  await f.submit();
  assert.equal(f.opened.length, 0);
  assert.equal(f.render().props["data-s2g-source-creation"], "reserved");
  assert.ok(!f.calls.some(call => call.path.endsWith("/abandon")));
  f.failPrompt = false; await f.submit();
  assert.equal(f.created.length, 1);
  assert.deepEqual(f.prompts.map(prompt => prompt.args[3]), ["stable-prompt-id", "stable-prompt-id"]);
  assert.deepEqual(f.opened, ["destination"]);
});

test("automatic saved creation continues without a form submission", async () => {
  const f = await browserFixture(true);
  f.render(); await f.settle();
  f.render(); await f.settle();
  assert.equal(f.prompts.length, 1);
  assert.equal(f.prompts[0].args[3], "stable-prompt-id");
  assert.deepEqual(f.opened, ["destination"]);
  assert.equal(f.render().props["data-s2g-source-creation"], "continued");
  assert.ok(!f.calls.some(call => call.path.endsWith("/sources/create")));
});

test("cancel keeps the user in the original chat and creates no destination", async () => {
  const f = await browserFixture();
  const button = f.nodes(f.render()).find(node => node.type === "button" && node.children[0] === "Cancel");
  await button.props.onClick();
  assert.equal(f.created.length, 0); assert.equal(f.prompts.length, 0); assert.equal(f.opened.length, 0);
  assert.equal(f.render().props["data-s2g-source-creation"], "cancelled");
});


test("architecture approval cards survive subsequent creation errors and replay", async () => {
  const f = await browserFixture();
  let tracking = f.events.start({}, { event: { type: "turn/start", data: { turn: 2 } } });
  const results = [
    { architecture_review: { reviewId: "review-1", status: "pending", plan: {} } },
    { architecture_review: { reviewId: "review-1", status: "pending", plan: {} } },
    { architecture_review: { reviewId: "review-2", status: "pending", plan: {} } },
    { creation_error: "Supply architecture_review_id." },
  ];
  results.forEach((value, i) => {
    const callId = `call-${i}`;
    tracking = f.events.update({ state: tracking }, { event: { type: "tool/call", data: {
      callId, name: i === 3 ? "prepare_spec_document_creation" : "prepare_architecture_review",
    } } });
    tracking = f.events.update({ state: tracking }, { event: { type: "tool/result", seq: i + 1, data: {
      message: { source: { callId }, content: [{ content: [{ type: "text", text: JSON.stringify(value) }] }] },
    } } });
  });
  const location = f.events.buildLocationData({ state: tracking }, "turn", null);
  const select = (seq: number) => f.tail.options.select({ seq, turn: { data: { get: () => location.value } } });
  const matched = select(5);
  assert.deepEqual(Array.from(matched.earlierArchitectureReviews, (review: any) => review.reviewId), ["review-1", "review-2"]);
  const node = f.tail.component({ matched });
  const tree = node.type(node.props);
  assert.equal(tree.children.filter((child: any) => child.type?.name === "ArchitectureReviewCard").length, 2);
  const latest = tree.children.at(-1);
  assert.equal(latest.type(latest.props).children[0].children[0], "Spec creation unavailable");
  assert.equal(select(3).architectureReview.reviewId, "review-1", "Later results cannot appear before their sequence");
  assert.equal(select(3).earlierArchitectureReviews.length, 0, "Repeated results do not duplicate a review card");
  assert.equal(select(1), null);
});

test("architecture schema failures remain visible after a blocked turn and clear when a retry succeeds", async () => {
  const f = await browserFixture();
  let tracking = f.events.start({}, { event: { type: "turn/start", data: { turn: 2 } } });
  tracking = f.events.update({ state: tracking }, { event: { type: "tool/call", data: {
    turn: 2, callId: "invalid", name: "prepare_architecture_review",
  } } });
  const failure = 'invalid arguments: "components[0].name" is required';
  tracking = f.events.update({ state: tracking }, { event: { type: "tool/result", seq: 3, data: {
    turn: 2, message: { source: { callId: "invalid" }, content: [{ isError: true, content: [{ type: "text", text: failure }] }] },
  } } });
  const beforeEnd = f.events.buildLocationData({ state: tracking }, "turn", null);
  assert.equal(f.events.match({ type: "turn/end", data: { turn: 2 } }).role, "update");
  tracking = f.events.update({ state: tracking }, { event: { type: "turn/end", seq: 5, data: { turn: 2, reason: { kind: "blocked" } } } });
  const afterEnd = f.events.buildLocationData({ state: tracking }, "turn", beforeEnd);
  assert.notEqual(beforeEnd, afterEnd, "The footer updates when a turn becomes blocked");
  const select = (seq: number, location = afterEnd) => f.tail.options.select({ seq, turn: { data: { get: () => location.value } } });
  const matched = select(6);
  assert.equal(matched.creationError, failure);
  const node = f.tail.component({ matched });
  const article = node.type(node.props);
  assert.equal(article.props.role, "alert");
  assert.equal(article.children[0].children[0], "Architecture review could not be prepared");
  assert.match(article.children[2].children[0], /turn stopped/);
  assert.equal(select(4).blocked, false, "Replay cannot show a block before its event");
  assert.equal(select(5).blocked, true, "The completed-turn footer is anchored at the turn/end sequence");

  tracking = f.events.start({}, { event: { type: "turn/start", data: { turn: 3 } } });
  tracking = f.events.update({ state: tracking }, { event: { type: "tool/call", data: { turn: 3, callId: "valid", name: "prepare_architecture_review" } } });
  tracking = f.events.update({ state: tracking }, { event: { type: "tool/result", seq: 8, data: {
    turn: 3, message: { source: { callId: "valid" }, content: [{ isError: false,
      content: [{ type: "text", text: JSON.stringify({ architecture_review: { reviewId: "corrected", status: "pending", plan: {} } }) }] }] },
  } } });
  const retried = select(9, f.events.buildLocationData({ state: tracking }, "turn", null));
  assert.equal(retried.architectureReview.reviewId, "corrected");
  assert.equal(retried.creationError, null);
  assert.equal(retried.blocked, false);
});

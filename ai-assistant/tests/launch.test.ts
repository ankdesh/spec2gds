import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import vm from "node:vm";
import { UNBOUND_SOURCE_PROMPT, authenticatedLaunchLocation, maxModelStepsForTurn } from "../src/index.js";

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

test("unbound editor launch still enters DSH through its one-time browser token", () => {
  const location = authenticatedLaunchLocation(
    { authenticatedUrl: base => `${base}/?token=one-time-secret` },
    undefined,
    true,
  );
  assert.equal(location, "/?token=one-time-secret#spec2gds_unbound=1");
  assert.ok(!location.includes("spec2gds_session"));
  assert.match(readFileSync(resolve(root, "src/index.ts"), "utf8"), /path: "\/launch"/);
});

test("browser plugin creates and opens the requested unbound session", async () => {
  let definition: { factory(require: (name: string) => unknown): { apply(ctx: unknown): void } } | undefined;
  let replaced = "";
  const created: unknown[] = [];
  const opened: unknown[] = [];
  const microtasks: Array<() => unknown> = [];
  const source = readFileSync(resolve(root, "client/index.js"), "utf8");
  const context = {
    URL,
    URLSearchParams,
    location: { pathname: "/", search: "", hash: "#spec2gds_unbound=1" },
    history: { replaceState: (_state: unknown, _title: string, url: string) => { replaced = url; } },
    document: {
      title: "",
      createElement: () => ({ dataset: {}, textContent: "" }),
      head: { appendChild: () => undefined },
    },
    fetch: async () => ({ ok: true, json: async () => ({ workspaces: [] }) }),
    queueMicrotask: (callback: () => unknown) => { microtasks.push(callback); },
    window: {
      alert: (message: unknown) => { throw new Error(`unexpected alert: ${String(message)}`); },
      __ModuleLoader__: { load: (value: typeof definition) => { definition = value; } },
    },
  };
  vm.runInNewContext(source, context, { filename: "client/index.js" });
  assert.ok(definition);
  const plugin = definition.factory(() => ({ createElement: () => null }));
  plugin.apply({
    uiSession: { registerNewSessionHandler: () => undefined },
    uiConversation: { events: { register: () => undefined } },
    slots: { inject: () => undefined },
    sessions: {
      create: async (value: unknown) => { created.push(value); return "unbound-session"; },
      open: (value: unknown) => { opened.push(value); },
    },
    workspaces: {
      list: { getSnapshot: () => ({ items: [] }) },
      create: async () => { throw new Error("unexpected workspace creation"); },
      rename: async () => { throw new Error("unexpected workspace rename"); },
    },
  });
  assert.equal(replaced, "/");
  assert.equal(microtasks.length, 2);
  for (const task of microtasks) await task();
  assert.equal(JSON.stringify(created), JSON.stringify([{ agentPreset: "focused" }]));
  assert.deepEqual(opened, ["unbound-session"]);
});

test("combined launcher starts the Assistant without opening a browser", () => {
  const launcher = readFileSync(resolve(root, "../scripts/serve-all.sh"), "utf8");
  assert.match(launcher, /start_service "ai-assistant"[^\n]+npm run dev -- --no-open/);
});

test("concurrent workspace synchronization and launch create once and signal readiness", async () => {
  let definition: any;
  const tasks: Array<() => Promise<void>> = [];
  const descriptor = { key: "assistant-unbound", title: "AI Assistant", path: "/workspace/unbound" };
  const rows: any[] = [], sessions: any[] = [], opened: string[] = [], alerts: string[] = [];
  let creates = 0;
  const documentElement = { dataset: {} as Record<string, string> };
  vm.runInNewContext(readFileSync(resolve(root, "client/index.js"), "utf8"), {
    URL, URLSearchParams, location: { pathname: "/", search: "", hash: "#spec2gds_unbound=1" },
    history: { replaceState() {} }, document: { documentElement, title: "", createElement: () => ({ dataset: {} }), head: { appendChild() {} } },
    queueMicrotask: (task: () => Promise<void>) => tasks.push(task),
    fetch: async () => ({ ok: true, json: async () => ({ workspaces: [descriptor], unbound_workspace: descriptor }) }),
    window: { alert: (message: string) => alerts.push(message), __ModuleLoader__: { load: (value: any) => { definition = value; } } },
  });
  definition.factory(() => ({ createElement: () => null })).apply({
    uiSession: { registerNewSessionHandler() {} }, uiConversation: { events: { register() {} } }, slots: { inject() {} },
    workspaces: { list: { getSnapshot: () => ({ items: rows }) }, refresh: async () => {},
      create: async (value: any) => { creates++; await new Promise(resolve => setImmediate(resolve)); const row = { ...value, workspaceId: "workspace" }; rows.push(row); return row; },
      rename: async (_id: string, title: string) => { rows[0].title = title; return rows[0]; } },
    sessions: { create: async (value: any) => { sessions.push(value); return "session"; }, refresh: async () => {}, open: (id: string) => opened.push(id) },
  });
  assert.equal(documentElement.dataset.spec2gdsLaunch, "pending");
  await Promise.all(tasks.map(task => task()));
  assert.equal(creates, 1);
  assert.equal(sessions[0].workspaceId, "workspace");
  assert.deepEqual(opened, ["session"]);
  assert.deepEqual(alerts, []);
  assert.equal(documentElement.dataset.spec2gdsLaunch, "ready");
});

test("focused web profile removes the generic DSH provider onboarding plugin", () => {
  const patch = readFileSync(resolve(root, "bundles/web/cordis.patch.yml"), "utf8");
  assert.match(patch, /- id: ui-settings-models\n  disabled: true/);
  assert.doesNotMatch(patch, /showTestingNotice|showDeepSeekOnboarding/);
});

test("goal state is host-owned while model goal tools remain preset-scoped", () => {
  const patch = readFileSync(resolve(root, "profile/cordis.patch.yml"), "utf8");
  const webPatch = readFileSync(resolve(root, "bundles/web/cordis.patch.yml"), "utf8");
  assert.match(patch, /- id: goal\n  disabled: false/);
  assert.match(patch, /- id: goal-round-driver\n  disabled: false/);
  assert.match(patch, /- id: command-goal\n  disabled: true/);
  assert.match(patch, /- id: tool-goal\n  disabled: true/);
  assert.match(patch, /- id: ui-goal\n  disabled: true/);
  assert.match(webPatch, /- id: agent-presets\n  disabled: false/);
  assert.match(webPatch, /default: focused/);
  assert.match(webPatch, /- id: ui-goal\n  disabled: false/);
});

test("catalog-backed presets separate focused, goal, and read-only orchestrated capabilities", () => {
  const focused = readFileSync(resolve(root, "profile/presets/focused/agent.cordis.yml"), "utf8");
  const goal = readFileSync(resolve(root, "profile/presets/goal/agent.cordis.yml"), "utf8");
  const orchestrated = readFileSync(resolve(root, "profile/presets/orchestrated/agent.cordis.yml"), "utf8");
  for (const preset of [focused, goal, orchestrated]) {
    assert.match(preset, /@deepseek-ai\/dsh-tool-ask-user/);
  }
  assert.doesNotMatch(focused, /tool-goal|tool-s-workflow|tool-subagent/);
  assert.match(goal, /@deepseek-ai\/dsh-tool-goal/);
  assert.doesNotMatch(goal, /tool-s-workflow/);
  assert.doesNotMatch(goal, /tool-subagent/);
  assert.doesNotMatch(orchestrated, /tool-subagent|tool-s-workflow|tool-goal/);
  const template = JSON.parse(readFileSync(resolve(root, "profile/catalog/event-systems/spec-orchestrated.yaml"), "utf8"));
  assert.deepEqual(template.agents.map((agent: any) => agent.id), ["primary", "analyst", "reviewer"]);
  assert.equal(template.subscriptions.find((subscription: any) => subscription.event === "analysis.ready").target, "reviewer");
  assert.equal(template.agents.find((agent: any) => agent.id === "analyst").tools.includes("prepare_spec_proposal"), false);
});

test("browser presets use Harness structured questions while headless stays noninteractive", () => {
  const packageJson = readFileSync(resolve(root, "package.json"), "utf8");
  const webPatch = readFileSync(resolve(root, "bundles/web/cordis.patch.yml"), "utf8");
  const sharedPatch = readFileSync(resolve(root, "profile/cordis.patch.yml"), "utf8");
  assert.match(packageJson, /"@deepseek-ai\/dsh-tool-ask-user": "0\.1\.6-alpha\.1"/);
  assert.doesNotMatch(webPatch, /- id: ui-user-questions\n  disabled: true/);
  assert.doesNotMatch(sharedPatch, /@deepseek-ai\/dsh-tool-ask-user/);
});

test("web proposal forms are profile-owned and do not depend on ask_user_question registration", () => {
  const patch = readFileSync(resolve(root, "profile/cordis.patch.yml"), "utf8");
  const server = readFileSync(resolve(root, "src/index.ts"), "utf8");
  const dev = readFileSync(resolve(root, "scripts/dev.mjs"), "utf8");
  assert.match(patch, /interactiveForms: !!js \(process\.env\.ASSISTANT_PROFILE \|\| 'spec2gds-web'\) === 'spec2gds-web'/);
  assert.match(server, /config\.interactiveForms/);
  assert.match(dev, /env\.ASSISTANT_PROFILE = profile/);
});

test("execution controls stay human-owned and are surfaced in the conversation dock", () => {
  const server = readFileSync(resolve(root, "src/index.ts"), "utf8");
  const client = readFileSync(resolve(root, "client/index.js"), "utf8");
  assert.ok(server.includes("execution\\/actions"));
  assert.match(server, /eventSystems\.control/);
  assert.doesNotMatch(server, /sWorkflow\.|startBoundWorkflow/);
  assert.match(server, /settleReviewedExecution\(binding, updated\)/);
  assert.match(server, /does not permit owner mutation/);
  assert.match(client, /conversation\.input\.dock/);
  assert.match(client, /data-s2g-execution/);
  assert.match(client, /execution\/actions/);
});

test("product policy bounds model steps and output tokens", () => {
  const source = readFileSync(resolve(root, "src/index.ts"), "utf8");
  const patch = readFileSync(resolve(root, "profile/cordis.patch.yml"), "utf8");
  assert.match(source, /ctx\.on\("agent\/pre-step"/);
  assert.match(source, /clarifiedTurns\.get\(String\(agent\.id\)\) === turn/);
  assert.match(source, /maxModelStepsForTurn/);
  assert.match(source, /event\.data\?\.name === "ask_user_question"/);
  assert.match(source, /ctx\.on\("agent\/request"/);
  assert.match(source, /maxTokens: config\.maxOutputTokens/);
  assert.match(patch, /ASSISTANT_MAX_STEPS_PER_TURN \|\| 3/);
  assert.match(patch, /ASSISTANT_MAX_OUTPUT_TOKENS \|\| 16384/);
});

test("OpenAI route offers GPT-5.6 Luna without changing the configured default", () => {
  const patch = readFileSync(resolve(root, "profile/cordis.patch.yml"), "utf8");
  assert.match(patch, /provider: openai\n    model: !!js process\.env\.OPENAI_MODEL \|\| 'gpt-4o-mini'/);
  assert.match(patch, /new Set\(\[process\.env\.OPENAI_MODEL \|\| 'gpt-4o-mini', 'gpt-5\.6-luna'\]\)/);
  assert.match(patch, /id => \(\{ id \}\)/);
});

test("a structured clarification grants only one additional focused model step", () => {
  assert.equal(maxModelStepsForTurn("focused", 3, false), 3);
  assert.equal(maxModelStepsForTurn("focused", 3, true), 4);
  assert.equal(maxModelStepsForTurn("goal", 3, false), 8);
  assert.equal(maxModelStepsForTurn("goal", 3, true), 8);
  assert.equal(maxModelStepsForTurn("orchestrated", 3, true), 8);
});

test("product dialog preserves the HTML hidden contract over layout styles", () => {
  const source = readFileSync(resolve(root, "client/index.js"), "utf8");
  assert.match(source, /\.s2g-dialog \[hidden\]\{display:none!important\}/);
  assert.match(source, /\.s2g-required input\{[^}]*background:#fff;color:#17211f;caret-color:#17211f/);
});

test("browser plugin owns New Session and consumes launch data from the fragment", async () => {
  let definition: { factory(require: (name: string) => unknown): { apply(ctx: unknown): void } } | undefined;
  let newSessionHandler: Record<string, unknown> | undefined;
  let proposalDefinition: any;
  let proposalTail: Record<string, any> | undefined;
  let replaced = "";
  const created: unknown[] = [];
  const opened: unknown[] = [];
  const renamed: unknown[] = [];
  const microtasks: Array<() => unknown> = [];
  const source = readFileSync(resolve(root, "client/index.js"), "utf8");
  const context = {
    URL,
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
        sessionId: "bound-session", preset: "focused", workspaceKey: "workspace-1", workspaceTitle: "Bound design",
        workspacePath: "/tmp/bound-design", workspaceDomain: "spec",
        workspaceServiceUrl: "http://127.0.0.1:6010", workspaceDocumentId: "doc-1",
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
    uiConversation: { events: { register: (value: unknown) => { proposalDefinition = value; } } },
    slots: {
      inject: (name: string, register: () => unknown) => {
        if (name === "conversation.chat.turnTail") register();
      },
      register: (options: Record<string, any>, component: unknown) => {
        proposalTail = { options, component };
        return () => undefined;
      },
    },
    sessions: {
      create: async (value: unknown) => { created.push(value); return "bound-session"; },
      open: (value: unknown) => { opened.push(value); },
    },
    workspaces: {
      list: { getSnapshot: () => ({ items: [{ workspaceId: "workspace-1", title: "workspace-1", path: "/tmp/bound-design" }] }) },
      create: async () => ({ workspaceId: "workspace-1", title: "Bound design", path: "/tmp/bound-design" }),
      rename: async (_workspaceId: string, title: string) => {
        renamed.push(title);
        if (title === "Bound design") throw new Error("workspace rename failed: workspace/name-conflict");
        return { workspaceId: "workspace-1", title, path: "/tmp/bound-design" };
      },
    },
  });

  assert.equal(newSessionHandler?.id, "spec2gds");
  assert.equal(newSessionHandler?.priority, -100);
  assert.equal(context.document.title, "spec2gds Assistant");
  assert.equal(proposalDefinition.kind, "spec2gds-proposal-reviews");
  assert.equal(proposalTail?.options.name, "conversation.chat.turnTail");
  assert.equal(replaced, "/");
  assert.equal(microtasks.length, 2);
  for (const task of microtasks) await task();
  await new Promise(resolvePromise => setImmediate(resolvePromise));
  assert.deepEqual(renamed, ["Bound design", "Bound design 2"]);
  assert.equal(JSON.stringify(created), JSON.stringify([{ sessionId: "bound-session", workspaceId: "workspace-1", agentPreset: "focused" }]));
  assert.deepEqual(opened, ["bound-session"]);

  const turnStart = { type: "turn/start", seq: 1, data: { turn: 4 } };
  let proposalState = proposalDefinition.start({}, { event: turnStart });
  proposalState = proposalDefinition.update({ state: proposalState }, { event: {
    type: "tool/call", seq: 2, data: { turn: 4, callId: "proposal-call", name: "prepare_circuit_proposal" },
  } });
  const review = { proposalId: "proposal-1", state: "ready", domain: "circuit", artifact: {} };
  proposalState = proposalDefinition.update({ state: proposalState }, { event: {
    type: "tool/result", seq: 3, data: { turn: 4, message: {
      source: { callId: "proposal-call" },
      content: [{ content: [{ type: "text", text: JSON.stringify({ review }) }] }],
    } },
  } });
  const published = proposalDefinition.buildLocationData({ state: proposalState }, "turn", null);
  const matched = proposalTail?.options.select({
    seq: 4,
    turn: { data: { get: (key: string) => key === "spec2gds-proposal-reviews" ? published.value : undefined } },
  });
  assert.equal(matched?.review?.proposalId, "proposal-1");

  let inputState = proposalDefinition.start({}, { event: { type: "turn/start", seq: 5, data: { turn: 5 } } });
  inputState = proposalDefinition.update({ state: inputState }, { event: {
    type: "tool/call", seq: 6, data: { turn: 5, callId: "input-call", name: "prepare_circuit_proposal" },
  } });
  const requiredInput = { title: "Complete the proposal details", fields: [{ name: "component_name", label: "Component name", default_value: "AndGate" }] };
  inputState = proposalDefinition.update({ state: inputState }, { event: {
    type: "tool/result", seq: 7, data: { turn: 5, message: {
      source: { callId: "input-call" },
      content: [{ content: [{ type: "text", text: JSON.stringify({ required_input: requiredInput }) }] }],
    } },
  } });
  const inputPublished = proposalDefinition.buildLocationData({ state: inputState }, "turn", null);
  const inputMatched = proposalTail?.options.select({
    seq: 8,
    turn: { data: { get: (key: string) => key === "spec2gds-proposal-reviews" ? inputPublished.value : undefined } },
  });
  assert.equal(inputMatched?.requiredInput?.fields[0]?.default_value, "AndGate");
  assert.match(source, /data-s2g-required-input/);
  assert.match(source, /inputActions\.setDraft\(requiredInputMessage/);
  assert.match(source, /inputActions\.submit\(\)/);
});

test("browser plugin fails closed if Harness does not preserve the reserved session identity", () => {
  const source = readFileSync(resolve(root, "client/index.js"), "utf8");
  assert.match(source, /if \(createdId !== id\) throw new Error/);
  assert.match(source, /instead of reserved binding/);
});

test("unbound sessions receive a product guard instead of design-editing claims", () => {
  const source = readFileSync(resolve(root, "src/index.ts"), "utf8");
  const guard = source.match(/name: "spec2gds:unbound-session",[\s\S]*?\}\)\);/)?.[0];
  assert.ok(guard, "Expected the unbound prompt guard registration.");
  assert.match(guard, /complete: true/);
  assert.match(guard, /instructionsFor\(agent.id\)\.text\("unbound"\)/);
  assert.match(UNBOUND_SOURCE_PROMPT, /Do not create a Goal before binding/);
  for (const name of ["domain-persona", "binding-context", "operation-constraints", "output-contract"]) {
    assert.doesNotMatch(guard, new RegExp(name));
  }
});

test("deployment persona contains identity only", () => {
  const patch = readFileSync(resolve(root, "profile/cordis.patch.yml"), "utf8");
  assert.match(patch, /personaPrefix: ""/);
  assert.doesNotMatch(patch, /Every useful conversation is permanently bound/);
});


test("execution dock sends exact retry, answer, and source-control identities", async () => {
  let definition: any, dock: any;
  const requests: Array<{ path: string; body: any }> = [];
  const execution = { status: "active", mode: "goal", revision: 17, reason: "", members: [{ id: "primary" }],
    limits: { maxRounds: 8, maxRequests: 32, maxTokens: 300000, maxActiveMillis: 60000 }, rounds: [], requests: [], events: [],
    deliveries: [{ id: "delivery-1", target: "primary", state: "interrupted", attempt: 1, error: "Interrupted" }],
    waits: [{ id: "wait-1", member: "primary", kind: "human", reason: "Which period?", state: "waiting" }] };
  const states = [execution, false, "", [{ id: "source-1", revision: 4, enabled: true, sequence: 0, definition: { url: "http://owner/document" } }], null, null, false];
  let stateIndex = 0;
  const react = { createElement: (type: any, props: any, ...children: any[]) => ({ type, props, children }),
    useState: () => [states[stateIndex++], () => {}], useEffect: () => {} };
  vm.runInNewContext(readFileSync(resolve(root, "client/index.js"), "utf8"), {
    URL, URLSearchParams, location: { pathname: "/", search: "", hash: "" },
    history: { replaceState: () => {} }, document: { createElement: () => ({ dataset: {} }), head: { appendChild: () => {} } },
    queueMicrotask: () => {}, window: { confirm: () => true, prompt: () => "10 cycles", __ModuleLoader__: { load: (value: any) => { definition = value; } } },
    fetch: async (path: string, options: any) => { requests.push({ path, body: JSON.parse(options.body) }); return { ok: true, json: async () => ({ execution, sources: [] }) }; },
  });
  definition.factory(() => react).apply({ uiSession: { registerNewSessionHandler: () => {} }, uiConversation: { events: { register: () => {} } },
    slots: { inject: (_name: string, fn: () => void) => fn(), register: (slot: any, component: any) => { if (slot.id === "execution") dock = component; } } });
  const buttons: any[] = [];
  function visit(node: any): void { if (!node || typeof node !== "object") return; if (node.type === "button") buttons.push(node); for (const child of node.children ?? []) visit(child); }
  const element = dock({ sessionId: "session/x" });
  visit(element.type(element.props));
  for (const label of ["Acknowledge uncertainty and retry", "Answer", "Disable monitor"]) {
    const button = buttons.find(item => item.children.includes(label)); assert.ok(button);
    await button.props.onClick(); await new Promise(resolve => setImmediate(resolve));
  }
  assert.deepEqual(requests, [
    { path: "/spec2gds-api/bindings/session%2Fx/execution/actions", body: { action: "retry", revision: 17, deliveryId: "delivery-1", acknowledgeUncertainty: true } },
    { path: "/spec2gds-api/bindings/session%2Fx/execution/answers", body: { waitId: "wait-1", revision: 17, answer: "10 cycles" } },
    { path: "/spec2gds-api/bindings/session%2Fx/execution/sources", body: { action: "disable", sourceId: "source-1", revision: 4 } },
  ]);
});

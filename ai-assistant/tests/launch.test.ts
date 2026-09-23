import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import vm from "node:vm";
import { authenticatedLaunchLocation, maxModelStepsForTurn } from "../src/index.js";

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
  assert.match(goal, /@deepseek-ai\/dsh-tool-s-workflow/);
  assert.doesNotMatch(goal, /tool-subagent/);
  assert.match(orchestrated, /toolName: delegate_workflow_step/);
  assert.match(orchestrated, /maxDepth: 1/);
  assert.match(orchestrated, /enableRunInBackground: false/);
  assert.match(orchestrated, /allow:\n        - get_bound_context/);
  assert.doesNotMatch(orchestrated.match(/toolFilter:[\s\S]*/)?.[0] ?? "", /ask_user_question/);
});

test("browser presets use Harness structured questions while headless stays noninteractive", () => {
  const packageJson = readFileSync(resolve(root, "package.json"), "utf8");
  const webPatch = readFileSync(resolve(root, "bundles/web/cordis.patch.yml"), "utf8");
  const sharedPatch = readFileSync(resolve(root, "profile/cordis.patch.yml"), "utf8");
  assert.match(packageJson, /"@deepseek-ai\/dsh-tool-ask-user": "0\.1\.6-alpha\.1"/);
  assert.doesNotMatch(webPatch, /- id: ui-user-questions\n  disabled: true/);
  assert.doesNotMatch(sharedPatch, /@deepseek-ai\/dsh-tool-ask-user/);
});

test("workflow controls stay human-owned and are surfaced in the conversation dock", () => {
  const server = readFileSync(resolve(root, "src/index.ts"), "utf8");
  const client = readFileSync(resolve(root, "client/index.js"), "utf8");
  assert.ok(server.includes("workflow\\/actions"));
  for (const action of ["pause", "resume", "cancel", "answer", "approve", "raise-budgets"]) {
    assert.ok(server.includes(`action === "${action}"`));
  }
  assert.match(server, /settleReviewedWorkflow\(binding, updated\)/);
  assert.match(server, /sWorkflow\.updateDraft/);
  assert.match(server, /does not permit owner mutation/);
  assert.match(client, /conversation\.input\.dock/);
  assert.match(client, /data-s2g-workflow/);
  assert.match(client, /workflow\/actions/);
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
  assert.match(patch, /ASSISTANT_MAX_OUTPUT_TOKENS \|\| 1200/);
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
});

test("browser plugin owns New Session and consumes launch data from the fragment", async () => {
  let definition: { factory(require: (name: string) => unknown): { apply(ctx: unknown): void } } | undefined;
  let newSessionHandler: Record<string, unknown> | undefined;
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
  assert.equal(replaced, "/");
  assert.equal(microtasks.length, 2);
  for (const task of microtasks) await task();
  await new Promise(resolvePromise => setImmediate(resolvePromise));
  assert.deepEqual(renamed, ["Bound design", "Bound design · 127.0.0.1:6010 · workspac"]);
  assert.equal(JSON.stringify(created), JSON.stringify([{ sessionId: "bound-session", workspaceId: "workspace-1", agentPreset: "focused" }]));
  assert.deepEqual(opened, ["bound-session"]);
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
  assert.match(guard, /Do not claim that work was completed and do not create a goal/);
  for (const name of ["domain-persona", "binding-context", "operation-constraints", "output-contract"]) {
    assert.doesNotMatch(guard, new RegExp(name));
  }
});

test("deployment persona contains identity only", () => {
  const patch = readFileSync(resolve(root, "profile/cordis.patch.yml"), "utf8");
  assert.match(patch, /personaPrefix: >-\n      You are the focused spec2gds hardware-design assistant\./);
  assert.doesNotMatch(patch, /Every useful conversation is permanently bound/);
});

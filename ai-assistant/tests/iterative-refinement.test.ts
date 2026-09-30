import assert from "node:assert/strict";
import { readFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { OwnerError } from "../src/owner-clients.js";
import { parseOwnerOperationContract } from "../src/owner-operation-schema.js";
import { ProductState } from "../src/state.js";
import { registerDomainTools } from "../src/tools.js";

function fixture(policy: "automatic" | "review" = "automatic", notificationFails = false) {
  const root = mkdtempSync(join(tmpdir(), "spec-iterative-"));
  const state = new ProductState(join(root, "state.sqlite3"));
  const binding = state.createBinding("chat", { domain: "spec", serviceBaseUrl: "http://owner", ownerUrl: "http://owner",
    documentId: "document", scope: "document", ownerDocumentKey: "package-A", workspaceKey: "workspace", workspaceTitle: "Workspace",
    workspacePath: root, workspaceDomain: "spec", workspaceOwnerUrl: "http://owner", workspaceDocumentId: "document" });
  let wire = JSON.parse(readFileSync(new URL("./fixtures/spec-document-operation-contract.json", import.meta.url), "utf8"));
  let revision = "sha256:A";
  let submissionError: Error | null = null;
  let discoveryError: Error | null = null;
  const submitted: any[] = [];
  const prepared: any[] = [];
  const owners: any = {
    context: async () => ({ document_id: "document", scope: "document", source_revision_hash: revision, owner_document_key: "package-A", approval_policy: policy,
      writable: {}, available_references: {}, diagnostics: [], rendered_context: { document_id: "document", source_revision_hash: revision, target: null, text: "Fixture" } }),
    operationContract: async () => wire,
    specPolicy: async () => { if (discoveryError) throw discoveryError; return { approval_policy: policy, submissions: true }; },
    previewSpec: async (_binding: any, artifact: any) => ({ status: "valid", diagnostics: [], diff: [], candidate_source_revision_hash: "sha256:B" }),
    submitSpec: async (target: any, artifact: any) => {
      submitted.push({ target, artifact });
      if (submissionError) throw submissionError;
      return { status: policy === "automatic" ? "applied" : "approval_required", source_revision_hash: policy === "automatic" ? "sha256:B" : revision,
        application_mode: policy };
    },
  };
  const tools = new Map<string, any>();
  registerDomainTools({ tools: { register: (tool: any) => { tools.set(tool.name, tool); return () => { tools.delete(tool.name); }; } } },
    binding, state, owners, undefined, review => { prepared.push(review); if (notificationFails) throw new Error("Execution ledger unavailable"); }, undefined, !notificationFails, parseOwnerOperationContract(wire));
  const args: any = { supported: true, base_source_revision_hash: revision, unsupported_reason: null, title: "Create leaf", summary: "Create leaf", rationale: "Requested", assumptions: [],
    operations: [{ operation_id: "create", type: "create_entity", kind: "component", name: "leaf", ports: [{ name: "clk", family: "wire", direction: "in" }], instances: [] }] };
  const execute = (values = args) => tools.get("prepare_spec_proposal").execute(values, { callId: "call", signal: new AbortController().signal });
  return { state, binding, tools, args, execute, submitted, prepared,
    set revision(value: string) { revision = value; },
    set contract(value: any) { wire = value; }, get contract() { return wire; },
    set discoveryError(value: Error) { discoveryError = value; },
    set submissionError(value: Error) { submissionError = value; },
    close() { state.close(); rmSync(root, { recursive: true, force: true }); },
  };
}

test("fully specified creation saves automatically without a details card", async () => {
  const f = fixture();
  try {
    const result = await f.execute();
    assert.equal(result.success, true);
    assert.equal(result.review.state, "applied");
    assert.equal(result.review.ownerResult.source_revision_hash, "sha256:B");
    assert.equal(f.submitted.length, 1);
    assert.equal(f.submitted[0].target.ownerDocumentKey, "package-A");
    assert.equal(f.submitted[0].artifact.base_source_revision_hash, "sha256:A");
    assert.equal(f.prepared[0].state, "applied");
    assert.equal(result.required_input, undefined);
  } finally { f.close(); }
});

test("restricted creation retains the details card; a complete confirmed proposal remains pending", async () => {
  const f = fixture("review");
  try {
    f.args.required_fields = [{ name: "width", label: "Width", description: "Bits", default_value: "8" }];
    const details = await f.execute();
    assert.ok(details.required_input);
    assert.equal(f.submitted.length, 0);
    const values = Object.fromEntries(details.required_input.fields.map((field: any) => [field.name, field.default_value]));
    f.state.confirmProposalInput(details.required_input.input_id, values);
    const result = await f.execute({ ...f.args, confirmed_input_id: details.required_input.input_id, confirmed_values: values });
    assert.equal(result.review.state, "ready");
    assert.equal(result.review.ownerResult.status, "approval_required");
  } finally { f.close(); }
});

test("duplicate tool execution returns its saved receipt despite a newer revision", async () => {
  const f = fixture();
  try {
    const first = await f.execute();
    f.revision = "sha256:B";
    const retry = await f.execute();
    assert.equal(retry.proposal_id, first.proposal_id);
    assert.equal(retry.review.state, "applied");
    assert.equal(f.submitted.length, 1);
    assert.equal(f.state.listReviews("chat").length, 1);
    const changed = await f.execute({ ...f.args, summary: "Changed content" });
    assert.equal(changed.error.error_code, "INVALID_PROPOSAL");
    assert.equal(f.submitted.length, 1);
  } finally { f.close(); }
});

test("old operations are rejected without replacing their authored revision", async () => {
  const f = fixture();
  try {
    f.revision = "sha256:B";
    const result = await f.execute();
    assert.equal(result.error.error_code, "STALE_REVISION");
    assert.equal(f.args.base_source_revision_hash, "sha256:A");
    assert.equal(f.submitted.length, 0);
    assert.match(result.instruction, /Never relabel/);
  } finally { f.close(); }
});

test("policy discovery failure cannot authorize an automatic save", async () => {
  const f = fixture();
  try {
    f.discoveryError = new OwnerError(503, "Policy unavailable");
    const result = await f.execute();
    assert.equal(result.success, false);
    assert.equal(f.submitted.length, 0);
  } finally { f.close(); }
});

test("available defaults avoid confirmation; genuinely missing input retains clarification", async () => {
  const f = fixture();
  try {
    const args = { ...f.args, supported: false, unsupported_reason: "Need width", operations: [], required_fields: [{ name: "width", label: "Width", description: "Bits", default_value: "8" }] };
    const defaults = await f.execute(args);
    assert.equal(defaults.required_input, undefined);
    assert.match(defaults.instruction, /assumptions/);
    const missing = await f.execute({ ...args, required_fields: [{ ...args.required_fields[0], default_value: "" }] });
    assert.equal(missing.required_input.fields.length, 1);
    assert.equal(f.submitted.length, 0);
  } finally { f.close(); }
});

test("context reads refresh a changed contract in the existing conversation", async () => {
  const f = fixture();
  try {
    const original = f.tools.get("prepare_spec_proposal");
    f.contract = { ...f.contract, digest: `sha256:${"b".repeat(64)}` };
    await f.tools.get("get_bound_context").execute({}, { callId: "context", signal: new AbortController().signal });
    assert.notEqual(f.tools.get("prepare_spec_proposal"), original);
    assert.equal(f.tools.size, 2);
    assert.equal((await f.execute()).review.state, "applied");
  } finally { f.close(); }
});

test("uncertain writes remain reconcilable and never claim an applied result", async () => {
  const f = fixture();
  try {
    f.submissionError = new OwnerError(503, "Response lost after save", true);
    const result = await f.execute();
    assert.equal(result.success, false);
    assert.equal(result.review.state, "reconcile");
    assert.equal(result.review.ownerResult, null);
  } finally { f.close(); }
});

test("Spec context refresh retains existing pending reviews", async () => {
  const f = fixture("review");
  try {
    f.state.createReview({ proposalId: "pending", sessionId: "chat", callId: "old", domain: "spec", state: "ready", baseRevision: "sha256:A", artifact: {}, preview: null, diagnostics: [], error: null, ownerResult: null });
    f.revision = "sha256:B";
    await f.tools.get("get_bound_context").execute({}, { callId: "context", signal: new AbortController().signal });
    assert.equal(f.state.getReview("chat", "pending")!.state, "ready");
  } finally { f.close(); }
});

for (const policy of ["automatic", "review"] as const) test(`a failed execution notification preserves the owner ${policy} result`, async () => {
  const f = fixture(policy, true);
  try {
    const result = await f.execute();
    assert.equal(result.review.state, policy === "automatic" ? "applied" : "ready");
    assert.equal(f.state.listReviews("chat")[0].state, result.review.state);
    assert.equal(result.error, undefined);
  } finally { f.close(); }
});

/** Product progress reads committed execution records; it grants no controls. */
import type { FlowView } from "@deepseek-ai/dsh-flow";
import { hasSavedReceipt, presentationFor } from "./change-presentation.js";
import { isRecord, type ProposalReview } from "./types.js";

export interface ProgressItem {
  id: string;
  label: string;
  state: "running" | "complete" | "waiting" | "failed" | "proposed" | "checked" | "saved" | "paused" | "cancelled";
}

const phases: Record<string, string> = {
  context: "Reading the source", edit_context: "Reading the source", authoring_context: "Reading the approved interface",
  draft: "Preparing changes", author: "Preparing the SystemVerilog section", content: "Preparing content",
  validated: "Checking changes", validate: "Checking changes", validate_edit: "Checking changes",
  plan: "Preparing the architecture", prepare: "Preparing the architecture", review: "Preparing the architecture review",
  architecture: "Reviewing the architecture", decision: "Awaiting architecture review", approved: "Checking the architecture decision",
  submit: "Checking and submitting changes", submit_content: "Checking and submitting changes", submit_architecture: "Checking and submitting changes",
  saved: "Awaiting a content decision", saved_content: "Awaiting a content decision", saved_architecture: "Awaiting a content decision",
  complete: "Confirming the saved changes", complete_content: "Confirming the saved changes", complete_architecture: "Confirming the saved changes",
  create: "Creating the Spec", created: "Creating the Spec", bind: "Connecting the Spec", reserve: "Preparing the Spec", confirmed: "Confirming the Spec",
  binding: "Connecting the Spec", destination: "Preparing the Spec", approval: "Awaiting architecture review",
};
const titles: Record<string, string> = {
  "spec2gds.edit_spec": "Edit Spec", "spec2gds.architecture": "Review architecture", "spec2gds.add_component": "Add Component",
  "spec2gds.component_content": "Prepare Component content", "spec2gds.create_spec_with_component": "Create Spec and Component", "spec2gds.create_empty_spec": "Create Spec",
};

/** Follow only designer revisions connected by committed parent identities. */
export function relatedFlowViews(root: FlowView, visible: readonly FlowView[]): FlowView[] {
  const result = [root];
  for (const flow of visible.filter(flow => flow.id !== root.id).sort((left, right) => left.createdAt - right.createdAt)) {
    if (flow.parentExecutionId && result.some(parent => parent.id === flow.parentExecutionId)) result.push(flow);
  }
  return result;
}

export function flowPresentation(flow: FlowView, reviews: readonly ProposalReview[], sourceName?: string) {
  const proposalIds = new Set<string>();
  for (const node of flow.nodes) {
    if (isRecord(node.output) && typeof node.output.proposal_id === "string") proposalIds.add(node.output.proposal_id);
    for (const review of reviews) if (review.callId === node.operationId) proposalIds.add(review.proposalId);
  }
  if (isRecord(flow.pending?.request) && typeof flow.pending.request.proposal_id === "string") proposalIds.add(flow.pending.request.proposal_id);
  const items: ProgressItem[] = [];
  for (const node of flow.nodes) {
    // Branch bookkeeping has no designer action. Recorded retries keep identity.
    if (node.kind === "branch" || node.kind === "flow") continue;
    const name = node.id.split("/").at(-1) ?? "";
    const phase = node.kind === "model" && /architecture/.test(node.id) ? "Preparing the architecture" : node.kind === "model" && /content/.test(node.id) ? "Preparing the SystemVerilog section"
      : phases[name] ?? (node.kind === "model" ? "Preparing content" : node.kind === "wait" ? "Awaiting review" : "Checking the result");
    const unfinished = ["running", "waiting"].includes(node.state);
    items.push({ id: `${node.id}:${node.attempt}`, label: name === "context" && sourceName ? `Reading ${sourceName}` : phase,
      state: unfinished && flow.status === "cancelled" ? "cancelled" : unfinished && ["paused", "needs-resume"].includes(flow.status) ? "paused"
        : node.state === "succeeded" ? "complete" : node.state === "failed" || node.state === "unknown" ? "failed" : node.state });
  }
  for (const review of reviews.filter(review => proposalIds.has(review.proposalId))) {
    const state: ProgressItem["state"] = hasSavedReceipt(review) ? "saved" : ["rejected", "stale", "discarded", "reconcile"].includes(review.state) ? "failed"
      : ["ready", "applying", "sent", "applied"].includes(review.state) ? "checked" : "proposed";
    for (const group of presentationFor(review).groups) for (const change of group.changes) {
      items.push({ id: `${review.proposalId}:${change.id}`, label: `${change.change === "added" ? "Add" : change.change === "removed" ? "Remove" : "Update"} ${change.label}`, state });
    }
    if (state === "saved") items.push({ id: `${review.proposalId}:saved`, label: "Changes saved", state });
  }
  return { title: titles[flow.definition.id] ?? "Spec flow", items, proposalIds: [...proposalIds],
    reviewReferences: reviews.filter(review => proposalIds.has(review.proposalId)).map(review => ({ proposalId: review.proposalId, sessionId: review.sessionId, version: review.version })) };
}

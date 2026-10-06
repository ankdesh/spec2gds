/** Internal review-state bridge for the two Python CLIs. */
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { ProductState, artifactDigest } from "../ai-assistant/lib/state.js";

const [command, root, proposalId] = process.argv.slice(2);
if (!root || !["list", "recover", "begin", "complete", "stale", "rejected", "reconcile", "discard", "architecture-list", "architecture-approved", "architecture-revised", "architecture-cancelled", "architecture-require"].includes(command)) {
  throw new Error("Internal usage: workspace-reviews <action> <state-root> [proposal-id]");
}
const database = resolve(root, "assistant.sqlite3");
if (!existsSync(database)) {
  if (["list", "architecture-list"].includes(command)) { console.log(JSON.stringify({ reviews: [], architecture_reviews: [] })); process.exit(0); }
  throw new Error("No assistant review state exists for this specification.");
}
const state = new ProductState(database);
try {
  if (command === "architecture-list") {
    console.log(JSON.stringify({ architecture_reviews: state.listArchitectureReviews() }));
  } else if (command.startsWith("architecture-")) {
    if (!proposalId) throw new Error("An architecture review ID is required.");
    const review = state.architectureReview(proposalId);
    if (!review) throw new Error("Unknown architecture review.");
    if (command === "architecture-require") {
      if (review.status !== "approved") throw new Error("Architecture has not been approved.");
      console.log(JSON.stringify({ architecture_review: review }));
    } else {
      console.log(JSON.stringify({ architecture_review: state.decideArchitecture(proposalId, command.slice("architecture-".length), "CLI decision") }));
    }
  } else if (command === "list") {
    const reviews = state.listBindings(true).flatMap(binding =>
      state.listReviews(binding.sessionId).map(review => ({
        ...review, documentId: binding.documentId, serviceUrl: binding.serviceUrl,
      })),
    );
    console.log(JSON.stringify({ reviews }));
  } else if (command === "recover") {
    console.log(JSON.stringify({ recovered: state.recoverInterruptedReviews() }));
  } else {
    if (!proposalId) throw new Error("A proposal ID is required.");
    const match = state.listBindings(true).map(binding => ({ binding, review: state.getReview(binding.sessionId, proposalId) }))
      .find(item => item.review !== null);
    if (!match) throw new Error(`Unknown proposal: ${proposalId}`);
    const { binding, review } = match;
    if (artifactDigest(review.artifact) !== review.artifactDigest) throw new Error("Proposal artifact failed its integrity check.");
    const payload = command === "complete" ? JSON.parse(await new Promise((done, fail) => {
      let input = "";
      process.stdin.setEncoding("utf8");
      process.stdin.on("data", chunk => { input += chunk; });
      process.stdin.on("end", () => done(input));
      process.stdin.on("error", fail);
    })) : {};
    const expected = {
      begin: ["ready", "reconcile"], complete: ["applying"], stale: ["applying"],
      reconcile: ["applying"], rejected: ["applying"], discard: ["ready", "rejected", "stale", "reconcile"],
    }[command];
    const next = {
      begin: "applying", complete: "applied", stale: "stale",
      reconcile: "reconcile", rejected: "rejected", discard: "discarded",
    }[command];
    const updated = state.transitionReview(binding.sessionId, proposalId, expected, next,
      command === "complete" ? { serviceResult: payload, error: null } : {});
    console.log(JSON.stringify({ review: updated }));
  }
} finally { state.close(); }

/** Read-only inspection of the Assistant product state. Decisions use flow commands. */
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { ProductState } from "../ai-assistant/lib/state.js";

const [command, root] = process.argv.slice(2);
if (!root || !["list", "architecture-list"].includes(command)) {
  throw new Error("Review inspection accepts list or architecture-list only. Use revision-checked flow controls and Spec Editor for decisions.");
}
const database = resolve(root, "assistant.sqlite3");
if (!existsSync(database)) {
  console.log(JSON.stringify({ reviews: [], architecture_reviews: [] }));
  process.exit(0);
}
const state = new ProductState(database);
try {
  if (command === "architecture-list") {
    console.log(JSON.stringify({ architecture_reviews: state.listArchitectureReviews() }));
  } else {
    const reviews = state.listBindings(true).flatMap(binding =>
      state.listReviews(binding.sessionId).map(review => ({
        ...review, documentId: binding.documentId, serviceUrl: binding.serviceUrl,
      })),
    );
    console.log(JSON.stringify({ reviews }));
  }
} finally { state.close(); }

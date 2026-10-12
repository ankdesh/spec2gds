import type { ProductState } from "../../src/state.js";

export const architecturePlan = { title: "Leaf architecture", components: [{ name: "leaf", purpose: "Concrete implementation" }],
  designs: [], interfaces: [{ component: "leaf", ports: [{ name: "clk", direction: "in", range: null, description: "Port purpose" }], parameters: [], constant_context: "" }], clocks_resets: [],
  decomposition_rationale: "Keep this cohesive leaf unified.", assumptions: [], open_questions: [], concrete_configuration: { width: 8 } };

export function approvedArchitecture(state: ProductState, sessionId: string, originalRequest = "Create the requested component", revision: string | null = null): string {
  const reviewId = `architecture-${sessionId}`;
  state.storeArchitecture({ reviewId, sessionId, callId: reviewId, status: "pending", plan: architecturePlan, originalRequest, sourceRevision: revision });
  state.decideArchitecture(reviewId, "approved", "");
  return reviewId;
}

/** Model capabilities for bound service context, typed proposals and clarification.
 * Tool schemas admit structural arguments; fresh authored revisions and service
 * preview enforce meaning. Standing specialists stay read-only; primary tools
 * cannot bypass immutable binding, review claims or native execution permission. */

import type { PromptSection } from "@deepseek-ai/dsh-system-prompt";
import { registeredTool, nativeTool, type ToolRunContext } from "./tool-registry.js";
import { defaultInstructions, type InstructionBundle } from "./instructions.js";
import { type ServiceClients } from "./service-clients.js";
import { catalogPromptSectionsFor, promptSectionsFor, type BoundPromptCatalog } from "./domain-context.js";
import { type ServiceOperationContract } from "./service-operation-schema.js";
import { proposalError } from "./proposal-presentation.js";
import { type ProductState } from "./state.js";
import type { ProposalReview, SessionBinding } from "./types.js";
import { isRecord } from "./types.js";
import { registerSpecProposalTool } from "./tools/prepare_spec_proposal.js";
import { registerCircuitProposalTool } from "./tools/prepare_circuit_proposal.js";
import { registerContextTool } from "./tools/get_bound_context.js";
import { structuredQuestionPrompt, failureResult, callId } from "./tools/shared.js";
export { proposalInputRequest, proposedComponentFields, structuredQuestionPrompt } from "./tools/shared.js";
export type { ProposalInputField, ProposalInputRequest } from "./tools/shared.js";

export function registerDomainTools(
  agentContext: {
    tools: { register(tool: unknown): () => void; get?(name: string): unknown };
    systemPrompt?: { section(value: PromptSection): () => void };
  },
  binding: SessionBinding,
  state: ProductState,
  owners: ServiceClients,
  promptCatalog?: BoundPromptCatalog,
  onReviewPrepared?: (review: ProposalReview) => void | Promise<void>,
  currentUserRequest?: () => string,
  interactiveForms = false,
  operationContract?: ServiceOperationContract,
  schemaError?: string,
  onDomainToolUse?: () => Promise<void>,
  readOnly = false,
  instructions: InstructionBundle = defaultInstructions,
): void {
  let specContract = operationContract;
  let disposeSpecTool: (() => void) | undefined;
  const installSpecTool = (contract: ServiceOperationContract) => {
    disposeSpecTool?.();
    specContract = contract;
    disposeSpecTool = registerSpecProposalTool(agentContext, binding, state, owners, contract, interactiveForms, onReviewPrepared, currentUserRequest, onDomainToolUse, instructions);
  };
  const sections = promptCatalog ? catalogPromptSectionsFor(promptCatalog, binding) : promptSectionsFor(binding, instructions);
  for (const section of sections) agentContext.systemPrompt?.section(section);
  const interactive = agentContext.tools.get?.("ask_user_question") !== undefined;
  const interaction = structuredQuestionPrompt(interactive, instructions);
  if (interaction) agentContext.systemPrompt?.section(interaction);
  registerContextTool(agentContext, binding, state, owners, instructions, readOnly, onDomainToolUse, latest => {
    if (!specContract || latest.digest !== specContract.digest) installSpecTool(latest);
  });

  if (readOnly) return;
  if (!operationContract) {
    const disposeUnavailable = agentContext.tools.register(registeredTool({
      ...nativeTool(binding.domain === "spec" ? "prepare_spec_proposal" : "prepare_circuit_proposal", instructions, undefined, true),
      async execute(_args: unknown, exec: ToolRunContext) {
        return failureResult(proposalError(binding, callId(exec), "SERVICE_CONTRACT_ERROR", schemaError ?? "Owner operation schema unavailable."),
          instructions.text("result.8"));
      },
    }));
    if (binding.domain === "spec") disposeSpecTool = disposeUnavailable;
    return;
  }
  if (binding.domain === "spec") installSpecTool(operationContract);
  else registerCircuitProposalTool(agentContext, binding, state, owners, operationContract, interactiveForms, onReviewPrepared, onDomainToolUse, instructions);
}

export function findProposal(value: Record<string, unknown>, proposalId: string): Record<string, unknown> | null {
  const proposals = value.proposals;
  if (!Array.isArray(proposals)) return null;
  return proposals.find(item => isRecord(item) && item.proposal_id === proposalId) as Record<string, unknown> | undefined ?? null;
}

export function findSpecChange(value: Record<string, unknown>, proposalId: string): Record<string, unknown> | null {
  const changes = value.assistant_changes;
  if (!Array.isArray(changes)) return null;
  return changes.find(item => isRecord(item) && item.proposal_id === proposalId) as Record<string, unknown> | undefined ?? null;
}

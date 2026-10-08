import { defaultInstructions } from "../instructions.js";
import { registeredTool, nativeTool, type ToolRunContext } from "../tool-registry.js";
import type { ToolArguments } from "../tool-arguments.js";
import { type InstructionBundle } from "../instructions.js";
import { snapshotJsonValue, type JsonValue } from "@deepseek-ai/dsh-util-values";
import type { AssistantPreset } from "../types.js";
import { SourceCreations, SourceCreationError } from "../source-creation.js";
export function registerSourceCreationTool(
  agent: { ctx: { tools: { register(tool: unknown): () => void }; systemPrompt?: { section(value: unknown): () => void } } },
  creations: SourceCreations,
  currentRequest: () => { sourceSessionId: string; originalRequest: string; preset: AssistantPreset; preferredOwner?: string },
  instructions: InstructionBundle = defaultInstructions,
): void {
  agent.ctx.systemPrompt?.section({ name: "spec2gds:source-creation", order: 175, text: instructions.text("source-creation") });
  agent.ctx.tools.register(registeredTool({
    ...nativeTool("prepare_spec_document_creation", instructions),
    async execute(args: ToolArguments["prepare_spec_document_creation"], exec: ToolRunContext) {
      try {
        const creation = await creations.prepare({ ...currentRequest(), callId: String(exec.callId), title: args.title, documentId: args.document_id,
          architectureReviewId: args.architecture_review_id, empty: args.empty });
        if (creation.automatic === true) {
          const policy = await creations.owners.specPolicy(String(creation.serviceBaseUrl), exec.signal);
          if (policy.approval_policy !== "automatic") throw new SourceCreationError(409, "The Spec service now requires designer approval. Prepare a new creation request.");
          const reserved = await creations.create(String(creation.requestId), {
            documentId: String(creation.documentId), title: String(creation.title), serviceBaseUrl: String(creation.serviceBaseUrl),
          });
          return snapshotJsonValue({ source_creation: reserved.creation_request,
            instruction: instructions.text("result.27") }) as JsonValue;
        }
        return snapshotJsonValue({ source_creation: creation, instruction: instructions.text("result.28") }) as JsonValue;
      } catch (error) {
        return { creation_error: error instanceof Error ? error.message : String(error), instruction: instructions.text("result.29") };
      }
    },
  }));
}

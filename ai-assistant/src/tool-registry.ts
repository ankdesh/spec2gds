/** Native registration consumes contracts; handlers retain service authority. */
import { assertObjectJsonSchema, validateJsonSchemaValue, valueSchemaSpecToJsonSchema, type ToolRunContext, type ValueSchemaSpec, type JsonSchemaNode } from "@ankdesh/dsh-tools";
import { defaultInstructions, type InstructionBundle } from "./instructions.js";
import { modelProposalResult, proposalPresentation } from "./review-transport.js";
import type { ToolName } from "./tool-arguments.js";

export function nativeTool(name: ToolName, instructions: InstructionBundle = defaultInstructions, operationSchema?: ValueSchemaSpec, unavailable = false) {
  const contract = instructions.contracts[name];
  if (unavailable && !contract.unavailable) throw new Error("Tool has no unavailable contract.");
  const parameters = structuredClone(unavailable ? contract.unavailable!.input_schema : contract.input_schema);
  if (contract.service_schema_slot && !unavailable) {
    if (!operationSchema) throw new Error("Live service operation schema is required.");
    parameters.properties!.operations!.items = valueSchemaSpecToJsonSchema(operationSchema);
  }
  assertObjectJsonSchema(parameters);
  return { name, description: instructions.text(unavailable ? contract.unavailable!.instruction_ref : contract.instruction_ref), parameters,
    output: { schema: contract.output_schema,
      render: (_args: unknown, value: unknown) => [{ type: "text" as const, text: name === "prepare_circuit_proposal" ? modelProposalResult(value) : JSON.stringify(value) }],
      ...(["prepare_circuit_proposal"].includes(name) ? { presentationMeta: (_args: unknown, value: unknown) => proposalPresentation(value) } : {}),
    },
    ...(contract.timeout_ms === undefined ? {} : { timeoutMs: contract.timeout_ms }) };
}
export type { ToolRunContext };

/** Keep argument admission identical for direct calls and native dispatch. */
export function registeredTool<T>(definition: { parameters: JsonSchemaNode; execute(args: T, exec: ToolRunContext): Promise<unknown> } & Record<string, unknown>) {
  return { ...definition, async execute(args: T, exec: ToolRunContext) {
    const violations = validateJsonSchemaValue(definition.parameters, args, "");
    if (violations.length) {
      throw new Error(violations.join("; "));
    }
    return definition.execute(args, exec);
  } };
}

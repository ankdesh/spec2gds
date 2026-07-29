/** Model-SDK-neutral structured tool declarations for external agent hosts. */
export interface CircuitToolDefinition {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  mutating: boolean;
}

const object = (
  properties: Record<string, unknown>,
  required: string[],
): Record<string, unknown> => ({
  type: "object",
  additionalProperties: false,
  properties,
  required,
});

const documentId = { type: "string", minLength: 1 };

export const circuitToolDefinitions: CircuitToolDefinition[] = [
  {
    name: "circuit_document_summary",
    description: "Return counts and diagnostics for one circuit document.",
    input_schema: object({ document_id: documentId }, ["document_id"]),
    mutating: false,
  },
  {
    name: "circuit_component_lookup",
    description: "Find available component definitions by text and origin.",
    input_schema: object({
      document_id: documentId,
      text: { type: "string" },
      origin: { enum: ["local", "builtin", "provider"] },
    }, ["document_id"]),
    mutating: false,
  },
  {
    name: "circuit_subgraph",
    description: "Return a selected circuit neighborhood for focused reasoning.",
    input_schema: object({
      document_id: documentId,
      element_ids: { type: "array", items: { type: "string" }, minItems: 1 },
      depth: { type: "integer", minimum: 0, maximum: 8 },
    }, ["document_id", "element_ids"]),
    mutating: false,
  },
  {
    name: "circuit_export",
    description: "Render canonical JSON, deterministic SVG, or PNG.",
    input_schema: object({
      document_id: documentId,
      format: { enum: ["json", "svg", "png"] },
      selection: { type: "array", items: { type: "string" } },
    }, ["document_id", "format"]),
    mutating: false,
  },
  {
    name: "circuit_validate_construction",
    description: "Compile and validate a compact complete-circuit construction.",
    input_schema: object({ construction: { $ref: "#/$defs/CircuitConstruction" } }, ["construction"]),
    mutating: false,
  },
  {
    name: "circuit_preview_operations",
    description: "Atomically preview a revision-guarded operation batch.",
    input_schema: object({
      document_id: documentId,
      batch: { $ref: "#/$defs/CircuitOperationBatch" },
    }, ["document_id", "batch"]),
    mutating: false,
  },
  {
    name: "circuit_submit_proposal",
    description: "Submit an immutable construction or operation proposal for human decision.",
    input_schema: object({ proposal: { $ref: "#/$defs/CircuitProposal" } }, ["proposal"]),
    mutating: true,
  },
];

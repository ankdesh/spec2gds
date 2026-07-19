import Ajv2020, { type ErrorObject, type ValidateFunction } from "ajv/dist/2020.js";
import protocolSchema from "./protocol.schema.json";

export * from "./types.generated";
export * from "./fixtures";

import type {
  AgentProposal,
  ChangePreview,
  CircuitDesignerProtocol,
  CircuitDesignCatalog,
  CircuitGraphSnapshot,
  CircuitNet,
  CircuitNode,
  CircuitTerminal,
  CommandBatch,
  Commands,
  EditLease,
} from "./types.generated";

export type DesignerCommand = Commands[number];

const ajv = new Ajv2020({ allErrors: true, strict: false });
const definitions = (protocolSchema as { $defs?: Record<string, unknown> }).$defs ?? {};
const graphValidator: ValidateFunction<CircuitGraphSnapshot> = ajv.compile({
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $ref: "#/$defs/CircuitGraphSnapshot",
  $defs: definitions,
});
const catalogValidator: ValidateFunction<CircuitDesignCatalog> = ajv.compile({
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $ref: "#/$defs/CircuitDesignCatalog",
  $defs: definitions,
});
const protocolValidator: ValidateFunction<CircuitDesignerProtocol> = ajv.compile(protocolSchema);

export interface ValidationResult {
  valid: boolean;
  errors: ErrorObject[];
}

export function validateGraph(value: unknown): ValidationResult {
  const valid = graphValidator(value);
  return { valid, errors: valid ? [] : [...(graphValidator.errors ?? [])] };
}

export function validateCatalog(value: unknown): ValidationResult {
  const valid = catalogValidator(value);
  return { valid, errors: valid ? [] : [...(catalogValidator.errors ?? [])] };
}

export interface CircuitDesignerReadOptions {
  signal?: AbortSignal;
}

/** Renderer-independent read interface shared by UI code and programmatic clients. */
export interface CircuitDesignerReadApi {
  getCatalog(options?: CircuitDesignerReadOptions): Promise<CircuitDesignCatalog>;
  getGraph(designId: string, options?: CircuitDesignerReadOptions): Promise<CircuitGraphSnapshot>;
}

export interface CircuitHistoryStatus {
  can_undo: boolean;
  can_redo: boolean;
}

export interface CircuitHistoryResult extends CircuitHistoryStatus {
  graph: CircuitGraphSnapshot;
}

export interface CircuitDesignerApi extends CircuitDesignerReadApi {
  getLease(options?: CircuitDesignerReadOptions): Promise<EditLease | null>;
  acquireLease(ownerId: string, ownerKind: "human" | "agent", ttlSeconds?: number): Promise<EditLease>;
  releaseLease(leaseId: string): Promise<void>;
  preview(batch: CommandBatch): Promise<ChangePreview>;
  apply(batch: CommandBatch, leaseId: string): Promise<ChangePreview>;
  getHistory(): Promise<CircuitHistoryStatus>;
  undo(leaseId: string, designId: string): Promise<CircuitHistoryResult>;
  redo(leaseId: string, designId: string): Promise<CircuitHistoryResult>;
  listProposals(): Promise<AgentProposal[]>;
  submitProposal(proposal: AgentProposal): Promise<AgentProposal>;
  decideProposal(proposalId: string, decision: "accepted" | "rejected", leaseId?: string): Promise<AgentProposal>;
}

export function validateProtocol(value: unknown): ValidationResult {
  const valid = protocolValidator(value);
  return { valid, errors: valid ? [] : [...(protocolValidator.errors ?? [])] };
}

const definitionValidators = new Map<string, ValidateFunction>();

export function validateContractDefinition(name: string, value: unknown): ValidationResult {
  let validator = definitionValidators.get(name);
  if (!validator) {
    if (!(name in definitions)) return { valid: false, errors: [] };
    validator = ajv.compile({
      $schema: "https://json-schema.org/draft/2020-12/schema",
      $ref: `#/$defs/${name}`,
      $defs: definitions,
    });
    definitionValidators.set(name, validator);
  }
  const valid = validator(value);
  return { valid, errors: valid ? [] : [...(validator.errors ?? [])] };
}

export interface GraphIndex {
  nodes: Map<string, CircuitNode>;
  terminals: Map<string, CircuitTerminal>;
  nets: Map<string, CircuitNet>;
  terminalNets: Map<string, CircuitNet[]>;
}

export function indexGraph(graph: CircuitGraphSnapshot): GraphIndex {
  const terminalNets = new Map<string, CircuitNet[]>();
  for (const terminal of graph.terminals) terminalNets.set(terminal.id, []);
  for (const net of graph.nets) {
    for (const endpoint of net.endpoints) {
      terminalNets.get(endpoint.terminal_id)?.push(net);
    }
  }
  return {
    nodes: new Map(graph.nodes.map((node) => [node.id, node])),
    terminals: new Map(graph.terminals.map((terminal) => [terminal.id, terminal])),
    nets: new Map(graph.nets.map((net) => [net.id, net])),
    terminalNets,
  };
}

export function connectedNodeIds(graph: CircuitGraphSnapshot, nodeId: string): string[] {
  const index = indexGraph(graph);
  const node = index.nodes.get(nodeId);
  if (!node) return [];
  const connected = new Set<string>();
  for (const terminalId of node.terminal_ids ?? []) {
    for (const net of index.terminalNets.get(terminalId) ?? []) {
      for (const endpoint of net.endpoints) {
        const peerNode = index.terminals.get(endpoint.terminal_id)?.node_id;
        if (peerNode && peerNode !== nodeId) connected.add(peerNode);
      }
    }
  }
  return [...connected].sort();
}

export function createCommandBatch(
  batchId: string,
  expectedSourceRevisionHash: string,
  commands: DesignerCommand[],
): CommandBatch {
  if (!commands.length) throw new Error("A command batch requires at least one command.");
  return {
    batch_id: batchId,
    expected_source_revision_hash: expectedSourceRevisionHash,
    commands: commands as Commands,
  };
}

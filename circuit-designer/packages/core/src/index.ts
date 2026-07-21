import Ajv2020, { type ErrorObject, type ValidateFunction } from "ajv/dist/2020.js";
import protocolSchema from "./protocol.schema.json";

export * from "./types.generated";
export * from "./fixtures";
export * from "./route-editor";

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
  NetRoute,
  ValidationDiagnostic,
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

/** Validate route-tree topology and its correspondence with one semantic net. */
export function validateNetRoute(graph: CircuitGraphSnapshot, netId: string, route: NetRoute): ValidationDiagnostic[] {
  const diagnostics: ValidationDiagnostic[] = [];
  const report = (code: string, message: string): void => {
    diagnostics.push({ severity: "error", code, message, element_id: netId });
  };
  const net = graph.nets.find((item) => item.id === netId);
  if (!net) { report("unknown_net", `Unknown net: ${netId}`); return diagnostics; }
  const vertices = new Map<string, NetRoute["vertices"][number]>();
  for (const vertex of route.vertices) {
    if (vertices.has(vertex.id)) report("duplicate_route_vertex", `Route vertex id is duplicated: ${vertex.id}`);
    vertices.set(vertex.id, vertex);
    if (!Number.isFinite(vertex.point.x) || !Number.isFinite(vertex.point.y)) report("invalid_route_coordinate", `Route vertex ${vertex.id} has a non-finite coordinate.`);
  }
  const segmentIds = new Set<string>();
  const segmentKeys = new Set<string>();
  const adjacency = new Map([...vertices.keys()].map((id) => [id, new Set<string>()]));
  for (const [index, segment] of route.segments.entries()) {
    const id = segment.id ?? `segment:${index}`;
    if (segmentIds.has(id)) report("duplicate_route_segment_id", `Route segment id is duplicated: ${id}`);
    segmentIds.add(id);
    const start = vertices.get(segment.from_vertex);
    const end = vertices.get(segment.to_vertex);
    if (!start || !end) { report("unknown_route_vertex", `Route segment ${id} references an unknown vertex.`); continue; }
    const key = [start.id, end.id].sort().join("|");
    if (segmentKeys.has(key)) report("duplicate_route_segment", `Route contains duplicate segment ${key}.`);
    segmentKeys.add(key);
    if (start.id === end.id || (start.point.x === end.point.x && start.point.y === end.point.y)) report("zero_length_route_segment", `Route segment ${id} has zero length.`);
    else if (start.point.x !== end.point.x && start.point.y !== end.point.y) report("diagonal_route_segment", `Route segment ${id} is not orthogonal.`);
    adjacency.get(start.id)?.add(end.id); adjacency.get(end.id)?.add(start.id);
  }
  if (vertices.size) {
    const visited = new Set<string>();
    const stack = [vertices.keys().next().value as string];
    while (stack.length) {
      const id = stack.pop()!;
      if (visited.has(id)) continue;
      visited.add(id); stack.push(...(adjacency.get(id) ?? []));
    }
    if (visited.size !== vertices.size) report("disconnected_route", "Route vertices must form one connected tree.");
    if (route.segments.length !== route.vertices.length - 1) report("cyclic_route", "A route must be acyclic and contain exactly vertices - 1 segments.");
  }
  const endpointVertices = route.vertices.filter((vertex) => vertex.kind === "endpoint");
  const expectedTerminals = [...net.endpoints.map((endpoint) => endpoint.terminal_id)].sort();
  const actualTerminals = endpointVertices.flatMap((vertex) => vertex.terminal_id ? [vertex.terminal_id] : []).sort();
  if (expectedTerminals.join("\0") !== actualTerminals.join("\0")) report("route_endpoint_mismatch", "Route endpoints must exactly match the semantic net endpoints.");
  for (const vertex of route.vertices) {
    const degree = adjacency.get(vertex.id)?.size ?? 0;
    if (vertex.kind === "endpoint" && degree !== 1) report("invalid_endpoint_degree", `Endpoint ${vertex.id} must have electrical degree one.`);
    if (vertex.kind === "junction" && degree < 3) report("invalid_junction_degree", `Junction ${vertex.id} must have electrical degree three or greater.`);
    if (vertex.kind === "bend" && degree !== 2) report("invalid_bend_degree", `Bend ${vertex.id} must have electrical degree two.`);
  }
  return diagnostics;
}

import Ajv2020, { type ErrorObject, type ValidateFunction } from "ajv/dist/2020.js";
import protocolSchema from "./protocol.schema.json";
import type {
  CircuitDocument,
  Diagnostic,
  NetRoute,
} from "./types.generated";
import type { CircuitGraphView } from "./model";
import { validateDocumentSemantics } from "./model";

export * from "./types.generated";
export * from "./model";
export * from "./engine";
export * from "./draft";
export * from "./primitives";
export * from "./fixtures";
export * from "./backend";
export * from "./hierarchy";
export * from "./export";
export * from "./tools";
export * from "./route-editor";
export * from "./preferences";
export * from "./source-binding";
export * from "./timing";
export * from "./theme";

const ajv = new Ajv2020({ allErrors: true, strict: false });
const definitions = (protocolSchema as { $defs?: Record<string, unknown> }).$defs ?? {};
const protocolValidator = ajv.compile(protocolSchema);
const definitionValidators = new Map<string, ValidateFunction>();

/** The logical operation subset offered to assistant clients by Circuit Designer. */
export function assistantCircuitOperationSchema(): Record<string, unknown> {
  const allowed = new Set([
    "AddComponentOperation", "UpdateComponentOperation", "RemoveComponentOperation",
    "AddInstanceOperation", "UpdateInstanceOperation", "RemoveInstanceOperation",
    "AddBoundaryTerminalOperation", "UpdateBoundaryTerminalOperation", "RemoveBoundaryTerminalOperation",
    "CreateNetOperation", "UpdateNetOperation", "DeleteNetOperation",
    "ConnectEndpointOperation", "DisconnectEndpointOperation",
  ]);
  const operation = definitions.CircuitOperation as { oneOf: Array<{ $ref: string }> };
  const branches = operation.oneOf.filter(branch => allowed.has(branch.$ref.split("/").at(-1) ?? ""));
  const selected: Record<string, unknown> = {};
  const visit = (value: unknown): void => {
    if (Array.isArray(value)) { value.forEach(visit); return; }
    if (!value || typeof value !== "object") return;
    const node = value as Record<string, unknown>;
    if (typeof node.$ref === "string" && node.$ref.startsWith("#/$defs/")) {
      const name = node.$ref.slice("#/$defs/".length);
      if (!(name in selected) && name in definitions) {
        selected[name] = definitions[name];
        visit(definitions[name]);
      }
    }
    Object.values(node).forEach(visit);
  };
  visit(branches);
  return {
    $schema: "https://json-schema.org/draft/2020-12/schema",
    oneOf: branches,
    $defs: selected,
  };
}

export interface SchemaValidationResult {
  valid: boolean;
  errors: ErrorObject[];
}

export interface DocumentValidationResult extends SchemaValidationResult {
  diagnostics: Diagnostic[];
}

/** Validate any named JSON Schema definition from the published protocol bundle. */
export function validateContractDefinition(name: string, value: unknown): SchemaValidationResult {
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

export function validateProtocol(value: unknown): SchemaValidationResult {
  const valid = protocolValidator(value);
  return { valid, errors: valid ? [] : [...(protocolValidator.errors ?? [])] };
}

/** Run both portable JSON shape validation and cross-reference/electrical validation. */
export function validateCircuitDocument(value: unknown): DocumentValidationResult {
  const schema = validateContractDefinition("CircuitDocument", value);
  if (!schema.valid) {
    return {
      ...schema,
      diagnostics: schema.errors.map((error) => ({
        severity: "error",
        code: "schema_validation",
        message: `${error.instancePath || "/"} ${error.message ?? "is invalid"}`,
        ...(error.instancePath ? { path: error.instancePath } : {}),
      })),
    };
  }
  const diagnostics = validateDocumentSemantics(value as CircuitDocument);
  return {
    ...schema,
    valid: !diagnostics.some((item) => item.severity === "error"),
    diagnostics,
  };
}

/** Validate route-tree topology and its correspondence with one flattened semantic net. */
export function validateNetRoute(graph: CircuitGraphView, netId: string, route: NetRoute): Diagnostic[] {
  const diagnostics: Diagnostic[] = [];
  const report = (code: string, message: string): void => {
    diagnostics.push({ severity: "error", code, message, element_key: netId });
  };
  const net = graph.nets.find((item) => item.id === netId);
  if (!net) {
    report("unknown_net", `Unknown net: ${netId}`);
    return diagnostics;
  }
  const vertices = new Map<string, NetRoute["vertices"][number]>();
  for (const vertex of route.vertices) {
    if (vertices.has(vertex.id)) report("duplicate_route_vertex", `Route vertex id is duplicated: ${vertex.id}`);
    vertices.set(vertex.id, vertex);
    if (!Number.isFinite(vertex.point.x) || !Number.isFinite(vertex.point.y)) {
      report("invalid_route_coordinate", `Route vertex ${vertex.id} has a non-finite coordinate.`);
    }
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
    if (!start || !end) {
      report("unknown_route_vertex", `Route segment ${id} references an unknown vertex.`);
      continue;
    }
    const key = [start.id, end.id].sort().join("|");
    if (segmentKeys.has(key)) report("duplicate_route_segment", `Route contains duplicate segment ${key}.`);
    segmentKeys.add(key);
    if (start.id === end.id || (start.point.x === end.point.x && start.point.y === end.point.y)) {
      report("zero_length_route_segment", `Route segment ${id} has zero length.`);
    } else if (start.point.x !== end.point.x && start.point.y !== end.point.y) {
      report("diagonal_route_segment", `Route segment ${id} is not orthogonal.`);
    }
    adjacency.get(start.id)?.add(end.id);
    adjacency.get(end.id)?.add(start.id);
  }
  if (vertices.size) {
    const visited = new Set<string>();
    const stack = [vertices.keys().next().value as string];
    while (stack.length) {
      const id = stack.pop()!;
      if (visited.has(id)) continue;
      visited.add(id);
      stack.push(...(adjacency.get(id) ?? []));
    }
    if (visited.size !== vertices.size) report("disconnected_route", "Route vertices must form one connected tree.");
    if (route.segments.length !== route.vertices.length - 1) {
      report("cyclic_route", "A route must be acyclic and contain exactly vertices - 1 segments.");
    }
  }
  const expectedTerminals = net.endpoints.map((endpoint) => endpoint.terminal_id).sort();
  const actualTerminals = route.vertices
    .filter((vertex) => vertex.kind === "endpoint")
    .flatMap((vertex) => vertex.terminal_id ? [vertex.terminal_id] : [])
    .sort();
  if (expectedTerminals.join("\0") !== actualTerminals.join("\0")) {
    report("route_endpoint_mismatch", "Route endpoints must exactly match the semantic net endpoints.");
  }
  for (const vertex of route.vertices) {
    const degree = adjacency.get(vertex.id)?.size ?? 0;
    if (vertex.kind === "endpoint" && degree !== 1) report("invalid_endpoint_degree", `Endpoint ${vertex.id} must have electrical degree one.`);
    if (vertex.kind === "junction" && degree < 3) report("invalid_junction_degree", `Junction ${vertex.id} must have electrical degree three or greater.`);
    if (vertex.kind === "bend" && degree !== 2) report("invalid_bend_degree", `Bend ${vertex.id} must have electrical degree two.`);
  }
  return diagnostics;
}

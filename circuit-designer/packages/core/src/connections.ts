import type { CircuitDocument, CircuitOperation, NetEndpoint } from "./types.generated";
import { endpointTerminalKey, validateDocumentSemantics } from "./model";

export class ConnectionChoiceRequired extends Error {
  constructor(readonly netIds: string[]) {
    super("Choose the existing net and its endpoint mapping before connecting this bus.");
  }
}

function terminal(document: CircuitDocument, endpoint: NetEndpoint) {
  return endpoint.kind === "boundary"
    ? document.design.boundary_terminals.find(item => item.id === endpoint.terminal_id)
    : document.components.find(item => item.id === document.design.instances.find(instance => instance.id === endpoint.instance_id)?.component_id)
      ?.terminals.find(item => item.id === endpoint.terminal_id);
}

function rangeKey(document: CircuitDocument, endpoint: NetEndpoint): string {
  const width = terminal(document, endpoint)?.width;
  return endpoint.slice ? `${endpoint.slice.lsb}:${endpoint.slice.width}` : `0:${width}`;
}

export function sameConnectionEndpoint(document: CircuitDocument, a: NetEndpoint, b: NetEndpoint): boolean {
  return endpointTerminalKey(a) === endpointTerminalKey(b) && rangeKey(document, a) === rangeKey(document, b);
}

/** Plan one manual connection without changing the document or weakening import validation. */
export function planConnection(
  document: CircuitDocument,
  endpoints: NetEndpoint[],
  options: { operationId: string; netId: string; label: string; existingNetId?: string; route?: CircuitDocument["layout"]["net_routes"][string] },
): CircuitOperation | undefined {
  if (!endpoints.length) throw new Error("Choose a connection endpoint.");
  for (const endpoint of endpoints) {
    if (!terminal(document, endpoint)) throw new Error("Choose a valid connection terminal.");
    if (endpoint.slice && (!Number.isInteger(endpoint.slice.lsb) || endpoint.slice.lsb < 0 || !Number.isInteger(endpoint.slice.width) || endpoint.slice.width <= 0)) throw new Error("Use a non-negative integer offset and a positive integer width.");
  }
  let net = options.existingNetId ? document.design.nets.find(item => item.id === options.existingNetId) : undefined;
  if (options.existingNetId && !net) throw new Error("Choose an existing net.");
  if (!net) {
    const matches = document.design.nets.filter(item => item.endpoints.some(saved => endpoints.some(endpoint => sameConnectionEndpoint(document, saved, endpoint))));
    if (matches.length > 1) throw new Error("These terminals belong to different nets. Disconnect them before reconnecting.");
    net = matches[0];
    const ambiguous = document.design.nets.filter(item => item.endpoints.some(saved => endpoints.some(endpoint =>
      endpointTerminalKey(saved) === endpointTerminalKey(endpoint) && !endpoint.slice && !sameConnectionEndpoint(document, saved, endpoint))));
    if (ambiguous.length) throw new ConnectionChoiceRequired(ambiguous.map(item => item.id));
  }
  const additions = net ? endpoints.filter(endpoint => !net!.endpoints.some(saved => sameConnectionEndpoint(document, saved, endpoint))) : endpoints;
  if (!additions.length) return undefined;
  if (net && additions.length !== 1) throw new Error("Select one new endpoint for this net.");
  const route = options.route ?? (net ? document.layout.net_routes[net.id] : undefined);
  if (net && (route?.vertices.some(item => item.locked) || route?.segments.some(item => item.locked))) {
    throw new Error("Unlock this net's route before adding an endpoint.");
  }
  const candidate = structuredClone(document);
  const changed: CircuitDocument["design"]["nets"][number] = net
    ? candidate.design.nets.find(item => item.id === net!.id)!
    : { id: options.netId, label: options.label, endpoints: [endpoints[0], ...endpoints.slice(1)] };
  if (net) changed.endpoints.push(...additions);
  else candidate.design.nets.push(changed);
  delete candidate.layout.net_routes[changed.id];
  const invalid = validateDocumentSemantics(candidate).filter(item => item.severity === "error" || (
    item.element_key === changed.id && ["width_mismatch", "multiple_net_sources", "net_without_source"].includes(item.code)
  ));
  if (invalid.length) throw new Error(invalid.map(item => item.message).join(" · "));
  if (net) return { operation_id: options.operationId, type: "connect_endpoint", net_id: net.id, endpoint: additions[0] };
  return { operation_id: options.operationId, type: "create_net", net: changed };
}

import type { CircuitDocument, CircuitTimingAnalysis, NetEndpoint } from "@spec2gds/circuit-core";

/** Resolve repeated instance subjects in the same order as the timing engine. */
export function timingPathEndpoints(document: CircuitDocument, paths: CircuitTimingAnalysis["paths"], index: number) {
  const path = paths[index];
  const net = document.design.nets.find(item => item.id === path.net_id);
  const subject = (endpoint: NetEndpoint) => endpoint.kind === "boundary" ? `boundary:${endpoint.terminal_id}` : `instance:${endpoint.instance_id}`;
  const isSink = (endpoint: NetEndpoint) => {
    const port = endpoint.kind === "boundary" ? document.design.boundary_terminals.find(item => item.id === endpoint.terminal_id)
      : document.components.find(item => item.id === document.design.instances.find(instance => instance.id === endpoint.instance_id)?.component_id)?.terminals.find(item => item.id === endpoint.terminal_id);
    return port?.direction === (endpoint.kind === "boundary" ? "output" : "input");
  };
  const source = net?.endpoints.find(endpoint => subject(endpoint) === path.source && !isSink(endpoint));
  const occurrence = paths.slice(0, index).filter(item => item.net_id === path.net_id && item.source === path.source && item.target === path.target).length;
  const target = net?.endpoints.filter(endpoint => subject(endpoint) === path.target)[occurrence];
  return { net, source, target };
}

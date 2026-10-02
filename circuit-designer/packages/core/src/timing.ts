/** Semantic stage/clock analysis independent of route geometry.
 * Cycle edges annotate pipeline boundaries; do not infer clocks or electrical
 * behavior from where a line happens to cross the canvas. Source adapters map
 * these stable semantic references before saving package annotations. */
import type {
  CircuitDocument,
  CircuitTimingV1,
  ClockDomainV1,
  CycleEdgeMarkerV1,
  Diagnostic,
  NetEndpoint,
  NodeGeometry,
} from "./types.generated";
const clone = <T>(value: T): T => structuredClone(value);

export const DEFAULT_CLOCK_DOMAIN_ID = "default";
export const DEFAULT_CLOCK_DOMAIN: ClockDomainV1 = { id: DEFAULT_CLOCK_DOMAIN_ID, label: "clk" };

export type TimingSubjectKey = `instance:${string}` | `boundary:${string}`;

export interface TimingSubjectStage {
  subject_key: TimingSubjectKey;
  stage: number;
  domain_id: string;
}

export interface TimingPathAnalysis {
  net_id: string;
  source: TimingSubjectKey;
  target: TimingSubjectKey;
  status: "ready" | "cdc" | "backward" | "unavailable";
  cycles?: number;
  source_stage?: number;
  target_stage?: number;
  source_domain_id: string;
  target_domain_id: string;
  message?: string;
}

export interface CircuitTimingAnalysis {
  subjects: TimingSubjectStage[];
  paths: TimingPathAnalysis[];
  diagnostics: Diagnostic[];
}

export function emptyCircuitTiming(): CircuitTimingV1 {
  return {
    schema_version: 1,
    clock_domains: [clone(DEFAULT_CLOCK_DOMAIN)],
    cycle_edges: [],
    subject_domain_overrides: {},
  };
}

export function effectiveCircuitTiming(document: Pick<CircuitDocument, "timing">): CircuitTimingV1 {
  if (!document.timing) return emptyCircuitTiming();
  const result = clone(document.timing);
  if (!result.clock_domains.some((domain) => domain.id === DEFAULT_CLOCK_DOMAIN_ID)) {
    result.clock_domains.unshift(clone(DEFAULT_CLOCK_DOMAIN));
  }
  return result;
}

export function sortedCycleEdges(timing: CircuitTimingV1): CycleEdgeMarkerV1[] {
  return [...timing.cycle_edges].sort((left, right) => left.x - right.x || left.id.localeCompare(right.id));
}

export function stageLabel(timing: CircuitTimingV1, stage: number): string {
  if (stage === 0) return timing.leading_stage_label ?? "Stage 0";
  const edge = sortedCycleEdges(timing)[stage - 1];
  return edge?.next_stage_label ?? `Stage ${stage}`;
}

/** Return the stage containing an entire horizontal span, or undefined when an edge bisects it. */
export function stageForHorizontalSpan(timing: CircuitTimingV1, left: number, right: number): number | undefined {
  const edges = sortedCycleEdges(timing);
  if (edges.some((edge) => edge.x > left && edge.x < right)) return undefined;
  return edges.filter((edge) => edge.x <= left).length;
}

export function timingSubjectDomain(timing: CircuitTimingV1, key: TimingSubjectKey): string {
  return timing.subject_domain_overrides[key] ?? DEFAULT_CLOCK_DOMAIN_ID;
}

function subjectKey(endpoint: NetEndpoint): TimingSubjectKey {
  return endpoint.kind === "instance" ? `instance:${endpoint.instance_id}` : `boundary:${endpoint.terminal_id}`;
}

function endpointDirection(document: CircuitDocument, endpoint: NetEndpoint): "source" | "sink" | "both" | undefined {
  if (endpoint.kind === "boundary") {
    const terminal = document.design.boundary_terminals.find((item) => item.id === endpoint.terminal_id);
    if (!terminal) return undefined;
    return terminal.direction === "input" ? "source" : terminal.direction === "output" ? "sink" : "both";
  }
  const instance = document.design.instances.find((item) => item.id === endpoint.instance_id);
  const component = document.components.find((item) => item.id === instance?.component_id);
  const terminal = component?.terminals.find((item) => item.id === endpoint.terminal_id);
  if (!terminal) return undefined;
  return terminal.direction === "output" ? "source" : terminal.direction === "input" ? "sink" : "both";
}

function subjectGeometry(
  document: CircuitDocument,
  key: TimingSubjectKey,
  boundaryGeometry: Record<string, NodeGeometry>,
): NodeGeometry | undefined {
  if (key.startsWith("instance:")) return document.layout.instance_geometry[key.slice("instance:".length)];
  const id = key.slice("boundary:".length);
  return boundaryGeometry[key] ?? boundaryGeometry[id];
}

export function validateCircuitTiming(document: CircuitDocument): Diagnostic[] {
  const timing = effectiveCircuitTiming(document);
  const diagnostics: Diagnostic[] = [];
  const report = (severity: Diagnostic["severity"], code: string, message: string, element_key?: string): void => {
    diagnostics.push({ severity, code, message, ...(element_key ? { element_key } : {}) });
  };
  const domainIds = new Set<string>();
  for (const domain of timing.clock_domains) {
    if (domainIds.has(domain.id)) report("error", "duplicate_clock_domain", `Clock domain ${domain.id} is duplicated.`, domain.id);
    domainIds.add(domain.id);
    if (domain.signal?.kind === "boundary" && !document.design.boundary_terminals.some((item) => item.id === domain.signal?.id)) {
      report("error", "unknown_clock_signal", `Clock domain ${domain.label} references an unknown boundary terminal.`, domain.id);
    }
    if (domain.signal?.kind === "net" && !document.design.nets.some((item) => item.id === domain.signal?.id)) {
      report("error", "unknown_clock_signal", `Clock domain ${domain.label} references an unknown net.`, domain.id);
    }
  }
  if (!domainIds.has(DEFAULT_CLOCK_DOMAIN_ID)) report("error", "missing_default_clock_domain", "Timing must contain the default clock domain.");
  const edgeIds = new Set<string>();
  const edgePositions = new Set<number>();
  for (const edge of timing.cycle_edges) {
    if (!Number.isFinite(edge.x)) report("error", "invalid_cycle_edge_position", `Cycle edge ${edge.id} has a non-finite position.`, edge.id);
    if (edgeIds.has(edge.id)) report("error", "duplicate_cycle_edge", `Cycle edge ${edge.id} is duplicated.`, edge.id);
    if (edgePositions.has(edge.x)) report("error", "duplicate_cycle_edge_position", `More than one cycle edge is placed at x=${edge.x}.`, edge.id);
    edgeIds.add(edge.id);
    edgePositions.add(edge.x);
    for (const [instanceId, geometry] of Object.entries(document.layout.instance_geometry)) {
      if (edge.x > geometry.x && edge.x < geometry.x + geometry.width) {
        report("error", "cycle_edge_intersects_instance", `Cycle edge ${edge.id} bisects instance ${instanceId}.`, edge.id);
      }
    }
  }
  const knownSubjects = new Set<string>([
    ...document.design.instances.map((item) => `instance:${item.id}`),
    ...document.design.boundary_terminals.map((item) => `boundary:${item.id}`),
  ]);
  for (const [key, domainId] of Object.entries(timing.subject_domain_overrides)) {
    if (!knownSubjects.has(key)) report("error", "unknown_timing_subject", `Timing references unknown subject ${key}.`, key);
    if (!domainIds.has(domainId)) report("error", "unknown_subject_clock_domain", `${key} references unknown clock domain ${domainId}.`, key);
    if (domainId === DEFAULT_CLOCK_DOMAIN_ID) report("warning", "redundant_default_domain_override", `${key} need not explicitly select the default clock.`, key);
  }
  return diagnostics;
}

export function analyzeCircuitTiming(
  document: CircuitDocument,
  boundaryGeometry: Record<string, NodeGeometry> = {},
): CircuitTimingAnalysis {
  const timing = effectiveCircuitTiming(document);
  const edges = sortedCycleEdges(timing);
  const diagnostics = validateCircuitTiming(document).filter((item) => item.severity !== "error");
  const subjects: TimingSubjectStage[] = [];
  const stages = new Map<TimingSubjectKey, number>();
  const keys: TimingSubjectKey[] = [
    ...document.design.instances.map((item) => `instance:${item.id}` as const),
    ...document.design.boundary_terminals.map((item) => `boundary:${item.id}` as const),
  ];
  for (const key of keys) {
    const geometry = subjectGeometry(document, key, boundaryGeometry);
    if (!geometry) continue;
    const stage = stageForHorizontalSpan(timing, geometry.x, geometry.x + geometry.width);
    if (stage === undefined) {
      diagnostics.push({ severity: "warning", code: "timing_subject_straddles_edge", message: `${key} crosses a cycle edge.`, element_key: key });
      continue;
    }
    stages.set(key, stage);
    subjects.push({ subject_key: key, stage, domain_id: timingSubjectDomain(timing, key) });
  }
  const paths: TimingPathAnalysis[] = [];
  for (const net of document.design.nets) {
    const sources = net.endpoints.filter((endpoint) => endpointDirection(document, endpoint) !== "sink");
    const sinks = net.endpoints.filter((endpoint) => endpointDirection(document, endpoint) !== "source");
    if (sources.length !== 1) {
      diagnostics.push({ severity: "warning", code: "timing_ambiguous_source", message: `Net ${net.label || net.id} does not have exactly one timing source.`, element_key: net.id });
      continue;
    }
    const source = subjectKey(sources[0]);
    for (const sinkEndpoint of sinks.filter((item) => subjectKey(item) !== source)) {
      const target = subjectKey(sinkEndpoint);
      const sourceGeometry = subjectGeometry(document, source, boundaryGeometry);
      const targetGeometry = subjectGeometry(document, target, boundaryGeometry);
      const sourceStage = stages.get(source);
      const targetStage = stages.get(target);
      const sourceDomainId = timingSubjectDomain(timing, source);
      const targetDomainId = timingSubjectDomain(timing, target);
      const base = { net_id: net.id, source, target, source_domain_id: sourceDomainId, target_domain_id: targetDomainId, source_stage: sourceStage, target_stage: targetStage };
      if (!sourceGeometry || !targetGeometry || sourceStage === undefined || targetStage === undefined) {
        paths.push({ ...base, status: "unavailable", message: "Endpoint geometry is unavailable." });
      } else if (sourceDomainId !== targetDomainId) {
        paths.push({ ...base, status: "cdc", message: "Clock-domain crossing; latency is unresolved." });
      } else if (targetGeometry.x < sourceGeometry.x) {
        paths.push({ ...base, status: "backward", message: "The path travels backward across the timing stages." });
      } else {
        const cycles = edges.filter((edge) => edge.x > sourceGeometry.x + sourceGeometry.width && edge.x <= targetGeometry.x).length;
        paths.push({ ...base, status: "ready", cycles });
      }
    }
  }
  return { subjects, paths, diagnostics };
}

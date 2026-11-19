import { useState } from "react";
import { circuitEndpointLabel, type CircuitDocument, type CircuitTimingAnalysis, type CircuitTimingV1 } from "@spec2gds/circuit-core";
import { timingPathEndpoints } from "./timing-presentation";

export function TimingPanel({ document, timing, analysis, onSelect }: {
  document: CircuitDocument; timing: CircuitTimingV1; analysis: CircuitTimingAnalysis;
  onSelect: (netId: string) => void;
}) {
  const [selected, setSelected] = useState<number>();
  const domain = (id: string) => timing.clock_domains.find(item => item.id === id)?.label ?? id;
  return <section aria-label="Timing analysis" className="inspector timing-panel">
    <p className="draw-hint">{timing.cycle_edges.length} cycle edges. Select a path to highlight its net in the circuit.</p>
    <div className="timing-analysis-list">{analysis.paths.map((path, index) => {
      const { net, source, target } = timingPathEndpoints(document, analysis.paths, index);
      return <button type="button" className="timing-path" data-status={path.status} aria-pressed={selected === index} key={index}
        onClick={() => { setSelected(index); onSelect(path.net_id); }}>
        <strong>{net?.label || "Net"}</strong>
        <span>{source ? circuitEndpointLabel(document, source) : path.source} → {target ? circuitEndpointLabel(document, target) : path.target}</span>
        <span>{domain(path.source_domain_id)}{path.source_domain_id !== path.target_domain_id ? ` → ${domain(path.target_domain_id)}` : ""} · {path.status === "ready" ? `${path.cycles ?? 0} ${path.cycles === 1 ? "cycle" : "cycles"}` : path.status === "cdc" ? "Clock-domain crossing" : path.status === "backward" ? "Backward path" : "Timing unavailable"}</span>
        {path.message && <small>{path.message}</small>}
      </button>;
    })}</div>
    {!analysis.paths.length && <p>No directed timing paths yet. Connect a driving port to a receiving port, then check timing again.</p>}
    <details><summary>Technical details</summary><pre>{JSON.stringify(analysis, null, 2)}</pre></details>
  </section>;
}

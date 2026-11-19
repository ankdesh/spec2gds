import { circuitTerminalLabel, type CircuitDocument, type CircuitTerminalView } from "@spec2gds/circuit-core";

export function CircuitPortsPanel({ document, terminals, editable, onSelect, onConnect }: {
  document: CircuitDocument; terminals: CircuitTerminalView[]; editable: boolean;
  onSelect: (terminal: CircuitTerminalView) => void; onConnect: (id: string) => void;
}) {
  const groups = [
    { id: "design", title: "Design ports", detail: "", ports: terminals.filter(port => !port.node_id) },
    ...document.design.instances.map(instance => ({ id: instance.id,
      title: document.components.find(component => component.id === instance.component_id)?.label || instance.component_id,
      detail: instance.label, ports: terminals.filter(port => port.node_id === instance.id) })),
  ];
  return <section aria-label="Circuit ports" className="ports-panel">
    {!terminals.length && <p className="draw-hint">No ports yet. Add a Design port or a Component.</p>}
    {groups.filter(group => group.ports.length).map(group => <section key={group.id} className="port-group" aria-label={group.detail ? `${group.title} · ${group.detail}` : group.title}>
      <header><h3>{group.title}</h3>{group.detail && <small>{group.detail}</small>}</header>
      {group.ports.map(port => {
        const name = circuitTerminalLabel(document, port.id);
        return <div key={port.id} className="port-row">
          <button type="button" className="port-row__select" aria-label={`Select ${name}`} title={name} onClick={() => onSelect(port)}>
            <span>{port.label || port.id}</span><small>{port.direction === "in" ? "in" : port.direction === "out" ? "out" : port.direction}</small>
            <small>{typeof port.width === "number" ? `${port.width} ${port.width === 1 ? "bit" : "bits"}` : port.width || "?"}</small>
          </button>
          <button type="button" className="port-row__connect" aria-label={`Connect from ${name}`} title={`Connect from ${name}`} disabled={!editable} onClick={() => onConnect(port.id)}>
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M2 5h4v6H2zM10 5h4v6h-4zM6 8h4" stroke="currentColor" strokeWidth="1.25" /></svg>
          </button>
        </div>;
      })}
    </section>)}
  </section>;
}

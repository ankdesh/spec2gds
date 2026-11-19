import { useRef, type ReactNode } from "react";

export type CircuitPanel = "inspector" | "ports" | "timing";
const panels: Array<{ id: CircuitPanel; label: string }> = [
  { id: "inspector", label: "Inspector" }, { id: "ports", label: "Ports" }, { id: "timing", label: "Timing" },
];

/** Keep panel contents mounted so each tab retains its scroll and selection. */
export function CircuitSidebar({ open, active, onSelect, onClose, inspector, ports, timing }: {
  open: boolean; active: CircuitPanel; onSelect: (panel: CircuitPanel) => void; onClose: () => void;
  inspector: ReactNode; ports: ReactNode; timing: ReactNode;
}) {
  const tabs = useRef<HTMLDivElement>(null);
  return <aside className="circuit-sidebar" aria-label="Circuit panels" hidden={!open} onKeyDown={event => {
    if (event.key === "Escape") { event.stopPropagation(); onClose(); }
  }}>
    <header className="circuit-sidebar__header">
      <div ref={tabs} role="tablist" aria-label="Circuit panels" onKeyDown={event => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const index = panels.findIndex(panel => panel.id === active);
        const next = event.key === "Home" ? 0 : event.key === "End" ? panels.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + panels.length) % panels.length;
        onSelect(panels[next].id);
        tabs.current?.querySelectorAll<HTMLButtonElement>("[role=tab]")[next]?.focus();
      }}>
        {panels.map(panel => <button key={panel.id} id={`circuit-tab-${panel.id}`} type="button" role="tab"
          aria-selected={active === panel.id} aria-controls={`circuit-panel-${panel.id}`} tabIndex={active === panel.id ? 0 : -1}
          onClick={() => onSelect(panel.id)}>{panel.label}</button>)}
      </div>
      <button type="button" className="panel-collapse" aria-label="Collapse sidebar" title="Collapse sidebar" onClick={onClose}>
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m6 3 5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
    </header>
    {panels.map(panel => <div key={panel.id} id={`circuit-panel-${panel.id}`} role="tabpanel" aria-labelledby={`circuit-tab-${panel.id}`}
      className="circuit-sidebar__panel" hidden={active !== panel.id}>{({ inspector, ports, timing })[panel.id]}</div>)}
  </aside>;
}

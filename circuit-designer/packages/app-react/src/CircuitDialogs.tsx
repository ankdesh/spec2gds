/* Reusable Circuit Designer application shell. */
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { DEFAULT_CLOCK_DOMAIN_ID, circuitEndpointLabel, endpointTerminalKey, type CircuitDocument, type CircuitProposal, type CircuitTimingAnalysis, type CircuitTimingV1, type ClockDomainV1, type CycleEdgeMarkerV1 } from "@spec2gds/circuit-core";
import { connectionSelectionLabel } from "./connection-input";

export type CircuitDialogId = "connect" | "catalog" | "new-component" | "proposals" | "clock-settings" | "timing-analysis" | "cycle-edge" | "getting-started" | "about";

function CircuitModal({ children, onClose, title }: { children: ReactNode; onClose: () => void; title: string }) {
  const dialogRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const menuTrigger = previousFocus?.closest(".circuit-menu")?.querySelector<HTMLElement>(":scope > button");
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault(); onCloseRef.current(); return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex='-1'])",
      ) ?? []);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLElement>("[autofocus], button, input, select")?.focus());
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (previousFocus?.isConnected && previousFocus !== document.body) {
        previousFocus.focus();
      } else if (menuTrigger?.isConnected) {
        menuTrigger.focus();
      }
    };
  }, []);

  return <div className="circuit-dialog-backdrop" onMouseDown={onClose} role="presentation">
    <section
      aria-labelledby="circuit-dialog-title"
      aria-modal="true"
      className="circuit-dialog"
      onMouseDown={(event) => event.stopPropagation()}
      ref={dialogRef}
      role="dialog"
    >
      <header><h2 id="circuit-dialog-title">{title}</h2><button aria-label="Close" className="dialog-close" onClick={onClose} type="button">×</button></header>
      {children}
    </section>
  </div>;
}

export function CircuitConfirmationDialog({
  title,
  message,
  confirmLabel,
  onCancel,
  onConfirm,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return <CircuitModal onClose={onCancel} title={title}>
    <div className="circuit-dialog__copy"><p>{message}</p></div>
    <div className="circuit-dialog__actions">
      <button autoFocus onClick={onCancel} type="button">Cancel</button>
      <button className="danger" onClick={onConfirm} type="button">{confirmLabel}</button>
    </div>
  </CircuitModal>;
}

export interface CircuitDialogsProps {
  dialog?: CircuitDialogId;
  document?: CircuitDocument;
  sourceDescription: string;
  onRenameComponent?: (id: string, name: string) => void;
  sourceIdentifierPattern?: string;
  sourceIdentifierHint?: string;
  proposals: CircuitProposal[];
  terminals: Array<{ id: string; label?: string; width?: number | string; direction?: string }>;
  netName: string;
  existingNetId?: string;
  connectionError?: string;
  onExistingNetChange: (id: string | undefined) => void;
  endpointA: string;
  endpointB: string;
  sliceLsb: number;
  sliceLsbB: number;
  sliceWidth: number;
  componentName: string;
  onClose: () => void;
  onNetNameChange: (value: string) => void;
  onEndpointAChange: (value: string) => void;
  onEndpointBChange: (value: string) => void;
  onSliceLsbChange: (value: number) => void;
  onSliceLsbBChange: (value: number) => void;
  onSliceWidthChange: (value: number) => void;
  onCreateConnection: () => boolean;
  onComponentNameChange: (value: string) => void;
  onCreateComponent: () => void;
  onPlaceComponent: (componentId: string, instanceName?: string) => boolean;
  onDecideProposal: (proposalId: string, decision: "accept" | "reject") => void;
  timing: CircuitTimingV1;
  timingAnalysis: CircuitTimingAnalysis;
  selectedCycleEdge?: CycleEdgeMarkerV1;
  selectedTimingSubject?: string;
  onSetClockDomain: (domain: ClockDomainV1) => void;
  onRemoveClockDomain: (domainId: string) => void;
  onAssignClockDomain: (subjectKey: string, domainId?: string) => void;
  onUpdateCycleEdge: (edge: CycleEdgeMarkerV1) => void;
}

export function CircuitDialogs(props: CircuitDialogsProps) {
  const [selectedComponentId, setSelectedComponentId] = useState<string>();
  const [instanceName, setInstanceName] = useState("");
  useEffect(() => setInstanceName(""), [props.dialog, selectedComponentId]);
  const [clockLabel, setClockLabel] = useState("clk");
  const [clockSignal, setClockSignal] = useState("");
  const [newDomainLabel, setNewDomainLabel] = useState("");
  const [edgeLabel, setEdgeLabel] = useState("");
  const [stageLabel, setStageLabel] = useState("");
  const [edgeX, setEdgeX] = useState(0);
  useEffect(() => {
    const domain = props.timing.clock_domains.find((item) => item.id === DEFAULT_CLOCK_DOMAIN_ID);
    setClockLabel(domain?.label ?? "clk");
    setClockSignal(domain?.signal ? `${domain.signal.kind}:${domain.signal.id}` : "");
  }, [props.dialog, props.timing.clock_domains]);
  useEffect(() => {
    setEdgeLabel(props.selectedCycleEdge?.label ?? "");
    setStageLabel(props.selectedCycleEdge?.next_stage_label ?? "");
    setEdgeX(props.selectedCycleEdge?.x ?? 0);
  }, [props.dialog, props.selectedCycleEdge]);
  if (!props.dialog) return null;

  if (props.dialog === "connect") {
    const existing = props.existingNetId !== undefined;
    const net = props.document?.design.nets.find(item => item.id === props.existingNetId);
    const firstEndpoint = net?.endpoints[0];
    const netWidth = firstEndpoint?.slice?.width ?? props.terminals.find(item => firstEndpoint && item.id === endpointTerminalKey(firstEndpoint))?.width;
    const a = props.terminals.find(item => item.id === props.endpointA);
    const b = props.terminals.find(item => item.id === props.endpointB);
    const width = props.sliceWidth || (existing ? netWidth : a?.width === b?.width ? a?.width : undefined);
    const from = existing ? net?.label || net?.id : a && connectionSelectionLabel(a.label || a.id, a.width, props.sliceLsb, props.sliceWidth);
    const to = b && connectionSelectionLabel(b.label || b.id, b.width, props.sliceLsbB, props.sliceWidth);
    const submit = (event: FormEvent) => {
      event.preventDefault();
      if (props.onCreateConnection()) props.onClose();
    };
    return <CircuitModal onClose={props.onClose} title="Create connection">
      <form className="circuit-dialog__form" onSubmit={submit}>
        <label>Connection action<select autoFocus value={existing ? "existing" : "new"} onChange={(event) => props.onExistingNetChange(event.target.value === "existing" ? "" : undefined)}><option value="new">New net</option><option value="existing">Add endpoint to existing net</option></select></label>
        {existing ? <>
          <label>Existing net<select aria-label="Existing net" value={props.existingNetId} onChange={(event) => props.onExistingNetChange(event.target.value)}><option value="">Choose…</option>{props.document?.design.nets.map(item => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}</select></label>
          {net && props.document && <p>Net width: {netWidth ?? "unresolved"}. Current endpoints: {net.endpoints.map(endpoint => {
            const terminal = props.terminals.find(item => item.id === endpointTerminalKey(endpoint));
            const role = terminal?.direction === "inout" ? "bidirectional"
              : terminal?.direction === (endpoint.kind === "boundary" ? "in" : "out") ? "driver" : "sink";
            return `${circuitEndpointLabel(props.document!, endpoint)} (${role})`;
          }).join(", ")}</p>}
        </> : <>
          <label>Net label<input value={props.netName} onChange={(event) => props.onNetNameChange(event.target.value)} /></label>
          <label>Endpoint A<select aria-label="Endpoint A" value={props.endpointA} onChange={(event) => props.onEndpointAChange(event.target.value)}><option value="">Choose…</option>{props.terminals.map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.label || "Port"}</option>)}</select></label>
        </>}
        <label>Endpoint B<select aria-label="Endpoint B" value={props.endpointB} onChange={(event) => props.onEndpointBChange(event.target.value)}><option value="">Choose…</option>{props.terminals.filter((terminal) => terminal.id !== props.endpointA).map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.label || "Port"}</option>)}</select></label>
        <div className="slice-row">{!existing && <label>LSB for A<input min="0" type="number" value={props.sliceLsb} onChange={(event) => props.onSliceLsbChange(Number(event.target.value))} /></label>}<label>LSB for B<input min="0" type="number" value={props.sliceLsbB} onChange={(event) => props.onSliceLsbBChange(Number(event.target.value))} /></label><label>Width (0=full)<input min="0" type="number" value={props.sliceWidth} onChange={(event) => props.onSliceWidthChange(Number(event.target.value))} /></label></div>
        {from && to && <output aria-label="Connection mapping" aria-live="polite">{from} → {to} · {typeof width === "number" ? `${width} ${width === 1 ? "bit" : "bits"}` : "whole ports"}</output>}
        {props.connectionError && <p role="alert">{props.connectionError}</p>}
        <div className="circuit-dialog__actions"><button type="button" onClick={props.onClose}>Cancel</button><button className="primary" disabled={(!existing && !props.endpointA) || !props.endpointB || (existing && !net)} type="submit">{existing ? "Add endpoint" : "Create net"}</button></div>
      </form>
    </CircuitModal>;
  }

  if (props.dialog === "new-component") {
    const sourceNameValid = Boolean(props.componentName.trim());
    return <CircuitModal onClose={props.onClose} title="New local component">
      <form className="circuit-dialog__form" onSubmit={(event) => {
        event.preventDefault();
        if (!props.componentName.trim()) return;
        props.onCreateComponent(); props.onClose();
      }}>
        <p>Create a local two-terminal component definition and its first instance.</p>
        <label>Name<input autoFocus maxLength={200} value={props.componentName} onChange={(event) => props.onComponentNameChange(event.target.value)} placeholder="Arithmetic unit" /></label>
        {props.sourceIdentifierPattern && !sourceNameValid && <p role="alert">{props.sourceIdentifierHint ?? "Use a source-compatible name."}</p>}
        <div className="circuit-dialog__actions"><button type="button" onClick={props.onClose}>Cancel</button><button className="primary" disabled={!props.componentName.trim() || !sourceNameValid} type="submit">Create definition + instance</button></div>
      </form>
    </CircuitModal>;
  }

  if (props.dialog === "catalog") {
    const selected = props.document?.components.find((component) => component.id === selectedComponentId);
    const name = instanceName.trim();
    const nameError = name && !/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)
      ? "Use letters, digits, and underscores. Start with a letter or underscore."
      : name && props.document?.design.instances.some(instance => instance.id === name || instance.label === name)
        ? "An instance with this name already exists." : "";
    return <CircuitModal onClose={props.onClose} title="Component catalog">
      <div className="catalog-dialog">
        <p>{props.sourceDescription}</p>
        <div className="metrics"><div><b>{props.document?.design.instances.length ?? 0}</b><span>Instances</span></div><div><b>{props.document?.design.nets.length ?? 0}</b><span>Nets</span></div></div>
        <div className="catalog-dialog__grid">
          <div className="catalog-list">{props.document?.components.map((component) => <button className={component.id === selectedComponentId ? "active" : ""} key={component.id} onClick={() => setSelectedComponentId(component.id)} type="button"><b>{component.label}</b><small>{component.origin}</small></button>)}</div>
          <div className="catalog-dialog__details">{selected ? <><h3>{selected.label}</h3>{selected.editable && props.onRenameComponent && <button type="button" onClick={() => { const name = window.prompt("Component name", selected.label); if (name?.trim()) props.onRenameComponent?.(selected.id, name); }}>Rename</button>}<p>{selected.terminals.length} terminals · {selected.parameters.length} parameters · {selected.editable ? "editable" : "source-defined"}</p><details><summary>Technical details</summary><code>{selected.id}</code></details><label>Instance name (optional)<input value={instanceName} maxLength={200} placeholder="Automatic name" onChange={event => setInstanceName(event.target.value)} aria-invalid={!!nameError} aria-describedby={nameError ? "catalog-name-error" : undefined} /></label>{nameError && <p id="catalog-name-error" role="alert">{nameError}</p>}<button className="primary" disabled={!!nameError} onClick={() => { if (props.onPlaceComponent(selected.id, name)) props.onClose(); }} type="button">Place instance</button></> : <p>Select a component to inspect its definition summary.</p>}</div>
        </div>
        {!props.document?.components.length && <p className="empty-copy">No component definitions are available yet.</p>}
      </div>
    </CircuitModal>;
  }

  if (props.dialog === "proposals") {
    return <CircuitModal onClose={props.onClose} title="Review proposals">
      <div className="proposal-dialog">{props.proposals.map((proposal) => <article className="proposal-card" key={proposal.proposal_id}>
        <b>{proposal.title}</b><p>{proposal.summary}</p><small>{proposal.diff.added.length} added · {proposal.diff.changed.length} changed · {proposal.diff.removed.length} removed</small>
        <div className="circuit-dialog__actions"><button onClick={() => props.onDecideProposal(proposal.proposal_id, "reject")} type="button">Reject</button><button className="primary" onClick={() => props.onDecideProposal(proposal.proposal_id, "accept")} type="button">Accept</button></div>
      </article>)}{!props.proposals.length && <p className="empty-copy">No proposals are waiting for review.</p>}</div>
    </CircuitModal>;
  }

  if (props.dialog === "clock-settings") {
    const signalOptions = [
      ...(props.document?.design.boundary_terminals.map((item) => ({ value: `boundary:${item.id}`, label: `Boundary: ${item.label}` })) ?? []),
      ...(props.document?.design.nets.map((item) => ({ value: `net:${item.id}`, label: `Net: ${item.label || item.id}` })) ?? []),
    ];
    const additional = props.timing.clock_domains.filter((domain) => domain.id !== DEFAULT_CLOCK_DOMAIN_ID);
    return <CircuitModal onClose={props.onClose} title="Clock settings">
      <form className="circuit-dialog__form" onSubmit={(event) => {
        event.preventDefault();
        const [kind, id] = clockSignal.split(":", 2);
        props.onSetClockDomain({ id: DEFAULT_CLOCK_DOMAIN_ID, label: clockLabel.trim() || "clk", ...(id ? { signal: { kind: kind as "boundary" | "net", id } } : {}) });
        props.onClose();
      }}>
        <p>All components use this clock automatically. Every cycle edge adds one cycle.</p>
        <label>Clock name<input autoFocus value={clockLabel} onChange={(event) => setClockLabel(event.target.value)} /></label>
        <label>Optional clock signal<select value={clockSignal} onChange={(event) => setClockSignal(event.target.value)}><option value="">Not bound</option>{signalOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <details><summary>Multiple clock domains</summary>
          <p>Use additional domains only for CDC identification. Cycle edges remain global.</p>
          <div className="clock-domain-list">{additional.map((domain) => <div key={domain.id}><span>{domain.label}</span><button className="danger" onClick={() => props.onRemoveClockDomain(domain.id)} type="button">Remove</button></div>)}</div>
          <div className="slice-row"><label>New domain<input value={newDomainLabel} onChange={(event) => setNewDomainLabel(event.target.value)} /></label><button disabled={!newDomainLabel.trim()} onClick={() => { props.onSetClockDomain({ id: `clock_${newDomainLabel.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "domain"}`, label: newDomainLabel.trim() }); setNewDomainLabel(""); }} type="button">Add</button></div>
          {props.selectedTimingSubject && additional.length > 0 && <label>Selected object domain<select value={props.timing.subject_domain_overrides[props.selectedTimingSubject] ?? DEFAULT_CLOCK_DOMAIN_ID} onChange={(event) => props.onAssignClockDomain(props.selectedTimingSubject!, event.target.value)}>{props.timing.clock_domains.map((domain) => <option key={domain.id} value={domain.id}>{domain.label}</option>)}</select></label>}
        </details>
        <div className="circuit-dialog__actions"><button type="button" onClick={props.onClose}>Cancel</button><button className="primary" type="submit">Apply</button></div>
      </form>
    </CircuitModal>;
  }

  if (props.dialog === "timing-analysis") {
    return <CircuitModal onClose={props.onClose} title="Timing analysis">
      <div className="circuit-dialog__copy"><p>{props.timing.cycle_edges.length} cycle edges · {props.timingAnalysis.subjects.length} placed timing subjects</p>
        <div className="timing-analysis-list">{props.timingAnalysis.paths.map((path) => <article data-status={path.status} key={`${path.net_id}:${path.source}:${path.target}`}><b>{path.net_id}</b><span>{path.source} → {path.target}</span><strong>{path.status === "ready" ? `${path.cycles ?? 0} cycle${path.cycles === 1 ? "" : "s"}` : path.status.toUpperCase()}</strong>{path.message && <small>{path.message}</small>}</article>)}</div>
        {!props.timingAnalysis.paths.length && <p className="empty-copy">No directed timing paths are available.</p>}
      </div>
      <div className="circuit-dialog__actions"><button autoFocus className="primary" onClick={props.onClose} type="button">Close</button></div>
    </CircuitModal>;
  }

  if (props.dialog === "cycle-edge" && props.selectedCycleEdge) {
    return <CircuitModal onClose={props.onClose} title="Edit cycle edge">
      <form className="circuit-dialog__form" onSubmit={(event) => {
        event.preventDefault();
        props.onUpdateCycleEdge({ ...props.selectedCycleEdge!, x: edgeX, ...(edgeLabel.trim() ? { label: edgeLabel.trim() } : { label: undefined }), ...(stageLabel.trim() ? { next_stage_label: stageLabel.trim() } : { next_stage_label: undefined }) });
        props.onClose();
      }}>
        <label>Edge label<input autoFocus placeholder="Automatic" value={edgeLabel} onChange={(event) => setEdgeLabel(event.target.value)} /></label>
        <label>Following stage label<input placeholder="Automatic" value={stageLabel} onChange={(event) => setStageLabel(event.target.value)} /></label>
        <label>X position<input step={props.document?.layout.grid_size ?? 20} type="number" value={edgeX} onChange={(event) => setEdgeX(Number(event.target.value))} /></label>
        <div className="circuit-dialog__actions"><button type="button" onClick={props.onClose}>Cancel</button><button className="primary" type="submit">Apply</button></div>
      </form>
    </CircuitModal>;
  }

  if (props.dialog === "getting-started") {
    return <CircuitModal onClose={props.onClose} title="Getting started">
      <div className="circuit-dialog__copy"><p>Use <strong>File → New Circuit</strong> or <strong>File → Open Circuit</strong>, then choose <strong>Edit → Begin Editing</strong> before changing the design.</p><p>Create components from the Components menu, connect free terminals directly or through Connect, and use Route for automatic and manual routing.</p><p>Save commits the private draft and downloads the canonical circuit file.</p></div>
    </CircuitModal>;
  }

  return <CircuitModal onClose={props.onClose} title="About Circuit Designer">
    <div className="circuit-dialog__copy"><p><strong>Circuit Designer</strong></p><p>A deterministic direct-manipulation editor for portable circuit documents.</p><p>Documents use host-provided service sessions; the host also controls files, preferences, source synchronization, and optional tools.</p></div>
  </CircuitModal>;
}

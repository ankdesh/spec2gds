import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import type { CircuitDocument, CircuitProposal } from "@spec2gds/circuit-core";

export type CircuitDialogId = "connect" | "catalog" | "new-component" | "proposals" | "getting-started" | "about";

function CircuitModal({ children, onClose, title }: { children: ReactNode; onClose: () => void; title: string }) {
  const dialogRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
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
      if (previousFocus?.isConnected && previousFocus !== document.body) previousFocus.focus();
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

export interface CircuitDialogsProps {
  dialog?: CircuitDialogId;
  document?: CircuitDocument;
  sourceDescription: string;
  proposals: CircuitProposal[];
  terminals: Array<{ id: string }>;
  netName: string;
  endpointA: string;
  endpointB: string;
  sliceLsb: number;
  sliceWidth: number;
  componentName: string;
  onClose: () => void;
  onNetNameChange: (value: string) => void;
  onEndpointAChange: (value: string) => void;
  onEndpointBChange: (value: string) => void;
  onSliceLsbChange: (value: number) => void;
  onSliceWidthChange: (value: number) => void;
  onCreateConnection: () => boolean;
  onComponentNameChange: (value: string) => void;
  onCreateComponent: () => void;
  onDecideProposal: (proposalId: string, decision: "accept" | "reject") => void;
}

export function CircuitDialogs(props: CircuitDialogsProps) {
  const [selectedComponentId, setSelectedComponentId] = useState<string>();
  if (!props.dialog) return null;

  if (props.dialog === "connect") {
    const submit = (event: FormEvent) => {
      event.preventDefault();
      if (props.onCreateConnection()) props.onClose();
    };
    return <CircuitModal onClose={props.onClose} title="Create connection">
      <form className="circuit-dialog__form" onSubmit={submit}>
        <label>Net label<input autoFocus value={props.netName} onChange={(event) => props.onNetNameChange(event.target.value)} /></label>
        <label>Endpoint A<select value={props.endpointA} onChange={(event) => props.onEndpointAChange(event.target.value)}><option value="">Choose…</option>{props.terminals.map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.id}</option>)}</select></label>
        <label>Endpoint B<select value={props.endpointB} onChange={(event) => props.onEndpointBChange(event.target.value)}><option value="">Choose…</option>{props.terminals.filter((terminal) => terminal.id !== props.endpointA).map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.id}</option>)}</select></label>
        <div className="slice-row"><label>LSB<input min="0" type="number" value={props.sliceLsb} onChange={(event) => props.onSliceLsbChange(Number(event.target.value))} /></label><label>Width (0=full)<input min="0" type="number" value={props.sliceWidth} onChange={(event) => props.onSliceWidthChange(Number(event.target.value))} /></label></div>
        <div className="circuit-dialog__actions"><button type="button" onClick={props.onClose}>Cancel</button><button className="primary" disabled={!props.endpointA || !props.endpointB} type="submit">Create net</button></div>
      </form>
    </CircuitModal>;
  }

  if (props.dialog === "new-component") {
    return <CircuitModal onClose={props.onClose} title="New local component">
      <form className="circuit-dialog__form" onSubmit={(event) => {
        event.preventDefault();
        if (!props.componentName.trim()) return;
        props.onCreateComponent(); props.onClose();
      }}>
        <p>Create a local two-terminal component definition and its first instance.</p>
        <label>Name<input autoFocus value={props.componentName} onChange={(event) => props.onComponentNameChange(event.target.value)} placeholder="Arithmetic unit" /></label>
        <div className="circuit-dialog__actions"><button type="button" onClick={props.onClose}>Cancel</button><button className="primary" disabled={!props.componentName.trim()} type="submit">Create definition + instance</button></div>
      </form>
    </CircuitModal>;
  }

  if (props.dialog === "catalog") {
    const selected = props.document?.components.find((component) => component.id === selectedComponentId);
    return <CircuitModal onClose={props.onClose} title="Component catalog">
      <div className="catalog-dialog">
        <p>{props.sourceDescription}</p>
        <div className="metrics"><div><b>{props.document?.design.instances.length ?? 0}</b><span>Instances</span></div><div><b>{props.document?.design.nets.length ?? 0}</b><span>Nets</span></div></div>
        <div className="catalog-dialog__grid">
          <div className="catalog-list">{props.document?.components.map((component) => <button className={component.id === selectedComponentId ? "active" : ""} key={component.id} onClick={() => setSelectedComponentId(component.id)} type="button"><b>{component.label}</b><small>{component.origin} · {component.appearance.renderer_key}</small></button>)}</div>
          <div className="catalog-dialog__details">{selected ? <><h3>{selected.label}</h3><code>{selected.id}</code><p>{selected.terminals.length} terminals · {selected.parameters.length} parameters · {selected.editable ? "editable" : "read only"}</p></> : <p>Select a component to inspect its definition summary.</p>}</div>
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

  if (props.dialog === "getting-started") {
    return <CircuitModal onClose={props.onClose} title="Getting started">
      <div className="circuit-dialog__copy"><p>Use <strong>File → New Circuit</strong> or <strong>File → Open Circuit</strong>, then choose <strong>Edit → Begin Editing</strong> before changing the design.</p><p>Create components from the Components menu, connect free terminals directly or through Connect, and use Route for automatic and manual routing.</p><p>Save commits the private draft and downloads the canonical circuit file.</p></div>
    </CircuitModal>;
  }

  return <CircuitModal onClose={props.onClose} title="About Circuit Designer">
    <div className="circuit-dialog__copy"><p><strong>spec2gds Circuit Designer</strong></p><p>A deterministic direct-manipulation editor for portable circuit documents.</p><p>Documents use ephemeral service sessions; user interface preferences are stored in the server-managed Circuit Designer preference file.</p></div>
  </CircuitModal>;
}

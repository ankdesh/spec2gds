import { useEffect, useRef, useState, type FormEvent } from "react";

export type CanvasActionMenu = "selection" | "connect" | "route" | "view";

export interface CanvasActionBarProps {
  editable: boolean;
  selectionCount: number;
  selectedNetId?: string;
  selectedRouteLocked: boolean;
  terminals: Array<{ id: string }>;
  netName: string;
  endpointA: string;
  endpointB: string;
  sliceLsb: number;
  sliceWidth: number;
  onNetNameChange: (value: string) => void;
  onEndpointAChange: (value: string) => void;
  onEndpointBChange: (value: string) => void;
  onSliceLsbChange: (value: number) => void;
  onSliceWidthChange: (value: number) => void;
  onCreateConnection: () => boolean;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onCenterSelection: () => void;
  onRerouteSelected: () => void;
  onSetRouteLocked: (locked: boolean) => void;
  onArrangeAll: () => void;
  onPan: (direction: "left" | "right" | "up" | "down") => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitView: () => void;
}

export function CanvasActionBar(props: CanvasActionBarProps) {
  const [open, setOpen] = useState<CanvasActionMenu>();
  const rootRef = useRef<HTMLDivElement>(null);
  const canUseSelectedNet = props.editable && Boolean(props.selectedNetId);

  useEffect(() => {
    const closeOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as globalThis.Node)) setOpen(undefined);
    };
    const closeWithEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(undefined);
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeWithEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeWithEscape);
    };
  }, []);

  const toggle = (menu: CanvasActionMenu) => setOpen((current) => current === menu ? undefined : menu);
  const run = (action: () => void) => {
    action();
    setOpen(undefined);
  };
  const submitConnection = (event: FormEvent) => {
    event.preventDefault();
    if (props.onCreateConnection()) setOpen(undefined);
  };

  return <div className="canvas-action-bar" ref={rootRef} aria-label="Circuit canvas actions">
    <div className="canvas-action-bar__group">
      <button type="button" aria-expanded={open === "selection"} onClick={() => toggle("selection")}>⌁ Selection</button>
      {open === "selection" && <div className="canvas-action-menu" role="menu">
        <button type="button" role="menuitem" onClick={() => run(props.onSelectAll)}>Select All <kbd>Ctrl/⌘ A</kbd></button>
        <button type="button" role="menuitem" disabled={!props.selectionCount} onClick={() => run(props.onClearSelection)}>Clear Selection <kbd>Esc</kbd></button>
        <button type="button" role="menuitem" disabled={!props.selectionCount} onClick={() => run(props.onCenterSelection)}>Center on Selection</button>
      </div>}
    </div>

    <div className="canvas-action-bar__group">
      <button type="button" aria-expanded={open === "connect"} disabled={!props.editable} title={props.editable ? "Create a new two-terminal net" : "Unlock the document to connect terminals."} onClick={() => toggle("connect")}>↝ Connect…</button>
      {open === "connect" && <form className="canvas-action-popover" onSubmit={submitConnection}>
        <strong>Create connection</strong>
        <label>Net label<input value={props.netName} onChange={(event) => props.onNetNameChange(event.target.value)} /></label>
        <label>Endpoint A<select value={props.endpointA} onChange={(event) => props.onEndpointAChange(event.target.value)}><option value="">Choose…</option>{props.terminals.map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.id}</option>)}</select></label>
        <label>Endpoint B<select value={props.endpointB} onChange={(event) => props.onEndpointBChange(event.target.value)}><option value="">Choose…</option>{props.terminals.filter((terminal) => terminal.id !== props.endpointA).map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.id}</option>)}</select></label>
        <div className="slice-row"><label>LSB<input type="number" min="0" value={props.sliceLsb} onChange={(event) => props.onSliceLsbChange(Number(event.target.value))} /></label><label>Width (0=full)<input type="number" min="0" value={props.sliceWidth} onChange={(event) => props.onSliceWidthChange(Number(event.target.value))} /></label></div>
        <button className="primary" type="submit" disabled={!props.endpointA || !props.endpointB}>Create net</button>
      </form>}
    </div>

    <div className="canvas-action-bar__group">
      <button type="button" aria-expanded={open === "route"} onClick={() => toggle("route")}>⌇ Route</button>
      {open === "route" && <div className="canvas-action-menu" role="menu">
        <button type="button" role="menuitem" disabled={!canUseSelectedNet || props.selectedRouteLocked} title={!props.selectedNetId ? "Select one net first." : props.selectedRouteLocked ? "Unlock the route before rerouting it." : undefined} onClick={() => run(props.onRerouteSelected)}>Reroute Selected Net</button>
        <button type="button" role="menuitem" disabled={!canUseSelectedNet || props.selectedRouteLocked} onClick={() => run(() => props.onSetRouteLocked(true))}>Lock Selected Route</button>
        <button type="button" role="menuitem" disabled={!canUseSelectedNet || !props.selectedRouteLocked} onClick={() => run(() => props.onSetRouteLocked(false))}>Unlock Selected Route</button>
        <button type="button" role="menuitem" disabled={!props.editable} title={props.editable ? undefined : "Unlock the document to arrange it."} onClick={() => run(props.onArrangeAll)}>Arrange and Route All</button>
      </div>}
    </div>

    <div className="canvas-action-bar__spacer" />

    <div className="canvas-action-bar__group">
      <button type="button" aria-expanded={open === "view"} onClick={() => toggle("view")}>◫ View</button>
      {open === "view" && <div className="canvas-action-menu canvas-action-menu--view" role="menu">
        <div className="pan-pad" aria-label="Pan canvas">
          <button type="button" aria-label="Pan up" onClick={() => props.onPan("up")}>↑</button>
          <button type="button" aria-label="Pan left" onClick={() => props.onPan("left")}>←</button>
          <button type="button" aria-label="Pan down" onClick={() => props.onPan("down")}>↓</button>
          <button type="button" aria-label="Pan right" onClick={() => props.onPan("right")}>→</button>
        </div>
        <button type="button" role="menuitem" onClick={props.onZoomIn}>Zoom In</button>
        <button type="button" role="menuitem" onClick={props.onZoomOut}>Zoom Out</button>
        <button type="button" role="menuitem" disabled={!props.selectionCount} onClick={() => run(props.onCenterSelection)}>Center on Selection</button>
        <button type="button" role="menuitem" onClick={() => run(props.onFitView)}>Fit Circuit</button>
      </div>}
    </div>
    <span className="canvas-action-bar__hint">Drag ports to connect · Wheel zoom · Space/middle-drag pan</span>
  </div>;
}

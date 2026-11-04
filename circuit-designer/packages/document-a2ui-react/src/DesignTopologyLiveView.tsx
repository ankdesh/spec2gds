import { OptionsMenu } from "./OptionsMenu";
import React, { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { getCircuitTheme } from "@spec2gds/circuit-core";
import type { NarrativeBlock } from "@spec2gds/document-core";

import {
  circuitSvgFilename,
  readDesignTopologyOptions,
  renderDesignTopology,
  type RenderedDesignTopology,
} from "./topology-live-view";

function TopologyDialog({
  imageUrl,
  label,
  onClose,
  restoreFocus,
}: {
  imageUrl: string;
  label: string;
  onClose: () => void;
  restoreFocus: React.RefObject<HTMLButtonElement>;
}) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not(:disabled), [href], [tabindex]:not([tabindex='-1'])",
      ) ?? []);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      restoreFocus.current?.focus();
    };
  }, [onClose, restoreFocus]);
  return createPortal(
    <div
      className="spec-topology-dialog-backdrop"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
      role="presentation"
    >
      <div
        aria-labelledby={titleId}
        aria-modal="true"
        className="spec-topology-dialog"
        ref={dialogRef}
        role="dialog"
      >
        <header>
          <h2 id={titleId}>{label}</h2>
          <button aria-label="Close circuit preview" onClick={onClose} ref={closeRef} type="button">Close</button>
        </header>
        <div className="spec-topology-dialog__viewport">
          <img alt={`${label} circuit diagram`} src={imageUrl} />
        </div>
      </div>
    </div>,
    document.body,
  );
}

export function DesignTopologyLiveView({
  block,
  onOpenCircuit,
}: {
  block: NarrativeBlock;
  documentId: string;
  onOpenCircuit?: () => void;
}) {
  const options = readDesignTopologyOptions(block.options);
  const [rendered, setRendered] = useState<RenderedDesignTopology>();
  const [renderError, setRenderError] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [themeId, setThemeId] = useState(() => typeof document !== "undefined" && document.documentElement.dataset.theme === "obsidian" ? "obsidian" : "blueprint-slate");
  const expandRef = useRef<HTMLButtonElement>(null);
  const label = options?.read_only ? "Interface preview (read-only)" : block.text || "Circuit topology";
  const ref = block.entity_refs[0];
  const entityName = ref ? block.entity_labels?.[`${ref.entity_kind}:${ref.entity_id}`]?.name || "Design" : "Design";

  useEffect(() => {
    const update = () => setThemeId(document.documentElement.dataset.theme === "obsidian" ? "obsidian" : "blueprint-slate");
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let active = true;
    setRendered(undefined);
    setRenderError("");
    if (options?.status !== "ready" || !options.circuit_document) return () => { active = false; };
    void renderDesignTopology(options.circuit_document, themeId).then((value) => {
      if (active) setRendered(value);
    }).catch((reason) => {
      if (active) setRenderError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => { active = false; };
  }, [options, themeId]);

  useEffect(() => {
    if (!rendered) {
      setImageUrl("");
      return;
    }
    const url = URL.createObjectURL(new Blob([rendered.svg], { type: "image/svg+xml" }));
    setImageUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [rendered]);

  if (!options) {
    return <div className="spec-topology-card spec-topology-card--unavailable" role="status">
      <strong>{label}</strong>
      <p>This topology view has unsupported renderer options.</p>
    </div>;
  }

  const omissions = [
    ...options.omitted_bus_items.map((item) => `Interface connection: ${item}`),
    ...options.omitted_ports.map((item) => `Port: ${item}`),
  ];
  const unavailableMessage = options.status === "unavailable" ? options.message || "This topology cannot be represented safely." : renderError;
  if (unavailableMessage) {
    return <div className="spec-topology-card spec-topology-card--unavailable" role="status">
      <strong>{label}</strong>
      <p>Preview unavailable: {unavailableMessage}</p>
    </div>;
  }
  if (options.status === "empty") {
    return <div className="spec-topology-card spec-topology-card--empty" role="status">
      <strong>{label}</strong>
      <p>No instances or physical-wire connections to display.</p>
    </div>;
  }

  return (
    <figure aria-busy={!imageUrl} className="spec-topology-card" style={{ "--spec-preview-canvas": getCircuitTheme(themeId).colors.canvas } as React.CSSProperties}>
      <figcaption>
        <div>
          <strong>{label}</strong>
          <span>Derived from the current specification revision</span>
        </div>
        <OptionsMenu label={label} triggerLabel="Options for circuit preview" triggerRef={expandRef}>
          {onOpenCircuit && <button role="menuitem" onClick={onOpenCircuit} type="button">Open in Circuit Designer</button>}
          <button role="menuitem" disabled={!imageUrl} onClick={() => setExpanded(true)} type="button">Expand</button>
          <a role="menuitem"
            aria-disabled={!imageUrl}
            download={circuitSvgFilename(String(block.options.document_name || "Specification"), entityName)}
            href={imageUrl || undefined}
            onClick={(event) => { if (!imageUrl) event.preventDefault(); }}
          >
            Download SVG
          </a>
        </OptionsMenu>
      </figcaption>
      <div className="spec-topology-card__preview">
        {imageUrl
          ? <img alt={`${label} circuit diagram`} height={rendered?.height} src={imageUrl} width={rendered?.width} />
          : <p className="spec-topology-card__loading" role="status">Laying out circuit…</p>}
      </div>
      {omissions.length > 0 && (
        <details className="spec-topology-card__omissions">
          <summary>{omissions.length} unsupported item{omissions.length === 1 ? "" : "s"} omitted from this preview</summary>
          <ul>{omissions.map((item) => <li key={item}>{item}</li>)}</ul>
        </details>
      )}
      {expanded && imageUrl && (
        <TopologyDialog imageUrl={imageUrl} label={label} onClose={() => setExpanded(false)} restoreFocus={expandRef} />
      )}
    </figure>
  );
}

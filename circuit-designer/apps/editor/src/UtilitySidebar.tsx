import { useEffect, useRef, useState, type ReactNode } from "react";

export type UtilityTab = "diagnostics" | "activity";
const widthKey = "spec2gds:spec-editor:panel-width";

export function clampPanelWidth(width: number, viewport: number): number {
  return Math.max(320, Math.min(560, viewport - 800, Number.isFinite(width) ? width : 400));
}

export function UtilitySidebar({ tab, onTab, onClose, children }: {
  tab: UtilityTab;
  onTab(tab: UtilityTab): void;
  onClose(restoreFocus?: boolean): void;
  children: ReactNode;
}) {
  const [viewport, setViewport] = useState(window.innerWidth);
  const [availableWidth, setAvailableWidth] = useState(document.body.clientWidth);
  const [preferredWidth, setPreferredWidth] = useState(() => {
    try { return Number(localStorage.getItem(widthKey)) || 400; } catch { return 400; }
  });
  const panel = useRef<HTMLElement>(null);
  const drag = useRef<{ id: number; x: number; width: number } | null>(null);
  const availableSpace = () => panel.current?.closest<HTMLElement>(".app-shell")?.clientWidth ?? document.body.clientWidth;
  const overlay = viewport < 1280;
  const width = clampPanelWidth(preferredWidth, availableWidth);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const resize = () => { setViewport(window.innerWidth); setAvailableWidth(availableSpace()); };
    window.addEventListener("resize", resize);
    const observer = new ResizeObserver(resize);
    observer.observe(panel.current?.closest(".app-shell") ?? document.documentElement);
    return () => { window.removeEventListener("resize", resize); observer.disconnect(); };
  }, []);
  useEffect(() => {
    const shell = panel.current?.closest<HTMLElement>(".app-shell");
    shell?.style.setProperty("--utility-width", `${width}px`);
    if (shell) shell.style.setProperty("--utility-inset", `${Math.max(0, window.innerWidth - shell.getBoundingClientRect().right)}px`);
    return () => { shell?.style.removeProperty("--utility-width"); shell?.style.removeProperty("--utility-inset"); };
  }, [width, availableWidth, viewport]);
  useEffect(() => { panel.current?.querySelector<HTMLButtonElement>("[role=tab][aria-selected=true]")?.focus(); }, []);
  useEffect(() => {
    if (!overlay) return;
    const background = Array.from(document.querySelectorAll<HTMLElement>(".app-shell > :not(main), .editor-document"));
    const previous = background.map(element => element.inert);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    background.forEach(element => { element.inert = true; });
    return () => {
      document.body.style.overflow = overflow;
      background.forEach((element, index) => { element.inert = previous[index]; });
    };
  }, [overlay]);
  const resize = (next: number) => {
    const clamped = clampPanelWidth(next, availableSpace());
    setPreferredWidth(clamped);
    try { localStorage.setItem(widthKey, String(clamped)); } catch { /* Resizing works without storage. */ }
  };
  return <>
    {overlay && <div className="utility-backdrop" onClick={() => onClose()} />}
    <aside className="utility-sidebar" id="editor-utility-panel" ref={panel}
      role={overlay ? "dialog" : "complementary"} aria-modal={overlay || undefined} aria-label="Diagnostics and Activity"
      onKeyDown={event => {
        if (event.defaultPrevented) return;
        if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); closeRef.current(); }
        if (overlay && event.key === "Tab") {
          const controls = Array.from(panel.current?.querySelectorAll<HTMLElement>("button, a[href], input, select, textarea, summary, [tabindex='0']") ?? [])
            .filter(item => item.tabIndex >= 0 && !item.closest("[hidden]") && item.getClientRects().length && !item.matches(":disabled"));
          const first = controls[0]; const last = controls[controls.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
        }
      }}>
      {!overlay && <div className="utility-resizer" role="separator" tabIndex={0} aria-label="Resize side panel" aria-orientation="vertical" aria-controls="editor-document-pane"
        aria-valuemin={320} aria-valuemax={Math.min(560, availableWidth - 800)} aria-valuenow={width}
        onPointerDown={event => {
          drag.current = { id: event.pointerId, x: event.clientX, width };
          event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault();
        }}
        onPointerMove={event => {
          const start = drag.current;
          if (start?.id === event.pointerId && event.currentTarget.hasPointerCapture(event.pointerId)) resize(start.width + start.x - event.clientX);
        }}
        onPointerUp={event => { drag.current = null; if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }}
        onPointerCancel={() => { drag.current = null; }}
        onKeyDown={event => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          resize(event.key === "Home" ? 320 : event.key === "End" ? 560 : width + (event.key === "ArrowLeft" ? 20 : -20));
        }} />}
      <header className="utility-sidebar__header">
        <div role="tablist" aria-label="Side panel">
          {(["diagnostics", "activity"] as const).map(item => <button id={`utility-tab-${item}`} key={item} type="button" role="tab"
            tabIndex={tab === item ? 0 : -1} aria-selected={tab === item} aria-controls="utility-panel-content"
            onClick={() => onTab(item)} onKeyDown={event => {
              if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
                event.preventDefault();
                const next = event.key === "Home" ? "diagnostics" : event.key === "End" ? "activity" : item === "activity" ? "diagnostics" : "activity";
                onTab(next); document.getElementById(`utility-tab-${next}`)?.focus();
              }
            }}>{item === "diagnostics" ? "Diagnostics" : "Activity"}</button>)}
        </div>
        <button type="button" aria-label="Close side panel" onClick={() => onClose()}>×</button>
      </header>
      <div className="utility-sidebar__body" role="tabpanel" id="utility-panel-content" aria-labelledby={`utility-tab-${tab}`}>
        {children}
      </div>
    </aside>
  </>;
}

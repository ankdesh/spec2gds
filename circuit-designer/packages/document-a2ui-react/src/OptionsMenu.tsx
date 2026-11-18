/** Shared, viewport-bound menu for saved-content actions. */
import React, { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const OPEN_EVENT = "spec2gds:section-menu-open";
export function OptionsMenu({ label, children, open: controlled, onOpenChange, closeOnSelect = true, triggerLabel, triggerRef, compact = false, className = "" }: {
  label: string; children: React.ReactNode; open?: boolean; onOpenChange?(open: boolean): void;
  closeOnSelect?: boolean; triggerLabel?: string; triggerRef?: React.RefObject<HTMLButtonElement>; compact?: boolean; className?: string;
}) {
  const [localOpen, setLocalOpen] = useState(false);
  const open = controlled ?? localOpen;
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const showTooltip = compact && tooltipVisible && !open;
  const trigger = useRef<HTMLButtonElement | null>(null);
  const menu = useRef<HTMLDivElement>(null);
  const tooltip = useRef<HTMLSpanElement>(null);
  const id = useId();
  const tooltipId = `${id}-tooltip`;
  const accessibleLabel = triggerLabel ?? (compact ? `Options for ${label}` : undefined);
  const change = (value: boolean, restore = false) => {
    setLocalOpen(value); onOpenChange?.(value);
    if (value) window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { menuId: id } }));
    if (restore) trigger.current?.focus({ preventScroll: true });
  };
  useLayoutEffect(() => {
    const panel = open ? menu.current : showTooltip ? tooltip.current : null;
    if (!panel || !trigger.current) return;
    const position = () => {
      const anchor = trigger.current!.getBoundingClientRect();
      const below = window.innerHeight - anchor.bottom - 12;
      const above = anchor.top - 12;
      panel.style.maxHeight = `${Math.max(0, Math.min(window.innerHeight - 16, Math.max(below, above)))}px`;
      panel.style.left = `${Math.max(8, Math.min(anchor.right - panel.offsetWidth, window.innerWidth - panel.offsetWidth - 8))}px`;
      const top = below >= panel.offsetHeight ? anchor.bottom + 4 : anchor.top - panel.offsetHeight - 4;
      panel.style.top = `${Math.max(8, Math.min(top, window.innerHeight - panel.offsetHeight - 8))}px`;
    };
    position();
    const scrolled = (event: Event) => {
      if (!panel.contains(event.target as Node)) position();
    };
    if (compact) {
      window.addEventListener("scroll", scrolled, true);
      window.addEventListener("resize", position);
    }
    const observer = new ResizeObserver(position);
    observer.observe(panel);
    if (open) panel.querySelector<HTMLButtonElement>("[role=menuitem]:not(:disabled)")?.focus({ preventScroll: true });
    return () => { observer.disconnect(); window.removeEventListener("scroll", scrolled, true); window.removeEventListener("resize", position); if (open && panel.contains(document.activeElement)) trigger.current?.focus({ preventScroll: true }); };
  }, [open, compact, showTooltip]);
  useEffect(() => {
    const outside = (event: PointerEvent) => {
      if (!trigger.current?.contains(event.target as Node) && !menu.current?.contains(event.target as Node)) change(false);
    };
    const other = (event: Event) => { if ((event as CustomEvent).detail.menuId !== id) change(false); };
    const moved = () => change(false);
    document.addEventListener("pointerdown", outside);
    window.addEventListener(OPEN_EVENT, other);
    window.addEventListener("resize", moved);
    return () => { document.removeEventListener("pointerdown", outside); window.removeEventListener(OPEN_EVENT, other); window.removeEventListener("resize", moved); };
  }, [id, onOpenChange]);
  const theme = trigger.current?.closest("[data-theme]")?.getAttribute("data-theme") ?? undefined;
  const panel = open && <div data-theme={theme}>
      <div className={`spec-options-menu spec-options-menu--portal${compact ? " spec-options-menu--compact" : ""}`} id={id} ref={menu} role="menu" aria-label={`Options for ${label}`}
        onClick={event => { if (closeOnSelect && (event.target as HTMLElement).closest("[role=menuitem]:not(:disabled):not([aria-disabled=true])")) change(false, true); }}
        onKeyDown={event => {
          if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); change(false, true); }
          if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
            event.preventDefault();
            const items = Array.from(menu.current?.querySelectorAll<HTMLButtonElement>("[role=menuitem]:not(:disabled)") ?? []);
            const current = items.indexOf(document.activeElement as HTMLButtonElement);
            const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : event.key === "ArrowDown" ? (current + 1) % items.length : (current + items.length - 1) % items.length;
            items[next]?.focus({ preventScroll: true });
          }
          if (event.key === "Tab") change(false);
        }}>{children}</div></div>;
  return <div className={`spec-section-options${compact ? " spec-section-options--compact" : ""} ${className}`}>
    <button className={`spec-options-trigger${compact ? " spec-options-trigger--compact" : ""}`} type="button" aria-label={accessibleLabel}
      aria-describedby={showTooltip ? tooltipId : undefined} aria-expanded={open} aria-controls={id} aria-haspopup="menu"
      ref={node => { trigger.current = node; if (triggerRef) (triggerRef as React.MutableRefObject<HTMLButtonElement | null>).current = node; }}
      onMouseEnter={() => { if (compact) setTooltipVisible(true); }} onMouseLeave={() => setTooltipVisible(false)}
      onFocus={() => { if (compact) setTooltipVisible(true); }} onBlur={() => setTooltipVisible(false)}
      onClick={() => change(!open)} onKeyDown={event => {
        if (["ArrowDown", "ArrowUp"].includes(event.key)) { event.preventDefault(); change(true); }
        if (event.key === "Escape") { setTooltipVisible(false); change(false, true); }
      }}>{!compact && "Options "}<span aria-hidden="true">▾</span></button>
    {showTooltip && createPortal(<div data-theme={theme}><span className="spec-options-tooltip" id={tooltipId} role="tooltip" ref={tooltip}>{accessibleLabel}</span></div>, document.body)}
    {compact && panel ? createPortal(panel, document.body) : panel}
  </div>;
}

/** Shared, viewport-bound menu for saved-content actions. */
import React, { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

const OPEN_EVENT = "spec2gds:section-menu-open";
export function OptionsMenu({ label, children, open: controlled, onOpenChange, closeOnSelect = true, triggerLabel, triggerRef, className = "" }: {
  label: string; children: React.ReactNode; open?: boolean; onOpenChange?(open: boolean): void;
  closeOnSelect?: boolean; triggerLabel?: string; triggerRef?: React.RefObject<HTMLButtonElement>; className?: string;
}) {
  const [localOpen, setLocalOpen] = useState(false);
  const open = controlled ?? localOpen;
  const trigger = useRef<HTMLButtonElement | null>(null);
  const menu = useRef<HTMLDivElement>(null);
  const id = useId();
  const change = (value: boolean, restore = false) => {
    setLocalOpen(value); onOpenChange?.(value);
    if (value) window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { menuId: id } }));
    if (restore) trigger.current?.focus({ preventScroll: true });
  };
  useLayoutEffect(() => {
    if (!open || !menu.current || !trigger.current) return;
    const anchor = trigger.current.getBoundingClientRect();
    const panel = menu.current;
    const below = window.innerHeight - anchor.bottom - 12;
    const above = anchor.top - 12;
    panel.style.maxHeight = `${Math.max(60, Math.max(below, above))}px`;
    panel.style.left = `${Math.max(8, Math.min(anchor.right - panel.offsetWidth, window.innerWidth - panel.offsetWidth - 8))}px`;
    panel.style.top = `${below >= panel.offsetHeight ? anchor.bottom + 4 : Math.max(8, anchor.top - panel.offsetHeight - 4)}px`;
    panel.querySelector<HTMLButtonElement>("[role=menuitem]:not(:disabled)")?.focus({ preventScroll: true });
    return () => { if (panel.contains(document.activeElement)) trigger.current?.focus({ preventScroll: true }); };
  }, [open]);
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
  return <div className={`spec-section-options ${className}`}>
    <button className="spec-options-trigger" type="button" aria-label={triggerLabel} aria-expanded={open} aria-controls={id} aria-haspopup="menu"
      ref={node => { trigger.current = node; if (triggerRef) (triggerRef as React.MutableRefObject<HTMLButtonElement | null>).current = node; }}
      onClick={() => change(!open)} onKeyDown={event => {
        if (["ArrowDown", "ArrowUp"].includes(event.key)) { event.preventDefault(); change(true); }
        if (event.key === "Escape") change(false, true);
      }}>Options <span aria-hidden="true">▾</span></button>
    {open && <div data-theme={trigger.current?.closest("[data-theme]")?.getAttribute("data-theme") ?? undefined}>
      <div className="spec-options-menu spec-options-menu--portal" id={id} ref={menu} role="menu" aria-label={`Options for ${label}`}
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
        }}>{children}</div></div>}
  </div>;
}

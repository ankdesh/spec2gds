import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import {
  circuitActionDefinitions,
  formatKeyboardShortcut,
  type ActionBindings,
  type CircuitActionId,
} from "./action-bindings";

type MenuEntry =
  | { kind: "action"; actionId: CircuitActionId; label?: string; checked?: boolean; status?: string }
  | { kind: "separator" }
  | { kind: "submenu"; id: string; label: string; entries: MenuEntry[] };

type MenuDefinition = { id: string; label: string; entries: MenuEntry[] };

const menus: MenuDefinition[] = [
  { id: "file", label: "File", entries: [
    { kind: "action", actionId: "new-document" },
    { kind: "action", actionId: "open-document" },
    { kind: "separator" },
    { kind: "action", actionId: "save-document" },
    { kind: "action", actionId: "cancel-changes" },
    { kind: "separator" },
    { kind: "submenu", id: "download", label: "Download", entries: [
      { kind: "action", actionId: "download-json" },
      { kind: "action", actionId: "export-svg" },
      { kind: "action", actionId: "export-png" },
    ] },
  ] },
  { id: "edit", label: "Edit", entries: [
    { kind: "action", actionId: "begin-edit" },
    { kind: "separator" },
    { kind: "action", actionId: "undo" },
    { kind: "action", actionId: "redo" },
    { kind: "separator" },
    { kind: "action", actionId: "delete-selection" },
    { kind: "separator" },
    { kind: "submenu", id: "preferences", label: "Preferences", entries: [
      { kind: "action", actionId: "open-preferences" },
    ] },
  ] },
  { id: "components", label: "Components", entries: [
    { kind: "action", actionId: "open-component-catalog" },
    { kind: "action", actionId: "create-local-component" },
    { kind: "action", actionId: "review-proposals" },
    { kind: "separator" },
    { kind: "action", actionId: "open-child-design" },
  ] },
  { id: "selection", label: "Selection", entries: [
    { kind: "action", actionId: "select-all" },
    { kind: "action", actionId: "clear-selection" },
    { kind: "action", actionId: "center-selection" },
  ] },
  { id: "connect", label: "Connect", entries: [
    { kind: "action", actionId: "open-connect" },
  ] },
  { id: "route", label: "Route", entries: [
    { kind: "action", actionId: "reroute-selected" },
    { kind: "action", actionId: "lock-selected-route" },
    { kind: "action", actionId: "unlock-selected-route" },
    { kind: "separator" },
    { kind: "action", actionId: "arrange-all" },
  ] },
  { id: "view", label: "View", entries: [
    { kind: "action", actionId: "toggle-inspector" },
    { kind: "separator" },
    { kind: "submenu", id: "pan", label: "Pan", entries: [
      { kind: "action", actionId: "pan-up" },
      { kind: "action", actionId: "pan-left" },
      { kind: "action", actionId: "pan-down" },
      { kind: "action", actionId: "pan-right" },
    ] },
    { kind: "action", actionId: "zoom-in" },
    { kind: "action", actionId: "zoom-out" },
    { kind: "separator" },
    { kind: "action", actionId: "center-selection" },
    { kind: "action", actionId: "fit-circuit" },
  ] },
  { id: "tools", label: "Tools", entries: [
    { kind: "action", actionId: "open-assistant" },
  ] },
  { id: "help", label: "Help", entries: [
    { kind: "action", actionId: "getting-started" },
    { kind: "separator" },
    { kind: "action", actionId: "about" },
  ] },
];

const definitions = new Map(circuitActionDefinitions.map((action) => [action.id, action]));

function directMenuItems(container: HTMLElement | null): HTMLButtonElement[] {
  return Array.from(container?.children ?? []).flatMap((child) => {
    if (child instanceof HTMLButtonElement && child.getAttribute("role") === "menuitem" && !child.disabled) return [child];
    if (child instanceof HTMLElement && child.classList.contains("circuit-submenu")) {
      const trigger = child.firstElementChild;
      return trigger instanceof HTMLButtonElement && !trigger.disabled ? [trigger] : [];
    }
    return [];
  });
}

function focusBoundary(container: HTMLElement | null, boundary: "first" | "last") {
  const items = directMenuItems(container);
  (boundary === "first" ? items[0] : items.at(-1))?.focus();
}

function MenuPanel({
  entries,
  id,
  isActionEnabled,
  onAction,
  onDismiss,
  onMoveTop,
  onReturnParent,
  bindings,
  depth = 0,
}: {
  entries: MenuEntry[];
  id: string;
  isActionEnabled: (actionId: CircuitActionId) => boolean;
  onAction: (actionId: CircuitActionId) => void;
  onDismiss: () => void;
  onMoveTop: (delta: number) => void;
  onReturnParent?: () => void;
  bindings: ActionBindings;
  depth?: number;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [openSubmenu, setOpenSubmenu] = useState<string>();

  useEffect(() => focusBoundary(panelRef.current, "first"), []);

  const moveFocus = (event: KeyboardEvent<HTMLDivElement>) => {
    const items = directMenuItems(panelRef.current);
    if (!items.length) return;
    const current = items.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === "Home") return items[0]?.focus();
    if (event.key === "End") return items.at(-1)?.focus();
    const next = event.key === "ArrowDown" ? (current + 1) % items.length : (current <= 0 ? items.length : current) - 1;
    items[next]?.focus();
  };

  return <div
    aria-label={id}
    className={`circuit-menu__panel${depth ? " circuit-menu__panel--nested" : ""}`}
    onKeyDown={(event) => {
      if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        event.stopPropagation();
        moveFocus(event);
      } else if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onDismiss();
      } else if (depth && event.key === "ArrowLeft") {
        event.preventDefault();
        event.stopPropagation();
        onReturnParent?.();
      } else if (depth && event.key === "ArrowRight") {
        event.preventDefault();
        event.stopPropagation();
      } else if (!depth && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
        const active = document.activeElement as HTMLElement | null;
        const submenuTrigger = active?.getAttribute("aria-haspopup") === "menu";
        if (event.key === "ArrowRight" && submenuTrigger) return;
        event.preventDefault();
        event.stopPropagation();
        onMoveTop(event.key === "ArrowRight" ? 1 : -1);
      }
    }}
    ref={panelRef}
    role="menu"
  >
    {entries.map((entry, index): ReactNode => {
      if (entry.kind === "separator") return <div className="circuit-menu__separator" key={`separator-${index}`} role="separator" />;
      if (entry.kind === "submenu") {
        const open = openSubmenu === entry.id;
        return <div className="circuit-submenu" key={entry.id} onPointerEnter={() => setOpenSubmenu(entry.id)}>
          <button
            aria-expanded={open}
            aria-haspopup="menu"
            onClick={() => setOpenSubmenu(open ? undefined : entry.id)}
            onKeyDown={(event) => {
              if (event.key !== "ArrowRight") return;
              event.preventDefault();
              setOpenSubmenu(entry.id);
            }}
            role="menuitem"
            type="button"
          ><span>{entry.label}</span><small aria-hidden="true">›</small></button>
          {open && <MenuPanel
            bindings={bindings}
            depth={depth + 1}
            entries={entry.entries}
            id={entry.label}
            isActionEnabled={isActionEnabled}
            onAction={onAction}
            onDismiss={onDismiss}
            onReturnParent={() => {
              setOpenSubmenu(undefined);
              requestAnimationFrame(() => panelRef.current?.querySelector<HTMLButtonElement>(`[aria-haspopup='menu']`)?.focus());
            }}
            onMoveTop={onMoveTop}
          />}
        </div>;
      }
      const definition = definitions.get(entry.actionId);
      const shortcut = bindings[entry.actionId].keyboard;
      return <button
        aria-checked={entry.actionId === "toggle-inspector" ? Boolean(entry.checked) : undefined}
        disabled={!isActionEnabled(entry.actionId)}
        key={`${entry.actionId}-${index}`}
        onClick={() => { onAction(entry.actionId); onDismiss(); }}
        role={entry.actionId === "toggle-inspector" ? "menuitemcheckbox" : "menuitem"}
        type="button"
      >
        <span>{entry.actionId === "toggle-inspector" && entry.checked ? "✓ " : ""}{entry.label ?? definition?.label ?? entry.actionId}</span>
        {(entry.status || shortcut) && <small>{entry.status ?? formatKeyboardShortcut(shortcut)}</small>}
      </button>;
    })}
  </div>;
}

export interface CircuitMenuBarProps {
  bindings: ActionBindings;
  inspectorOpen: boolean;
  proposalCount: number;
  isActionEnabled: (actionId: CircuitActionId) => boolean;
  onAction: (actionId: CircuitActionId) => void;
}

export function CircuitMenuBar({ bindings, inspectorOpen, proposalCount, isActionEnabled, onAction }: CircuitMenuBarProps) {
  const [openMenu, setOpenMenu] = useState<string>();
  const rootRef = useRef<HTMLElement>(null);
  const effectiveMenus = useMemo(() => menus.map((menu) => ({
    ...menu,
    entries: menu.entries.map((entry) => entry.kind === "action" && entry.actionId === "toggle-inspector"
      ? { ...entry, checked: inspectorOpen }
      : entry.kind === "action" && entry.actionId === "review-proposals"
        ? { ...entry, status: proposalCount ? String(proposalCount) : undefined }
        : entry),
  })), [inspectorOpen, proposalCount]);

  useEffect(() => {
    const closeOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpenMenu(undefined);
    };
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, []);

  const moveTop = (from: string, delta: number, keepOpen: boolean) => {
    const index = effectiveMenus.findIndex((menu) => menu.id === from);
    const next = effectiveMenus[(index + delta + effectiveMenus.length) % effectiveMenus.length];
    if (!next) return;
    setOpenMenu(keepOpen ? next.id : undefined);
    requestAnimationFrame(() => document.getElementById(`circuit-${next.id}-menu-trigger`)?.focus());
  };

  return <nav aria-label="Circuit Designer menu" className="circuit-menubar" ref={rootRef} role="menubar">
    {effectiveMenus.map((menu) => {
      const open = openMenu === menu.id;
      return <div className="circuit-menu" key={menu.id} role="none">
        <button
          aria-expanded={open}
          aria-haspopup="menu"
          id={`circuit-${menu.id}-menu-trigger`}
          onClick={() => setOpenMenu(open ? undefined : menu.id)}
          onKeyDown={(event) => {
            if (["Enter", " ", "ArrowDown"].includes(event.key)) {
              event.preventDefault(); setOpenMenu(menu.id);
            } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
              event.preventDefault(); moveTop(menu.id, event.key === "ArrowRight" ? 1 : -1, false);
            } else if (event.key === "Home" || event.key === "End") {
              event.preventDefault();
              const target = event.key === "Home" ? effectiveMenus[0] : effectiveMenus.at(-1);
              if (target) document.getElementById(`circuit-${target.id}-menu-trigger`)?.focus();
            }
          }}
          onPointerEnter={() => { if (openMenu) setOpenMenu(menu.id); }}
          role="menuitem"
          type="button"
        >{menu.label}</button>
        {open && <MenuPanel
          bindings={bindings}
          entries={menu.entries}
          id={menu.label}
          isActionEnabled={isActionEnabled}
          onAction={onAction}
          onDismiss={() => {
            setOpenMenu(undefined);
            requestAnimationFrame(() => document.getElementById(`circuit-${menu.id}-menu-trigger`)?.focus());
          }}
          onMoveTop={(delta) => moveTop(menu.id, delta, true)}
        />}
      </div>;
    })}
  </nav>;
}

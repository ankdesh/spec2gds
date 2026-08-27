import { useEffect, useMemo, useRef, useState } from "react";
import { circuitActionDefinitions, formatKeyboardShortcut, type ActionBindings, type CircuitActionId } from "./action-bindings";
import { CircuitActionMenuPanel, type CircuitMenuEntry } from "./CircuitActionMenu";

type MenuDefinition = { id: string; label: string; entries: CircuitMenuEntry<CircuitActionId>[] };
const definitions = new Map(circuitActionDefinitions.map((item) => [item.id, item]));
const action = (commandId: CircuitActionId): CircuitMenuEntry<CircuitActionId> => ({
  kind: "action", commandId, label: definitions.get(commandId)?.label ?? commandId,
});
const menus: MenuDefinition[] = [
  { id: "file", label: "File", entries: [action("new-document"), action("open-document"), { kind: "separator" }, action("save-document"), action("cancel-changes"), { kind: "separator" }, { kind: "submenu", id: "download", label: "Download", entries: [action("download-json"), action("export-svg"), action("export-png")] }] },
  { id: "edit", label: "Edit", entries: [action("begin-edit"), { kind: "separator" }, action("undo"), action("redo"), { kind: "separator" }, action("delete-selection"), { kind: "separator" }, { kind: "submenu", id: "preferences", label: "Preferences", entries: [action("open-preferences")] }] },
  { id: "components", label: "Components", entries: [action("open-component-catalog"), action("create-local-component"), action("review-proposals"), { kind: "separator" }, action("open-child-design")] },
  { id: "selection", label: "Selection", entries: [action("select-all"), action("clear-selection"), action("center-selection")] },
  { id: "connect", label: "Connect", entries: [action("open-connect")] },
  { id: "route", label: "Route", entries: [action("reroute-selected"), action("lock-selected-route"), action("unlock-selected-route"), { kind: "separator" }, action("arrange-all")] },
  { id: "view", label: "View", entries: [action("toggle-inspector"), { kind: "separator" }, { kind: "submenu", id: "pan", label: "Pan", entries: [action("pan-up"), action("pan-left"), action("pan-down"), action("pan-right")] }, action("zoom-in"), action("zoom-out"), { kind: "separator" }, action("center-selection"), action("fit-circuit")] },
  { id: "tools", label: "Tools", entries: [action("open-assistant")] },
  { id: "help", label: "Help", entries: [action("getting-started"), { kind: "separator" }, action("about")] },
];

export interface CircuitMenuBarProps {
  bindings: ActionBindings;
  inspectorOpen: boolean;
  proposalCount: number;
  isActionEnabled: (actionId: CircuitActionId) => boolean;
  onAction: (actionId: CircuitActionId) => void;
  dismissVersion?: number;
  onOpenChange?: (open: boolean) => void;
  sourceBound?: boolean;
}

export function CircuitMenuBar({ bindings, inspectorOpen, proposalCount, isActionEnabled, onAction, dismissVersion, onOpenChange, sourceBound }: CircuitMenuBarProps) {
  const [openMenu, setOpenMenu] = useState<string>();
  const rootRef = useRef<HTMLElement>(null);
  const effectiveMenus = useMemo(() => menus.map((menu) => ({
    ...menu,
    entries: menu.entries.map((entry) => entry.kind === "action" && entry.commandId === "save-document" && sourceBound
      ? { ...entry, label: "Save to Specification" }
      : entry.kind === "action" && entry.commandId === "toggle-inspector"
      ? { ...entry, checked: inspectorOpen, checkType: "checkbox" as const }
      : entry.kind === "action" && entry.commandId === "review-proposals"
        ? { ...entry, status: proposalCount ? String(proposalCount) : undefined }
        : entry),
  })), [inspectorOpen, proposalCount, sourceBound]);
  const close = () => { setOpenMenu(undefined); onOpenChange?.(false); };
  const setOpen = (id: string | undefined) => { setOpenMenu(id); onOpenChange?.(Boolean(id)); };

  useEffect(() => close(), [dismissVersion]);
  useEffect(() => {
    const closeOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close();
    };
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, []);

  const moveTop = (from: string, delta: number, keepOpen: boolean) => {
    const index = effectiveMenus.findIndex((menu) => menu.id === from);
    const next = effectiveMenus[(index + delta + effectiveMenus.length) % effectiveMenus.length];
    if (!next) return;
    setOpen(keepOpen ? next.id : undefined);
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
          onClick={() => setOpen(open ? undefined : menu.id)}
          onKeyDown={(event) => {
            if (["Enter", " ", "ArrowDown"].includes(event.key)) {
              event.preventDefault(); setOpen(menu.id);
            } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
              event.preventDefault(); moveTop(menu.id, event.key === "ArrowRight" ? 1 : -1, false);
            } else if (event.key === "Home" || event.key === "End") {
              event.preventDefault();
              const target = event.key === "Home" ? effectiveMenus[0] : effectiveMenus.at(-1);
              if (target) document.getElementById(`circuit-${target.id}-menu-trigger`)?.focus();
            }
          }}
          onPointerEnter={() => { if (openMenu) setOpen(menu.id); }}
          role="menuitem"
          type="button"
        >{menu.label}</button>
        {open && <CircuitActionMenuPanel
          entries={menu.entries}
          isCommandEnabled={isActionEnabled}
          label={menu.label}
          onCommand={onAction}
          onDismiss={() => {
            close();
            requestAnimationFrame(() => document.getElementById(`circuit-${menu.id}-menu-trigger`)?.focus());
          }}
          onMoveTop={(delta) => moveTop(menu.id, delta, true)}
          shortcutFor={(commandId) => bindings[commandId].keyboard ? formatKeyboardShortcut(bindings[commandId].keyboard) : undefined}
        />}
      </div>;
    })}
  </nav>;
}

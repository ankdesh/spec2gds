/* Reusable Circuit Designer application shell. */
import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

export type CircuitMenuEntry<CommandId extends string> =
  | { kind: "action"; commandId: CommandId; label: string; checked?: boolean; checkType?: "checkbox" | "radio"; status?: string }
  | { kind: "separator" }
  | { kind: "submenu"; id: string; label: string; entries: CircuitMenuEntry<CommandId>[] };

function directMenuItems(container: HTMLElement | null): HTMLButtonElement[] {
  return Array.from(container?.children ?? []).flatMap((child) => {
    if (child instanceof HTMLButtonElement && child.getAttribute("role")?.startsWith("menuitem") && !child.disabled) return [child];
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

export function CircuitActionMenuPanel<CommandId extends string>({
  entries,
  label,
  isCommandEnabled,
  onCommand,
  onDismiss,
  onMoveTop,
  onReturnParent,
  shortcutFor,
  depth = 0,
}: {
  entries: CircuitMenuEntry<CommandId>[];
  label: string;
  isCommandEnabled: (commandId: CommandId) => boolean;
  onCommand: (commandId: CommandId) => void;
  onDismiss: () => void;
  onMoveTop?: (delta: number) => void;
  onReturnParent?: () => void;
  shortcutFor?: (commandId: CommandId) => string | undefined;
  depth?: number;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [openSubmenu, setOpenSubmenu] = useState<string>();
  const [nestedStyle, setNestedStyle] = useState<CSSProperties>();

  useEffect(() => focusBoundary(panelRef.current, "first"), []);
  useLayoutEffect(() => {
    if (!depth || !panelRef.current) return;
    const bounds = panelRef.current.getBoundingClientRect();
    const next: CSSProperties = {};
    if (bounds.right > window.innerWidth - 8) {
      next.left = "auto";
      next.right = "calc(100% + 4px)";
    }
    if (bounds.bottom > window.innerHeight - 8) next.transform = `translateY(-${bounds.bottom - window.innerHeight + 8}px)`;
    setNestedStyle(next);
  }, [depth, entries.length]);

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
    aria-label={label}
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
      } else if (!depth && (event.key === "ArrowLeft" || event.key === "ArrowRight") && onMoveTop) {
        const active = document.activeElement as HTMLElement | null;
        if (event.key === "ArrowRight" && active?.getAttribute("aria-haspopup") === "menu") return;
        event.preventDefault();
        event.stopPropagation();
        onMoveTop(event.key === "ArrowRight" ? 1 : -1);
      }
    }}
    ref={panelRef}
    role="menu"
    style={nestedStyle}
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
          {open && <CircuitActionMenuPanel
            depth={depth + 1}
            entries={entry.entries}
            isCommandEnabled={isCommandEnabled}
            label={entry.label}
            onCommand={onCommand}
            onDismiss={onDismiss}
            onReturnParent={() => {
              setOpenSubmenu(undefined);
              requestAnimationFrame(() => panelRef.current?.querySelector<HTMLButtonElement>(`[aria-haspopup='menu'][aria-expanded='false']`)?.focus());
            }}
            shortcutFor={shortcutFor}
          />}
        </div>;
      }
      const shortcut = shortcutFor?.(entry.commandId);
      const role = entry.checkType === "checkbox" ? "menuitemcheckbox" : entry.checkType === "radio" ? "menuitemradio" : "menuitem";
      return <button
        aria-checked={entry.checkType ? Boolean(entry.checked) : undefined}
        disabled={!isCommandEnabled(entry.commandId)}
        key={`${entry.commandId}-${index}`}
        onClick={() => { onCommand(entry.commandId); onDismiss(); }}
        role={role}
        type="button"
      >
        <span>{entry.checkType && entry.checked ? "✓ " : ""}{entry.label}</span>
        {(entry.status || shortcut) && <small>{entry.status ?? shortcut}</small>}
      </button>;
    })}
  </div>;
}

export function CircuitContextMenu<CommandId extends string>({
  entries,
  point,
  isCommandEnabled,
  onCommand,
  onDismiss,
  shortcutFor,
}: {
  entries: CircuitMenuEntry<CommandId>[];
  point: { x: number; y: number };
  isCommandEnabled: (commandId: CommandId) => boolean;
  onCommand: (commandId: CommandId) => void;
  onDismiss: () => void;
  shortcutFor?: (commandId: CommandId) => string | undefined;
}) {
  const anchorRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState(point);

  useLayoutEffect(() => {
    const bounds = anchorRef.current?.getBoundingClientRect();
    if (!bounds) return;
    setPosition({
      x: Math.max(8, Math.min(point.x, window.innerWidth - bounds.width - 8)),
      y: Math.max(8, Math.min(point.y, window.innerHeight - bounds.height - 8)),
    });
  }, [point.x, point.y, entries.length]);

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const items = directMenuItems(anchorRef.current?.querySelector<HTMLElement>("[role='menu']") ?? null);
      if (!items.some((item) => item === document.activeElement)) items[0]?.focus();
    });
    return () => cancelAnimationFrame(frame);
  }, [point.x, point.y]);

  useEffect(() => {
    const outside = (event: PointerEvent) => {
      if (!anchorRef.current?.contains(event.target as Node)) onDismiss();
    };
    const dismiss = () => onDismiss();
    document.addEventListener("pointerdown", outside, true);
    window.addEventListener("resize", dismiss);
    window.addEventListener("scroll", dismiss, true);
    return () => {
      document.removeEventListener("pointerdown", outside, true);
      window.removeEventListener("resize", dismiss);
      window.removeEventListener("scroll", dismiss, true);
    };
  }, [onDismiss]);

  return createPortal(<div
    className="circuit-context-menu"
    ref={anchorRef}
    style={{ left: position.x, top: position.y }}
  >
    <CircuitActionMenuPanel
      entries={entries}
      isCommandEnabled={isCommandEnabled}
      label="Circuit context menu"
      onCommand={onCommand}
      onDismiss={onDismiss}
      shortcutFor={shortcutFor}
    />
  </div>, document.body);
}

import {
  createDefaultCircuitActionBindings,
  createDefaultCircuitDesignerPreferences,
  validateCircuitDesignerPreferences,
  type CircuitActionBindings,
  type CircuitActionId,
  type CircuitDesignerPreferencesV1,
  type CircuitMouseShortcut,
} from "@spec2gds/circuit-core";

export type ActionBindings = CircuitActionBindings;
export type MouseShortcut = CircuitMouseShortcut;
export type { CircuitActionId };

export type CircuitActionGroup = "File" | "Edit" | "Components" | "Selection" | "Connect" | "Route" | "View" | "Tools" | "Help";
export type CircuitActionDefinition = {
  id: CircuitActionId;
  group: CircuitActionGroup;
  label: string;
  description: string;
  mouseOptions: MouseShortcut[];
};

const commandMouseOptions: MouseShortcut[] = ["none", "primary-click", "primary-double-click", "middle-click", "secondary-click"];
const command = (id: CircuitActionId, group: CircuitActionGroup, label: string, description: string): CircuitActionDefinition => ({
  id, group, label, description, mouseOptions: commandMouseOptions,
});

export const circuitActionDefinitions: CircuitActionDefinition[] = [
  command("new-document", "File", "New circuit", "Start a new empty circuit document."),
  command("open-document", "File", "Open circuit", "Open a canonical Circuit Designer JSON file."),
  command("save-document", "File", "Save changes", "Commit the private draft and download its canonical circuit file."),
  command("cancel-changes", "File", "Cancel changes", "Discard the current private draft."),
  command("download-json", "File", "Download circuit JSON", "Download the authoritative canonical circuit file."),
  command("export-svg", "File", "Export SVG", "Export the circuit as an SVG image."),
  command("export-png", "File", "Export PNG", "Export the circuit as a PNG image."),
  command("begin-edit", "Edit", "Begin editing", "Acquire a private edit lease for this circuit."),
  command("undo", "Edit", "Undo", "Undo the most recent private draft operation."),
  command("redo", "Edit", "Redo", "Redo the most recently undone draft operation."),
  command("delete-selection", "Edit", "Delete selected", "Delete the selected instance with its connectivity, or the selected net."),
  command("open-preferences", "Edit", "Actions and shortcuts", "Open Circuit Designer input preferences."),
  command("open-component-catalog", "Components", "Component catalog", "Browse definitions available to this circuit."),
  command("create-local-component", "Components", "New local component", "Create a local definition and its first instance."),
  command("review-proposals", "Components", "Review proposals", "Review pending external circuit proposals."),
  command("open-child-design", "Components", "Open selected child design", "Resolve the selected instance's component design."),
  command("select-all", "Selection", "Select all", "Select every instance, boundary terminal, and net."),
  command("clear-selection", "Selection", "Clear selection", "Deselect every item and cancel a keyboard connection."),
  command("center-selection", "Selection", "Center on selection", "Fit the viewport around the selected items."),
  command("open-connect", "Connect", "New connection", "Open the form for a named or sliced two-terminal net."),
  command("reroute-selected", "Route", "Reroute selected net", "Automatically route the selected unlocked net."),
  command("lock-selected-route", "Route", "Lock selected route", "Prevent changes to the selected route."),
  command("unlock-selected-route", "Route", "Unlock selected route", "Allow the selected route to be edited again."),
  command("arrange-all", "Route", "Arrange and route all", "Run automatic layout and routing for the complete circuit."),
  command("toggle-inspector", "View", "Show Inspector", "Show or hide the circuit selection Inspector."),
  { id: "pan-canvas", group: "View", label: "Drag canvas", description: "Pan by dragging empty canvas.", mouseOptions: ["none", "primary-drag", "middle-drag", "secondary-drag"] },
  command("pan-up", "View", "Pan up", "Move the viewport upward by one step."),
  command("pan-left", "View", "Pan left", "Move the viewport left by one step."),
  command("pan-down", "View", "Pan down", "Move the viewport downward by one step."),
  command("pan-right", "View", "Pan right", "Move the viewport right by one step."),
  { id: "zoom-in", group: "View", label: "Zoom in", description: "Increase the canvas zoom level.", mouseOptions: ["none", "wheel-up", ...commandMouseOptions.slice(1)] },
  { id: "zoom-out", group: "View", label: "Zoom out", description: "Decrease the canvas zoom level.", mouseOptions: ["none", "wheel-down", ...commandMouseOptions.slice(1)] },
  command("fit-circuit", "View", "Fit circuit", "Fit the complete circuit in the viewport."),
  command("open-assistant", "Tools", "AI Assistant", "Open a chat bound to this circuit."),
  command("getting-started", "Help", "Getting started", "Show a concise Circuit Designer workflow guide."),
  command("about", "Help", "About Circuit Designer", "Show product and persistence information."),
];

export const circuitActionGroups: CircuitActionGroup[] = ["File", "Edit", "Components", "Selection", "Connect", "Route", "View", "Tools", "Help"];

export const mouseShortcutLabels: Record<MouseShortcut, string> = {
  none: "Not assigned",
  "primary-click": "Left click (empty canvas)",
  "primary-double-click": "Left double-click (empty canvas)",
  "middle-click": "Middle click (empty canvas)",
  "secondary-click": "Right click (empty canvas)",
  "primary-drag": "Left drag",
  "middle-drag": "Middle drag",
  "secondary-drag": "Right drag",
  "wheel-up": "Wheel up",
  "wheel-down": "Wheel down",
};

const legacyStorageKey = "spec2gds.circuit-designer.action-bindings.v1";
const cacheStorageKey = "spec2gds.circuit-designer.preferences-cache.v1";
type BindingStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function createDefaultActionBindings(): ActionBindings {
  return createDefaultCircuitActionBindings();
}

export function loadCachedPreferences(storage: BindingStorage): CircuitDesignerPreferencesV1 | undefined {
  try {
    const cached = JSON.parse(storage.getItem(cacheStorageKey) ?? "null") as unknown;
    const checked = validateCircuitDesignerPreferences(cached);
    if (checked.valid) return checked.preferences;
    const legacy = JSON.parse(storage.getItem(legacyStorageKey) ?? "null") as {
      bindings?: Partial<Record<CircuitActionId, { keyboard?: unknown; mouse?: unknown }>>;
    } | null;
    if (!legacy?.bindings) return undefined;
    const preferences = createDefaultCircuitDesignerPreferences();
    for (const action of circuitActionDefinitions) {
      const saved = legacy.bindings[action.id];
      if (!saved) continue;
      if (typeof saved.keyboard === "string") preferences.action_bindings[action.id].keyboard = saved.keyboard;
      if (typeof saved.mouse === "string" && action.mouseOptions.includes(saved.mouse as MouseShortcut)) {
        preferences.action_bindings[action.id].mouse = saved.mouse as MouseShortcut;
      }
    }
    return preferences;
  } catch {
    return undefined;
  }
}

export function cachePreferences(storage: BindingStorage, preferences: CircuitDesignerPreferencesV1): void {
  try { storage.setItem(cacheStorageKey, JSON.stringify(preferences)); } catch { /* The server file remains authoritative. */ }
}

export function clearCachedPreferences(storage: BindingStorage): void {
  try {
    storage.removeItem(cacheStorageKey);
    storage.removeItem(legacyStorageKey);
  } catch { /* Clearing a migration cache must not interrupt the editor. */ }
}

export function assignKeyboardShortcut(bindings: ActionBindings, actionId: CircuitActionId, keyboard: string): ActionBindings {
  const next = structuredClone(bindings);
  if (keyboard) {
    for (const action of circuitActionDefinitions) {
      if (action.id !== actionId && next[action.id].keyboard === keyboard) next[action.id].keyboard = "";
    }
  }
  next[actionId].keyboard = keyboard;
  return next;
}

export function assignMouseShortcut(bindings: ActionBindings, actionId: CircuitActionId, mouse: MouseShortcut): ActionBindings {
  const next = structuredClone(bindings);
  if (mouse !== "none") {
    for (const action of circuitActionDefinitions) {
      if (action.id !== actionId && next[action.id].mouse === mouse) next[action.id].mouse = "none";
    }
  }
  next[actionId].mouse = mouse;
  return next;
}

const keyAliases: Record<string, string> = { " ": "Space", "+": "Plus", Esc: "Escape", Control: "Control", Meta: "Meta", Alt: "Alt", Shift: "Shift" };
function normalizedKey(key: string): string {
  const value = keyAliases[key] ?? key;
  return value.length === 1 ? value.toUpperCase() : value;
}

export function keyboardShortcutFromEvent(event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey">): string {
  const key = normalizedKey(event.key);
  if (["Control", "Meta", "Alt", "Shift"].includes(key)) return key === "Meta" ? "Mod" : key;
  const parts: string[] = [];
  if (event.ctrlKey || event.metaKey) parts.push("Mod");
  if (event.altKey) parts.push("Alt");
  if (event.shiftKey) parts.push("Shift");
  parts.push(key);
  return parts.join("+");
}

export function keyboardEventMatches(event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey">, shortcut: string): boolean {
  if (!shortcut) return false;
  const parts = shortcut.split("+");
  const expectedKey = parts.at(-1) ?? "";
  const expectsMod = parts.includes("Mod");
  const expectsAlt = parts.includes("Alt");
  const expectsShift = parts.includes("Shift");
  const modifierKey = ["Mod", "Control", "Meta", "Alt", "Shift"].includes(expectedKey);
  const keyMatches = expectedKey === "Mod" ? event.key === "Control" || event.key === "Meta" : normalizedKey(event.key) === expectedKey;
  if (!keyMatches) return false;
  if (modifierKey) return true;
  return (event.ctrlKey || event.metaKey) === expectsMod && event.altKey === expectsAlt && event.shiftKey === expectsShift;
}

export function formatKeyboardShortcut(shortcut: string): string {
  if (!shortcut) return "Not assigned";
  return shortcut.split("+").map((part) => part === "Mod" ? "Ctrl/⌘" : part === "Plus" ? "+" : part).join(" ");
}

export function actionBindingLabel(bindings: ActionBindings, actionId: CircuitActionId): string {
  const binding = bindings[actionId];
  return [binding.keyboard ? formatKeyboardShortcut(binding.keyboard) : "", binding.mouse !== "none" ? mouseShortcutLabels[binding.mouse] : ""].filter(Boolean).join(" · ");
}

export function panMouseButtons(binding: MouseShortcut): Array<0 | 1 | 2> {
  if (binding === "primary-drag") return [0];
  if (binding === "middle-drag") return [1];
  if (binding === "secondary-drag") return [2];
  return [];
}

export function reactFlowKeyCode(shortcut: string): string | string[] | null {
  if (!shortcut) return null;
  if (!shortcut.includes("Mod")) return shortcut;
  return [shortcut.replace("Mod", "Control"), shortcut.replace("Mod", "Meta")];
}

export function standardWheelZoomEnabled(bindings: ActionBindings): boolean {
  return bindings["zoom-in"].mouse === "wheel-up" && bindings["zoom-out"].mouse === "wheel-down";
}

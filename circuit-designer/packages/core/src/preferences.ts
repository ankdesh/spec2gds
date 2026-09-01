export const circuitActionIds = [
  "new-document",
  "open-document",
  "save-document",
  "cancel-changes",
  "download-json",
  "export-svg",
  "export-png",
  "begin-edit",
  "undo",
  "redo",
  "delete-selection",
  "open-preferences",
  "open-component-catalog",
  "create-local-component",
  "review-proposals",
  "open-child-design",
  "select-all",
  "clear-selection",
  "center-selection",
  "open-connect",
  "reroute-selected",
  "lock-selected-route",
  "unlock-selected-route",
  "arrange-all",
  "add-cycle-edge",
  "open-clock-settings",
  "open-timing-analysis",
  "edit-cycle-edge",
  "lock-cycle-edge",
  "unlock-cycle-edge",
  "delete-cycle-edge",
  "toggle-inspector",
  "toggle-timing-overlay",
  "pan-canvas",
  "pan-up",
  "pan-left",
  "pan-down",
  "pan-right",
  "zoom-in",
  "zoom-out",
  "fit-circuit",
  "run-primary-tool",
  "getting-started",
  "about",
] as const;

export type CircuitActionId = typeof circuitActionIds[number];

export const circuitMouseShortcuts = [
  "none",
  "primary-click",
  "primary-double-click",
  "middle-click",
  "secondary-click",
  "primary-drag",
  "middle-drag",
  "secondary-drag",
  "wheel-up",
  "wheel-down",
] as const;

export type CircuitMouseShortcut = typeof circuitMouseShortcuts[number];

export interface CircuitActionBinding {
  keyboard: string;
  mouse: CircuitMouseShortcut;
}

export type CircuitActionBindings = Record<CircuitActionId, CircuitActionBinding>;

export interface CircuitDesignerPreferencesV1 {
  schema_version: 1;
  ui: {
    inspector_open: boolean;
    timing_overlay_visible: boolean;
  };
  action_bindings: CircuitActionBindings;
}

const keyboardDefaults: Partial<Record<CircuitActionId, string>> = {
  "new-document": "Mod+N",
  "open-document": "Mod+O",
  "save-document": "Mod+S",
  undo: "Mod+Z",
  redo: "Mod+Shift+Z",
  "delete-selection": "Delete",
  "select-all": "Mod+A",
  "clear-selection": "Escape",
  "pan-canvas": "Space",
};

const mouseDefaults: Partial<Record<CircuitActionId, CircuitMouseShortcut>> = {
  "pan-canvas": "primary-drag",
  "zoom-in": "wheel-up",
  "zoom-out": "wheel-down",
};

export function createDefaultCircuitActionBindings(): CircuitActionBindings {
  return Object.fromEntries(circuitActionIds.map((actionId) => [actionId, {
    keyboard: keyboardDefaults[actionId] ?? "",
    mouse: mouseDefaults[actionId] ?? "none",
  }])) as CircuitActionBindings;
}

export function createDefaultCircuitDesignerPreferences(): CircuitDesignerPreferencesV1 {
  return {
    schema_version: 1,
    ui: { inspector_open: false, timing_overlay_visible: true },
    action_bindings: createDefaultCircuitActionBindings(),
  };
}

export type CircuitPreferenceValidationResult =
  | { valid: true; preferences: CircuitDesignerPreferencesV1 }
  | { valid: false; message: string };

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function validateCircuitDesignerPreferences(value: unknown): CircuitPreferenceValidationResult {
  if (!isRecord(value) || value.schema_version !== 1) {
    return { valid: false, message: "Circuit Designer preferences must use schema_version 1." };
  }
  if (!isRecord(value.ui) || typeof value.ui.inspector_open !== "boolean") {
    return { valid: false, message: "Circuit Designer preferences.ui.inspector_open must be boolean." };
  }
  if (!isRecord(value.action_bindings)) {
    return { valid: false, message: "Circuit Designer preferences.action_bindings must be an object." };
  }
  const knownActions = new Set<string>(circuitActionIds);
  const legacyActionAliases: Record<string, CircuitActionId> = { "open-assistant": "run-primary-tool" };
  const knownMouseShortcuts = new Set<string>(circuitMouseShortcuts);
  for (const [actionId, binding] of Object.entries(value.action_bindings)) {
    if (!knownActions.has(actionId) && !(actionId in legacyActionAliases)) {
      return { valid: false, message: `Unknown Circuit Designer action: ${actionId}.` };
    }
    if (!isRecord(binding) || typeof binding.keyboard !== "string" || binding.keyboard.length > 64) {
      return { valid: false, message: `Action ${actionId} must have a keyboard shortcut of at most 64 characters.` };
    }
    if (typeof binding.mouse !== "string" || !knownMouseShortcuts.has(binding.mouse)) {
      return { valid: false, message: `Action ${actionId} has an unsupported mouse shortcut.` };
    }
  }
  const preferences = createDefaultCircuitDesignerPreferences();
  preferences.ui.inspector_open = value.ui.inspector_open;
  preferences.ui.timing_overlay_visible = typeof value.ui.timing_overlay_visible === "boolean" ? value.ui.timing_overlay_visible : true;
  for (const actionId of circuitActionIds) {
    const legacyId = Object.entries(legacyActionAliases).find(([, next]) => next === actionId)?.[0];
    const binding = value.action_bindings[actionId] ?? (legacyId ? value.action_bindings[legacyId] : undefined);
    if (!isRecord(binding)) continue;
    preferences.action_bindings[actionId] = {
      keyboard: binding.keyboard as string,
      mouse: binding.mouse as CircuitMouseShortcut,
    };
  }
  return { valid: true, preferences };
}

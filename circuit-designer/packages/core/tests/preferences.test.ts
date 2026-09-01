import { describe, expect, test } from "vitest";
import {
  circuitActionIds,
  createDefaultCircuitDesignerPreferences,
  validateCircuitDesignerPreferences,
} from "../src/index";

describe("Circuit Designer preferences", () => {
  test("provides complete standard action defaults with a closed inspector", () => {
    const preferences = createDefaultCircuitDesignerPreferences();
    expect(preferences.ui.inspector_open).toBe(false);
    expect(Object.keys(preferences.action_bindings)).toHaveLength(circuitActionIds.length);
    expect(preferences.action_bindings["new-document"].keyboard).toBe("Mod+N");
    expect(preferences.action_bindings.undo.keyboard).toBe("Mod+Z");
    expect(preferences.action_bindings["pan-canvas"].mouse).toBe("primary-drag");
  });

  test("merges missing known actions from defaults", () => {
    const checked = validateCircuitDesignerPreferences({
      schema_version: 1,
      ui: { inspector_open: true },
      action_bindings: { "fit-circuit": { keyboard: "F", mouse: "none" } },
    });
    expect(checked.valid).toBe(true);
    if (!checked.valid) return;
    expect(checked.preferences.ui.inspector_open).toBe(true);
    expect(checked.preferences.action_bindings["fit-circuit"].keyboard).toBe("F");
    expect(checked.preferences.action_bindings["select-all"].keyboard).toBe("Mod+A");
  });

  test("migrates the former assistant action to the host-tool action", () => {
    const checked = validateCircuitDesignerPreferences({
      schema_version: 1,
      ui: { inspector_open: false, timing_overlay_visible: true },
      action_bindings: { "open-assistant": { keyboard: "Mod+J", mouse: "none" } },
    });
    expect(checked.valid).toBe(true);
    if (!checked.valid) return;
    expect(checked.preferences.action_bindings["run-primary-tool"].keyboard).toBe("Mod+J");
  });

  test("rejects unknown actions, invalid mouse inputs, and oversized keys", () => {
    const defaults = createDefaultCircuitDesignerPreferences();
    expect(validateCircuitDesignerPreferences({
      ...defaults,
      action_bindings: { ...defaults.action_bindings, surprise: { keyboard: "", mouse: "none" } },
    }).valid).toBe(false);
    expect(validateCircuitDesignerPreferences({
      ...defaults,
      action_bindings: { ...defaults.action_bindings, undo: { keyboard: "", mouse: "telepathy" } },
    }).valid).toBe(false);
    expect(validateCircuitDesignerPreferences({
      ...defaults,
      action_bindings: { ...defaults.action_bindings, undo: { keyboard: "x".repeat(65), mouse: "none" } },
    }).valid).toBe(false);
  });
});

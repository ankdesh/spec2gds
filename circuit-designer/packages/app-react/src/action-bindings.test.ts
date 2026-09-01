import { describe, expect, test } from "vitest";
import {
  assignKeyboardShortcut,
  assignMouseShortcut,
  cachePreferences,
  clearCachedPreferences,
  createDefaultActionBindings,
  keyboardEventMatches,
  keyboardShortcutFromEvent,
  loadCachedPreferences,
  normalizeContextMenuMouseBindings,
  panMouseButtons,
  standardWheelZoomEnabled,
  circuitActionDefinitions,
} from "./action-bindings";
import { createDefaultCircuitDesignerPreferences } from "@spec2gds/circuit-core";

function keyEvent(key: string, modifiers: Partial<Pick<KeyboardEvent, "ctrlKey" | "metaKey" | "altKey" | "shiftKey">> = {}) {
  return { key, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...modifiers };
}

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, next: string) => { values.set(key, next); },
    removeItem: (key: string) => { values.delete(key); },
    value: (key: string) => values.get(key),
  };
}

describe("Circuit Designer action bindings", () => {
  test("ships the current actions with left-drag canvas panning", () => {
    const bindings = createDefaultActionBindings();

    expect(bindings["select-all"].keyboard).toBe("Mod+A");
    expect(bindings["clear-selection"].keyboard).toBe("Escape");
    expect(bindings["pan-canvas"]).toEqual({ keyboard: "Space", mouse: "primary-drag" });
    expect(panMouseButtons(bindings["pan-canvas"].mouse)).toEqual([0]);
    expect(standardWheelZoomEnabled(bindings)).toBe(true);
  });

  test("moves a keyboard or mouse shortcut instead of creating a conflict", () => {
    const defaults = createDefaultActionBindings();
    const keyboard = assignKeyboardShortcut(defaults, "fit-circuit", "Escape");
    const mouse = assignMouseShortcut(defaults, "fit-circuit", "primary-click");

    expect(keyboard["fit-circuit"].keyboard).toBe("Escape");
    expect(keyboard["clear-selection"].keyboard).toBe("");
    expect(mouse["fit-circuit"].mouse).toBe("primary-click");
  });

  test("records and matches cross-platform modifier shortcuts", () => {
    expect(keyboardShortcutFromEvent(keyEvent("a", { ctrlKey: true }))).toBe("Mod+A");
    expect(keyboardEventMatches(keyEvent("a", { ctrlKey: true }), "Mod+A")).toBe(true);
    expect(keyboardEventMatches(keyEvent("a", { metaKey: true }), "Mod+A")).toBe(true);
    expect(keyboardEventMatches(keyEvent("a"), "Mod+A")).toBe(false);
    expect(keyboardShortcutFromEvent(keyEvent(" "))).toBe("Space");
  });

  test("uses local storage only as a valid failed-save cache", () => {
    const storage = memoryStorage();
    const preferences = createDefaultCircuitDesignerPreferences();
    preferences.action_bindings = assignKeyboardShortcut(preferences.action_bindings, "fit-circuit", "F");
    cachePreferences(storage, preferences);

    expect(loadCachedPreferences(storage)?.action_bindings["fit-circuit"].keyboard).toBe("F");
    clearCachedPreferences(storage);
    expect(loadCachedPreferences(storage)).toBeUndefined();
  });

  test("migrates the legacy browser-local binding profile", () => {
    const legacy = memoryStorage({
      "spec2gds.circuit-designer.action-bindings.v1": JSON.stringify({
        bindings: { "fit-circuit": { keyboard: "F", mouse: "primary-double-click" } },
      }),
    });

    expect(loadCachedPreferences(legacy)?.action_bindings["fit-circuit"]).toEqual({
      keyboard: "F",
      mouse: "primary-double-click",
    });
    expect(loadCachedPreferences(memoryStorage({
      "spec2gds.circuit-designer.preferences-cache.v1": "not-json",
    }))).toBeUndefined();
  });

  test("reserves secondary click for semantic context menus", () => {
    const preferences = createDefaultCircuitDesignerPreferences();
    preferences.action_bindings["fit-circuit"].mouse = "secondary-click";
    const normalized = normalizeContextMenuMouseBindings(preferences);

    expect(normalized.changed).toBe(true);
    expect(normalized.preferences.action_bindings["fit-circuit"].mouse).toBe("none");
    expect(normalizeContextMenuMouseBindings(normalized.preferences).changed).toBe(false);
    expect(circuitActionDefinitions.every((action) => !action.mouseOptions.includes("secondary-click"))).toBe(true);
    expect(circuitActionDefinitions.find((action) => action.id === "pan-canvas")?.mouseOptions).toContain("secondary-drag");
  });
});

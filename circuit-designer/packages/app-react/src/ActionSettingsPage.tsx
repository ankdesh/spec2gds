/* Reusable Circuit Designer application shell. */
import { useState, type KeyboardEvent } from "react";
import { createDefaultCircuitDesignerPreferences, circuitThemes, type CircuitDesignerPreferencesV1 } from "@spec2gds/circuit-core";
import {
  assignKeyboardShortcut,
  assignMouseShortcut,
  circuitActionDefinitions,
  circuitActionGroups,
  formatKeyboardShortcut,
  keyboardShortcutFromEvent,
  mouseShortcutLabels,
  type CircuitActionId,
  type MouseShortcut,
} from "./action-bindings";

export interface ActionSettingsPageProps {
  preferences: CircuitDesignerPreferencesV1;
  preferenceStatus: "loading" | "saved" | "saving" | "error";
  onPreferencesChange: (preferences: CircuitDesignerPreferencesV1) => void;
  onClose: () => void;
}

export function ActionSettingsPage({ preferences, preferenceStatus, onPreferencesChange, onClose }: ActionSettingsPageProps) {
  const [message, setMessage] = useState("Changes are saved to the shared Circuit Designer preference file.");
  const bindings = preferences.action_bindings;
  const updateBindings = (next: typeof bindings) => onPreferencesChange({ ...preferences, action_bindings: next });

  const recordKeyboard = (actionId: CircuitActionId, label: string, event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "Tab") return;
    event.preventDefault();
    event.stopPropagation();
    const keyboard = keyboardShortcutFromEvent(event.nativeEvent);
    updateBindings(assignKeyboardShortcut(bindings, actionId, keyboard));
    setMessage(`${label} now uses ${formatKeyboardShortcut(keyboard)}.`);
  };

  const clearKeyboard = (actionId: CircuitActionId, label: string) => {
    updateBindings(assignKeyboardShortcut(bindings, actionId, ""));
    setMessage(`Removed the keyboard shortcut for ${label}.`);
  };

  const changeMouse = (actionId: CircuitActionId, label: string, mouse: MouseShortcut) => {
    updateBindings(assignMouseShortcut(bindings, actionId, mouse));
    setMessage(mouse === "none"
      ? `Removed the mouse shortcut for ${label}.`
      : `${label} now uses ${mouseShortcutLabels[mouse]}.`);
  };

  return <section className="action-settings" aria-labelledby="action-settings-title">
    <header className="action-settings__header">
      <div>
        <p className="eyebrow">Input configuration</p>
        <h2 id="action-settings-title">Circuit Designer preferences</h2>
        <p>Choose interface preferences and the keyboard and mouse input for every command. Assigning an input already in use moves it to the new action.</p>
      </div>
      <div className="action-settings__header-actions">
        <button type="button" onClick={() => {
          onPreferencesChange(createDefaultCircuitDesignerPreferences());
          setMessage("Restored all current default bindings.");
        }}>Reset defaults</button>
        <button className="primary" type="button" onClick={onClose}>Done</button>
      </div>
    </header>

    <p className={`action-settings__status action-settings__status--${preferenceStatus}`} role="status">{message} · {preferenceStatus === "loading" ? "Loading…" : preferenceStatus === "saving" ? "Saving…" : preferenceStatus === "saved" ? "Saved" : "Save failed"}</p>

    <section className="action-settings__group">
      <h3>Appearance & Theme</h3>
      <div className="action-settings__theme-grid" role="radiogroup" aria-label="Visual Theme">
        {Object.values(circuitThemes).map((theme) => {
          const isSelected = (preferences.ui.theme_id || "blueprint-slate") === theme.id;
          return (
            <button
              key={theme.id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              className={`action-settings__theme-card${isSelected ? " action-settings__theme-card--selected" : ""}`}
              onClick={() => {
                onPreferencesChange({ ...preferences, ui: { ...preferences.ui, theme_id: theme.id } });
                setMessage(`Active theme switched to ${theme.label ?? theme.id}.`);
              }}
            >
              <div className="action-settings__theme-swatches">
                <span className="swatch-canvas" style={{ background: theme.colors.canvas }}>
                  <span className="swatch-surface" style={{ background: theme.colors.surface, borderColor: theme.colors.border }}>
                    <span className="swatch-net" style={{ background: theme.colors.net }} />
                  </span>
                </span>
              </div>
              <div className="action-settings__theme-info">
                <strong>{theme.label ?? theme.id}</strong>
                <small>{theme.description ?? ""}</small>
                {isSelected && <span className="action-settings__theme-badge">Active</span>}
              </div>
            </button>
          );
        })}
      </div>
    </section>

    <section className="action-settings__group">
      <h3>Interface</h3>
      <label className="preference-toggle">
        <input
          checked={preferences.ui.inspector_open}
          onChange={(event) => onPreferencesChange({ ...preferences, ui: { ...preferences.ui, inspector_open: event.target.checked } })}
          type="checkbox"
        />
        <span><strong>Show Inspector</strong><small>Keep selection properties visible on the right side of the canvas.</small></span>
      </label>
      <label className="preference-toggle">
        <input
          checked={preferences.ui.timing_overlay_visible}
          onChange={(event) => onPreferencesChange({ ...preferences, ui: { ...preferences.ui, timing_overlay_visible: event.target.checked } })}
          type="checkbox"
        />
        <span><strong>Show timing overlay</strong><small>Show cycle edges and latency annotations on the interactive canvas.</small></span>
      </label>
    </section>

    {circuitActionGroups.map((group) => <section className="action-settings__group" key={group}>
      <h3>{group}</h3>
      <div className="action-settings__table" role="table" aria-label={`${group} action bindings`}>
        <div className="action-settings__row action-settings__row--heading" role="row">
          <span role="columnheader">Action</span>
          <span role="columnheader">Keyboard</span>
          <span role="columnheader">Mouse</span>
        </div>
        {circuitActionDefinitions.filter((action) => action.group === group).map((action) => <div className="action-settings__row" role="row" key={action.id}>
          <div className="action-settings__action" role="cell">
            <strong>{action.label}</strong>
            <small>{action.description}</small>
          </div>
          <div className="keyboard-binding" role="cell">
            <button
              type="button"
              aria-label={`${action.label} keyboard shortcut`}
              title="Focus, then press the new shortcut"
              onKeyDown={(event) => recordKeyboard(action.id, action.label, event)}
            >{formatKeyboardShortcut(bindings[action.id].keyboard)}</button>
            <button
              className="keyboard-binding__clear"
              type="button"
              aria-label={`Remove keyboard binding for ${action.label}`}
              disabled={!bindings[action.id].keyboard}
              onClick={() => clearKeyboard(action.id, action.label)}
            >×</button>
          </div>
          <label className="mouse-binding" role="cell">
            <span className="sr-only">{action.label} mouse shortcut</span>
            <select
              aria-label={`${action.label} mouse shortcut`}
              value={bindings[action.id].mouse}
              onChange={(event) => changeMouse(action.id, action.label, event.target.value as MouseShortcut)}
            >
              {action.mouseOptions.map((mouse) => <option key={mouse} value={mouse}>{mouseShortcutLabels[mouse]}</option>)}
            </select>
          </label>
        </div>)}
      </div>
    </section>)}
  </section>;
}

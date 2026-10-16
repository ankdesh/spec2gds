import { useEffect, useRef } from "react";
import { SPEC_EDITOR_THEMES, type SpecEditorThemeId } from "./preferences";

interface PreferencesDialogProps {
  currentThemeId: SpecEditorThemeId;
  onThemeChange: (themeId: SpecEditorThemeId) => void;
  onClose: () => void;
  restoreFocusId?: string;
}

export function PreferencesDialog({
  currentThemeId,
  onThemeChange,
  onClose,
  restoreFocusId,
}: PreferencesDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const menuTrigger = previousFocus?.closest(".editor-menu")?.querySelector<HTMLElement>(":scope > button");

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled), [tabindex]:not([tabindex='-1'])",
        ) ?? [],
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    requestAnimationFrame(() => {
      const preferred = dialogRef.current?.querySelector<HTMLElement>(
        "[autofocus], .preferences-theme-card--selected, button, input",
      );
      preferred?.focus();
    });
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (previousFocus?.isConnected && previousFocus !== document.body && previousFocus.getClientRects().length) {
        previousFocus.focus();
      } else if (restoreFocusId && document.getElementById(restoreFocusId)) {
        document.getElementById(restoreFocusId)?.focus();
      } else if (menuTrigger?.isConnected) {
        menuTrigger.focus();
      }
    };
  }, [restoreFocusId]);

  return (
    <div className="editor-dialog-backdrop" onMouseDown={onClose} role="presentation">
      <section
        aria-labelledby="preferences-dialog-title"
        aria-modal="true"
        className="editor-dialog preferences-dialog"
        onMouseDown={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
      >
        <header>
          <div>
            <p className="utility-kicker">User Preferences</p>
            <h2 id="preferences-dialog-title">Preferences</h2>
          </div>
          <button aria-label="Close" className="icon-button" onClick={onClose} type="button">
            ×
          </button>
        </header>

        <div className="preferences-dialog__content">
          <section className="preferences-section">
            <header className="preferences-section__header">
              <h3>Appearance & Theme</h3>
              <p>Choose your visual presentation profile. Themes apply instantly and persist across sessions.</p>
            </header>

            <div className="preferences-theme-grid" role="radiogroup" aria-label="Theme profiles">
              {SPEC_EDITOR_THEMES.map((theme) => {
                const isSelected = theme.id === currentThemeId;
                return (
                  <button
                    aria-checked={isSelected}
                    className={`preferences-theme-card${isSelected ? " preferences-theme-card--selected" : ""}`}
                    key={theme.id}
                    onClick={() => onThemeChange(theme.id)}
                    role="radio"
                    type="button"
                  >
                    <div className="preferences-theme-card__preview">
                      <div
                        className="preferences-theme-card__swatch-canvas"
                        style={{ background: theme.canvasColor }}
                      >
                        <div
                          className="preferences-theme-card__swatch-paper"
                          style={{
                            background: theme.paperColor,
                            borderColor: theme.colorScheme === "dark" ? "#27272a" : "#d8dedd",
                          }}
                        >
                          <div
                            className="preferences-theme-card__swatch-accent"
                            style={{ background: theme.accentColor }}
                          />
                        </div>
                      </div>
                    </div>
                    <div className="preferences-theme-card__info">
                      <div className="preferences-theme-card__title">
                        <span>{theme.icon}</span>
                        <strong>{theme.label}</strong>
                        {isSelected && <span className="preferences-theme-card__badge">Active</span>}
                      </div>
                      <p>{theme.description}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        </div>

        <footer>
          <button className="primary" onClick={onClose} type="button">
            Done
          </button>
        </footer>
      </section>
    </div>
  );
}

export default PreferencesDialog;

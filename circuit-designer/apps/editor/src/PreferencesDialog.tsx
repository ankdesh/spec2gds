import { useEffect, useRef } from "react";
import { SPEC_EDITOR_THEMES, type SpecEditorThemeId } from "./preferences";

interface PreferencesDialogProps {
  currentThemeId: SpecEditorThemeId;
  onThemeChange: (themeId: SpecEditorThemeId) => void;
  onClose: () => void;
}

export function PreferencesDialog({
  currentThemeId,
  onThemeChange,
  onClose,
}: PreferencesDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    dialogRef.current?.querySelector<HTMLElement>("button, input")?.focus();
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

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

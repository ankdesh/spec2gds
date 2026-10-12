/** Extensible user preferences and theme profiles for Spec Editor.
 * Persisted in browser localStorage independently of Circuit Designer.
 */

export type SpecEditorThemeId = "clean" | "obsidian" | string;

export interface SpecEditorThemeDefinition {
  id: SpecEditorThemeId;
  label: string;
  description: string;
  colorScheme: "light" | "dark";
  accentColor: string;
  canvasColor: string;
  paperColor: string;
  icon: string;
}

export const SPEC_EDITOR_THEMES: SpecEditorThemeDefinition[] = [
  {
    id: "obsidian",
    label: "Obsidian (Dark)",
    description: "Modern dark dashboard aesthetic with violet accents and electric blue outlines.",
    colorScheme: "dark",
    accentColor: "#8b5cf6",
    canvasColor: "#0d0d0f",
    paperColor: "#121316",
    icon: "🌙",
  },
  {
    id: "clean",
    label: "Clean (Light)",
    description: "Crisp parchment and slate aesthetic with deep teal accents and high contrast text.",
    colorScheme: "light",
    accentColor: "#246b5a",
    canvasColor: "#f3f5f4",
    paperColor: "#ffffff",
    icon: "☀️",
  },
];

export const DEFAULT_SPEC_EDITOR_THEME_ID: SpecEditorThemeId = "obsidian";

const PREFERENCES_STORAGE_KEY = "spec2gds:spec-editor:preferences";

export interface SpecEditorPreferences {
  schema_version: 1;
  theme_id: SpecEditorThemeId;
}

export function getSpecEditorTheme(themeId?: string): SpecEditorThemeDefinition {
  const found = SPEC_EDITOR_THEMES.find((item) => item.id === themeId);
  return found ?? SPEC_EDITOR_THEMES[0];
}

export function loadSpecEditorPreferences(): SpecEditorPreferences {
  try {
    const raw = typeof window !== "undefined" ? window.localStorage.getItem(PREFERENCES_STORAGE_KEY) : null;
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<SpecEditorPreferences>;
      if (parsed && typeof parsed === "object" && typeof parsed.theme_id === "string") {
        return {
          schema_version: 1,
          theme_id: parsed.theme_id,
        };
      }
    }
  } catch {
    // Ignore storage errors and fall back to default
  }
  return {
    schema_version: 1,
    theme_id: DEFAULT_SPEC_EDITOR_THEME_ID,
  };
}

export function saveSpecEditorPreferences(preferences: SpecEditorPreferences): void {
  try {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
    }
  } catch {
    // Ignore storage quota/permission errors
  }
}

export function applySpecEditorTheme(themeId: string): void {
  if (typeof document === "undefined") return;
  const theme = getSpecEditorTheme(themeId);
  document.documentElement.setAttribute("data-theme", theme.id);

  let meta = document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]');
  if (!meta) {
    meta = document.createElement("meta");
    meta.name = "color-scheme";
    document.head.appendChild(meta);
  }
  meta.content = theme.colorScheme;
}

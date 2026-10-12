/** Semantic visual tokens shared by the interactive canvas and deterministic exports. */
export interface CircuitThemeDefinition {
  id: string;
  label?: string;
  description?: string;
  color_scheme: "light" | "dark";
  colors: {
    chrome: string;
    chrome_foreground: string;
    canvas: string;
    surface: string;
    surface_subtle: string;
    text: string;
    text_muted: string;
    border: string;
    border_strong: string;
    primary: string;
    primary_foreground: string;
    net: string;
    warning: string;
    warning_surface: string;
    success: string;
    success_surface: string;
    danger: string;
    danger_surface: string;
    focus: string;
    grid: string;
  };
}

/** Default professional profile: dark precision chrome around a printable light canvas. */
export const blueprintSlateTheme: CircuitThemeDefinition = {
  id: "blueprint-slate",
  label: "Blueprint Slate (Clean Light)",
  description: "Dark precision chrome framing a clean light engineering canvas.",
  color_scheme: "light",
  colors: {
    chrome: "#081f33",
    chrome_foreground: "#f7fafc",
    canvas: "#f7f9fc",
    surface: "#ffffff",
    surface_subtle: "#edf3f7",
    text: "#102a43",
    text_muted: "#60758a",
    border: "#b8c6d1",
    border_strong: "#7b8fa1",
    primary: "#007c89",
    primary_foreground: "#ffffff",
    net: "#1d64c8",
    warning: "#9a5d00",
    warning_surface: "#fff4da",
    success: "#12805c",
    success_surface: "#e7f7f1",
    danger: "#c43d4e",
    danger_surface: "#fff0f2",
    focus: "#3aaed8",
    grid: "#b9c9d6",
  },
};

/** Modern dark dashboard profile: obsidian canvas with neon purple and electric blue accents. */
export const obsidianTheme: CircuitThemeDefinition = {
  id: "obsidian",
  label: "Obsidian (Dark Canvas)",
  description: "Modern dark canvas with glowing electric nets and neon accents.",
  color_scheme: "dark",
  colors: {
    chrome: "#0d0d0f",
    chrome_foreground: "#f4f4f5",
    canvas: "#09090b",
    surface: "#18181b",
    surface_subtle: "#141416",
    text: "#f4f4f5",
    text_muted: "#a1a1aa",
    border: "#27272a",
    border_strong: "#3f3f46",
    primary: "#8b5cf6",
    primary_foreground: "#ffffff",
    net: "#38bdf8",
    warning: "#fb923c",
    warning_surface: "rgba(249, 115, 22, 0.15)",
    success: "#10b981",
    success_surface: "rgba(16, 185, 129, 0.15)",
    danger: "#ef4444",
    danger_surface: "rgba(239, 68, 68, 0.15)",
    focus: "#3b82f6",
    grid: "#222226",
  },
};

/** Extensible registry of Circuit Designer theme profiles. */
export const circuitThemes: Record<string, CircuitThemeDefinition> = {
  "blueprint-slate": blueprintSlateTheme,
  obsidian: obsidianTheme,
};

/** Resolves a theme profile by ID with fallback to the default light blueprint profile. */
export function getCircuitTheme(id?: string): CircuitThemeDefinition {
  return (id && circuitThemes[id]) || blueprintSlateTheme;
}

/** CSS properties intentionally scoped to a Circuit Designer host element. */
export function circuitThemeCssProperties(theme: CircuitThemeDefinition): Record<`--cd-${string}`, string> {
  return Object.fromEntries(Object.entries(theme.colors).map(([name, value]) => [
    `--cd-${name.replaceAll("_", "-")}`,
    value,
  ])) as Record<`--cd-${string}`, string>;
}


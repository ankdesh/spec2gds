/** Semantic visual tokens shared by the interactive canvas and deterministic exports. */
export interface CircuitThemeDefinition {
  id: string;
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

/** CSS properties intentionally scoped to a Circuit Designer host element. */
export function circuitThemeCssProperties(theme: CircuitThemeDefinition): Record<`--cd-${string}`, string> {
  return Object.fromEntries(Object.entries(theme.colors).map(([name, value]) => [
    `--cd-${name.replaceAll("_", "-")}`,
    value,
  ])) as Record<`--cd-${string}`, string>;
}

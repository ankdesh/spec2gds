import type { NetEndpoint } from "@spec2gds/circuit-core";

/** A complete numeric selection is a whole terminal, independent of its HDL shape. */
export function connectionEndpoint(key: string, lsb: number, width: number, terminalWidth?: number | string): NetEndpoint {
  const whole = lsb === 0 && typeof terminalWidth === "number" && width === terminalWidth;
  const slice = width > 0 && !whole ? { slice: { lsb, width } } : {};
  if (key.startsWith("boundary:")) return { kind: "boundary", terminal_id: key.slice(9), ...slice };
  const separator = key.indexOf(":");
  return { kind: "instance", instance_id: key.slice(0, separator), terminal_id: key.slice(separator + 1), ...slice };
}

export function connectionSelectionLabel(label: string, terminalWidth: number | string | undefined, lsb: number, width: number): string {
  if (width === 0 || (lsb === 0 && terminalWidth === width)) return label;
  return width === 1 ? `${label}[${lsb}]` : `${label}[${lsb + width - 1}:${lsb}]`;
}

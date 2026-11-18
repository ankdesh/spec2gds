import { planConnection, type CircuitDocument, type NetEndpoint } from "@spec2gds/circuit-core";

export interface ConnectionPort { id: string; label?: string; width?: number | string; direction?: string }

/** Preview the same constraints used on commit. This never changes the document. */
export function connectionIssue(document: CircuitDocument | undefined, ports: ConnectionPort[], from: string, to: string,
  lsb: number, lsbB: number, width: number, existingNetId?: string): string | undefined {
  if (!document || !to || (existingNetId === undefined && !from)) return;
  if (existingNetId === "") return "Choose an existing net.";
  if (![lsb, lsbB, width].every(Number.isInteger) || Math.min(lsb, lsbB, width) < 0) return "Use whole numbers of zero or more for offsets and width.";
  if (!width && (lsb || lsbB)) return "Enter a positive width when selecting bits.";
  const a = ports.find(port => port.id === from);
  const b = ports.find(port => port.id === to);
  const first = document.design.nets.find(net => net.id === existingNetId)?.endpoints[0];
  const sourceWidth = existingNetId ? first?.slice?.width ?? ports.find(port => first && (first.kind === "boundary" ? `boundary:${first.terminal_id}` : `${first.instance_id}:${first.terminal_id}`) === port.id)?.width : a?.width;
  if (!width && typeof sourceWidth === "number" && typeof b?.width === "number" && sourceWidth !== b.width) {
    const bits = (value: number) => `${value} ${value === 1 ? "bit" : "bits"}`;
    return `Port widths differ: ${bits(sourceWidth)} → ${bits(b.width)}. Choose a matching port, or use Advanced to select bits.`;
  }
  if (from === to && existingNetId === undefined) return "Choose two different ports.";
  const endpoint = (key: string, offset: number) => connectionEndpoint(key, offset, width, ports.find(port => port.id === key)?.width);
  try {
    let id = "connection_preview";
    while (document.design.nets.some(net => net.id === id)) id += "_";
    planConnection(document, existingNetId ? [endpoint(to, lsbB)] : [endpoint(from, lsb), endpoint(to, lsbB)], {
      operationId: "preview", netId: id, label: "Connection", existingNetId,
    });
  } catch (error) { return error instanceof Error ? error.message : String(error); }
}

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

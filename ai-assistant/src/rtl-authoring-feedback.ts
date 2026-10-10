/** Give concrete sizing syntax for actual compiler diagnostics. Never rewrite RTL. */
import { isRecord } from "./types.js";

export function rtlSizingFeedback(diagnostics: unknown, artifact: unknown): string {
  if (!Array.isArray(diagnostics)) return "";
  const messages = diagnostics.filter((item): item is string => typeof item === "string");
  const widths = [...new Set(messages.flatMap(message => {
    const match = /expects (\d+) bits/.exec(message);
    const width = match ? Number(match[1]) : 0;
    return Number.isSafeInteger(width) && width > 0 && width <= 65536 ? [width] : [];
  }))].slice(0, 3);
  if (!widths.length) return "";
  const operations = isRecord(artifact) && Array.isArray(artifact.operations) ? artifact.operations : [];
  const inputs = operations.flatMap(operation => isRecord(operation) && operation.type === "create_entity" && Array.isArray(operation.ports)
    ? operation.ports.filter(port => isRecord(port) && port.direction === "in" && typeof port.name === "string" && /^[A-Za-z_][A-Za-z0-9_]*$/.test(port.name)) : []);
  const names = [...new Set(inputs.map(port => String(port.name)))].slice(0, 8);
  return widths.map(width => `Compiler sizing target: ${width} bits. Use a SystemVerilog sized cast such as ${width}'(operand) before the reported operation. ${names.length ? `For the stored input ports, concrete casts are ${names.map(name => `${width}'(${name})`).join(", ")}.` : ""} Keep the approved ports unchanged; author the corrected RTL body and submit a new proposal.`).join("\n");
}

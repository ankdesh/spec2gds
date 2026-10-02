/** Public labels and filenames never supply document authority or hardware IDs. */
import type { CircuitDocument, NetEndpoint } from "./types.generated";
import { CASE_FOLD } from "./name-casefold";

export function cleanHumanName(value: string): string {
  const name = value.normalize("NFKC").replace(/[\s\u0085\u001c-\u001f]+/g, " ").trim();
  if (!name || Array.from(name).length > 200) throw new Error("Name must contain 1 to 200 characters.");
  return name;
}

export function humanNameKey(value: string): string {
  return Array.from(cleanHumanName(value), character => CASE_FOLD[character] ?? character.toLowerCase()).join("");
}

export function availableHumanName(value: string, existing: string[]): string {
  const name = cleanHumanName(value), used = new Set(existing.map(humanNameKey));
  let candidate = name, number = 2;
  while (used.has(humanNameKey(candidate))) {
    const suffix = ` ${number++}`;
    candidate = `${Array.from(name).slice(0, 200 - suffix.length).join("").trimEnd()}${suffix}`;
  }
  return candidate;
}

export function publicFilenameStem(value: string, fallback = "document"): string {
  let stem = value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Za-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80).replace(/-+$/g, "").toLowerCase() || fallback;
  if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i.test(stem)) stem = `${fallback}-${stem}`;
  return stem;
}

export function circuitTerminalLabel(document: CircuitDocument, terminalKey: string): string {
  if (terminalKey.startsWith("boundary:")) {
    const terminal = document.design.boundary_terminals.find(item => item.id === terminalKey.slice(9));
    return terminal ? `Boundary · ${terminal.label}` : "Unavailable boundary port";
  }
  const colon = terminalKey.indexOf(":");
  const instance = document.design.instances.find(item => item.id === terminalKey.slice(0, colon));
  const component = document.components.find(item => item.id === instance?.component_id);
  const terminal = component?.terminals.find(item => item.id === terminalKey.slice(colon + 1));
  return instance && terminal ? `${instance.label}.${terminal.label}` : "Unavailable port";
}

export function circuitEndpointLabel(document: CircuitDocument, endpoint: NetEndpoint): string {
  const key = endpoint.kind === "instance" ? `${endpoint.instance_id}:${endpoint.terminal_id}` : `boundary:${endpoint.terminal_id}`;
  const slice = endpoint.slice ? ` [${endpoint.slice.lsb + endpoint.slice.width - 1}:${endpoint.slice.lsb}]` : "";
  return circuitTerminalLabel(document, key) + slice;
}

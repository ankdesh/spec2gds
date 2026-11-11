/** Convert saved table cells into a private port draft without changing source IDs. */
import type { ComponentPortInput, DocumentTable, TransactionalPortKind } from "@spec2gds/document-core";

export function rowText(row: DocumentTable["rows"][number], key: string): string {
  const value = row.cells[key]?.value;
  return value === null || value === undefined ? "" : String(value);
}

export function portInputFromRow(row: DocumentTable["rows"][number]): ComponentPortInput {
  const name = rowText(row, "name");
  const description = rowText(row, "description");
  const family = rowText(row, "family") as ComponentPortInput["family"];
  if (family === "transactional") {
    return { name, family, description,
      initiative: rowText(row, "initiative") as Extract<ComponentPortInput, { family: "transactional" }>["initiative"],
      kind: (rowText(row, "transaction_kind") || null) as TransactionalPortKind | null,
      custom_kind: rowText(row, "custom_kind") || null,
      bus_width: rowText(row, "bus_width") || null };
  }
  if (family === "structured") {
    return { name, family, description,
      direction: rowText(row, "direction") as Extract<ComponentPortInput, { family: "structured" }>["direction"] };
  }
  return { name, family: "wire", description,
    direction: rowText(row, "direction") as Extract<ComponentPortInput, { family: "wire" }>["direction"],
    range: rowText(row, "range") || null };
}

export const WIRE_RANGE_GUIDANCE = "Use left:right, for example 15:0 or WIDTH-1:0. Leave blank for a scalar port.";

/** Check explicit bounds without compiling or evaluating constant expressions. */
export function wireRangeError(source: string): string | null {
  if (!source.trim()) return null;
  const value = source.trim().replace(/^\[([\s\S]*)\]$/, "$1");
  const stack: string[] = [];
  let conditional = 0, separator = -1;
  const error = `Range must use a left:right expression pair. ${WIRE_RANGE_GUIDANCE}`;
  for (const scope of value.matchAll(/::/g)) {
    if (!/[A-Za-z_$][\w$]*\s*$/.test(value.slice(0, scope.index)) || !/^\s*[A-Za-z_$]/.test(value.slice(scope.index + 2))) return error;
  }
  for (let index = 0; index < value.length; index++) {
    const character = value[index];
    if ("([{".includes(character)) stack.push(character);
    else if (")]}".includes(character)) {
      if (stack.pop() !== "([{"[")]}".indexOf(character)]) return error;
    } else if (!stack.length && character === "?") conditional++;
    else if (!stack.length && character === ":") {
      if (value[index + 1] === ":") {
        if (!/[A-Za-z_$][\w$]*\s*$/.test(value.slice(0, index)) || !/^\s*[A-Za-z_$]/.test(value.slice(index + 2))) return error;
        index++;
      } else if (conditional) conditional--;
      else if (separator !== -1) return error;
      else separator = index;
    }
  }
  if (stack.length || conditional || separator === -1 || !value.slice(0, separator).trim() || !value.slice(separator + 1).trim()) return error;
  return null;
}

export function normalizeWireRange(source: string): string | null {
  return source.trim().replace(/^\[([\s\S]*)\]$/, "$1").trim() || null;
}

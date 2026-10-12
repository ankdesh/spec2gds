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

/** Check range delimiters without restricting valid constant-expression formulas. */
export function wireRangeError(source: string): string | null {
  const value = source.trim().replace(/^\[(.*)\]$/, "$1");
  let depth = 0, conditional = 0, separator = -1;
  const error = "Range must use a left:right expression pair with balanced delimiters.";
  for (let index = 0; index < value.length; index++) {
    const character = value[index];
    if ("([{".includes(character)) depth++;
    else if (")]}".includes(character)) depth--;
    else if (!depth && character === "?") conditional++;
    else if (!depth && character === ":") {
      if (value[index + 1] === ":") {
        if (!/[A-Za-z_$][\w$]*\s*$/.test(value.slice(0, index)) || !/^\s*[A-Za-z_$]/.test(value.slice(index + 2))) return error;
        index++;
      } else if (conditional) conditional--;
      else if (separator !== -1) return error;
      else separator = index;
    }
    if (depth < 0) return error;
  }
  if (depth || conditional || separator !== -1 && (!value.slice(0, separator).trim() || !value.slice(separator + 1).trim())) return error;
  return null;
}

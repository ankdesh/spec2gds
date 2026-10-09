/** Convert saved table cells into a private port draft without changing source IDs. */
import type { ComponentPortInput, DocumentTable, TransactionalPortKind } from "@spec2gds/document-core";

export function rowText(row: DocumentTable["rows"][number], key: string): string {
  const value = row.cells[key]?.value;
  return value === null || value === undefined ? "" : String(value);
}

export function portInputFromRow(row: DocumentTable["rows"][number]): ComponentPortInput {
  const name = rowText(row, "name");
  const display_name = rowText(row, "display_name");
  const description = rowText(row, "description");
  const family = rowText(row, "family") as ComponentPortInput["family"];
  if (family === "transactional") {
    return { name, family, display_name, description,
      initiative: rowText(row, "initiative") as Extract<ComponentPortInput, { family: "transactional" }>["initiative"],
      kind: (rowText(row, "transaction_kind") || null) as TransactionalPortKind | null,
      custom_kind: rowText(row, "custom_kind") || null,
      bus_width: rowText(row, "bus_width") || null };
  }
  if (family === "structured") {
    return { name, family, display_name, description,
      direction: rowText(row, "direction") as Extract<ComponentPortInput, { family: "structured" }>["direction"] };
  }
  return { name, family: "wire", display_name, description,
    direction: rowText(row, "direction") as Extract<ComponentPortInput, { family: "wire" }>["direction"],
    range: rowText(row, "range") || null };
}

import type { WirePortInput } from "@spec2gds/document-core";
import { wireRangeError } from "./port-input";

export type PastedPort = { port: WirePortInput; errors: string[] };
const clean = (text: string) => text.trim().replace(/^`(.*)`$/, "$1");
const header = (text: string) => clean(text).toLowerCase().replace(/[^a-z]/g, "");

export function parsePortRows(source: string, existing: string[] = []): PastedPort[] {
  const lines = source.split(/\r?\n/).filter(line => line.trim());
  const markdown = Boolean(lines[0] && !lines[0].includes("\t") && lines[0].includes("|"));
  const rows = lines.map(line => markdown
    ? line.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map(value => value.replace(/\\\|/g, "|"))
    : line.split("\t"));
  if (!rows.length) return [];
  let columns = ["id", "direction", "range", "description"];
  if (["id", "portid", "name"].includes(header(rows[0][0]))) {
    columns = rows.shift()!.map(value => {
      const key = header(value);
      return ["portid", "name"].includes(key) ? "id" : key.startsWith("range") ? "range" : key;
    });
  }
  const used = new Set(existing);
  return rows.filter(row => !row.every(value => /^\s*:?-+:?\s*$/.test(value))).map(row => {
    const get = (key: string) => {
      const index = columns.indexOf(key);
      return index < 0 || index >= row.length ? undefined : clean(row[index]);
    };
    const name = get("id") ?? "";
    const direction = get("direction") || "in";
    const rawRange = get("range");
    const range = rawRange === undefined ? "0:0" : /^(leave blank.*|scalar)$/i.test(rawRange) ? "" : rawRange;
    const errors: string[] = [];
    if (!/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(name)) errors.push("Enter a valid Port ID.");
    if (used.has(name)) errors.push(`Port ${name} already exists.`);
    used.add(name);
    if (!["in", "out", "inout"].includes(direction)) errors.push("Direction must be in, out, or inout.");
    const rangeError = wireRangeError(range);
    if (rangeError) errors.push(rangeError);
    return { port: { name, family: "wire", direction: direction as WirePortInput["direction"], range: range || null, description: get("description") || "" }, errors };
  });
}

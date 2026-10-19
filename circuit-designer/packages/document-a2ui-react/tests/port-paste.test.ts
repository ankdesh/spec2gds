import { describe, expect, it } from "vitest";
import { parsePortRows } from "../src/port-paste";

describe("port row authoring", () => {
  it("distinguishes omitted ranges from explicit scalars", () => {
    expect(parsePortRows("a\tin")[0].port.range).toBe("0:0");
    expect(parsePortRows("clk\tin\t\tClock")[0].port.range).toBeNull();
    expect(parsePortRows("Port ID\tDescription\na\tInput")[0].port).toMatchObject({ direction: "in", range: "0:0" });
  });
  it("accepts the canonical Markdown input pack and ignores informational Bits", () => {
    const rows = parsePortRows("| Port ID | Direction | Range to enter | Bits | Description |\n| --- | --- | --- | ---: | --- |\n| `a` | `in` | `N-1:0` | N | First operand. |\n| `cin` | `in` | leave blank (scalar) | 1 | Carry. |");
    expect(rows).toHaveLength(2);
    expect(rows[0].port).toMatchObject({ name: "a", range: "N-1:0", description: "First operand." });
    expect(rows[1].port.range).toBeNull();
    expect(rows.flatMap(row => row.errors)).toEqual([]);
  });
  it("reports every duplicate, invalid direction and invalid range without dropping rows", () => {
    const rows = parsePortRows("a\tin\t31:0\nnew\tbad\t31::0\nnew\tout\t0:0", ["a"]);
    expect(rows).toHaveLength(3);
    expect(rows.every(row => row.errors.length > 0)).toBe(true);
    expect(rows[1].errors).toHaveLength(2);
  });
  it("accepts Markdown without outside pipes and retains escaped description pipes", () => {
    const rows = parsePortRows("ID | Direction | Range | Description\n--- | --- | --- | ---\na | in | 7:0 | Valid \\| ready");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ port: { name: "a", range: "7:0", description: "Valid | ready" }, errors: [] });
  });
});

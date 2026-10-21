import { expect, test } from "vitest";
import { connectionEndpoint, connectionSelectionLabel } from "./connection-input";

test("maps a scalar to an independently selected high bus bit", () => {
  expect(connectionEndpoint("boundary:cin", 0, 1, 1)).toEqual({ kind: "boundary", terminal_id: "cin" });
  expect(connectionEndpoint("reg:din", 64, 1, 65)).toEqual({ kind: "instance", instance_id: "reg", terminal_id: "din", slice: { lsb: 64, width: 1 } });
  expect(connectionSelectionLabel("cin", 1, 0, 1)).toBe("cin");
  expect(connectionSelectionLabel("din", 65, 64, 1)).toBe("din[64]");
});

test("keeps partial and symbolic selections and recognises whole numeric ports", () => {
  expect(connectionEndpoint("reg:din", 0, 8, 8)).not.toHaveProperty("slice");
  expect(connectionEndpoint("reg:din", 8, 8, 16)).toHaveProperty("slice", { lsb: 8, width: 8 });
  expect(connectionSelectionLabel("din", 16, 8, 8)).toBe("din[15:8]");
  expect(connectionEndpoint("reg:din", 0, 8, "[N-1:0]")).toHaveProperty("slice", { lsb: 0, width: 8 });
  expect(connectionEndpoint("reg:din", 1, 1, 1)).toHaveProperty("slice", { lsb: 1, width: 1 });
});

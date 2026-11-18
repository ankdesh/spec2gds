import { expect, test } from "vitest";
import { simpleDocumentFixture, projectDocument } from "@spec2gds/circuit-core";
import { connectionEndpoint, connectionSelectionLabel, connectionIssue } from "./connection-input";

test("maps a scalar to an independently selected high bus bit", () => {
  expect(connectionEndpoint("boundary:cin", 0, 1, 1)).toEqual({ kind: "boundary", terminal_id: "cin" });
  expect(connectionEndpoint("reg:din", 64, 1, 65)).toEqual({ kind: "instance", instance_id: "reg", terminal_id: "din", slice: { lsb: 64, width: 1 } });
  expect(connectionSelectionLabel("cin", 1, 0, 1)).toBe("cin");
  expect(connectionSelectionLabel("din", 65, 64, 1)).toBe("din[64]");
});

test("prevents mismatched whole ports and out-of-range slices before submission", () => {
  const document = simpleDocumentFixture();
  document.design.nets = [];
  document.design.boundary_terminals = [{ id: "cin", label: "cin", direction: "input", width: 1, category: "port" }];
  document.components[1].terminals[0].width = 65;
  const ports = projectDocument(document, "1").terminals;
  const before = structuredClone(document);
  expect(connectionIssue(document, ports, "boundary:cin", "consumer_0:data", 0, 0, 0)).toContain("1 bit → 65 bits");
  expect(connectionIssue(document, ports, "boundary:cin", "consumer_0:data", 0, 64, 2)).toMatch(/range|width|slice/i);
  expect(connectionIssue(document, ports, "boundary:cin", "consumer_0:data", 0, 64, 1)).toBeUndefined();
  expect(connectionIssue(document, ports, "boundary:cin", "consumer_0:data", 0, 64, 0)).toContain("positive width");
  expect(document).toEqual(before);
});

test("uses the connection planner for driver and existing-net constraints", () => {
  const document = simpleDocumentFixture();
  const ports = projectDocument(document, "1").terminals;
  expect(connectionIssue(document, ports, "producer_0:data", "consumer_0:data", 0, 0, 0)).toBeUndefined();
  document.design.instances.push({ ...document.design.instances[0], id: "other_source", label: "Other source" });
  const expanded = projectDocument(document, "1").terminals;
  expect(connectionIssue(document, expanded, "producer_0:data", "other_source:data", 0, 0, 0)).toMatch(/source|driver/i);
  expect(connectionIssue(document, expanded, "", "consumer_0:data", 0, 0, 0, "")).toBe("Choose an existing net.");
  expect(connectionIssue(document, expanded, "producer_0:data", "consumer_0:data", -1, 0, 1)).toContain("whole numbers");
});

test("keeps partial and symbolic selections and recognises whole numeric ports", () => {
  expect(connectionEndpoint("reg:din", 0, 8, 8)).not.toHaveProperty("slice");
  expect(connectionEndpoint("reg:din", 8, 8, 16)).toHaveProperty("slice", { lsb: 8, width: 8 });
  expect(connectionSelectionLabel("din", 16, 8, 8)).toBe("din[15:8]");
  expect(connectionEndpoint("reg:din", 0, 8, "[N-1:0]")).toHaveProperty("slice", { lsb: 0, width: 8 });
  expect(connectionEndpoint("reg:din", 1, 1, 1)).toHaveProperty("slice", { lsb: 1, width: 1 });
});

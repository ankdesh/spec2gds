import { expect, test } from "vitest";
import { analyzeCircuitTiming, simpleDocumentFixture } from "@spec2gds/circuit-core";
import { timingPathEndpoints } from "./timing-presentation";

test("resolves exact source and repeated target ports without changing timing results", () => {
  const document = simpleDocumentFixture();
  document.components[0].terminals.push({ ...document.components[0].terminals[0], id: "feedback", label: "feedback", direction: "input" });
  document.components[1].terminals.push({ ...document.components[1].terminals[0], id: "second", label: "second" });
  document.design.nets[0].endpoints.unshift({ kind: "instance", instance_id: "producer_0", terminal_id: "feedback" });
  document.design.nets[0].endpoints.push({ kind: "instance", instance_id: "consumer_0", terminal_id: "second" });
  const before = structuredClone(document);
  const { paths } = analyzeCircuitTiming(document);
  expect(paths).toHaveLength(2);
  expect(timingPathEndpoints(document, paths, 0).source?.terminal_id).toBe("data");
  expect(timingPathEndpoints(document, paths, 0).target?.terminal_id).toBe("data");
  expect(timingPathEndpoints(document, paths, 1).target?.terminal_id).toBe("second");
  expect(document).toEqual(before);
});

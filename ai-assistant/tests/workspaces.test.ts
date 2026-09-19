import assert from "node:assert/strict";
import test from "node:test";
import { workspaceDescriptor } from "../src/workspaces.js";

test("source-derived Circuits share their source Spec workspace", () => {
  const spec = workspaceDescriptor("/tmp/product", {
    domain: "spec", serviceBaseUrl: "http://spec.test", documentId: "soc", scope: "document",
  }, "http://spec.test", { document_id: "soc" });
  const circuit = workspaceDescriptor("/tmp/product", {
    domain: "circuit", serviceBaseUrl: "http://circuit.test/api/circuit-designer/v1",
    documentId: "soc-top", scope: "document",
  }, "http://circuit.test/api/circuit-designer/v1", { document: { label: "SoC top" } }, {
    source_service_url: "http://spec.test", source_document_id: "soc",
  });
  assert.equal(circuit.key, spec.key);
  assert.equal(circuit.path, spec.path);
  assert.equal(circuit.domain, "spec");
  assert.equal(circuit.documentId, "soc");
});

test("independent Circuits retain an independent workspace identity", () => {
  const circuit = workspaceDescriptor("/tmp/product", {
    domain: "circuit", serviceBaseUrl: "http://circuit.test/api/circuit-designer/v1",
    documentId: "standalone", scope: "document",
  }, "http://circuit.test/api/circuit-designer/v1", { document: { label: "Standalone design" } });
  assert.equal(circuit.domain, "circuit");
  assert.equal(circuit.documentId, "standalone");
  assert.equal(circuit.title, "Standalone design");
});

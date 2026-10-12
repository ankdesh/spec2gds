import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { initialContentTemplate } from "../src/initial-content-template.js";
import { parseServiceOperationContract, validateServiceOperations } from "../src/service-operation-schema.js";
import type { SessionBinding } from "../src/types.js";

const binding = { domain: "spec", scope: "document", sessionId: "created", documentId: "adder-spec", serviceDocumentKey: "adder-key" } as SessionBinding;
const contract = parseServiceOperationContract({ schema_version: 1, digest: `sha256:${"a".repeat(64)}`,
  operation_schema: JSON.parse(readFileSync(new URL("../../spec2gds/spec/spec_format/assistant_operation_schema.json", import.meta.url), "utf8")) });

for (const width of [4, 8, 13]) test(`approved ${width}-bit leaf authoring preserves exact interfaces and leaves behavior to the model`, () => {
  const review = { status: "approved", reviewId: "approved", destinationSessionId: "created", destinationSourceRevision: "sha256:initial",
    destinationDocumentId: "adder-spec", destinationServiceDocumentKey: "adder-key",
    plan: { title: "Unsigned adder", components: [{ name: "adder" }], designs: [], assumptions: [],
      interfaces: [{ component: "adder", ports: [
        { name: "a", direction: "in", width }, { name: "b", direction: "in", width },
        { name: "cin", direction: "in", range: null, description: "Port purpose" }, { name: "sum", direction: "out", width }, { name: "cout", direction: "out", range: null, description: "Port purpose" },
      ] }] } };
  const template = initialContentTemplate(binding, review, "sha256:initial")!;
  assert.equal(template.architecture_review_id, review.reviewId);
  assert.equal(template.operations[0].ports[0].range, `${width - 1}:0`);
  assert.equal(template.operations[0].ports[2].range, undefined);
  assert.equal(template.operations[0].systemverilog, "");
  assert.equal(template.operations[1].description, "");
  assert.equal(template.operations[0].entity_id, template.operations[1].entity.entity_id);
  assert.doesNotThrow(() => validateServiceOperations(contract, template.operations));
  assert.equal(initialContentTemplate(binding, review, "sha256:changed"), null);
  assert.equal(initialContentTemplate(binding, { ...review, status: "pending" }, "sha256:initial"), null);
  assert.equal(initialContentTemplate(binding, { ...review, destinationServiceDocumentKey: "other-key" }, "sha256:initial"), null);
  assert.equal(initialContentTemplate({ ...binding, scope: "entity" }, review, "sha256:initial"), null);
  assert.equal(initialContentTemplate({ ...binding, domain: "circuit" }, review, "sha256:initial"), null);
});

import { describe, expect, it } from "vitest";

import {
  PERSISTED_ENTITY_SECTION_TYPES,
  SPEC_DOCUMENT_CATALOG_ID,
} from "../src/entity-section-registry";

describe("entity section renderer registry", () => {
  it("has a renderer for every persisted section type in the V2 catalog", () => {
    expect(PERSISTED_ENTITY_SECTION_TYPES).toEqual(["sv"]);
    expect(SPEC_DOCUMENT_CATALOG_ID).toBe("urn:spec2gds:a2ui:document:v2");
  });
});

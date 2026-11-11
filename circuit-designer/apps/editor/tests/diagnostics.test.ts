import { describe, expect, it } from "vitest";
import type { DocumentSnapshot, EntityRef } from "@spec2gds/document-core";
import { collectFindings } from "../src/diagnostics";
import { clampPanelWidth } from "../src/UtilitySidebar";

const target: EntityRef = { document_id: "spec", entity_kind: "component", entity_id: "fifo" };
const diagnostic = { code: "WIDTH", message: "Width mismatch", line: 2, column: 1, blocking: true, file_path: "fifo.sv", source_kind: "section" as const };
function source(): DocumentSnapshot {
  return {
    owner_document_key: "bound-spec", schema_version: "v2", document_id: "spec", source_revision_hash: "current",
    components: [], designs: [], entry_designs: [], bus_definitions: [], abstraction_definitions: [], component_compositions: [],
    narrative: { title: "Spec", blocks: [] }, diagnostics: { source: [], artifacts: [] },
    entity_sections: [{ section_id: "body", parent: target, section_type: "sv", type_version: 1, title: "SystemVerilog", media_type: "text/x-systemverilog", source_path: "fifo.sv", source_sha256: "hash", content: "logic a;" }],
    section_validation: [{ section_id: "body", status: "errors", diagnostics: [diagnostic] }],
    verifications: [{ target, source_revision_hash: "current", status: "failed", tool_version: "fixture", diagnostics: [diagnostic], functional_simulation: "unverified" }],
  };
}

describe("diagnostic attention counts", () => {
  it("counts a Section and target finding once and retains its navigation location", () => {
    expect(collectFindings(source())).toMatchObject([{ code: "WIDTH", target, sectionId: "body", revision: "current" }]);
  });
  it("excludes stale verification findings and published evidence", () => {
    const snapshot = source(); snapshot.section_validation = [];
    snapshot.verifications![0].source_revision_hash = "old";
    snapshot.catalog_origins = [{ component_key: "fifo", version: "1", package_sha256: "sha", source_vlnv: "v:l:fifo:1", root: target,
      evidence: [{ evidence_sha256: "release", report: { checks: [{ kind: "lint", status: "failed", summary: "Published release" }] } }] }];
    expect(collectFindings(snapshot)).toEqual([]);
  });
  it("keeps distinct locations and source/artifact issues", () => {
    const snapshot = source();
    snapshot.verifications![0].diagnostics.push({ ...diagnostic, line: 3 });
    snapshot.diagnostics = { source: ["Invalid reference", "Invalid reference"], artifacts: ["Missing output"] };
    expect(collectFindings(snapshot)).toHaveLength(4);
  });
  it("does not map generated RTL onto a saved SystemVerilog line", () => {
    const snapshot = source(); snapshot.section_validation = [];
    snapshot.verifications![0].diagnostics = [{ ...diagnostic, source_kind: "generated" }];
    expect(collectFindings(snapshot)[0].sectionId).toBeUndefined();
  });
});

describe("dock sizing", () => {
  it("keeps at least 800 pixels for the document", () => {
    expect(clampPanelWidth(560, 1280)).toBe(480);
    expect(clampPanelWidth(999, 1440)).toBe(560);
    expect(clampPanelWidth(100, 1440)).toBe(320);
    expect(clampPanelWidth(NaN, 1440)).toBe(400);
  });
});

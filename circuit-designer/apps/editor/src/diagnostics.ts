import type { DocumentSnapshot, EntityRef, SectionDiagnostic } from "@spec2gds/document-core";

export interface Finding {
  key: string;
  message: string;
  code?: string;
  target?: EntityRef;
  sectionId?: string;
  diagnostic?: Partial<SectionDiagnostic>;
  revision: string;
  group: "target" | "source" | "artifacts";
}

/** One finding can arrive in both Section validation and a target check. */
export function collectFindings(snapshot: DocumentSnapshot | null): Finding[] {
  if (!snapshot) return [];
  const findings = new Map<string, Finding>();
  const add = (diagnostic: Partial<SectionDiagnostic> & { message: string }, target: EntityRef, sectionId?: string) => {
    const section = snapshot.entity_sections.find(item => item.section_id === sectionId)
      ?? (diagnostic.source_kind !== "generated" ? snapshot.entity_sections.find(item =>
        item.source_path === diagnostic.file_path || (item.parent.entity_id === target.entity_id && item.parent.entity_kind === target.entity_kind)) : undefined);
    const key = JSON.stringify([diagnostic.file_path || section?.source_path || `${target.entity_kind}:${target.entity_id}`,
      diagnostic.source_kind || "section", diagnostic.code, diagnostic.message, diagnostic.line ?? null, diagnostic.column ?? null]);
    if (!findings.has(key)) findings.set(key, {
      key, message: diagnostic.message, code: diagnostic.code, target: section?.parent ?? target,
      sectionId: section?.section_id, diagnostic, revision: snapshot.source_revision_hash, group: "target",
    });
  };
  for (const result of snapshot.section_validation) {
    const section = snapshot.entity_sections.find(item => item.section_id === result.section_id);
    if (section) for (const diagnostic of result.diagnostics) add(diagnostic, section.parent, section.section_id);
  }
  for (const result of snapshot.verifications ?? []) {
    if (result.status === "stale" || result.source_revision_hash !== snapshot.source_revision_hash) continue;
    for (const diagnostic of result.diagnostics) add(diagnostic, result.target);
    if (result.status === "failed" && !result.diagnostics.length) add({ message: "Lint failed. Inspect the check details." }, result.target);
  }
  for (const group of ["source", "artifacts"] as const) {
    for (const message of snapshot.diagnostics[group]) {
      const key = `${group}:${message}`;
      findings.set(key, { key, message, group, revision: snapshot.source_revision_hash });
    }
  }
  return [...findings.values()];
}

export function targetName(snapshot: DocumentSnapshot, ref: EntityRef): string {
  const entity = [...snapshot.components, ...snapshot.designs].find(item => item.ref.entity_id === ref.entity_id && item.ref.entity_kind === ref.entity_kind);
  return entity?.display_name || entity?.vlnv.split(":")[2] || ref.entity_id;
}

/** Read-only display projections. Exact artifacts and previews stay in storage. */
import { isRecord, type PresentedChange, type ProposalPresentation, type ProposalReview } from "./types.js";

export const displayLabel = (value: string): string => value.replaceAll("_", " ").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, letter => letter.toUpperCase());
const rows = (value: unknown): Record<string, unknown>[] => Array.isArray(value) ? value.filter(isRecord) : [];
const text = (value: unknown): string => typeof value === "string" ? value : "";

/** Display useful service messages, without printing diagnostic envelopes. */
export function readableDiagnostic(value: unknown, fallback = "The changes need attention."): string {
  if (isRecord(value)) {
    for (const key of ["message", "details", "detail", "reason"]) {
      if (value[key]) return readableDiagnostic(value[key], fallback);
    }
    return fallback;
  }
  if (typeof value !== "string" || !value.trim()) return fallback;
  if (/^\s*[\[{]/.test(value)) {
    try { return readableDiagnostic(JSON.parse(value), fallback); } catch { return fallback; }
  }
  return value.replace(/sha256:[\w.-]+/g, "the saved revision");
}

export function readableProposalError(error: ProposalReview["error"]): string {
  const messages: Record<string, string> = {
    STALE_REVISION: "The Spec or Circuit changed. Review the current source before retrying.",
    SERVICE_LOCKED: "The source is being edited. Try again when it is available.",
    SERVICE_UNAVAILABLE: "The service is unavailable. Try again when it is available.",
    SERVICE_CONTRACT_ERROR: "The service could not check this proposal.",
    INTERNAL_ERROR: "The proposal could not be prepared. See the developer logs for the cause.",
  };
  return error ? messages[error.error_code] ?? readableDiagnostic(error.details, "The proposal was not accepted.") : "";
}

const hiddenFields = new Set(["id", "document_id", "entity_id", "section_id", "block_id", "row_id", "cell_id", "table_id", "operation_id", "proposal_id", "session_id", "source_revision_hash", "base_source_revision_hash", "candidate_source_revision_hash", "owner_document_key", "artifactDigest", "schema_version", "type_version", "schema_path", "reference_anchor", "presence", "available_section_types", "editable", "edit", "actions", "entity_ref", "entity_refs", "target", "ref", "source_binding"]);

/** Omit transport metadata, retain hardware IDs/names and every content field. */
function displayValue(value: unknown, names: ReadonlyMap<string, string> = new Map(), field = ""): unknown {
  if (Array.isArray(value)) return value.map(item => displayValue(item, names, field));
  if (!isRecord(value)) return value;
  // A2UI cells carry the content alongside editing and provenance metadata.
  if (Object.hasOwn(value, "value") && (Object.hasOwn(value, "display_text") || Object.hasOwn(value, "editable"))) return value.value;
  if (value.kind === "instance" && typeof value.instance_id === "string" && typeof value.terminal_id === "string") {
    return `${names.get(value.instance_id) ?? "Instance"} › ${names.get(value.terminal_id) ?? value.terminal_id}`;
  }
  if (value.kind === "boundary" && typeof value.terminal_id === "string") return names.get(value.terminal_id) ?? "Boundary terminal";
  const used = new Set<string>();
  return Object.fromEntries(Object.entries(value).filter(([key]) => !hiddenFields.has(key) && !(key === "display_name" && Object.hasOwn(value, "family") && Object.hasOwn(value, "name"))).map(([key, item]) => {
    const baseLabel = names.get(key) ?? displayLabel(key);
    let label = baseLabel, count = 2;
    while (used.has(label)) label = `${baseLabel} (${count++})`;
    used.add(label);
    const resolved = typeof item === "string" && ["component_id", "instance_id", "terminal_id", "net_id"].includes(key)
      ? names.get(item) ?? `Unavailable ${key.replace("_id", "")}` : displayValue(item, names, key);
    return [field === "position" ? key.toUpperCase() : label, resolved];
  }));
}

function changeKind(label: string, path: string, before: unknown, after: unknown): PresentedChange["kind"] {
  if (typeof before !== "string" && typeof after !== "string") return "value";
  if (/systemverilog|\bsv\b|source code/i.test(label + " " + path)) return "code";
  return /narrative|description|content|text/i.test(label + " " + path) || [before, after].some(value => typeof value === "string" && value.includes("\n")) ? "text" : "value";
}

function specChanges(review: ProposalReview): Array<{ group: string; change: PresentedChange }> {
  const preview = review.preview ?? {};
  const changes = rows(preview.diff);
  return changes.filter(item => {
    const path = text(item.path), leaf = path.split(".").at(-1) ?? "";
    return !(path.includes("-ports]") && path.includes(".cells.display_name.")) && !hiddenFields.has(leaf) && !(leaf === "display_text" && changes.some(other => other.path === path.replace(/display_text$/, "value")));
  }).flatMap((item, index) => {
    const path = text(item.path);
    const field = /\.cells\.([^.[\]]+)\.(?:value|display_text)$/.exec(path)?.[1];
    const leaf = path.split(".").at(-1) || "Section";
    let label = text(item.label) || (leaf.includes("[") ? "Section" : displayLabel(leaf));
    const source = isRecord(item.after) ? item.after : isRecord(item.before) ? item.before : {};
    // The service's generic path suffix for whole keyed records contains storage
    // identities. Use the record's document title or port name instead.
    if (path.endsWith("]") && ["section_id", "table_id", "row_id", "block_id"].some(key => Object.hasOwn(source, key))) {
      if (typeof source.level === "number" && typeof source.title === "string") {
        const kind = isRecord(source.entity_ref) ? text(source.entity_ref.entity_kind) : "";
        label = `${["component", "design"].includes(kind) ? displayLabel(kind) + " · " : ""}${source.title}`;
      } else {
        const context = label.split(" › ").slice(0, -1);
        const nameCell = isRecord(source.cells) && isRecord(source.cells.name) ? source.cells.name : {};
        const name = text(source.title) || text(nameCell.value) || text(nameCell.display_text);
        if (name && context.at(-1) !== name) context.push(name);
        label = context.join(" › ") || "Section";
      }
    }
    if (field) label = label.replace(/(?:Value|Display text)$/i, displayLabel(field));
    const parts = label.split(" › ");
    const group = parts.length > 1 ? parts.slice(0, Math.min(2, parts.length - 1)).join(" › ") : label;
    const change: PresentedChange = { id: `change-${index}`, label, change: item.change === "added" || item.change === "removed" ? item.change : "changed",
      kind: changeKind(label, path, item.before, item.after), before: displayValue(item.before), after: displayValue(item.after),
      beforeAvailable: Object.hasOwn(item, "before"), afterAvailable: Object.hasOwn(item, "after") };
    if (source.section_type === "sv") {
      const old = isRecord(item.before) && isRecord(item.before.payload) ? item.before.payload.content : null;
      const next = isRecord(item.after) && isRecord(item.after.payload) ? item.after.payload.content : null;
      if (typeof old === "string" || typeof next === "string") { change.before = old; change.after = next; change.kind = "code"; }
    }
    const oldSections = rows(isRecord(item.before) ? item.before.content_sections : undefined);
    const nextSections = rows(isRecord(item.after) ? item.after.content_sections : undefined);
    if (!oldSections.length && !nextSections.length) return [{ group, change }];
    for (const side of ["before", "after"] as const) if (isRecord(change[side])) delete change[side]["Content sections"];
    const sectionIds = [...new Set([...oldSections, ...nextSections].map(section => text(section.section_id)))];
    return [{ group, change }, ...sectionIds.map((id, sectionIndex) => {
      const old = oldSections.find(section => section.section_id === id), next = nextSections.find(section => section.section_id === id), section = next ?? old!;
      const before = isRecord(old?.payload) ? old.payload.content ?? old.payload : null;
      const after = isRecord(next?.payload) ? next.payload.content ?? next.payload : null;
      const sectionLabel = `${label} › ${section.section_type === "sv" ? "SystemVerilog" : text(section.title) || "Section"}`;
      return { group, change: { id: `change-${index}-section-${sectionIndex}`, label: sectionLabel,
        change: !old ? "added" : !next ? "removed" : "changed", kind: section.section_type === "sv" && (typeof before === "string" || typeof after === "string") ? "code" : "value",
        before: displayValue(before), after: displayValue(after), beforeAvailable: change.beforeAvailable, afterAvailable: change.afterAvailable } as PresentedChange };
    })];
  });
}

function circuitChanges(review: ProposalReview): Array<{ group: string; change: PresentedChange }> {
  const preview = review.preview ?? {}, diff = isRecord(preview.diff) ? preview.diff : {};
  const before = isRecord(preview.base_document) ? preview.base_document : null;
  const afterValue = preview.candidate ?? (isRecord(preview.snapshot) ? preview.snapshot.document : undefined);
  const after = isRecord(afterValue) ? afterValue : null;
  const names = new Map<string, string>();
  for (const document of [before, after]) {
    if (!document) continue;
    const design = isRecord(document.design) ? document.design : {};
    for (const item of [...rows(document.components), ...rows(design.instances), ...rows(design.nets), ...rows(design.boundary_terminals)]) {
      if (typeof item.id === "string" && typeof item.label === "string") names.set(item.id, item.label);
      for (const terminal of rows(item.terminals)) if (typeof terminal.id === "string" && typeof terminal.label === "string") names.set(terminal.id, terminal.label);
    }
  }
  const find = (document: Record<string, unknown> | null, kind: string, id: string): unknown => {
    if (!document) return undefined;
    if (kind === "document") return { label: document.label };
    if (kind === "layout" || kind === "timing") return document[kind];
    const design = isRecord(document.design) ? document.design : {};
    const source = kind === "component" ? document.components : design[{ instance: "instances", net: "nets", boundary_terminal: "boundary_terminals" }[kind] ?? ""];
    return rows(source).find(item => item.id === id) ?? null;
  };
  const output: Array<{ group: string; change: PresentedChange }> = [];
  const append = (kind: string, id: string, change: PresentedChange["change"], old: unknown, next: unknown, field = "") => {
    const group = kind === "layout" ? "Placement" : kind === "timing" ? "Timing" : kind === "document" ? "Circuit" : `${displayLabel(kind)} · ${names.get(id) ?? "Unnamed"}`;
    const label = field ? `${group} › ${displayLabel(field)}` : group;
    output.push({ group, change: { id: `change-${output.length}`, label, change, kind: changeKind(label, field, old, next),
      before: displayValue(old, names, field), after: displayValue(next, names, field), beforeAvailable: before !== null, afterAvailable: after !== null } });
  };
  for (const change of ["added", "removed", "changed"] as const) {
    for (const item of rows(diff[change])) {
      const kind = text(item.kind), id = text(item.id), old = find(before, kind, id), next = find(after, kind, id);
      if (change === "changed" && isRecord(old) && isRecord(next)) {
        for (const field of [...new Set([...Object.keys(old), ...Object.keys(next)])].sort()) {
          if (!hiddenFields.has(field) && JSON.stringify(old[field]) !== JSON.stringify(next[field])) append(kind, id, change, old[field] ?? null, next[field] ?? null, field);
        }
      } else append(kind, id, change, old ?? null, next ?? null);
    }
  }
  // Some services report changed connections without repeating the net in changed.
  for (const id of Array.isArray(diff.connections_changed) ? diff.connections_changed : []) {
    if (typeof id !== "string" || [...rows(diff.added), ...rows(diff.removed), ...rows(diff.changed)].some(item => item.kind === "net" && item.id === id)) continue;
    const old = find(before, "net", id), next = find(after, "net", id);
    append("net", id, "changed", isRecord(old) ? old.endpoints : null, isRecord(next) ? next.endpoints : null, "connections");
  }
  return output;
}

export function presentationFor(review: ProposalReview): ProposalPresentation {
  const groups = new Map<string, PresentedChange[]>();
  for (const item of review.domain === "spec" ? specChanges(review) : circuitChanges(review)) groups.set(item.group, [...groups.get(item.group) ?? [], item.change]);
  const diagnostics = Array.isArray(review.diagnostics) ? review.diagnostics : review.diagnostics ? [review.diagnostics] : [];
  const validation = rows(review.preview?.section_validation).flatMap(section => Array.isArray(section.diagnostics) ? section.diagnostics : []);
  const summary = text(review.artifact.summary) || (groups.size ? `Changes to ${[...groups.keys()].join(", ")}.` : "No content changes reported.");
  return {
    summary: summary.length > 300 ? summary.split("\n")[0]!.slice(0, 300) + "…" : summary,
    rationale: text(review.artifact.rationale), assumptions: Array.isArray(review.artifact.assumptions) ? review.artifact.assumptions.filter((value): value is string => typeof value === "string") : [],
    warnings: [...new Set([...diagnostics, ...validation].map(value => readableDiagnostic(value)))],
    previewAvailable: review.preview !== null && (review.domain === "spec" ? Array.isArray(review.preview.diff) : isRecord(review.preview.diff)),
    errorMessage: readableProposalError(review.error), saved: hasSavedReceipt(review),
    groups: [...groups].map(([label, changes]) => ({ label, changes })),
  };
}

export function hasSavedReceipt(review: ProposalReview): boolean {
  const receipt = isRecord(review.serviceResult) ? review.serviceResult : {};
  return review.state === "applied" && (!receipt.proposal_id || receipt.proposal_id === review.proposalId)
    && typeof (review.domain === "spec" ? receipt.source_revision_hash : receipt.revision) === "string"
    && Boolean(review.domain === "spec" ? receipt.source_revision_hash : receipt.revision);
}

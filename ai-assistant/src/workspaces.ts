import { createHash } from "node:crypto";
import { resolve } from "node:path";
import type { BindingInput, WorkspaceDescriptor } from "./types.js";
import { isRecord } from "./types.js";

function digest(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

/** Derive the logical design-source workspace for one validated binding. */
export function workspaceDescriptor(
  scratchRoot: string,
  input: BindingInput,
  ownerUrl: string,
  context: Record<string, unknown>,
  sourceBinding?: Record<string, unknown> | null,
): WorkspaceDescriptor {
  let domain = input.domain;
  let workspaceOwnerUrl = ownerUrl;
  let documentId = input.documentId;
  let title = input.title?.trim() || `${input.domain === "spec" ? "Spec Editor" : "Circuit Designer"} · ${input.documentId}`;
  if (input.domain === "circuit" && sourceBinding && typeof sourceBinding.source_document_id === "string"
    && typeof sourceBinding.source_service_url === "string") {
    domain = "spec";
    workspaceOwnerUrl = sourceBinding.source_service_url.replace(/\/$/, "");
    documentId = sourceBinding.source_document_id;
    title = `Spec Editor · ${documentId}`;
  } else if (input.domain === "circuit" && isRecord(context.document)) {
    const label = context.document.label;
    if (typeof label === "string" && label.trim()) title = label.trim();
  }
  // Private CLI owners change ports each turn; the package path supplies a stable key.
  const identityOwnerUrl = process.env.SPEC2GDS_CLI_WORKSPACE_IDENTITY || workspaceOwnerUrl;
  const ownerDocumentKey = domain === "spec" && !process.env.SPEC2GDS_CLI_WORKSPACE_IDENTITY
    && typeof context.owner_document_key === "string" ? context.owner_document_key : undefined;
  const key = digest({ domain, ownerUrl: identityOwnerUrl, documentId, ...(ownerDocumentKey ? { ownerDocumentKey } : {}) });
  return {
    key,
    title,
    path: resolve(scratchRoot, "design-sources", key),
    domain,
    ownerUrl: workspaceOwnerUrl,
    documentId,
  };
}

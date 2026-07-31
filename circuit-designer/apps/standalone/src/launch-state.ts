/** Resolve an editor-published circuit session from the standalone URL. */
export function linkedCircuitDocumentId(search: string): string | undefined {
  return new URLSearchParams(search).get("document_id")?.trim() || undefined;
}

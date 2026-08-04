/** Resolve an editor-published circuit session from the standalone URL. */
export function linkedCircuitDocumentId(search: string): string | undefined {
  return new URLSearchParams(search).get("document_id")?.trim() || undefined;
}

/** Build the popup-safe Assistant entry point for one authoritative circuit. */
export function assistantCircuitUrl(
  assistantUiUrl: string,
  circuitServiceUrl: string,
  documentId: string,
): string {
  const target = new URL("/launch/circuit", assistantUiUrl);
  target.searchParams.set("service_base_url", circuitServiceUrl);
  target.searchParams.set("document_id", documentId);
  return target.toString();
}

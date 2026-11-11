/** Only known cancellation and draft-conflict events are expected. */
export function expectedBrowserFailure(
  kind: "console" | "network", url: string, message: string,
  context: { stopping: boolean; serviceUrl: string; scenario: string; documentChanged?: boolean },
): boolean {
  const stopping = context.stopping && url.startsWith(context.serviceUrl)
    && /\/(events|activity-events|documents\/view)(?:\?|$)/.test(url);
  if (kind === "console") return stopping || (context.scenario === "live" && url.startsWith(context.serviceUrl)
    && /\/transactions(?:\?|$)/.test(url) && /409/.test(message));
  const releaseOnUnload = url.startsWith(context.serviceUrl + "/documents/edit-access/release?")
    && /ERR_ABORTED|AbortError/.test(message);
  const localDownload = url.startsWith(`blob:${context.serviceUrl}/`) && /ERR_ABORTED|AbortError/.test(message);
  // Navigation can cancel a bound history read that belonged to the previous page.
  // A failure on the current page, a different endpoint, or another origin still fails.
  const historyOnNavigation = context.documentChanged && url.startsWith(context.serviceUrl + "/assistant/history?")
    && Boolean(new URL(url).searchParams.get("owner_document_key")) && /ERR_ABORTED|AbortError/.test(message);
  return stopping || releaseOnUnload || localDownload || Boolean(historyOnNavigation)
    || (/\/(events|activity-events)(?:\?|$)/.test(url) && /ERR_ABORTED|AbortError/.test(message));
}

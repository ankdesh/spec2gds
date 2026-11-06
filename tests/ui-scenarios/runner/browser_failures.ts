/** Only known cancellation and draft-conflict events are expected. */
export function expectedBrowserFailure(
  kind: "console" | "network", url: string, message: string,
  context: { stopping: boolean; serviceUrl: string; scenario: string },
): boolean {
  const stopping = context.stopping && url.startsWith(context.serviceUrl)
    && /\/(events|activity-events|documents\/view)(?:\?|$)/.test(url);
  if (kind === "console") return stopping || (context.scenario === "live" && url.startsWith(context.serviceUrl)
    && /\/transactions(?:\?|$)/.test(url) && /409/.test(message));
  const releaseOnUnload = url.startsWith(context.serviceUrl + "/documents/edit-access/release?")
    && /ERR_ABORTED|AbortError/.test(message);
  const localDownload = url.startsWith(`blob:${context.serviceUrl}/`) && /ERR_ABORTED|AbortError/.test(message);
  return stopping || releaseOnUnload || localDownload || (/\/(events|activity-events)(?:\?|$)/.test(url) && /ERR_ABORTED|AbortError/.test(message));
}

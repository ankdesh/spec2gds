/** Only known cancellation and draft-conflict events are expected. */
export function expectedBrowserFailure(
  kind: "console" | "network", url: string, message: string,
  context: { stopping: boolean; serviceUrl: string; scenario: string },
): boolean {
  const stopping = context.stopping && url.startsWith(context.serviceUrl)
    && /\/(events|activity-events|documents\/view)(?:\?|$)/.test(url);
  if (kind === "console") return stopping || (context.scenario === "live" && url.startsWith(context.serviceUrl)
    && /\/transactions(?:\?|$)/.test(url) && /409/.test(message));
  return stopping || (/\/(events|activity-events)(?:\?|$)/.test(url) && /ERR_ABORTED|AbortError/.test(message));
}

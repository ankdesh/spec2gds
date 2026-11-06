import { useEffect, useMemo, useState } from "react";
import { CircuitDesignerApp, linkedCircuitDocumentId, type CircuitToolContribution } from "@spec2gds/circuit-app-react";
import { HttpCircuitDesignerBackend } from "@spec2gds/circuit-client-http";
import { BrowserLogger } from "@spec2gds/observability/browser";
import { createBrowserFileAdapter, createBrowserPreferencesAdapter, createHttpSourceAdapter } from "./browser-adapters";
import { assistantUrl, resolveAssistantLinks } from "./assistant-links";

/** Browser composition for the reusable Circuit Designer application shell. */
export function App() {
  const apiBase = "/api/circuit-designer/v1";
  const backend = useMemo(() => new HttpCircuitDesignerBackend({ baseUrl: apiBase }), [apiBase]);
  const files = useMemo(() => createBrowserFileAdapter(), []);
  const preferences = useMemo(() => createBrowserPreferencesAdapter(backend), [backend]);
  const source = useMemo(() => createHttpSourceAdapter(backend), [backend]);
  const telemetry = useMemo(() => new BrowserLogger(`${apiBase}/logs/events`, { enabled: false, level: "info" }), [apiBase]);
  const linkConfig = useMemo(() => ({
    apiBase,
    origin: window.location.origin,
    hostname: window.location.hostname,
  }), [apiBase]);
  const [assistantLinks, setAssistantLinks] = useState(() => resolveAssistantLinks(linkConfig));
  useEffect(() => {
    let active = true;
    void fetch(`${apiBase}/services`).then(async response => {
      if (response.ok && active) setAssistantLinks(resolveAssistantLinks({ ...linkConfig, directory: await response.json() }));
    }).catch(() => undefined);
    return () => { active = false; };
  }, [apiBase, linkConfig]);
  const launch = useMemo(() => {
    const documentId = linkedCircuitDocumentId(window.location.search);
    return documentId ? { kind: "document" as const, documentId } : { kind: "new" as const };
  }, []);
  useEffect(() => {
    const renew = () => {
      const id = linkedCircuitDocumentId(window.location.search);
      if (id) void fetch(`${apiBase}/documents/${encodeURIComponent(id)}/source/renew`, { method: "POST" }).catch(() => undefined);
    };
    renew();
    const timer = window.setInterval(renew, 30_000);
    return () => window.clearInterval(timer);
  }, [apiBase]);
  const tools = useMemo<CircuitToolContribution[]>(() => [{
    id: "spec2gds.ai-assistant",
    label: "AI Assistant",
    description: "Open a conversation bound to the current circuit.",
    run: ({ snapshot }) => {
      if (!assistantLinks.uiUrl) throw new Error("The service directory is unavailable.");
      const target = assistantUrl(assistantLinks.uiUrl, assistantLinks.serviceUrl, snapshot.document.document_id);
      const opened = window.open(target, "_blank", "noopener,noreferrer");
      if (opened) opened.opener = null;
    },
  }], [assistantLinks]);
  return <CircuitDesignerApp
    backend={backend}
    events={backend}
    files={files}
    launch={launch}
    onLaunchChange={(next) => {
      const url = next.kind === "document" ? `?document_id=${encodeURIComponent(next.documentId)}` : window.location.pathname;
      window.history.replaceState({}, "", url);
    }}
    preferences={preferences}
    source={source}
    telemetry={telemetry}
    tools={tools}
  />;
}

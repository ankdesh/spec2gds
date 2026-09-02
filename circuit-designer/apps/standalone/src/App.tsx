import { useMemo } from "react";
import { CircuitDesignerApp, linkedCircuitDocumentId, type CircuitToolContribution } from "@spec2gds/circuit-app-react";
import { HttpCircuitDesignerBackend } from "@spec2gds/circuit-client-http";
import { BrowserLogger } from "@spec2gds/observability/browser";
import { createBrowserFileAdapter, createBrowserPreferencesAdapter, createHttpSourceAdapter } from "./browser-adapters";

function assistantUrl(uiUrl: string, serviceUrl: string, documentId: string): string {
  const url = new URL("/launch/circuit", uiUrl);
  url.searchParams.set("service_base_url", serviceUrl);
  url.searchParams.set("document_id", documentId);
  return url.toString();
}

/** Browser composition for the reusable Circuit Designer application shell. */
export function App() {
  const apiBase = import.meta.env.VITE_CIRCUIT_DESIGNER_API_BASE ?? "/api/circuit-designer/v1";
  const backend = useMemo(() => new HttpCircuitDesignerBackend({ baseUrl: apiBase }), [apiBase]);
  const files = useMemo(() => createBrowserFileAdapter(), []);
  const preferences = useMemo(() => createBrowserPreferencesAdapter(backend), [backend]);
  const source = useMemo(() => createHttpSourceAdapter(backend), [backend]);
  const telemetry = useMemo(() => new BrowserLogger(`${apiBase}/logs/events`, { enabled: false, level: "info" }), [apiBase]);
  const launch = useMemo(() => {
    const documentId = linkedCircuitDocumentId(window.location.search);
    return documentId ? { kind: "document" as const, documentId } : { kind: "new" as const };
  }, []);
  const tools = useMemo<CircuitToolContribution[]>(() => [{
    id: "spec2gds.ai-assistant",
    label: "AI Assistant",
    description: "Open a chat bound to the current circuit.",
    run: ({ snapshot }) => {
      const host = window.location.hostname;
      const target = assistantUrl(`http://${host}:6013`, `http://${host}:6011/api/circuit-designer/v1`, snapshot.document.document_id);
      const opened = window.open(target, "_blank", "noopener,noreferrer");
      if (opened) opened.opener = null;
    },
  }], []);
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

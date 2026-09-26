export interface AssistantLinkConfig {
  apiBase: string;
  origin: string;
  hostname: string;
  assistantUiUrl?: string;
  circuitServiceUrl?: string;
  directory?: { services?: {
    ai_assistant?: { ui_url?: string };
    circuit_designer?: { service_url?: string };
  } };
}

/** Resolve explicit URLs first, then the service directory, then local standalone defaults. */
export function resolveAssistantLinks(config: AssistantLinkConfig): { uiUrl: string; serviceUrl: string } {
  const protocol = new URL(config.origin).protocol;
  return {
    uiUrl: config.assistantUiUrl || config.directory?.services?.ai_assistant?.ui_url
      || `${protocol}//${config.hostname}:6013`,
    serviceUrl: config.circuitServiceUrl || config.directory?.services?.circuit_designer?.service_url
      || (/^https?:\/\//.test(config.apiBase) ? config.apiBase
        : `${protocol}//${config.hostname}:6011/api/circuit-designer/v1`),
  };
}

export function assistantUrl(uiUrl: string, serviceUrl: string, documentId: string): string {
  const url = new URL("launch/circuit", `${uiUrl.replace(/\/$/, "")}/`);
  url.searchParams.set("service_base_url", serviceUrl);
  url.searchParams.set("document_id", documentId);
  return url.toString();
}

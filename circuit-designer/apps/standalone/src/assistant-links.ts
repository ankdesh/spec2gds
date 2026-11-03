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

/** Read browser links from the effective service directory. */
export function resolveAssistantLinks(config: AssistantLinkConfig): { uiUrl: string; serviceUrl: string } {
  return {
    uiUrl: config.assistantUiUrl || config.directory?.services?.ai_assistant?.ui_url
      || "",
    serviceUrl: config.circuitServiceUrl || config.directory?.services?.circuit_designer?.service_url
      || new URL(config.apiBase, config.origin).href,
  };
}

export function assistantUrl(uiUrl: string, serviceUrl: string, documentId: string): string {
  const url = new URL("launch/circuit", `${uiUrl.replace(/\/$/, "")}/`);
  url.searchParams.set("service_base_url", serviceUrl);
  url.searchParams.set("document_id", documentId);
  return url.toString();
}

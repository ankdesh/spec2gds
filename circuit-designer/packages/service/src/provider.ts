import type {
  ComponentDefinition,
  ComponentDesignProvider,
  ProviderCommitRequest,
  ProviderCommitResult,
  ResolvedComponentDesign,
} from "@spec2gds/circuit-core";

export interface CallbackRegistration {
  callback_url: string;
  allow_non_loopback?: boolean;
}

function loopback(hostname: string): boolean {
  return hostname === "localhost"
    || hostname === "127.0.0.1"
    || hostname === "::1"
    || hostname.endsWith(".localhost");
}

export function validateCallbackUrl(value: string, allowedHosts: Set<string>, allowNonLoopback = false): URL {
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol)) throw new Error("Provider callback must use HTTP or HTTPS.");
  if (!loopback(url.hostname) && !allowNonLoopback && !allowedHosts.has(url.hostname)) {
    throw new Error(`Provider host ${url.hostname} is not loopback and is not allowlisted.`);
  }
  return url;
}

export class HttpCallbackProvider implements ComponentDesignProvider {
  constructor(
    private readonly callback: URL,
    private readonly fetchImpl: typeof fetch = fetch,
  ) {}

  async resolveComponentDesign(
    component: ComponentDefinition,
    context: { parent_document_id: string; ancestry: string[] },
  ): Promise<ResolvedComponentDesign> {
    const response = await this.fetchImpl(new URL("resolve", `${this.callback.toString().replace(/\/?$/, "/")}`), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ component, context }),
    });
    if (!response.ok) return { status: "unavailable", message: `Provider returned HTTP ${response.status}.` };
    return response.json() as Promise<ResolvedComponentDesign>;
  }

  async commitComponentDesign(request: ProviderCommitRequest): Promise<ProviderCommitResult> {
    const response = await this.fetchImpl(new URL("commit", `${this.callback.toString().replace(/\/?$/, "/")}`), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      return {
        accepted: false,
        provider_revision: request.base_provider_revision,
        diagnostics: [{
          severity: "error",
          code: "provider_http_error",
          message: `Provider returned HTTP ${response.status}.`,
        }],
      };
    }
    return response.json() as Promise<ProviderCommitResult>;
  }
}

import type { BindingInput, SessionBinding } from "./types.js";
import { isRecord } from "./types.js";

export class OwnerError extends Error {
  constructor(readonly status: number, readonly detail: unknown, readonly uncertain = false) {
    super(typeof detail === "string" ? detail : `Owner request failed (${status}).`);
    this.name = "OwnerError";
  }
}

function canonicalUrl(value: string): URL {
  const url = new URL(value.trim());
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error("Owner URL must be an HTTP(S) URL without credentials, query, or fragment.");
  }
  url.pathname = url.pathname.replace(/\/$/, "");
  return url;
}

function normalizedUrl(value: string): string {
  return canonicalUrl(value).toString().replace(/\/$/, "");
}

export function normalizeSpecUrl(value: string, allowlist: string[]): string {
  const url = canonicalUrl(value);
  if (url.pathname !== "/" && url.pathname !== "") throw new Error("Spec Editor URL must contain only scheme, host, and port.");
  const normalized = url.origin;
  const allowed = new Set(allowlist.map(normalizedUrl));
  if (!allowed.has(normalized)) throw new Error("Spec Editor URL is not in SPEC_SERVICE_ALLOWLIST.");
  return normalized;
}

export function normalizeCircuitUrl(value: string, allowlist: string[]): string {
  const url = canonicalUrl(value);
  if (!url.pathname.endsWith("/api/circuit-designer/v1")) {
    throw new Error("Circuit Designer URL must end with /api/circuit-designer/v1.");
  }
  const normalized = normalizedUrl(value);
  const allowed = new Set(allowlist.map(normalizedUrl));
  if (!allowed.has(normalized)) throw new Error("Circuit Designer URL is not in CIRCUIT_SERVICE_ALLOWLIST.");
  return normalized;
}

export class OwnerClients {
  readonly specAllowlist: string[];
  readonly circuitAllowlist: string[];
  readonly timeoutMs: number;

  constructor(
    specAllowlist: string[],
    circuitAllowlist: string[],
    timeoutMs: number,
  ) {
    this.specAllowlist = specAllowlist.map(value => normalizeSpecUrl(value, [value]));
    this.circuitAllowlist = circuitAllowlist.map(value => normalizeCircuitUrl(value, [value]));
    this.timeoutMs = timeoutMs;
  }

  normalize(input: BindingInput): string {
    return input.domain === "spec"
      ? normalizeSpecUrl(input.serviceBaseUrl, this.specAllowlist)
      : normalizeCircuitUrl(input.serviceBaseUrl, this.circuitAllowlist);
  }

  assertStoredBinding(binding: SessionBinding): void {
    const normalized = binding.domain === "spec"
      ? normalizeSpecUrl(binding.ownerUrl, this.specAllowlist)
      : normalizeCircuitUrl(binding.ownerUrl, this.circuitAllowlist);
    if (normalized !== binding.ownerUrl) throw new Error("Stored owner URL is not canonical.");
  }

  async validateBinding(input: BindingInput, signal?: AbortSignal): Promise<{ ownerUrl: string; context: Record<string, unknown> }> {
    const ownerUrl = this.normalize(input);
    const binding: SessionBinding = {
      sessionId: "validation", status: "creating", domain: input.domain, ownerUrl,
      documentId: input.documentId, scope: input.domain === "circuit" ? "document" : input.scope ?? "document",
      entityKind: input.entityKind ?? null, entityId: input.entityId ?? null,
      title: input.title ?? input.documentId, archived: false, createdAt: "", updatedAt: "",
    };
    return { ownerUrl, context: await this.context(binding, signal) };
  }

  async context(binding: SessionBinding, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    if (binding.domain === "circuit") {
      return this.request("GET", `${binding.ownerUrl}/documents/${encodeURIComponent(binding.documentId)}`, undefined, signal);
    }
    if (binding.scope === "document") {
      const query = new URLSearchParams({ document_id: binding.documentId });
      return this.request("GET", `${binding.ownerUrl}/assistant/context/document?${query}`, undefined, signal);
    }
    const query = new URLSearchParams({
      document_id: binding.documentId,
      entity_kind: binding.entityKind ?? "",
      entity_id: binding.entityId ?? "",
    });
    return this.request("GET", `${binding.ownerUrl}/assistant/context?${query}`, undefined, signal);
  }

  async previewSpec(binding: SessionBinding, artifact: Record<string, unknown>, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", `${binding.ownerUrl}/assistant/proposals/preview`, artifact, signal);
  }

  async applySpec(binding: SessionBinding, artifact: Record<string, unknown>, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", `${binding.ownerUrl}/assistant/proposals/apply`, artifact, signal, true);
  }

  async specChanges(binding: SessionBinding, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("GET", `${binding.ownerUrl}/assistant/changes`, undefined, signal);
  }

  async previewCircuit(binding: SessionBinding, batch: Record<string, unknown>, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", `${binding.ownerUrl}/documents/${encodeURIComponent(binding.documentId)}/operations/preview`, batch, signal);
  }

  async circuitSvg(binding: SessionBinding, signal?: AbortSignal): Promise<string> {
    this.assertStoredBinding(binding);
    if (binding.domain !== "circuit") throw new Error("SVG context is only available for Circuit bindings.");
    const timeout = AbortSignal.timeout(this.timeoutMs);
    const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
    let response: Response;
    try {
      response = await fetch(`${binding.ownerUrl}/documents/${encodeURIComponent(binding.documentId)}/exports`, {
        method: "POST", redirect: "error", signal: combined,
        headers: { Accept: "image/svg+xml", "Content-Type": "application/json" }, body: JSON.stringify({ format: "svg" }),
      });
    } catch (error) {
      throw new OwnerError(503, `Circuit SVG request failed: ${error instanceof Error ? error.message : String(error)}`);
    }
    const text = await response.text();
    if (text.length > 2 * 1024 * 1024) throw new OwnerError(502, "Circuit SVG exceeded 2 MiB.");
    if (!response.ok) throw new OwnerError(response.status, text);
    if (!response.headers.get("content-type")?.startsWith("image/svg+xml") || !/^\s*<svg\b/i.test(text)) throw new OwnerError(502, "Circuit owner returned an invalid SVG export.");
    return text;
  }

  async sendCircuit(binding: SessionBinding, artifact: Record<string, unknown>, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    const proposal = {
      proposal_id: artifact.proposal_id,
      document_id: artifact.document_id,
      base_revision: artifact.base_revision,
      title: artifact.title,
      summary: artifact.summary,
      rationale: artifact.rationale,
      assumptions: artifact.assumptions,
      batch: artifact.batch,
    };
    return this.request("POST", `${binding.ownerUrl}/documents/${encodeURIComponent(binding.documentId)}/proposals`, proposal, signal, true);
  }

  async circuitProposals(binding: SessionBinding, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("GET", `${binding.ownerUrl}/documents/${encodeURIComponent(binding.documentId)}/proposals`, undefined, signal);
  }

  async capabilities(): Promise<Record<string, unknown>> {
    // Availability is advisory UI data. Keep a stopped or unroutable owner from
    // delaying the workspace chooser by the full mutation/request timeout.
    const probeTimeoutMs = Math.min(this.timeoutMs, 2_000);
    const probe = async (domain: "spec" | "circuit", url: string): Promise<Record<string, unknown>> => {
      const target = domain === "spec" ? `${url}/health` : `${url}/capabilities`;
      try {
        const detail = await this.request("GET", target, undefined, AbortSignal.timeout(probeTimeoutMs));
        return { available: true, url, detail };
      } catch (error) {
        return { available: false, url, detail: error instanceof Error ? error.message : String(error) };
      }
    };
    const [spec, circuit] = await Promise.all([
      Promise.all(this.specAllowlist.map(url => probe("spec", url))),
      Promise.all(this.circuitAllowlist.map(url => probe("circuit", url))),
    ]);
    return { spec, circuit };
  }

  private async request(
    method: "GET" | "POST",
    url: string,
    body?: unknown,
    signal?: AbortSignal,
    mutation = false,
  ): Promise<Record<string, unknown>> {
    const timeout = AbortSignal.timeout(this.timeoutMs);
    const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
    let response: Response;
    try {
      response = await fetch(url, {
        method,
        redirect: "error",
        signal: combined,
        headers: { Accept: "application/json", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      throw new OwnerError(503, `Owner service request failed: ${reason}`, mutation);
    }
    const text = await response.text();
    if (text.length > 4 * 1024 * 1024) throw new OwnerError(502, "Owner response exceeded 4 MiB.");
    let value: unknown = {};
    if (text) {
      try { value = JSON.parse(text); }
      catch { throw new OwnerError(502, "Owner returned non-JSON content."); }
    }
    if (!response.ok) {
      const detail = isRecord(value) && "detail" in value ? value.detail : value;
      throw new OwnerError(response.status, detail, mutation && response.status >= 500);
    }
    if (!isRecord(value)) throw new OwnerError(502, "Owner returned a non-object JSON response.");
    return value;
  }
}

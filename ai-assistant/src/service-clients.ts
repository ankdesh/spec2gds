import { specAdapter } from "./service-adapters/spec.js";
import { circuitAdapter } from "./service-adapters/circuit.js";
/** Bound owner HTTP capabilities and immutable document context.
 * Recheck stored owner URLs against current deployment approval before reads or
 * submissions. Transport uncertainty and domain rejection have different retry
 * meanings; only the owner can prove that its source was saved. */
import type { BindingInput, SessionBinding } from "./types.js";
import { isRecord } from "./types.js";

export class ServiceError extends Error {
  constructor(readonly status: number, readonly detail: unknown, readonly uncertain = false) {
    super(typeof detail === "string" ? detail : `Owner request failed (${status}).`);
    this.name = "ServiceError";
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

export class ServiceClients {
  readonly specAllowlist: string[];
  readonly circuitAllowlist: string[];
  readonly timeoutMs: number;

  private specUrl(binding: SessionBinding, path: string, values: Record<string, string> = {}): string {
    const query = new URLSearchParams(values);
    if (binding.serviceDocumentKey) query.set("owner_document_key", binding.serviceDocumentKey);
    return `${binding.serviceUrl}${path}${query.size ? `?${query}` : ""}`;
  }

  async specPolicy(serviceUrl: string, signal?: AbortSignal): Promise<{ approval_policy: "automatic" | "review"; submissions: boolean; creationReceipts?: boolean }> {
    const url = normalizeSpecUrl(serviceUrl, this.specAllowlist);
    try {
      const value = await this.request("GET", `${url}/assistant/capabilities`, undefined, signal);
      if (value.approval_policy !== "automatic" && value.approval_policy !== "review") {
        throw new ServiceError(502, "Spec service did not publish a valid approval policy.");
      }
      return { approval_policy: value.approval_policy, submissions: value.submission_endpoint === "/assistant/proposals/submit",
        ...(value.creation_receipts === true ? { creationReceipts: true } : {}) };
    } catch (error) {
      if (error instanceof ServiceError && error.status === 404) throw new ServiceError(422, "Spec flows require a service with durable capabilities and submission receipts.");
      throw error;
    }
  }

  constructor(
    specAllowlist: string[],
    circuitAllowlist: string[],
    timeoutMs: number,
  ) {
    this.specAllowlist = specAllowlist.map(value => normalizeSpecUrl(value, [value]));
    this.circuitAllowlist = circuitAllowlist.map(value => normalizeCircuitUrl(value, [value]));
    this.timeoutMs = timeoutMs;
  }

  async connect(domain: "spec" | "circuit", value: string): Promise<Record<string, unknown>> {
    const url = domain === "spec"
      ? normalizeSpecUrl(value, [value])
      : normalizeCircuitUrl(value, [value]);
    const detail = await this.request("GET", domain === "spec" ? `${url}/health` : `${url}/capabilities`);
    const list = domain === "spec" ? this.specAllowlist : this.circuitAllowlist;
    if (!list.includes(url)) list.push(url);
    return { domain, url, detail };
  }

  async targets(domain: "spec" | "circuit", value: string): Promise<Record<string, unknown>> {
    const url = domain === "spec"
      ? normalizeSpecUrl(value, this.specAllowlist)
      : normalizeCircuitUrl(value, this.circuitAllowlist);
    if (domain === "spec") {
      try {
        const catalog = await this.request("GET", `${url}/documents`);
        if (Array.isArray(catalog.documents)) return { domain, serviceBaseUrl: url, documents: catalog.documents };
      } catch (error) { if (!(error instanceof ServiceError && [400, 404].includes(error.status))) throw error; }
      const snapshot = await this.request("GET", `${url}/documents/snapshot`);
      const entities = ([
        ["components", "component"], ["designs", "design"],
        ["bus_definitions", "bus_definition"], ["abstraction_definitions", "abstraction_definition"],
      ] as const).flatMap(([key, kind]) => (Array.isArray(snapshot[key]) ? snapshot[key] as unknown[] : [])
        .filter(isRecord)
        .flatMap(item => {
          const ref = isRecord(item.ref) ? item.ref : {};
          const entityId = ref.entity_id ?? item.id ?? item.name;
          return typeof entityId === "string" ? [{ document_id: snapshot.document_id, entity_id: entityId,
            entity_kind: kind, title: item.display_name || item.title || item.name || "Entity" }] : [];
        }));
      return { domain, serviceBaseUrl: url, document: {
        document_id: snapshot.document_id,
        ...(typeof snapshot.owner_document_key === "string" ? { owner_document_key: snapshot.owner_document_key } : {}),
        title: snapshot.name || (isRecord(snapshot.narrative) ? snapshot.narrative.title : "Specification"),
      }, entities };
    }
    const listed = await this.request("GET", `${url}/documents`);
    const summaries = Array.isArray(listed.documents) ? listed.documents.filter(isRecord) : [];
    const documents = await Promise.all(summaries.map(async summary => {
      const documentId = String(summary.document_id ?? "");
      let source_binding: Record<string, unknown> | null = null;
      try { source_binding = await this.request("GET", `${url}/documents/${encodeURIComponent(documentId)}/source-binding`); }
      catch (error) { if (!(error instanceof ServiceError && error.status === 404)) throw error; }
      return { ...summary, source_binding };
    }));
    return { domain, serviceBaseUrl: url, documents };
  }

  async createSpec(value: string, path: string, documentId: string, title: string, requestId: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
    const url = normalizeSpecUrl(value, this.specAllowlist);
    return this.request("POST", `${url}/documents/create`, { path, document_id: documentId, title,
      request_id: requestId, derive_named_path: true }, signal, true);
  }

  async createCircuit(value: string, documentId: string, title: string): Promise<Record<string, unknown>> {
    const url = normalizeCircuitUrl(value, this.circuitAllowlist);
    return this.request("POST", `${url}/documents/empty`, {
      document_id: documentId, label: title, request_id: `assistant-create:${documentId}`,
    });
  }

  normalize(input: BindingInput): string {
    return input.domain === "spec"
      ? normalizeSpecUrl(input.serviceBaseUrl, this.specAllowlist)
      : normalizeCircuitUrl(input.serviceBaseUrl, this.circuitAllowlist);
  }

  assertStoredBinding(binding: SessionBinding): void {
    const normalized = binding.domain === "spec"
      ? normalizeSpecUrl(binding.serviceUrl, this.specAllowlist)
      : normalizeCircuitUrl(binding.serviceUrl, this.circuitAllowlist);
    if (normalized !== binding.serviceUrl) throw new Error("Stored owner URL is not canonical.");
  }

  async validateBinding(input: BindingInput, signal?: AbortSignal): Promise<{ serviceUrl: string; context: Record<string, unknown> }> {
    const serviceUrl = this.normalize(input);
    const binding: SessionBinding = {
      sessionId: "validation", status: "creating", preset: input.preset ?? "focused", domain: input.domain, serviceUrl,
      documentId: input.documentId, scope: input.domain === "circuit" ? "document" : input.scope ?? "document",
      serviceDocumentKey: input.serviceDocumentKey,
      entityKind: input.entityKind ?? null, entityId: input.entityId ?? null,
      title: input.title ?? input.documentId, archived: false, createdAt: "", updatedAt: "",
      workspaceKey: "validation", workspaceTitle: input.documentId, workspacePath: "validation",
      workspaceDomain: input.domain, workspaceServiceUrl: serviceUrl, workspaceDocumentId: input.documentId,
    };
    return { serviceUrl, context: await this.context(binding, signal) };
  }

  async context(binding: SessionBinding, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    if (binding.domain === "circuit") {
      return this.request("GET", `${binding.serviceUrl}/documents/${encodeURIComponent(binding.documentId)}`, undefined, signal);
    }
    if (binding.scope === "document") {
      return this.request("GET", this.specUrl(binding, "/assistant/context/document", { document_id: binding.documentId }), undefined, signal);
    }
    return this.request("GET", this.specUrl(binding, "/assistant/context", {
      document_id: binding.documentId,
      entity_kind: binding.entityKind ?? "",
      entity_id: binding.entityId ?? "",
    }), undefined, signal);
  }

  async circuitSourceBinding(binding: SessionBinding, signal?: AbortSignal): Promise<Record<string, unknown> | null> {
    if (binding.domain !== "circuit") return null;
    try {
      const source = await this.request("GET", `${binding.serviceUrl}/documents/${encodeURIComponent(binding.documentId)}/source-binding`, undefined, signal);
      try {
        const names = await this.sourceNames(source);
        return names ? { ...source, source_name: names.name, source_entity_name: names.target_name } : source;
      } catch { return source; }
    } catch (error) {
      if (error instanceof ServiceError && error.status === 404) return null;
      throw error;
    }
  }

  private async sourceNames(source: Record<string, unknown>): Promise<Record<string, unknown> | null> {
    if (typeof source.source_service_url !== "string" || typeof source.source_owner_document_key !== "string") return null;
    const url = normalizeSpecUrl(source.source_service_url, this.specAllowlist);
    const ref = isRecord(source.source_entity) ? source.source_entity : {};
    const query = new URLSearchParams({ owner_document_key: source.source_owner_document_key,
      document_id: String(source.source_document_id), entity_kind: String(ref.entity_kind), entity_id: String(ref.entity_id) });
    return this.request("GET", `${url}/documents/names?${query}`);
  }

  async names(binding: SessionBinding): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    if (binding.domain === "spec") return this.request("GET", this.specUrl(binding, "/documents/names", {
      document_id: binding.documentId,
      ...(binding.scope === "entity" ? { entity_kind: binding.entityKind ?? "", entity_id: binding.entityId ?? "" } : {}),
    }));
    const source = await this.circuitSourceBinding(binding);
    if (source) {
      const names = await this.sourceNames(source);
      if (names) return names;
    }
    const snapshot = await this.context(binding);
    return { name: isRecord(snapshot.document) ? snapshot.document.label : "Circuit" };
  }

  async contextPage(binding: SessionBinding, options: { cursor?: string; entity_ids?: string[] }, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    if (binding.domain !== "spec") return this.context(binding, signal);
    return this.request("GET", this.specUrl(binding, binding.scope === "document" ? "/assistant/context/document" : "/assistant/context", {
      document_id: binding.documentId, paged: "true",
      ...(binding.scope === "entity" ? { entity_kind: binding.entityKind ?? "", entity_id: binding.entityId ?? "" } : {}),
      ...(options.cursor ? { cursor: options.cursor } : {}),
      ...(options.entity_ids ? { entity_ids: JSON.stringify(options.entity_ids) } : {}),
    }), undefined, signal);
  }

  async operationContract(binding: SessionBinding, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    const query = new URLSearchParams({ document_id: binding.documentId, scope: binding.scope });
    if (binding.serviceDocumentKey) query.set("owner_document_key", binding.serviceDocumentKey);
    if (binding.scope === "entity") {
      query.set("entity_kind", binding.entityKind ?? "");
      query.set("entity_id", binding.entityId ?? "");
    }
    return this.request("GET", `${binding.serviceUrl}/assistant/operation-schema?${query}`, undefined, signal);
  }

  async previewSpec(binding: SessionBinding, artifact: Record<string, unknown>, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", this.specUrl(binding, "/assistant/proposals/preview"), artifact, signal);
  }



  async submitSpec(binding: SessionBinding, artifact: Record<string, unknown>, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", this.specUrl(binding, "/assistant/proposals/submit", { session_id: binding.sessionId }), artifact, signal, true);
  }







  async specChanges(binding: SessionBinding, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("GET", this.specUrl(binding, "/assistant/changes"), undefined, signal);
  }

  async specSubmission(binding: SessionBinding, proposalId: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("GET", this.specUrl(binding, `/assistant/proposals/${encodeURIComponent(proposalId)}`), undefined, signal);
  }

  async previewCircuit(binding: SessionBinding, batch: Record<string, unknown>, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", `${binding.serviceUrl}/documents/${encodeURIComponent(binding.documentId)}/operations/preview`, batch, signal);
  }

  async circuitSvg(binding: SessionBinding, signal?: AbortSignal): Promise<string> {
    this.assertStoredBinding(binding);
    if (binding.domain !== "circuit") throw new Error("SVG context is only available for Circuit bindings.");
    await this.integrationMetadata("circuit", binding.serviceUrl, signal);
    const timeout = AbortSignal.timeout(this.timeoutMs);
    const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
    let response: Response;
    try {
      response = await fetch(circuitAdapter.requestUrl(binding.serviceUrl, "export_svg", { document_id: binding.documentId }), {
        method: "POST", redirect: "error", signal: combined,
        headers: { Accept: "image/svg+xml", "Content-Type": "application/json" }, body: JSON.stringify({ format: "svg" }),
      });
    } catch (error) {
      throw new ServiceError(503, `Circuit SVG request failed: ${error instanceof Error ? error.message : String(error)}`);
    }
    const text = await response.text();
    if (text.length > 2 * 1024 * 1024) throw new ServiceError(502, "Circuit SVG exceeded 2 MiB.");
    if (!response.ok) throw new ServiceError(response.status, text);
    if (!response.headers.get("content-type")?.startsWith("image/svg+xml") || !/^\s*<svg\b/i.test(text)) throw new ServiceError(502, "Circuit service returned an invalid SVG export.");
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
    return this.request("POST", `${binding.serviceUrl}/documents/${encodeURIComponent(binding.documentId)}/proposals`, proposal, signal, true);
  }

  async circuitProposals(binding: SessionBinding, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("GET", `${binding.serviceUrl}/documents/${encodeURIComponent(binding.documentId)}/proposals`, undefined, signal);
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

  async integrationMetadata(domain: "spec" | "circuit", value: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
    const base = domain === "spec" ? normalizeSpecUrl(value, this.specAllowlist) : normalizeCircuitUrl(value, this.circuitAllowlist);
    const adapter = domain === "spec" ? specAdapter : circuitAdapter;
    try {
      const metadata = await this.request("GET", `${base}/assistant/integration-metadata`, undefined, signal, false, true);
      adapter.validate(metadata);
      return metadata;
    } catch (error) {
      throw new ServiceError(502, `The selected ${domain} service integration metadata is unavailable or incompatible: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async validateServiceRequest(method: string, url: string, signal?: AbortSignal): Promise<string> {
    const parsed = new URL(url);
    for (const [domain, bases, adapter] of [["spec", this.specAllowlist, specAdapter], ["circuit", this.circuitAllowlist, circuitAdapter]] as const) {
      const base = bases.find(item => url.startsWith(item + "/"));
      if (!base) continue;
      const path = parsed.pathname.slice(new URL(base).pathname.replace(/\/$/, "").length);
      const action = adapter.match(method, path);
      // Liveness probes remain available for service setup. All design API actions require metadata.
      if (!action) throw new ServiceError(502, "Unknown service API action. No request was submitted.");
      if (action !== "health") await this.integrationMetadata(domain, base, signal);
      const declaration = adapter.actions[action]!;
      const pathValues: Record<string, string> = {};
      declaration.path.split("/").forEach((segment, index) => {
        if (segment.startsWith("{")) pathValues[segment.slice(1, -1)] = decodeURIComponent(path.split("/")[index]!);
      });
      return adapter.requestUrl(base, action, pathValues) + parsed.search;
    }
    return url; // Explicit connection probes can precede allowlist registration.
  }

  private async request(
    method: "GET" | "POST",
    url: string,
    body?: unknown,
    signal?: AbortSignal,
    mutation = false,
    metadataRead = false,
  ): Promise<Record<string, unknown>> {
    if (!metadataRead) url = await this.validateServiceRequest(method, url, signal);
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
      throw new ServiceError(503, `Service request failed: ${reason}`, mutation);
    }
    let text: string;
    try { text = await response.text(); }
    catch (error) { throw new ServiceError(502, `Service response could not be read: ${String(error)}`, mutation); }
    if (text.length > 4 * 1024 * 1024) throw new ServiceError(502, "Service response exceeded 4 MiB.", mutation);
    let value: unknown = {};
    if (text) {
      try { value = JSON.parse(text); }
      catch { throw new ServiceError(502, "Service returned non-JSON content.", mutation); }
    }
    if (!response.ok) {
      const detail = isRecord(value) && "detail" in value ? value.detail : value;
      throw new ServiceError(response.status, detail, mutation && response.status >= 500);
    }
    if (!isRecord(value)) throw new ServiceError(502, "Service returned a non-object JSON response.", mutation);
    return value;
  }
}

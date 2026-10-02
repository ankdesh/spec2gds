/** Bound owner HTTP capabilities and immutable document context.
 * Recheck stored owner URLs against current deployment approval before reads or
 * submissions. Transport uncertainty and domain rejection have different retry
 * meanings; only the owner can prove that its source was saved. */
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

  private specUrl(binding: SessionBinding, path: string, values: Record<string, string> = {}): string {
    const query = new URLSearchParams(values);
    if (binding.ownerDocumentKey) query.set("owner_document_key", binding.ownerDocumentKey);
    return `${binding.ownerUrl}${path}${query.size ? `?${query}` : ""}`;
  }

  async specPolicy(ownerUrl: string, signal?: AbortSignal): Promise<{ approval_policy: "automatic" | "review"; submissions: boolean; creationReceipts?: boolean }> {
    const url = normalizeSpecUrl(ownerUrl, this.specAllowlist);
    try {
      const value = await this.request("GET", `${url}/assistant/capabilities`, undefined, signal);
      if (value.approval_policy !== "automatic" && value.approval_policy !== "review") {
        throw new OwnerError(502, "Spec owner did not publish a valid approval policy.");
      }
      return { approval_policy: value.approval_policy, submissions: value.submission_endpoint === "/assistant/proposals/submit",
        ...(value.creation_receipts === true ? { creationReceipts: true } : {}) };
    } catch (error) {
      // An older owner retains its explicit human review flow. Other discovery
      // failures stop submission rather than assuming permission to write.
      if (error instanceof OwnerError && error.status === 404) return { approval_policy: "review", submissions: false };
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
            entity_kind: kind, title: item.title ?? item.name ?? item.vlnv ?? entityId }] : [];
        }));
      return { domain, serviceBaseUrl: url, document: {
        document_id: snapshot.document_id,
        ...(typeof snapshot.owner_document_key === "string" ? { owner_document_key: snapshot.owner_document_key } : {}),
        title: isRecord(snapshot.narrative) ? snapshot.narrative.title : snapshot.document_id,
      }, entities };
    }
    const listed = await this.request("GET", `${url}/documents`);
    const summaries = Array.isArray(listed.documents) ? listed.documents.filter(isRecord) : [];
    const documents = await Promise.all(summaries.map(async summary => {
      const documentId = String(summary.document_id ?? "");
      let source_binding: Record<string, unknown> | null = null;
      try { source_binding = await this.request("GET", `${url}/documents/${encodeURIComponent(documentId)}/source-binding`); }
      catch (error) { if (!(error instanceof OwnerError && error.status === 404)) throw error; }
      return { ...summary, source_binding };
    }));
    return { domain, serviceBaseUrl: url, documents };
  }

  async createSpec(value: string, path: string, documentId: string, title: string, requestId?: string): Promise<Record<string, unknown>> {
    const url = normalizeSpecUrl(value, this.specAllowlist);
    return this.request("POST", `${url}/documents/create`, { path, document_id: documentId, title, ...(requestId ? { request_id: requestId } : {}) }, undefined, true);
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
      ? normalizeSpecUrl(binding.ownerUrl, this.specAllowlist)
      : normalizeCircuitUrl(binding.ownerUrl, this.circuitAllowlist);
    if (normalized !== binding.ownerUrl) throw new Error("Stored owner URL is not canonical.");
  }

  async validateBinding(input: BindingInput, signal?: AbortSignal): Promise<{ ownerUrl: string; context: Record<string, unknown> }> {
    const ownerUrl = this.normalize(input);
    const binding: SessionBinding = {
      sessionId: "validation", status: "creating", preset: input.preset ?? "focused", domain: input.domain, ownerUrl,
      documentId: input.documentId, scope: input.domain === "circuit" ? "document" : input.scope ?? "document",
      ownerDocumentKey: input.ownerDocumentKey,
      entityKind: input.entityKind ?? null, entityId: input.entityId ?? null,
      title: input.title ?? input.documentId, archived: false, createdAt: "", updatedAt: "",
      workspaceKey: "validation", workspaceTitle: input.documentId, workspacePath: "validation",
      workspaceDomain: input.domain, workspaceOwnerUrl: ownerUrl, workspaceDocumentId: input.documentId,
    };
    return { ownerUrl, context: await this.context(binding, signal) };
  }

  async context(binding: SessionBinding, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    if (binding.domain === "circuit") {
      return this.request("GET", `${binding.ownerUrl}/documents/${encodeURIComponent(binding.documentId)}`, undefined, signal);
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
      return await this.request("GET", `${binding.ownerUrl}/documents/${encodeURIComponent(binding.documentId)}/source-binding`, undefined, signal);
    } catch (error) {
      if (error instanceof OwnerError && error.status === 404) return null;
      throw error;
    }
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
    if (binding.ownerDocumentKey) query.set("owner_document_key", binding.ownerDocumentKey);
    if (binding.scope === "entity") {
      query.set("entity_kind", binding.entityKind ?? "");
      query.set("entity_id", binding.entityId ?? "");
    }
    return this.request("GET", `${binding.ownerUrl}/assistant/operation-schema?${query}`, undefined, signal);
  }

  async previewSpec(binding: SessionBinding, artifact: Record<string, unknown>, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", this.specUrl(binding, "/assistant/proposals/preview"), artifact, signal);
  }

  async applySpec(binding: SessionBinding, artifact: Record<string, unknown>, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", this.specUrl(binding, "/assistant/proposals/apply"), artifact, signal, true);
  }

  async submitSpec(binding: SessionBinding, artifact: Record<string, unknown>, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", this.specUrl(binding, "/assistant/proposals/submit", { session_id: binding.sessionId }), artifact, signal, true);
  }

  async stageSpec(binding: SessionBinding, artifact: Record<string, unknown>, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", this.specUrl(binding, "/assistant/proposals/stage", { session_id: binding.sessionId }), artifact, signal);
  }

  async approveSpec(binding: SessionBinding, proposalId: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", this.specUrl(binding, `/assistant/proposals/${encodeURIComponent(proposalId)}/approve`), {}, signal, true);
  }

  async rejectSpec(binding: SessionBinding, proposalId: string): Promise<Record<string, unknown>> {
    this.assertStoredBinding(binding);
    return this.request("POST", this.specUrl(binding, `/assistant/proposals/${encodeURIComponent(proposalId)}/reject`), {});
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
    let text: string;
    try { text = await response.text(); }
    catch (error) { throw new OwnerError(502, `Owner response could not be read: ${String(error)}`, mutation); }
    if (text.length > 4 * 1024 * 1024) throw new OwnerError(502, "Owner response exceeded 4 MiB.", mutation);
    let value: unknown = {};
    if (text) {
      try { value = JSON.parse(text); }
      catch { throw new OwnerError(502, "Owner returned non-JSON content.", mutation); }
    }
    if (!response.ok) {
      const detail = isRecord(value) && "detail" in value ? value.detail : value;
      throw new OwnerError(response.status, detail, mutation && response.status >= 500);
    }
    if (!isRecord(value)) throw new OwnerError(502, "Owner returned a non-object JSON response.", mutation);
    return value;
  }
}

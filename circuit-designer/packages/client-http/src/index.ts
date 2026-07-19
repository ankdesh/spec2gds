import {
  type CircuitDesignerReadApi,
  type CircuitDesignerReadOptions,
  type CircuitDesignCatalog,
  type CircuitGraphSnapshot,
  validateCatalog,
  validateGraph,
} from "@spec2gds/circuit-core";

export type CircuitFetch = (input: string, init?: RequestInit) => Promise<Response>;

export class CircuitDesignerHttpError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown,
  ) {
    super(message);
    this.name = "CircuitDesignerHttpError";
  }
}

export interface HttpCircuitDesignerOptions {
  baseUrl?: string;
  fetch?: CircuitFetch;
}

/** HTTP implementation of the common read API; it contains no React or ELK concerns. */
export class HttpCircuitDesignerReadApi implements CircuitDesignerReadApi {
  readonly baseUrl: string;
  readonly fetch: CircuitFetch;

  constructor(options: HttpCircuitDesignerOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "/api/circuit-designer").replace(/\/$/, "");
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async getCatalog(options: CircuitDesignerReadOptions = {}): Promise<CircuitDesignCatalog> {
    const value = await this.getJson(`${this.baseUrl}/catalog`, options.signal);
    const validation = validateCatalog(value);
    if (!validation.valid) throw new CircuitDesignerHttpError("Server returned an invalid circuit catalog.", 502, validation.errors);
    return value as CircuitDesignCatalog;
  }

  async getGraph(designId: string, options: CircuitDesignerReadOptions = {}): Promise<CircuitGraphSnapshot> {
    if (!designId) throw new TypeError("designId is required.");
    const value = await this.getJson(`${this.baseUrl}/designs/${encodeURIComponent(designId)}`, options.signal);
    const validation = validateGraph(value);
    if (!validation.valid) throw new CircuitDesignerHttpError("Server returned an invalid circuit graph.", 502, validation.errors);
    return value as CircuitGraphSnapshot;
  }

  private async getJson(url: string, signal?: AbortSignal): Promise<unknown> {
    const response = await this.fetch(url, { headers: { Accept: "application/json" }, signal });
    const body = await response.json().catch(() => undefined);
    if (!response.ok) {
      const detail = body && typeof body === "object" && "detail" in body ? String((body as { detail: unknown }).detail) : response.statusText;
      throw new CircuitDesignerHttpError(detail || `Circuit Designer request failed (${response.status}).`, response.status, body);
    }
    return body;
  }
}

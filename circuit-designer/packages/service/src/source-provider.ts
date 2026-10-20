/** Authenticated callback bridge to the source owner for projected circuits.
 * Circuit preview and source preview have different validation scopes. Only an
 * explicit source commit may save the package; failed responses preserve the
 * authored base revision so callers cannot treat uncertainty as a fresh save. */
import type {
  CircuitDocument,
  CircuitOperationBatch,
  CircuitSourceBindingV1,
  CircuitSourceSyncResult,
} from "@spec2gds/circuit-core";

export type { CircuitSourceBindingV1, CircuitSourceSyncResult } from "@spec2gds/circuit-core";

export interface SourceBindingRegistration {
  binding: CircuitSourceBindingV1;
  callback_url: string;
  token: string;
  allow_non_loopback?: boolean;
  recovery?: { expected_lease_id: string; owner_id: string };
}

export interface CircuitSourceSyncRequest {
  request_id: string;
  base_source_revision_hash: string;
  candidate_document: CircuitDocument;
}

export class HttpSourceDesignProvider {
  constructor(
    private readonly callback: URL,
    private readonly token: string,
    private readonly fetchImpl: typeof fetch = fetch,
  ) {}

  resolve(binding: CircuitSourceBindingV1): Promise<CircuitSourceSyncResult> {
    return this.call("resolve", {
      request_id: `resolve:${Date.now()}`,
      base_source_revision_hash: binding.base_source_revision_hash,
    });
  }

  preview(binding: CircuitSourceBindingV1, requestId: string, candidate: CircuitDocument): Promise<CircuitSourceSyncResult> {
    return this.call("preview", {
      request_id: requestId,
      base_source_revision_hash: binding.base_source_revision_hash,
      candidate_document: candidate,
    });
  }

  commit(binding: CircuitSourceBindingV1, requestId: string, candidate: CircuitDocument): Promise<CircuitSourceSyncResult> {
    return this.call("commit", {
      request_id: requestId,
      base_source_revision_hash: binding.base_source_revision_hash,
      candidate_document: candidate,
    });
  }

  private async call(action: string, body: Record<string, unknown>): Promise<CircuitSourceSyncResult> {
    const response = await this.fetchImpl(new URL(action, `${this.callback.toString().replace(/\/?$/, "/")}`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: `Bearer ${this.token}`,
      },
      body: JSON.stringify(body),
    });
    const value = await response.json().catch(() => undefined) as CircuitSourceSyncResult | undefined;
    if (!response.ok || !value || typeof value.accepted !== "boolean" || typeof value.source_revision_hash !== "string") {
      return {
        accepted: false,
        source_revision_hash: body.base_source_revision_hash as string,
        diagnostics: [{
          severity: "error",
          code: response.status === 409 ? "source_revision_conflict" : "source_provider_http_error",
          message: `Source provider returned HTTP ${response.status}.`,
        }],
      };
    }
    return value;
  }
}

export interface StoredSourceBinding {
  binding: CircuitSourceBindingV1;
  provider: HttpSourceDesignProvider;
}

export interface SourceCommitBody {
  batch: CircuitOperationBatch;
  lease_id: string;
  proposal_id?: string;
}

/** Browser implementations of the Circuit shell's host capabilities.
 * Downloads save independent files; source synchronization calls the registered
 * owner path. Keep those save meanings distinct, and retain rejected draft data
 * so a failed owner request does not look like a successful local download. */
import { HttpCircuitDesignerBackend } from "@spec2gds/circuit-client-http";
import {
  validateContractDefinition,
  validateCircuitDesignerPreferences,
  type CircuitDesignerPreferencesV1,
  type CircuitDocument,
} from "@spec2gds/circuit-core";
import {
  type CircuitFileAdapter,
  type CircuitPreferencesAdapter,
  type CircuitSourceAdapter,
} from "@spec2gds/circuit-app-react";

export function createBrowserFileAdapter(): CircuitFileAdapter {
  return {
    async open() {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".json,application/json";
      const file = await new Promise<File | undefined>((resolve) => {
        input.addEventListener("change", () => resolve(input.files?.[0]), { once: true });
        input.click();
      });
      if (!file) return undefined;
      let parsed: unknown;
      try { parsed = JSON.parse(await file.text()); }
      catch (cause) { throw new Error(`Could not open ${file.name}: ${cause instanceof Error ? cause.message : String(cause)}`); }
      const result = validateContractDefinition("CircuitDocument", parsed);
      if (!result.valid) throw new Error(result.errors.map((item) => item.message).join(" · "));
      return { document: parsed as CircuitDocument, displayName: file.name };
    },
    async write(request) {
      const blob = new Blob([request.data], { type: request.mediaType });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = request.suggestedName;
      anchor.hidden = true;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    },
  };
}

export function createBrowserPreferencesAdapter(backend: HttpCircuitDesignerBackend): CircuitPreferencesAdapter {
  const key = "spec2gds.circuit.preferences.v1";
  return {
    async load() {
      try {
        const stored = window.localStorage.getItem(key);
        if (stored) {
          const checked = validateCircuitDesignerPreferences(JSON.parse(stored));
          if (checked.valid) return { preferences: checked.preferences, persisted: true };
        }
      } catch { /* Use deployment defaults when local preferences are unavailable. */ }
      return backend.getPreferences();
    },
    async save(preferences: CircuitDesignerPreferencesV1) {
      const checked = validateCircuitDesignerPreferences(preferences);
      if (!checked.valid) throw new Error(checked.message);
      window.localStorage.setItem(key, JSON.stringify(checked.preferences));
      return { preferences: checked.preferences, persisted: true };
    },
  };
}

export function createHttpSourceAdapter(backend: HttpCircuitDesignerBackend): CircuitSourceAdapter {
  const state = (binding: Awaited<ReturnType<HttpCircuitDesignerBackend["getSourceBinding"]>>) => binding ? ({
    id: binding.binding_id,
    label: binding.source_name || "Specification package",
    revision: binding.base_source_revision_hash,
    writable: binding.writable,
    pendingInternalDesign: binding.pending_internal_design,
    svChoiceRequired: binding.sv_choice_required,
    interfacePreview: binding.source_entity.entity_kind === "component" && !binding.editable_design_id,
    capabilities: binding.capabilities,
    message: binding.message,
    saveLabel: "Save to Spec",
    draftLabel: "Specification draft",
    boundLabel: "Specification bound",
    identifierPattern: "^[A-Za-z_][A-Za-z0-9_.-]*$",
    identifierHint: "Use an XML-compatible name without spaces.",
    metadata: binding,
  }) : undefined;
  return {
    async load(documentId) {
      return state(await backend.getSourceBinding(documentId));
    },
    async recover(documentId, expectedLeaseId, clientId) {
      const result = await backend.recoverSource(documentId, expectedLeaseId, clientId);
      return { lease: result.lease, snapshot: result.snapshot, state: state(result.binding) };
    },
    async prepareInternalDesign(documentId, leaseId, requestId) {
      const result = await backend.transitionInternalDesign(documentId, "prepare", leaseId, requestId);
      return { accepted: result.accepted, revision: result.source_revision_hash, diagnostics: result.diagnostics,
        state: state(result.binding), snapshot: result.snapshot, lease: result.lease };
    },
    async discardInternalDesign(documentId, leaseId, requestId) {
      const result = await backend.transitionInternalDesign(documentId, "discard", leaseId, requestId);
      return { accepted: result.accepted, revision: result.source_revision_hash, diagnostics: result.diagnostics,
        state: state(result.binding), snapshot: result.snapshot, lease: result.lease };
    },
    async commit(documentId, batch, leaseId, proposalId, svDisposition) {
      const result = await backend.commitSource(documentId, batch, leaseId, proposalId, svDisposition);
      return {
        accepted: result.accepted,
        revision: result.source_revision_hash,
        diagnostics: result.diagnostics,
        state: state(result.binding),
        snapshot: result.snapshot,
      };
    },
    async reload(documentId) {
      const result = await backend.reloadSource(documentId);
      return {
        accepted: result.accepted,
        revision: result.source_revision_hash,
        diagnostics: result.diagnostics,
        state: state(result.binding),
        snapshot: result.snapshot,
      };
    },
  };
}

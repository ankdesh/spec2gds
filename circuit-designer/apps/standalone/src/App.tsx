import { useEffect, useMemo, useRef, useState, type ChangeEvent, type MouseEvent as ReactMouseEvent, type WheelEvent as ReactWheelEvent } from "react";
import { CircuitDesignerHttpError, HttpCircuitDesignerBackend } from "@spec2gds/circuit-client-http";
import {
  CircuitDraft,
  createDefaultCircuitDesignerPreferences,
  createEmptyCircuitDocument,
  exportCircuitJson,
  projectDocument,
  uniqueSlug,
  type CircuitDocument,
  type CircuitDesignerPreferencesV1,
  type CircuitExport,
  type CircuitOperation,
  type CircuitProposal,
  type CircuitSnapshot,
  type ComponentDefinition,
  type EditLease,
  type NetEndpoint,
  type NetRoute,
  type NodeGeometry,
  setAllRouteLocks,
} from "@spec2gds/circuit-core";
import {
  createLayoutTask,
  layoutCircuitGraph,
  routeCircuitNets,
  type LayoutResult,
} from "@spec2gds/circuit-layout";
import {
  CircuitDesignerCanvas,
  type CircuitCanvasSelection,
  type CircuitDesignerCanvasHandle,
} from "@spec2gds/circuit-react";
import {
  circuitDocumentFileContents,
  circuitDocumentFilename,
  parseCircuitDocumentJson,
  summarizeFileDiagnostics,
} from "./circuit-files";
import { assistantCircuitUrl, linkedCircuitDocumentId } from "./launch-state";
import { browserRandomUuid } from "./browser-id";
import { BrowserLogger, type PublicLoggingConfig } from "@spec2gds/observability/browser";
import { ActionSettingsPage } from "./ActionSettingsPage";
import { CircuitMenuBar } from "./CircuitMenuBar";
import { CircuitDialogs, type CircuitDialogId } from "./CircuitDialogs";
import {
  cachePreferences,
  circuitActionDefinitions,
  clearCachedPreferences,
  keyboardEventMatches,
  loadCachedPreferences,
  panMouseButtons,
  reactFlowKeyCode,
  standardWheelZoomEnabled,
  type CircuitActionId,
  type MouseShortcut,
} from "./action-bindings";

type ServiceDirectory = {
  schema_version: 2;
  services: {
    circuit_designer: { service_url: string; ui_url: string };
    ai_assistant: { service_url: string; ui_url: string };
  };
  logging: PublicLoggingConfig;
};

const defaultHost = window.location.hostname;
const defaultServices: ServiceDirectory = {
  schema_version: 2,
  services: {
    circuit_designer: {
      service_url: `http://${defaultHost}:6011/api/circuit-designer/v1`,
      ui_url: `http://${defaultHost}:6012`,
    },
    ai_assistant: {
      service_url: `http://${defaultHost}:6013`,
      ui_url: `http://${defaultHost}:6013`,
    },
  },
  logging: { enabled: false, level: "info" },
};
const operationId = (prefix: string) => `${prefix}_${browserRandomUuid()}`;
const emptyDocument = () => createEmptyCircuitDocument(
  `local_${browserRandomUuid().replaceAll("-", "_")}`,
);

function endpointFromTerminal(terminalKey: string, lsb: number, width: number): NetEndpoint {
  const slice = width > 0 ? { slice: { lsb, width } } : {};
  if (terminalKey.startsWith("boundary:")) {
    return { kind: "boundary", terminal_id: terminalKey.slice("boundary:".length), ...slice };
  }
  const separator = terminalKey.indexOf(":");
  return {
    kind: "instance",
    instance_id: terminalKey.slice(0, separator),
    terminal_id: terminalKey.slice(separator + 1),
    ...slice,
  };
}

export function App() {
  const [activePage, setActivePage] = useState<"canvas" | "actions">("canvas");
  const initialCachedPreferences = useMemo(() => loadCachedPreferences(window.localStorage), []);
  const [preferences, setPreferences] = useState<CircuitDesignerPreferencesV1>(
    () => initialCachedPreferences ?? createDefaultCircuitDesignerPreferences(),
  );
  const [preferenceStatus, setPreferenceStatus] = useState<"loading" | "saved" | "saving" | "error">("loading");
  const [dialog, setDialog] = useState<CircuitDialogId>();
  const [linkedDocumentId, setLinkedDocumentId] = useState<string | undefined>(
    () => linkedCircuitDocumentId(window.location.search),
  );
  const [initial, setInitial] = useState<CircuitDocument>(emptyDocument);
  const apiBase = import.meta.env.VITE_CIRCUIT_DESIGNER_API_BASE ?? "/api/circuit-designer/v1";
  const backend = useMemo(
    () => new HttpCircuitDesignerBackend({ baseUrl: apiBase }),
    [apiBase],
  );
  const [services, setServices] = useState<ServiceDirectory>(defaultServices);
  const browserLogger = useMemo(
    () => new BrowserLogger(`${apiBase}/logs/events`, services.logging),
    [apiBase, services.logging],
  );
  const [snapshot, setSnapshot] = useState<CircuitSnapshot>();
  const [document, setDocument] = useState<CircuitDocument>();
  const [lease, setLease] = useState<EditLease>();
  const [layout, setLayout] = useState<LayoutResult>();
  const [layoutProgress, setLayoutProgress] = useState("");
  const [selection, setSelection] = useState<CircuitCanvasSelection>([]);
  const [message, setMessage] = useState("Ready. Unlock to make a private draft.");
  const [componentName, setComponentName] = useState("");
  const [endpointA, setEndpointA] = useState("");
  const [endpointB, setEndpointB] = useState("");
  const [netName, setNetName] = useState("");
  const [sliceLsb, setSliceLsb] = useState(0);
  const [sliceWidth, setSliceWidth] = useState(0);
  const [proposals, setProposals] = useState<CircuitProposal[]>([]);
  const [sourceDescription, setSourceDescription] = useState("Empty local circuit. Add definitions and instances after unlocking.");
  const [openingFile, setOpeningFile] = useState(false);
  const draftRef = useRef<CircuitDraft>();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<CircuitDesignerCanvasHandle>(null);
  const actionExecutorRef = useRef<(actionId: CircuitActionId) => boolean>(() => false);
  const preferencesHydratedRef = useRef(false);
  const savedPreferencesRef = useRef("");

  const actionBindings = preferences.action_bindings;
  const inspectorOpen = preferences.ui.inspector_open;

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const loaded = await backend.getPreferences();
        let next = loaded.preferences;
        if (!loaded.persisted && initialCachedPreferences) {
          next = (await backend.putPreferences(initialCachedPreferences)).preferences;
        }
        if (!active) return;
        savedPreferencesRef.current = JSON.stringify(next);
        setPreferences(next);
        setPreferenceStatus("saved");
        preferencesHydratedRef.current = true;
        clearCachedPreferences(window.localStorage);
      } catch (reason) {
        if (!active) return;
        savedPreferencesRef.current = JSON.stringify(preferences);
        preferencesHydratedRef.current = true;
        setPreferenceStatus("error");
        setMessage(`Could not load Circuit Designer preferences: ${reason instanceof Error ? reason.message : String(reason)}`);
      }
    })();
    return () => { active = false; };
  }, [backend, initialCachedPreferences]);

  useEffect(() => {
    if (!preferencesHydratedRef.current) return;
    const serialized = JSON.stringify(preferences);
    if (serialized === savedPreferencesRef.current) return;
    cachePreferences(window.localStorage, preferences);
    setPreferenceStatus("saving");
    const timer = window.setTimeout(() => {
      void backend.putPreferences(preferences).then((result) => {
        savedPreferencesRef.current = JSON.stringify(result.preferences);
        setPreferenceStatus("saved");
        clearCachedPreferences(window.localStorage);
      }).catch((reason) => {
        setPreferenceStatus("error");
        setMessage(`Could not save Circuit Designer preferences: ${reason instanceof Error ? reason.message : String(reason)}`);
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [backend, preferences]);

  useEffect(() => {
    void fetch(`${apiBase}/services`)
      .then((response) => response.ok ? response.json() as Promise<ServiceDirectory> : Promise.reject())
      .then(setServices)
      .catch(() => undefined);
  }, [apiBase]);

  useEffect(() => browserLogger.captureGlobalErrors(), [browserLogger]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        if (linkedDocumentId) {
          const next = await backend.get(linkedDocumentId);
          if (!active) return;
          setSnapshot(next);
          setDocument(next.document);
          setLayout(undefined);
          setSelection([]);
          setLease(undefined);
          setSourceDescription("Projected from the specification editor through the direct-port adapter.");
          setMessage(`Opened source-owned projection at revision ${next.revision}. Return to the specification editor to change source.`);
          draftRef.current = undefined;
          return;
        }
        let joined = false;
        let next: CircuitSnapshot | undefined;
        try {
          next = (await backend.create(initial, operationId("initialize"))).snapshot;
        } catch (reason) {
          if (!(reason instanceof CircuitDesignerHttpError) || reason.status !== 409) throw reason;
          next = await backend.get(initial.document_id);
          joined = true;
        }
        if (!next) {
          throw new Error("The service rejected the empty document.");
        }
        if (!active) return;
        setSnapshot(next);
        setDocument(next.document);
        setLayout(undefined);
        setSelection([]);
        setLease(undefined);
        setSourceDescription("Empty local circuit. Add definitions and instances after unlocking.");
        setMessage(joined
          ? `Joined the existing REST session at revision ${next.revision}.`
          : `Created REST session at revision ${next.revision}.`);
        browserLogger.event(
          "documents", joined ? "joined" : "created",
          joined ? "Joined Circuit Designer session" : "Created Circuit Designer session",
          "info", { snapshot: next },
        );
        draftRef.current = undefined;
      } catch (reason) {
        browserLogger.event("documents", "initialization_failed", "Could not initialize Circuit Designer", "error", { error: String(reason) });
        if (!active) return;
        setSnapshot(undefined);
        setDocument(undefined);
        setLayout(undefined);
        setMessage(`Circuit Designer service unavailable: ${reason instanceof Error ? reason.message : String(reason)}`);
      }
    })();
    return () => { active = false; };
  }, [backend, browserLogger, initial, linkedDocumentId]);

  function newDocument(): void {
    setSnapshot(undefined);
    setDocument(undefined);
    setLayout(undefined);
    setSelection([]);
    setLease(undefined);
    setLinkedDocumentId(undefined);
    window.history.replaceState({}, "", window.location.pathname);
    draftRef.current = undefined;
    setInitial(emptyDocument());
  }

  const graph = useMemo(
    () => document ? projectDocument(document, lease ? "draft" : snapshot?.revision ?? "loading") : undefined,
    [document, lease, snapshot?.revision],
  );

  useEffect(() => {
    if (!graph) return;
    const nodeIds = new Set(graph.nodes.map((node) => node.id));
    const boundaryIds = new Set(graph.terminals.filter((terminal) => !terminal.node_id).map((terminal) => terminal.id));
    const netIds = new Set(graph.nets.map((net) => net.id));
    setSelection((current) => {
      const next = current.filter((item) => item.kind === "node" ? nodeIds.has(item.id) : item.kind === "boundary" ? boundaryIds.has(item.id) : netIds.has(item.id));
      return next.length === current.length ? current : next;
    });
  }, [graph]);

  useEffect(() => {
    if (!graph) return;
    let active = true;
    layoutCircuitGraph(graph).then((result) => {
      if (active) setLayout(result);
    }).catch((reason) => {
      if (active) setMessage(`Layout failed: ${String(reason)}`);
    });
    return () => { active = false; };
  }, [graph]);

  useEffect(() => {
    if (!snapshot || !backend) return;
    void backend.listProposals(snapshot.document.document_id).then(setProposals);
  }, [backend, snapshot]);

  useEffect(() => {
    if (!snapshot) return;
    const documentId = snapshot.document.document_id;
    return backend.subscribe(documentId, (event) => {
      if (event.kind === "proposal.changed") {
        void backend.listProposals(documentId).then(setProposals).catch(() => undefined);
        return;
      }
      if (event.kind !== "document.changed" || lease) return;
      void backend.get(documentId).then((next) => {
        if (next.revision === snapshot.revision) return;
        setSnapshot(next);
        setDocument(next.document);
        setSelection([]);
        setLayout(undefined);
        setMessage(`REST session updated by another client to revision ${next.revision}.`);
      }).catch((reason) => {
        setMessage(`Could not refresh the REST session: ${reason instanceof Error ? reason.message : String(reason)}`);
      });
    });
  }, [backend, lease, snapshot?.document.document_id, snapshot?.revision]);

  function mutate(operation: CircuitOperation, success: string): boolean {
    const draft = draftRef.current;
    if (!draft) {
      setMessage("Unlock the document before editing.");
      return false;
    }
    const diagnostics = draft.apply(operation);
    const errors = diagnostics.filter((item) => item.severity === "error");
    if (errors.length) {
      setMessage(errors.map((item) => item.message).join(" · "));
      return false;
    }
    setDocument(draft.document);
    setMessage(success);
    return true;
  }

  async function unlock(): Promise<void> {
    if (!snapshot || !backend || lease) return;
    try {
      const nextLease = await backend.acquireLease(snapshot.document.document_id, "standalone-canvas");
      draftRef.current = new CircuitDraft(snapshot.document, snapshot.revision);
      setLease(nextLease);
      setDocument(draftRef.current.document);
      setMessage("Private draft opened. Save commits atomically; Cancel discards it.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function save(): Promise<void> {
    const draft = draftRef.current;
    if (!snapshot || !backend || !lease || !draft) return;
    if (!draft.dirty) {
      await cancel();
      return;
    }
    const result = await backend.commit(
      snapshot.document.document_id,
      draft.toBatch(operationId("draft_save")),
      lease.lease_id,
    );
    if (result.status !== "accepted" || !result.snapshot) {
      setMessage(result.diagnostics.map((item) => item.message).join(" · "));
      return;
    }
    await backend.releaseLease(snapshot.document.document_id, lease.lease_id);
    draftRef.current = undefined;
    setLease(undefined);
    setSnapshot(result.snapshot);
    setDocument(result.snapshot.document);
    downloadCircuitDocument(result.snapshot.document);
    setMessage(`Saved revision ${result.snapshot.revision} and downloaded ${circuitDocumentFilename(result.snapshot.document)}.`);
  }

  async function cancel(): Promise<void> {
    if (!snapshot || !backend || !lease) return;
    await backend.releaseLease(snapshot.document.document_id, lease.lease_id);
    draftRef.current?.cancel();
    draftRef.current = undefined;
    setLease(undefined);
    setDocument(snapshot.document);
    setMessage("Draft cancelled. No changes were persisted.");
  }

  function undoDraft(direction: "undo" | "redo"): void {
    const draft = draftRef.current;
    if (!draft) return;
    setDocument(direction === "undo" ? draft.undo() : draft.redo());
    setMessage(direction === "undo" ? "Draft change undone." : "Draft change redone.");
  }

  function addLocalComponent(): void {
    if (!document || !componentName.trim()) return;
    const componentId = uniqueSlug(componentName, document.components.map((item) => item.id));
    const instanceId = uniqueSlug(componentName, document.design.instances.map((item) => item.id));
    const component: ComponentDefinition = {
      id: componentId,
      label: componentName.trim(),
      origin: "local",
      editable: true,
      terminals: [
        { id: "input", label: "input", direction: "input", width: 1, category: "port" },
        { id: "output", label: "output", direction: "output", width: 1, category: "port" },
      ],
      parameters: [],
      appearance: { renderer_key: "generic", properties: {} },
    };
    if (!mutate({ operation_id: operationId("component"), type: "add_component", component }, "Local component definition created.")) return;
    mutate({
      operation_id: operationId("instance"),
      type: "add_instance",
      instance: { id: instanceId, label: componentName.trim(), component_id: componentId, parameter_values: {} },
    }, "Local component and first instance created.");
    setComponentName("");
  }

  function createNet(source: string, target: string, requestedName = "", lsb = sliceLsb, width = sliceWidth): boolean {
    if (!document || !source || !target || source === target) return false;
    const label = requestedName.trim() || `net ${document.design.nets.length + 1}`;
    const id = uniqueSlug(label, document.design.nets.map((item) => item.id));
    const created = mutate({
      operation_id: operationId("net"),
      type: "create_net",
      net: {
        id,
        label,
        endpoints: [
          endpointFromTerminal(source, lsb, width),
          endpointFromTerminal(target, lsb, width),
        ],
      },
    }, `Created net “${label}”.`);
    if (created) setSelection([{ kind: "net", id }]);
    return created;
  }

  function moveNodes(changes: Record<string, NodeGeometry>): void {
    for (const [instanceId, geometry] of Object.entries(changes)) {
      mutate({
        operation_id: operationId("move"),
        type: "set_instance_geometry",
        instance_id: instanceId,
        geometry,
      }, `Moved ${Object.keys(changes).length} selected instance${Object.keys(changes).length === 1 ? "" : "s"}.`);
    }
  }

  function saveRoute(netId: string, route: NetRoute): void {
    mutate({
      operation_id: operationId("route"),
      type: "set_net_route",
      net_id: netId,
      route,
    }, `Updated route ${netId}.`);
  }

  async function autoLayout(): Promise<void> {
    if (!document || !draftRef.current) {
      setMessage("Unlock before applying automatic layout.");
      return;
    }
    setLayoutProgress("Starting layout…");
    const task = createLayoutTask(document, {
      layout: { preserveNodeGeometry: "pinned" },
      onProgress: (phase, progress) => setLayoutProgress(`${phase} · ${Math.round(progress * 100)}%`),
    });
    try {
      const result = await task.result;
      for (const [instanceId, geometry] of Object.entries(result.document.layout.instance_geometry)) {
        mutate({
          operation_id: operationId("layout"),
          type: "set_instance_geometry",
          instance_id: instanceId,
          geometry,
        }, "Applying automatic layout…");
      }
      for (const [terminalKey, placement] of Object.entries(result.document.layout.terminal_placements)) {
        mutate({
          operation_id: operationId("placement"),
          type: "set_terminal_placement",
          terminal_key: terminalKey,
          placement,
        }, "Applying automatic layout…");
      }
      for (const [netId, route] of Object.entries(result.document.layout.net_routes)) saveRoute(netId, route);
      setMessage(`Automatic layout completed in ${result.elapsed_ms} ms.`);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLayoutProgress("");
    }
  }

  function triggerDownload(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.hidden = true;
    window.document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function downloadCircuitDocument(value: CircuitDocument): void {
    triggerDownload(
      new Blob([circuitDocumentFileContents(value)], { type: "application/json" }),
      circuitDocumentFilename(value),
    );
  }

  async function download(format: "json" | "svg" | "png"): Promise<void> {
    if (!snapshot || lease) {
      setMessage("Save or Cancel the private draft before downloading an authoritative file.");
      return;
    }
    if (format === "json") {
      downloadCircuitDocument(snapshot.document);
      setMessage(`Downloaded ${circuitDocumentFilename(snapshot.document)}.`);
      return;
    }
    try {
      const exported: CircuitExport = await backend.export(snapshot.document.document_id, { format });
      const data = typeof exported.data === "string"
        ? exported.data
        : exported.data.slice().buffer;
      triggerDownload(new Blob([data], { type: exported.media_type }), exported.filename);
      setMessage(`Exported ${format.toUpperCase()}.`);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function openCircuitFile(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const input = event.currentTarget;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    if (lease) {
      setMessage("Save or Cancel the private draft before opening another circuit file.");
      return;
    }

    setOpeningFile(true);
    try {
      const parsed = parseCircuitDocumentJson(await file.text());
      if (!parsed.valid) {
        setMessage(`Could not open ${file.name}: ${summarizeFileDiagnostics(parsed.diagnostics)}`);
        return;
      }
      const displayName = file.name.endsWith(".json") ? file.name : circuitDocumentFilename(parsed.document);
      let joined = false;
      let next: CircuitSnapshot | undefined;
      try {
        next = (await backend.create(parsed.document, operationId("open_file"))).snapshot;
      } catch (reason) {
        if (!(reason instanceof CircuitDesignerHttpError) || reason.status !== 409) throw reason;
        const existing = await backend.get(parsed.document.document_id);
        if (exportCircuitJson(existing.document) !== exportCircuitJson(parsed.document)) {
          setMessage(
            `Could not open ${displayName}: a different REST session already uses document ID “${parsed.document.document_id}”.`,
          );
          return;
        }
        next = existing;
        joined = true;
      }
      if (!next) {
        setMessage(`Could not open ${displayName}: the service rejected the document.`);
        return;
      }
      draftRef.current = undefined;
      setSnapshot(next);
      setDocument(next.document);
      setLease(undefined);
      setSelection([]);
      setLayout(undefined);
      setProposals(await backend.listProposals(next.document.document_id));
      setLinkedDocumentId(undefined);
      window.history.replaceState({}, "", window.location.pathname);
      setSourceDescription(`Opened from ${displayName}; permanent changes are saved by downloading a new file.`);
      const warnings = parsed.diagnostics.filter((item) => item.severity === "warning");
      setMessage(
        `${joined ? "Joined matching session for" : "Opened"} ${displayName} at revision ${next.revision}`
        + (warnings.length ? ` with ${warnings.length} warning${warnings.length === 1 ? "" : "s"}.` : "."),
      );
    } catch (reason) {
      setMessage(`Could not open ${file.name}: ${reason instanceof Error ? reason.message : String(reason)}`);
    } finally {
      setOpeningFile(false);
    }
  }

  async function openHierarchy(componentId: string): Promise<void> {
    if (!document || !backend || draftRef.current?.dirty) {
      setMessage("Save or Cancel the current draft before navigating into a child design.");
      return;
    }
    try {
      const result = await backend.resolveComponentDesign(document.document_id, componentId);
      setMessage(result.status === "available" ? `Resolved child design ${result.document?.label}.` : result.message ?? "No child design is available.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function decideProposal(proposalId: string, decision: "accept" | "reject"): Promise<void> {
    if (!document || !backend) return;
    const result = await backend.decideProposal(document.document_id, proposalId, decision);
    setProposals(await backend.listProposals(document.document_id));
    if (result?.snapshot) {
      setSnapshot(result.snapshot);
      setDocument(result.snapshot.document);
    }
    setMessage(`Proposal ${decision === "accept" ? "accepted" : "rejected"}.`);
  }

  function openAssistant(): void {
    if (!snapshot) return;
    const target = assistantCircuitUrl(
      services.services.ai_assistant.ui_url,
      services.services.circuit_designer.service_url,
      snapshot.document.document_id,
    );
    const opened = window.open(target, "_blank", "noopener,noreferrer");
    if (opened) opened.opener = null;
  }

  const selectedItem = selection.length === 1 ? selection[0] : undefined;
  const selectedInstance = selectedItem?.kind === "node"
    ? document?.design.instances.find((item) => item.id === selectedItem.id)
    : undefined;
  const selectedBoundary = selectedItem?.kind === "boundary"
    ? document?.design.boundary_terminals.find((item) => item.id === selectedItem.id)
    : undefined;
  const selectedNet = selectedItem?.kind === "net"
    ? document?.design.nets.find((item) => item.id === selectedItem.id)
    : undefined;
  const terminals = graph?.terminals ?? [];
  const selectedRoute = selectedNet && layout ? layout.layout.net_routes[selectedNet.id] : undefined;
  const selectedRouteLocked = Boolean(
    selectedRoute?.segments.some((segment) => segment.locked)
    || selectedRoute?.vertices.some((vertex) => vertex.locked),
  );

  function selectAllCanvas(): void {
    if (!graph) return;
    setSelection([
      ...graph.nodes.map((node) => ({ kind: "node" as const, id: node.id })),
      ...graph.terminals.filter((terminal) => !terminal.node_id).map((terminal) => ({ kind: "boundary" as const, id: terminal.id })),
      ...graph.nets.map((net) => ({ kind: "net" as const, id: net.id })),
    ]);
  }

  function createConnectionFromDialog(): boolean {
    const created = createNet(endpointA, endpointB, netName, sliceLsb, sliceWidth);
    if (!created) return false;
    setNetName("");
    setEndpointA("");
    setEndpointB("");
    setSliceLsb(0);
    setSliceWidth(0);
    return true;
  }

  function rerouteSelectedNet(): void {
    if (!graph || !layout || !selectedNet || selectedRouteLocked) return;
    const route = routeCircuitNets(graph, layout.layout, layout.boundary_geometry, [selectedNet.id], false)[selectedNet.id];
    if (route) saveRoute(selectedNet.id, route);
  }

  function setSelectedRouteLocked(locked: boolean): void {
    if (!selectedNet || !selectedRoute) return;
    saveRoute(selectedNet.id, setAllRouteLocks(selectedRoute, locked));
  }

  function reportConnectionRejection(reason: "same_terminal" | "terminal_in_use" | "invalid_target"): void {
    setMessage(reason === "same_terminal"
      ? "Choose two different terminals."
      : reason === "terminal_in_use"
        ? "That terminal is already connected. Extending and merging nets are not available yet."
        : "Drop the connection on another free terminal.");
  }

  function isActionEnabled(actionId: CircuitActionId): boolean {
    switch (actionId) {
      case "new-document": return !lease && !openingFile;
      case "open-document": return Boolean(snapshot) && !lease && !openingFile;
      case "save-document":
      case "cancel-changes": return Boolean(lease);
      case "download-json":
      case "export-svg":
      case "export-png": return Boolean(snapshot) && !lease;
      case "begin-edit": return Boolean(snapshot) && !lease && !linkedDocumentId;
      case "undo": return Boolean(lease && draftRef.current?.canUndo);
      case "redo": return Boolean(lease && draftRef.current?.canRedo);
      case "delete-selection": return Boolean(lease && (selectedInstance || selectedNet));
      case "open-component-catalog": return Boolean(document);
      case "create-local-component": return Boolean(lease && document);
      case "review-proposals": return proposals.length > 0;
      case "open-child-design": return Boolean(selectedInstance && !draftRef.current?.dirty);
      case "select-all": return Boolean(graph);
      case "clear-selection": return Boolean(graph);
      case "center-selection": return selection.length > 0;
      case "open-connect": return Boolean(lease);
      case "reroute-selected": return Boolean(lease && selectedNet && !selectedRouteLocked);
      case "lock-selected-route": return Boolean(lease && selectedNet && selectedRoute && !selectedRouteLocked);
      case "unlock-selected-route": return Boolean(lease && selectedNet && selectedRoute && selectedRouteLocked);
      case "arrange-all": return Boolean(lease);
      case "pan-up":
      case "pan-left":
      case "pan-down":
      case "pan-right":
      case "zoom-in":
      case "zoom-out":
      case "fit-circuit": return Boolean(graph && layout);
      case "open-assistant": return Boolean(snapshot) && !lease;
      case "open-preferences":
      case "toggle-inspector":
      case "getting-started":
      case "about": return true;
      case "pan-canvas": return false;
    }
  }

  function executeCircuitAction(actionId: CircuitActionId): boolean {
    if (!isActionEnabled(actionId)) return false;
    switch (actionId) {
      case "new-document": newDocument(); return true;
      case "open-document": fileInputRef.current?.click(); return true;
      case "save-document": void save(); return true;
      case "cancel-changes": void cancel(); return true;
      case "download-json": void download("json"); return true;
      case "export-svg": void download("svg"); return true;
      case "export-png": void download("png"); return true;
      case "begin-edit": void unlock(); return true;
      case "undo": undoDraft("undo"); return true;
      case "redo": undoDraft("redo"); return true;
      case "delete-selection":
        if (selectedInstance) {
          return mutate({ operation_id: operationId("remove"), type: "remove_instance", instance_id: selectedInstance.id, cascade: true }, "Instance removed with explicit connectivity cascade.");
        }
        if (selectedNet) {
          return mutate({ operation_id: operationId("delete_net"), type: "delete_net", net_id: selectedNet.id }, "Net deleted.");
        }
        return false;
      case "open-preferences": setActivePage("actions"); return true;
      case "open-component-catalog": setDialog("catalog"); return true;
      case "create-local-component": setDialog("new-component"); return true;
      case "review-proposals": setDialog("proposals"); return true;
      case "open-child-design": void openHierarchy(selectedInstance!.component_id); return true;
      case "select-all": selectAllCanvas(); return true;
      case "clear-selection":
        canvasRef.current?.cancelPendingConnection();
        setSelection([]);
        return true;
      case "center-selection": canvasRef.current?.centerSelection(); return true;
      case "open-connect": setDialog("connect"); return true;
      case "reroute-selected": rerouteSelectedNet(); return true;
      case "lock-selected-route": setSelectedRouteLocked(true); return true;
      case "unlock-selected-route": setSelectedRouteLocked(false); return true;
      case "arrange-all": void autoLayout(); return true;
      case "toggle-inspector":
        setPreferences((current) => ({ ...current, ui: { inspector_open: !current.ui.inspector_open } }));
        return true;
      case "pan-up":
      case "pan-left":
      case "pan-down":
      case "pan-right":
        canvasRef.current?.pan(actionId.slice("pan-".length) as "up" | "left" | "down" | "right");
        return true;
      case "zoom-in": canvasRef.current?.zoomIn(); return true;
      case "zoom-out": canvasRef.current?.zoomOut(); return true;
      case "fit-circuit": canvasRef.current?.fitView(); return true;
      case "open-assistant": openAssistant(); return true;
      case "getting-started": setDialog("getting-started"); return true;
      case "about": setDialog("about"); return true;
      case "pan-canvas": return false;
    }
  }

  actionExecutorRef.current = executeCircuitAction;

  useEffect(() => {
    if (activePage !== "canvas" || dialog) return;
    const runShortcut = (event: KeyboardEvent) => {
      const target = event.target;
      if (target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement
        || (target instanceof HTMLElement && target.isContentEditable)) return;
      const action = circuitActionDefinitions.find((definition) => definition.id !== "pan-canvas"
        && keyboardEventMatches(event, actionBindings[definition.id].keyboard));
      if (!action || !actionExecutorRef.current(action.id)) return;
      event.preventDefault();
    };
    window.addEventListener("keydown", runShortcut);
    return () => window.removeEventListener("keydown", runShortcut);
  }, [actionBindings, activePage, dialog]);

  function actionForMouseShortcut(mouse: MouseShortcut): CircuitActionId | undefined {
    return circuitActionDefinitions.find((action) => actionBindings[action.id].mouse === mouse)?.id;
  }

  function runCanvasMouseShortcut(mouse: MouseShortcut, event: ReactMouseEvent | ReactWheelEvent): void {
    const actionId = actionForMouseShortcut(mouse);
    if (!actionId || !executeCircuitAction(actionId)) return;
    event.preventDefault();
  }

  function emptyCanvasPointer(event: ReactMouseEvent): boolean {
    return event.target instanceof Element && event.target.classList.contains("react-flow__pane");
  }

  return <main className="standalone-shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark">CD</span><h1>Circuit Designer</h1></div>
      <CircuitMenuBar
        bindings={actionBindings}
        inspectorOpen={inspectorOpen}
        isActionEnabled={isActionEnabled}
        onAction={executeCircuitAction}
        proposalCount={proposals.length}
      />
      <div className="document-status" title={sourceDescription}>
        <strong>{document?.label ?? "Loading…"}</strong>
        <small>{linkedDocumentId ? "source-owned" : lease ? "private draft" : `revision ${snapshot?.revision ?? "…"}`}</small>
      </div>
      <input
        ref={fileInputRef}
        className="file-input"
        type="file"
        accept=".json,application/json"
        aria-label="Circuit file"
        disabled={!snapshot || Boolean(lease) || openingFile}
        onChange={(event) => void openCircuitFile(event)}
      />
    </header>
    <div className="notice">
      <span className="local-dot" />
      {activePage === "actions" ? "Actions & shortcuts" : linkedDocumentId ? "Editor projection" : "Independent document"}
      <span>{activePage === "actions"
        ? `Shared preference file · ${preferenceStatus === "loading" ? "loading…" : preferenceStatus === "saving" ? "saving…" : preferenceStatus === "saved" ? "saved" : "save failed"}`
        : layoutProgress || message}</span>
    </div>
    {activePage === "actions" ? <ActionSettingsPage
      onClose={() => setActivePage("canvas")}
      onPreferencesChange={setPreferences}
      preferences={preferences}
      preferenceStatus={preferenceStatus}
    /> : <section className={`workspace${inspectorOpen ? " workspace--inspector-open" : ""}`}>
      <div className="stage">
        <div
          className="canvas-surface"
          onClick={(event) => {
            if (event.detail === 1 && emptyCanvasPointer(event)) runCanvasMouseShortcut("primary-click", event);
          }}
          onDoubleClick={(event) => {
            if (emptyCanvasPointer(event)) runCanvasMouseShortcut("primary-double-click", event);
          }}
          onAuxClick={(event) => {
            if (event.button === 1 && emptyCanvasPointer(event)) runCanvasMouseShortcut("middle-click", event);
          }}
          onContextMenu={(event) => {
            if (!emptyCanvasPointer(event)) return;
            if (actionBindings["pan-canvas"].mouse === "secondary-drag") event.preventDefault();
            runCanvasMouseShortcut("secondary-click", event);
          }}
          onWheelCapture={(event) => {
            if (standardWheelZoomEnabled(actionBindings)) return;
            runCanvasMouseShortcut(event.deltaY < 0 ? "wheel-up" : "wheel-down", event);
          }}
        >
          {!layout && <div className="loading">Computing flattened canvas projection…</div>}
          {graph && layout && <CircuitDesignerCanvas
            ref={canvasRef}
            graph={graph}
            layout={layout.layout}
            boundaryGeometry={layout.boundary_geometry}
            editable={Boolean(lease)}
            selection={selection}
            onSelectionChange={setSelection}
            onNodeGeometryChanges={moveNodes}
            onConnectTerminals={(source, target) => { createNet(source, target, "", 0, 0); }}
            onConnectionRejected={reportConnectionRejection}
            onNetRouteChange={saveRoute}
            fitViewOnInit={false}
            showInlineViewportControls={false}
            viewportPanMouseButtons={panMouseButtons(actionBindings["pan-canvas"].mouse)}
            viewportPanActivationKeyCode={reactFlowKeyCode(actionBindings["pan-canvas"].keyboard)}
            wheelZoomEnabled={standardWheelZoomEnabled(actionBindings)}
            useDefaultEscapeBinding={false}
          />}
          {layout && <div className="layout-time">Grid router · {layout.elapsed_ms} ms</div>}
        </div>
      </div>
      {inspectorOpen && <aside className="inspector">
        <p className="eyebrow">Inspector</p>
        {selection.length === 0 && <div className="empty-inspector"><span>⌁</span><p>Select an instance, boundary terminal, or net to inspect its properties.</p></div>}
        {selection.length > 1 && <div className="multi-inspector"><span className="kind">selection</span><h2>{selection.length} items selected</h2><p>{selection.filter((item) => item.kind === "node").length} instances · {selection.filter((item) => item.kind === "boundary").length} boundary terminals · {selection.filter((item) => item.kind === "net").length} nets</p></div>}
        {selectedInstance && document && <><span className="kind">instance</span><h2>{selectedInstance.label}</h2><code>{selectedInstance.id}</code>
          <label>Label<input value={selectedInstance.label} onChange={(event) => mutate({ operation_id: operationId("label"), type: "update_instance", instance: { ...selectedInstance, label: event.target.value || selectedInstance.id } }, "Instance label updated.")} disabled={!lease} /></label>
          <details><summary>Canonical data</summary><pre>{JSON.stringify(selectedInstance, null, 2)}</pre></details>
        </>}
        {selectedBoundary && <><span className="kind">boundary terminal</span><h2>{selectedBoundary.label}</h2><code>{selectedBoundary.id}</code><p className="draw-hint">{selectedBoundary.direction} · {String(selectedBoundary.width)} bit{selectedBoundary.width === 1 ? "" : "s"}</p><details><summary>Canonical data</summary><pre>{JSON.stringify(selectedBoundary, null, 2)}</pre></details></>}
        {selectedNet && <><span className="kind">net</span><h2>{selectedNet.label || selectedNet.id}</h2><code>{selectedNet.id}</code>
          <p className="draw-hint">{selectedRouteLocked ? "Route locked. Use Route → Unlock Selected Route before editing." : "Drag highlighted segments or handles to edit this route."}</p>
          <p className="draw-hint">{selectedNet.endpoints.map((endpoint) => JSON.stringify(endpoint)).join("\n")}</p>
          <details><summary>Canonical data</summary><pre>{JSON.stringify(selectedNet, null, 2)}</pre></details>
        </>}
      </aside>}
    </section>}
    <CircuitDialogs
      componentName={componentName}
      dialog={dialog}
      document={document}
      endpointA={endpointA}
      endpointB={endpointB}
      netName={netName}
      onClose={() => setDialog(undefined)}
      onComponentNameChange={setComponentName}
      onCreateComponent={addLocalComponent}
      onCreateConnection={createConnectionFromDialog}
      onDecideProposal={(proposalId, decision) => void decideProposal(proposalId, decision)}
      onEndpointAChange={setEndpointA}
      onEndpointBChange={setEndpointB}
      onNetNameChange={setNetName}
      onSliceLsbChange={setSliceLsb}
      onSliceWidthChange={setSliceWidth}
      proposals={proposals}
      sliceLsb={sliceLsb}
      sliceWidth={sliceWidth}
      sourceDescription={sourceDescription}
      terminals={terminals}
    />
  </main>;
}

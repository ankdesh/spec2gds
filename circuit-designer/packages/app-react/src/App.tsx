/* Reusable Circuit Designer application shell. */
import { useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent as ReactMouseEvent, type WheelEvent as ReactWheelEvent } from "react";
import {
  CircuitDraft,
  analyzeCircuitTiming,
  createDefaultCircuitDesignerPreferences,
  createEmptyCircuitDocument,
  exportCircuitJson,
  endpointTerminalKey,
  effectiveCircuitTiming,
  insertRouteBend,
  projectDocument,
  removeRouteBend,
  renderCircuitPng,
  renderCircuitSvg,
  uniqueSlug,
  type CircuitDocument,
  type ClockDomainV1,
  type CycleEdgeMarkerV1,
  type CircuitDesignerPreferencesV1,
  type CircuitOperation,
  type CircuitProposal,
  type CircuitSnapshot,
  type ComponentDefinition,
  type EditLease,
  type NetEndpoint,
  type NetRoute,
  type NodeGeometry,
  type TerminalPlacement,
  setAllRouteLocks,
  blueprintSlateTheme,
  circuitThemeCssProperties,
  type CircuitDesignerBackend,
  type CircuitThemeDefinition,
} from "@spec2gds/circuit-core";
import {
  createLayoutTask,
  layoutCircuitGraph,
  routeCircuitNets,
  type LayoutResult,
} from "@spec2gds/circuit-layout";
import {
  CircuitDesignerCanvas,
  type CircuitCanvasContextMenuRequest,
  type CircuitCanvasContextTarget,
  type CircuitCanvasSelection,
  type CircuitDesignerCanvasHandle,
} from "@spec2gds/circuit-react";
import {
  circuitDocumentFileContents,
  circuitDocumentFilename,
  parseCircuitDocumentJson,
  summarizeFileDiagnostics,
} from "./circuit-files";
import { browserRandomUuid } from "./browser-id";
import { ActionSettingsPage } from "./ActionSettingsPage";
import { CircuitMenuBar } from "./CircuitMenuBar";
import { CircuitConfirmationDialog, CircuitDialogs, type CircuitDialogId } from "./CircuitDialogs";
import { CircuitContextMenu } from "./CircuitActionMenu";
import {
  buildCircuitContextMenu,
  type CircuitActionInvocation,
  type CircuitCommandId,
} from "./context-actions";
import {
  circuitActionDefinitions,
  formatKeyboardShortcut,
  keyboardEventMatches,
  normalizeContextMenuMouseBindings,
  panMouseButtons,
  reactFlowKeyCode,
  standardWheelZoomEnabled,
  type CircuitActionId,
  type MouseShortcut,
} from "./action-bindings";
import type {
  CircuitFileAdapter,
  CircuitEventAdapter,
  CircuitLaunch,
  CircuitPreferencesAdapter,
  CircuitSourceAdapter,
  CircuitSourceState,
  CircuitTelemetrySink,
  CircuitToolContribution,
} from "./adapters";
import { noopCircuitTelemetry } from "./adapters";
const operationId = (prefix: string) => `${prefix}_${browserRandomUuid()}`;
const emptyDocument = () => createEmptyCircuitDocument(
  `local_${browserRandomUuid().replaceAll("-", "_")}`,
);
const isConflictError = (reason: unknown): boolean => Boolean(
  reason && typeof reason === "object" && "status" in reason && reason.status === 409,
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

export interface CircuitDesignerAppProps {
  backend: CircuitDesignerBackend;
  events?: CircuitEventAdapter;
  files: CircuitFileAdapter;
  preferences: CircuitPreferencesAdapter;
  launch?: CircuitLaunch;
  source?: CircuitSourceAdapter;
  telemetry?: CircuitTelemetrySink;
  theme?: CircuitThemeDefinition;
  tools?: CircuitToolContribution[];
  onLaunchChange?: (launch: CircuitLaunch) => void;
}

export function App({
  backend,
  events,
  files,
  preferences: preferencesAdapter,
  launch = { kind: "new" },
  source,
  telemetry = noopCircuitTelemetry,
  theme = blueprintSlateTheme,
  tools = [],
  onLaunchChange,
}: CircuitDesignerAppProps) {
  const [activePage, setActivePage] = useState<"canvas" | "actions">("canvas");
  const initialCachedPreferences = useMemo(() => preferencesAdapter.readCached?.(), [preferencesAdapter]);
  const [preferences, setPreferences] = useState<CircuitDesignerPreferencesV1>(
    () => initialCachedPreferences ?? createDefaultCircuitDesignerPreferences(),
  );
  const [preferenceStatus, setPreferenceStatus] = useState<"loading" | "saved" | "saving" | "error">("loading");
  const [dialog, setDialog] = useState<CircuitDialogId>();
  const [confirmation, setConfirmation] = useState<{
    title: string;
    message: string;
    confirmLabel: string;
    onConfirm: () => void;
  }>();
  const [linkedDocumentId, setLinkedDocumentId] = useState<string | undefined>(
    () => launch.kind === "document" ? launch.documentId : undefined,
  );
  const [initial, setInitial] = useState<CircuitDocument>(() => launch.kind === "new" && launch.document ? launch.document : emptyDocument());
  const [snapshot, setSnapshot] = useState<CircuitSnapshot>();
  const [document, setDocument] = useState<CircuitDocument>();
  const [lease, setLease] = useState<EditLease>();
  const [sourceBinding, setSourceBinding] = useState<CircuitSourceState>();
  const [sourceConflict, setSourceConflict] = useState(false);
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
  const [stagedProposalId, setStagedProposalId] = useState<string>();
  const [sourceDescription, setSourceDescription] = useState("Empty local circuit. Add definitions and instances after unlocking.");
  const [openingFile, setOpeningFile] = useState(false);
  const [contextRequest, setContextRequest] = useState<(CircuitCanvasContextMenuRequest & { selection: CircuitCanvasSelection })>();
  const [componentCreationPoint, setComponentCreationPoint] = useState<{ x: number; y: number }>();
  const [menubarDismissVersion, setMenubarDismissVersion] = useState(0);
  const [placingCycleEdge, setPlacingCycleEdge] = useState(false);
  const [viewport, setViewport] = useState({ x: 20, y: 20, zoom: 1 });
  const draftRef = useRef<CircuitDraft>();
  const appRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<CircuitDesignerCanvasHandle>(null);
  const actionExecutorRef = useRef<(invocation: CircuitActionInvocation) => boolean>(() => false);
  const preferencesHydratedRef = useRef(false);
  const savedPreferencesRef = useRef("");

  const actionBindings = preferences.action_bindings;
  const inspectorOpen = preferences.ui.inspector_open;
  const timingOverlayVisible = preferences.ui.timing_overlay_visible;
  const sourceIdentifierPattern = sourceBinding?.identifierPattern;
  const isSourceIdentifier = (value: string): boolean => !sourceIdentifierPattern || new RegExp(sourceIdentifierPattern).test(value);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const loaded = await preferencesAdapter.load();
        let next = loaded.preferences;
        if (!loaded.persisted && initialCachedPreferences) {
          next = (await preferencesAdapter.save(initialCachedPreferences)).preferences;
        }
        const normalized = normalizeContextMenuMouseBindings(next);
        next = normalized.preferences;
        if ((loaded.persisted || initialCachedPreferences) && normalized.changed) next = (await preferencesAdapter.save(next)).preferences;
        if (!active) return;
        savedPreferencesRef.current = JSON.stringify(next);
        setPreferences(next);
        setPreferenceStatus("saved");
        preferencesHydratedRef.current = true;
        preferencesAdapter.clearCache?.();
      } catch (reason) {
        if (!active) return;
        savedPreferencesRef.current = JSON.stringify(preferences);
        preferencesHydratedRef.current = true;
        setPreferenceStatus("error");
        setMessage(`Could not load Circuit Designer preferences: ${reason instanceof Error ? reason.message : String(reason)}`);
      }
    })();
    return () => { active = false; };
  }, [initialCachedPreferences, preferencesAdapter]);

  useEffect(() => {
    if (!preferencesHydratedRef.current) return;
    const serialized = JSON.stringify(preferences);
    if (serialized === savedPreferencesRef.current) return;
    preferencesAdapter.cacheFailedSave?.(preferences);
    setPreferenceStatus("saving");
    const timer = window.setTimeout(() => {
      void preferencesAdapter.save(preferences).then((result) => {
        savedPreferencesRef.current = JSON.stringify(result.preferences);
        setPreferenceStatus("saved");
        preferencesAdapter.clearCache?.();
      }).catch((reason) => {
        setPreferenceStatus("error");
        setMessage(`Could not save Circuit Designer preferences: ${reason instanceof Error ? reason.message : String(reason)}`);
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [preferences, preferencesAdapter]);

  useEffect(() => telemetry.captureGlobalErrors?.(), [telemetry]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        if (linkedDocumentId) {
          const [next, binding] = await Promise.all([
            backend.get(linkedDocumentId),
            source?.load(linkedDocumentId),
          ]);
          if (!active) return;
          setSnapshot(next);
          setDocument(next.document);
          setLayout(undefined);
          setSelection([]);
          setLease(undefined);
          setStagedProposalId(undefined);
          setSourceBinding(binding);
          setSourceConflict(false);
          setSourceDescription(binding?.writable
            ? binding.message ?? `Bound to ${binding.label}. Save commits topology and layout back to its authoritative source.`
            : binding?.message ?? `Read-only projection owned by ${binding?.label ?? "an external source"}.`);
          setMessage(binding?.writable
            ? `Opened writable source design at revision ${binding.revision.slice(0, 20)}…`
            : binding?.message ?? `Opened source-owned projection at revision ${next.revision}.`);
          draftRef.current = undefined;
          return;
        }
        let joined = false;
        let next: CircuitSnapshot | undefined;
        try {
          next = (await backend.create(initial, operationId("initialize"))).snapshot;
        } catch (reason) {
          if (!isConflictError(reason)) throw reason;
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
        setStagedProposalId(undefined);
        setSourceDescription("Empty local circuit. Add definitions and instances after unlocking.");
        setMessage(joined
          ? `Joined the existing REST session at revision ${next.revision}.`
          : `Created REST session at revision ${next.revision}.`);
        telemetry.event(
          "documents", joined ? "joined" : "created",
          joined ? "Joined Circuit Designer session" : "Created Circuit Designer session",
          "info", { snapshot: next },
        );
        draftRef.current = undefined;
      } catch (reason) {
        telemetry.event("documents", "initialization_failed", "Could not initialize Circuit Designer", "error", { error: String(reason) });
        if (!active) return;
        setSnapshot(undefined);
        setDocument(undefined);
        setLayout(undefined);
        setMessage(`Circuit Designer service unavailable: ${reason instanceof Error ? reason.message : String(reason)}`);
      }
    })();
    return () => { active = false; };
  }, [backend, initial, linkedDocumentId, source, telemetry]);

  function newDocument(): void {
    setSnapshot(undefined);
    setDocument(undefined);
    setLayout(undefined);
    setSelection([]);
    setLease(undefined);
    setStagedProposalId(undefined);
    setSourceBinding(undefined);
    setSourceConflict(false);
    setLinkedDocumentId(undefined);
    onLaunchChange?.({ kind: "new" });
    draftRef.current = undefined;
    setInitial(emptyDocument());
  }

  const graph = useMemo(
    () => document ? projectDocument(document, lease ? "draft" : snapshot?.revision ?? "loading") : undefined,
    [document, lease, snapshot?.revision],
  );
  const timing = useMemo(() => document ? effectiveCircuitTiming(document) : effectiveCircuitTiming({}), [document]);
  const timingAnalysis = useMemo(
    () => document ? analyzeCircuitTiming(document, layout?.boundary_geometry) : { subjects: [], paths: [], diagnostics: [] },
    [document, layout?.boundary_geometry],
  );

  useEffect(() => {
    if (!graph) return;
    const nodeIds = new Set(graph.nodes.map((node) => node.id));
    const boundaryIds = new Set(graph.terminals.filter((terminal) => !terminal.node_id).map((terminal) => terminal.id.replace(/^boundary:/, "")));
    const netIds = new Set(graph.nets.map((net) => net.id));
    const edgeIds = new Set(timing.cycle_edges.map((edge) => edge.id));
    setSelection((current) => {
      const next = current.filter((item) => item.kind === "node" ? nodeIds.has(item.id) : item.kind === "boundary" ? boundaryIds.has(item.id) : item.kind === "cycle-edge" ? edgeIds.has(item.id) : netIds.has(item.id));
      return next.length === current.length ? current : next;
    });
  }, [graph, timing.cycle_edges]);

  useEffect(() => setContextRequest(undefined), [document]);

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
    if (!snapshot || !events) return;
    const documentId = snapshot.document.document_id;
    return events.subscribe(documentId, (event) => {
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
  }, [backend, events, lease, snapshot?.document.document_id, snapshot?.revision]);

  function mutate(operation: CircuitOperation, success: string): boolean {
    return mutateBatch([operation], success);
  }

  function mutateBatch(operations: CircuitOperation[], success: string): boolean {
    const draft = draftRef.current;
    if (!draft) {
      setMessage("Unlock the document before editing.");
      return false;
    }
    const diagnostics = draft.applyBatch(operations);
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
    if (sourceBinding) {
      if (!sourceBinding.writable) return;
      if (!layout) {
        setMessage("Wait for the visible circuit layout before saving to the source.");
        return;
      }
      const materialize: CircuitOperation[] = [
        ...Object.entries(layout.layout.node_geometry).map(([instanceId, geometry]) => ({
          operation_id: operationId("save_geometry"),
          type: "set_instance_geometry" as const,
          instance_id: instanceId,
          geometry,
        })),
        ...Object.entries(layout.layout.terminal_placements).map(([terminalKey, placement]) => ({
          operation_id: operationId("save_placement"),
          type: "set_terminal_placement" as const,
          terminal_key: terminalKey,
          placement,
        })),
        ...Object.entries(layout.layout.net_routes).map(([netId, route]) => ({
          operation_id: operationId("save_route"),
          type: "set_net_route" as const,
          net_id: netId,
          route,
        })),
      ];
      const materializeDiagnostics = draft.applyBatch(materialize);
      const materializeErrors = materializeDiagnostics.filter((item) => item.severity === "error");
      if (materializeErrors.length) {
        setMessage(materializeErrors.map((item) => item.message).join(" · "));
        return;
      }
      setDocument(draft.document);
      if (!source) {
        setMessage("This host did not provide a writable source adapter.");
        return;
      }
      let result;
      try {
        result = await source.commit(
          snapshot.document.document_id,
          draft.toBatch(operationId("source_save")),
          lease.lease_id,
          stagedProposalId,
        );
      } catch (reason) {
        setMessage(`The source save response was lost or failed. The complete draft is preserved; retry the save. ${reason instanceof Error ? reason.message : String(reason)}`);
        return;
      }
      if (!result.accepted || !result.snapshot) {
        const conflict = result.diagnostics.some((item) => item.code === "source_revision_conflict");
        setSourceConflict(conflict);
        setMessage(result.diagnostics.map((item) => item.message).join(" · ") || "Source save was rejected.");
        return;
      }
      draftRef.current = undefined;
      setLease(undefined);
      setStagedProposalId(undefined);
      setSnapshot(result.snapshot);
      setDocument(result.snapshot.document);
      setSelection([]);
      setSourceBinding(result.state ?? { ...sourceBinding, revision: result.revision });
      setSourceConflict(false);
      setMessage(`Saved to the source at ${result.revision.slice(0, 20)}… Edit mode closed.`);
      void backend.listProposals(snapshot.document.document_id).then(setProposals).catch(() => undefined);
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
    await downloadCircuitDocument(result.snapshot.document);
    setMessage(`Saved revision ${result.snapshot.revision} and downloaded ${circuitDocumentFilename(result.snapshot.document)}.`);
  }

  async function reopenLatestSource(): Promise<void> {
    if (!snapshot || !sourceBinding || !source) return;
    if (lease) await backend.releaseLease(snapshot.document.document_id, lease.lease_id);
    draftRef.current?.cancel();
    draftRef.current = undefined;
    setLease(undefined);
    setStagedProposalId(undefined);
    const result = await source.reload(snapshot.document.document_id);
    if (!result.accepted || !result.snapshot) {
      setMessage(result.diagnostics.map((item) => item.message).join(" · "));
      return;
    }
    setSnapshot(result.snapshot);
    setDocument(result.snapshot.document);
    setSourceBinding(result.state ?? { ...sourceBinding, revision: result.revision });
    setSelection([]);
    setSourceConflict(false);
    void backend.listProposals(snapshot.document.document_id).then(setProposals).catch(() => undefined);
    setMessage("Reopened the latest source revision. The previous unsaved draft was discarded.");
  }

  async function cancel(): Promise<void> {
    if (!snapshot || !backend || !lease) return;
    await backend.releaseLease(snapshot.document.document_id, lease.lease_id);
    draftRef.current?.cancel();
    draftRef.current = undefined;
    setLease(undefined);
    setStagedProposalId(undefined);
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
    if (!isSourceIdentifier(componentName.trim())) {
      setMessage(sourceBinding?.identifierHint ?? "Use a source-compatible component name.");
      return;
    }
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
    const operations: CircuitOperation[] = [
      { operation_id: operationId("component"), type: "add_component", component },
      {
        operation_id: operationId("instance"),
        type: "add_instance",
        instance: { id: instanceId, label: componentName.trim(), component_id: componentId, parameter_values: {} },
      },
    ];
    if (componentCreationPoint) {
      const grid = document.layout.grid_size || 20;
      operations.push({
        operation_id: operationId("geometry"),
        type: "set_instance_geometry",
        instance_id: instanceId,
        geometry: {
          x: Math.round((componentCreationPoint.x - 90) / grid) * grid,
          y: Math.round((componentCreationPoint.y - 50) / grid) * grid,
          width: 180,
          height: 100,
          pinned: true,
        },
      });
    }
    if (!mutateBatch(operations, "Local component and first instance created.")) return;
    setSelection([{ kind: "node", id: instanceId }]);
    setComponentName("");
    setComponentCreationPoint(undefined);
  }

  function placeCatalogComponent(componentId: string): void {
    if (!document || !lease) return;
    const component = document.components.find((item) => item.id === componentId);
    if (!component) return;
    const instanceId = uniqueSlug(component.label, document.design.instances.map((item) => item.id));
    if (mutate({
      operation_id: operationId("instance"),
      type: "add_instance",
      instance: { id: instanceId, label: instanceId, component_id: component.id, parameter_values: {} },
    }, `Placed ${component.label} as ${instanceId}.`)) setSelection([{ kind: "node", id: instanceId }]);
  }

  function addBoundaryPort(): void {
    if (!document || !lease || !sourceBinding?.capabilities.includes("boundary-ports")) return;
    const id = uniqueSlug("port", document.design.boundary_terminals.map((item) => item.id));
    if (mutate({
      operation_id: operationId("boundary"),
      type: "add_boundary_terminal",
      terminal: { id, label: id, direction: "inout", width: 1, category: "port" },
    }, `Added boundary port ${id}.`)) setSelection([{ kind: "boundary", id }]);
  }

  function updateBoundaryPort(value: CircuitDocument["design"]["boundary_terminals"][number] | undefined): void {
    if (!value) return;
    mutate({
      operation_id: operationId("boundary"),
      type: "update_boundary_terminal",
      terminal: value,
      cascade: false,
    }, `Updated boundary port ${value.label}.`);
  }

  function createNet(source: string, target: string, requestedName = "", lsb = sliceLsb, width = sliceWidth): boolean {
    if (!document || !source || !target || source === target) return false;
    const label = requestedName.trim() || `${sourceBinding ? "net_" : "net "}${document.design.nets.length + 1}`;
    if (!isSourceIdentifier(label)) {
      setMessage(sourceBinding?.identifierHint ?? "Use a source-compatible connection name.");
      return false;
    }
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
    mutateBatch(Object.entries(changes).map(([instanceId, geometry]) => ({
        operation_id: operationId("move"),
        type: "set_instance_geometry",
        instance_id: instanceId,
        geometry,
      })), `Moved ${Object.keys(changes).length} selected instance${Object.keys(changes).length === 1 ? "" : "s"}.`);
  }

  function edgeIntersectsVisibleObject(x: number): boolean {
    if (!document) return false;
    return [
      ...Object.values(document.layout.instance_geometry),
      ...Object.values(layout?.boundary_geometry ?? {}),
    ].some((geometry) => x > geometry.x && x < geometry.x + geometry.width);
  }

  function addCycleEdgeAt(rawX: number): boolean {
    if (!document) return false;
    const x = Math.round(rawX / document.layout.grid_size) * document.layout.grid_size;
    if (edgeIntersectsVisibleObject(x)) {
      setMessage("Place the cycle edge between components; it cannot divide an object.");
      return false;
    }
    const id = uniqueSlug(`cycle_edge_${timing.cycle_edges.length + 1}`, timing.cycle_edges.map((edge) => edge.id));
    const created = mutate({ operation_id: operationId("cycle_edge"), type: "add_cycle_edge", edge: { id, x, locked: false } }, `Added cycle edge at x=${x}.`);
    if (created) setSelection([{ kind: "cycle-edge", id }]);
    return created;
  }

  function updateCycleEdge(edge: CycleEdgeMarkerV1): boolean {
    if (edgeIntersectsVisibleObject(edge.x)) {
      setMessage("The cycle edge cannot divide a component or boundary terminal.");
      return false;
    }
    return mutate({ operation_id: operationId("cycle_edge"), type: "update_cycle_edge", edge }, `Updated ${edge.label ?? edge.id}.`);
  }

  function setClockDomain(domain: ClockDomainV1): void {
    mutate({ operation_id: operationId("clock_domain"), type: "set_clock_domain", domain }, `Updated clock domain ${domain.label}.`);
  }

  function removeClockDomain(domainId: string): void {
    const domain = timing.clock_domains.find((item) => item.id === domainId);
    if (!domain) return;
    setConfirmation({
      title: "Remove clock domain?",
      message: `Remove “${domain.label}” and return its assigned objects to the default clock?`,
      confirmLabel: "Remove domain",
      onConfirm: () => { setConfirmation(undefined); mutate({ operation_id: operationId("clock_domain"), type: "remove_clock_domain", domain_id: domainId }, `Removed clock domain ${domain.label}.`); },
    });
  }

  function assignClockDomain(subjectKey: string, domainId?: string): void {
    mutate({ operation_id: operationId("clock_assignment"), type: "set_subject_clock_domain", subject_key: subjectKey, domain_id: domainId }, `Updated the selected object's clock domain.`);
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
      const operations: CircuitOperation[] = [
        ...Object.entries(result.document.layout.instance_geometry).map(([instanceId, geometry]): CircuitOperation => ({
          operation_id: operationId("layout"),
          type: "set_instance_geometry",
          instance_id: instanceId,
          geometry,
        })),
        ...Object.entries(result.document.layout.terminal_placements).map(([terminalKey, placement]): CircuitOperation => ({
          operation_id: operationId("placement"),
          type: "set_terminal_placement",
          terminal_key: terminalKey,
          placement,
        })),
        ...Object.entries(result.document.layout.net_routes).map(([netId, route]): CircuitOperation => ({ operation_id: operationId("route"), type: "set_net_route", net_id: netId, route })),
        ...(result.document.timing?.cycle_edges ?? []).flatMap((edge): CircuitOperation[] => {
          const previous = timing.cycle_edges.find((item) => item.id === edge.id);
          return previous && previous.x !== edge.x ? [{ operation_id: operationId("cycle_edge"), type: "update_cycle_edge", edge }] : [];
        }),
      ];
      if (mutateBatch(operations, `Automatic layout completed in ${result.elapsed_ms} ms.`)) setLayout(undefined);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLayoutProgress("");
    }
  }

  async function downloadCircuitDocument(value: CircuitDocument): Promise<void> {
    await files.write({
      suggestedName: circuitDocumentFilename(value),
      mediaType: "application/json",
      data: circuitDocumentFileContents(value),
    });
  }

  async function download(format: "json" | "svg" | "png"): Promise<void> {
    if (!snapshot || lease) {
      setMessage("Save or Cancel the private draft before downloading an authoritative file.");
      return;
    }
    if (format === "json") {
      await downloadCircuitDocument(snapshot.document);
      setMessage(`Downloaded ${circuitDocumentFilename(snapshot.document)}.`);
      return;
    }
    if (!layout) {
      setMessage("Wait for the visible circuit layout before exporting an image.");
      return;
    }
    try {
      const exportDocument: CircuitDocument = {
        ...snapshot.document,
        layout: {
          ...snapshot.document.layout,
          direction: layout.layout.direction,
          instance_geometry: structuredClone(layout.layout.node_geometry),
          terminal_placements: structuredClone(layout.layout.terminal_placements),
          net_routes: structuredClone(layout.layout.net_routes),
        },
      };
      const options = { boundaryGeometry: layout.boundary_geometry };
      const stem = `${snapshot.document.document_id}-${snapshot.document.design.id}`;
      if (format === "svg") {
        await files.write({ suggestedName: `${stem}.svg`, mediaType: "image/svg+xml", data: renderCircuitSvg(exportDocument, options) });
      } else {
        const png = await renderCircuitPng(exportDocument, options);
        await files.write({ suggestedName: `${stem}.png`, mediaType: "image/png", data: new Uint8Array(await png.arrayBuffer()) });
      }
      setMessage(`Exported ${format.toUpperCase()}.`);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function openCircuitFile(): Promise<void> {
    if (lease) {
      setMessage("Save or Cancel the private draft before opening another circuit file.");
      return;
    }

    setOpeningFile(true);
    try {
      const opened = await files.open();
      if (!opened) return;
      const parsed = parseCircuitDocumentJson(exportCircuitJson(opened.document));
      if (!parsed.valid) throw new Error(summarizeFileDiagnostics(parsed.diagnostics));
      const displayName = opened.displayName ?? circuitDocumentFilename(parsed.document);
      let joined = false;
      let next: CircuitSnapshot | undefined;
      try {
        next = (await backend.create(parsed.document, operationId("open_file"))).snapshot;
      } catch (reason) {
        if (!isConflictError(reason)) throw reason;
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
      onLaunchChange?.({ kind: "new", document: next.document });
      setSourceDescription(`Opened from ${displayName}; permanent changes are saved by downloading a new file.`);
      const warnings = parsed.diagnostics.filter((item) => item.severity === "warning");
      setMessage(
        `${joined ? "Joined matching session for" : "Opened"} ${displayName} at revision ${next.revision}`
        + (warnings.length ? ` with ${warnings.length} warning${warnings.length === 1 ? "" : "s"}.` : "."),
      );
    } catch (reason) {
      setMessage(`Could not open circuit file: ${reason instanceof Error ? reason.message : String(reason)}`);
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
    if (!document || !backend || !snapshot) return;
    if (decision === "accept" && sourceBinding) {
      if (!sourceBinding.writable || lease || draftRef.current) {
        setMessage("Save or Cancel the current draft before accepting a proposal.");
        return;
      }
      const proposal = proposals.find(item => item.proposal_id === proposalId);
      if (!proposal?.batch || proposal.base_revision !== snapshot.revision) {
        setMessage("This proposal cannot be staged as a source draft. Refresh the proposal.");
        return;
      }
      let nextLease;
      try {
        nextLease = await backend.acquireLease(document.document_id, "standalone-canvas");
        const draft = new CircuitDraft(snapshot.document, snapshot.revision);
        const diagnostics = draft.applyBatch(proposal.batch.operations);
        const errors = diagnostics.filter(item => item.severity === "error");
        if (errors.length) throw new Error(errors.map(item => item.message).join(" · "));
        draftRef.current = draft;
        setLease(nextLease);
        setStagedProposalId(proposalId);
        setDocument(draft.document);
        setMessage("Proposal staged in a private draft. Save to Specification to persist it, or Cancel to discard the draft.");
      } catch (reason) {
        if (nextLease) await backend.releaseLease(document.document_id, nextLease.lease_id).catch(() => undefined);
        setMessage(reason instanceof Error ? reason.message : String(reason));
      }
      return;
    }
    if (decision === "reject" && stagedProposalId === proposalId && lease) {
      await backend.releaseLease(document.document_id, lease.lease_id);
      draftRef.current?.cancel();
      draftRef.current = undefined;
      setLease(undefined);
      setStagedProposalId(undefined);
      setDocument(snapshot.document);
    }
    const result = await backend.decideProposal(document.document_id, proposalId, decision);
    setProposals(await backend.listProposals(document.document_id));
    if (result?.snapshot) {
      setSnapshot(result.snapshot);
      setDocument(result.snapshot.document);
    }
    setMessage(`Proposal ${decision === "accept" ? "accepted" : "rejected"}.`);
  }

  function runTool(toolId: string): void {
    const tool = tools.find(item => item.id === toolId);
    if (!snapshot || !tool || lease) return;
    void Promise.resolve(tool.run({ backend, document: snapshot.document, snapshot })).catch((reason) => {
      setMessage(`${tool.label} failed: ${reason instanceof Error ? reason.message : String(reason)}`);
    });
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
  const selectedCycleEdge = selectedItem?.kind === "cycle-edge"
    ? timing.cycle_edges.find((edge) => edge.id === selectedItem.id)
    : undefined;
  const selectedTimingSubject = selectedItem?.kind === "node" ? `instance:${selectedItem.id}`
    : selectedItem?.kind === "boundary" ? `boundary:${selectedItem.id}`
      : undefined;
  const terminals = graph?.terminals ?? [];
  const selectedRoute = selectedNet && layout ? layout.layout.net_routes[selectedNet.id] : undefined;
  const selectedRouteLocked = Boolean(
    selectedRoute?.segments.some((segment) => segment.locked)
    || selectedRoute?.vertices.some((vertex) => vertex.locked),
  );

  const selectionItemForTarget = (target: CircuitCanvasContextTarget): CircuitCanvasSelection[number] | undefined => {
    if (target.kind === "node") return { kind: "node", id: target.nodeId };
    if (target.kind === "boundary") return { kind: "boundary", id: target.terminalId };
    if (target.kind === "terminal") return target.owner.kind === "node"
      ? { kind: "node", id: target.owner.id }
      : { kind: "boundary", id: target.owner.id };
    if (target.kind === "net" || target.kind === "route-segment" || target.kind === "route-vertex") return { kind: "net", id: target.netId };
    if (target.kind === "cycle-edge") return { kind: "cycle-edge", id: target.edgeId };
    return undefined;
  };
  const targetTerminalKey = (target: CircuitCanvasContextTarget | undefined): string | undefined => {
    if (!target) return undefined;
    if (target.kind === "terminal") return target.terminalId;
    if (target.kind === "boundary") return `boundary:${target.terminalId}`;
    return undefined;
  };
  const targetNetId = (target: CircuitCanvasContextTarget | undefined): string | undefined => {
    if (!target) return undefined;
    if (target.kind === "net" || target.kind === "route-segment" || target.kind === "route-vertex") return target.netId;
    const terminalKey = targetTerminalKey(target);
    return terminalKey ? document?.design.nets.find((net) => net.endpoints.some((endpoint) => endpointTerminalKey(endpoint) === terminalKey))?.id : undefined;
  };
  const contextTargetItem = contextRequest ? selectionItemForTarget(contextRequest.target) : undefined;
  const contextTargetSelected = Boolean(contextTargetItem && contextRequest?.selection.some((item) => item.kind === contextTargetItem.kind && item.id === contextTargetItem.id));
  const contextSelectionWide = Boolean(contextRequest && contextRequest.selection.length > 1 && (
    (contextRequest.keyboard && contextRequest.target.kind === "canvas")
    || (contextTargetSelected && ["node", "boundary", "net"].includes(contextRequest.target.kind))
  ));
  const contextTerminalKey = targetTerminalKey(contextRequest?.target);
  const contextNetId = targetNetId(contextRequest?.target);
  const contextNet = document?.design.nets.find((net) => net.id === contextNetId);
  const contextRoute = contextNetId ? layout?.layout.net_routes[contextNetId] : undefined;
  const contextPlacement = contextTerminalKey ? layout?.layout.terminal_placements[contextTerminalKey] : undefined;
  const contextRouteLocked = Boolean(contextRoute?.segments.some((segment) => segment.locked)
    || contextRoute?.vertices.some((vertex) => vertex.locked));
  const contextCycleEdgeId = contextRequest?.target.kind === "cycle-edge" ? contextRequest.target.edgeId : undefined;
  const contextEntries = contextRequest ? buildCircuitContextMenu({
    target: contextRequest.target,
    selectionWide: contextSelectionWide,
    inspectorOpen,
    terminalConnected: Boolean(contextNet),
    terminalSide: contextPlacement?.side,
    terminalPlacementLocked: contextPlacement?.locked,
    routeLocked: contextRouteLocked,
    cycleEdgeLocked: contextCycleEdgeId ? timing.cycle_edges.find((edge) => edge.id === contextCycleEdgeId)?.locked : undefined,
  }) : [];

  function openCanvasContextMenu(request: CircuitCanvasContextMenuRequest): void {
    const item = selectionItemForTarget(request.target);
    const preservedSelection = item && !selection.some((selected) => selected.kind === item.kind && selected.id === item.id) ? [item] : selection;
    if (preservedSelection !== selection) setSelection(preservedSelection);
    setDialog(undefined);
    setMenubarDismissVersion((value) => value + 1);
    setContextRequest({ ...request, selection: preservedSelection });
  }

  function closeContextMenu(restoreFocus = true): void {
    const target = contextRequest?.focusTarget;
    setContextRequest(undefined);
    if (restoreFocus && target?.isConnected) requestAnimationFrame(() => (target as HTMLElement).focus?.());
  }

  function selectAllCanvas(): void {
    if (!graph) return;
    setSelection([
      ...graph.nodes.map((node) => ({ kind: "node" as const, id: node.id })),
      ...graph.terminals.filter((terminal) => !terminal.node_id).map((terminal) => ({ kind: "boundary" as const, id: terminal.id.replace(/^boundary:/, "") })),
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

  function deleteCurrentSelection(fallback?: CircuitCanvasSelection[number], selectionOverride?: CircuitCanvasSelection): boolean {
    const effectiveSelection = selectionOverride ?? selection;
    if (!document || (!effectiveSelection.length && !fallback)) return false;
    const captured = effectiveSelection.length ? [...effectiveSelection] : [fallback!];
    const applyDelete = () => {
      const selectedNetIds = new Set(captured.filter((item) => item.kind === "net").map((item) => item.id));
      const operations: CircuitOperation[] = [
        ...[...selectedNetIds].map((netId): CircuitOperation => ({ operation_id: operationId("delete_net"), type: "delete_net", net_id: netId })),
        ...captured.filter((item) => item.kind === "node").map((item): CircuitOperation => ({ operation_id: operationId("remove"), type: "remove_instance", instance_id: item.id, cascade: true })),
        ...captured.filter((item) => item.kind === "boundary").map((item): CircuitOperation => ({ operation_id: operationId("remove_boundary"), type: "remove_boundary_terminal", terminal_id: item.id, cascade: true })),
        ...captured.filter((item) => item.kind === "cycle-edge").map((item): CircuitOperation => ({ operation_id: operationId("remove_cycle_edge"), type: "remove_cycle_edge", edge_id: item.id })),
      ];
      const changed = mutateBatch(operations, `Deleted ${captured.length} selected item${captured.length === 1 ? "" : "s"} atomically.`);
      if (changed) setSelection([]);
      return changed;
    };
    const boundaryCount = captured.filter((item) => item.kind === "boundary").length;
    const edgeCount = captured.filter((item) => item.kind === "cycle-edge").length;
    if (boundaryCount || edgeCount) {
      setConfirmation({
        title: edgeCount ? "Delete selected cycle edge?" : "Delete selected boundary terminals?",
        message: edgeCount
          ? "Removing this edge renumbers following stages and reduces affected path latency by one cycle."
          : `This will delete ${boundaryCount} boundary terminal${boundaryCount === 1 ? "" : "s"} and explicitly cascade their connectivity. The complete selection is deleted as one undoable change.`,
        confirmLabel: "Delete selection",
        onConfirm: () => { setConfirmation(undefined); applyDelete(); },
      });
      return true;
    }
    return applyDelete();
  }

  function terminalContext(target: CircuitCanvasContextTarget | undefined) {
    const terminalKey = targetTerminalKey(target);
    if (!terminalKey || !graph || !layout) return undefined;
    const terminal = graph.terminals.find((item) => item.id === terminalKey);
    if (!terminal) return undefined;
    const ownerTerminals = graph.terminals.filter((item) => terminal.node_id ? item.node_id === terminal.node_id : !item.node_id);
    const placement = layout.layout.terminal_placements[terminalKey];
    const sameSide = ownerTerminals
      .filter((item) => layout.layout.terminal_placements[item.id]?.side === placement?.side)
      .sort((left, right) => (layout.layout.terminal_placements[left.id]?.order ?? 0) - (layout.layout.terminal_placements[right.id]?.order ?? 0));
    return { terminalKey, terminal, ownerTerminals, placement, sameSide, index: sameSide.findIndex((item) => item.id === terminalKey) };
  }

  function setTerminalSide(target: CircuitCanvasContextTarget | undefined, side: TerminalPlacement["side"]): boolean {
    const context = terminalContext(target);
    if (!context) return false;
    const orders = context.ownerTerminals
      .map((terminal) => layout?.layout.terminal_placements[terminal.id])
      .filter((placement): placement is TerminalPlacement => placement?.side === side)
      .map((placement) => placement.order);
    return mutate({
      operation_id: operationId("placement"),
      type: "set_terminal_placement",
      terminal_key: context.terminalKey,
      placement: { side, order: (orders.length ? Math.max(...orders) : -1) + 1, locked: context.placement?.locked ?? false },
    }, `Moved ${context.terminalKey} to the ${side.toLowerCase()} side.`);
  }

  function moveTerminalInOrder(target: CircuitCanvasContextTarget | undefined, delta: -1 | 1): boolean {
    const context = terminalContext(target);
    const adjacent = context && context.sameSide[context.index + delta];
    if (!context?.placement || !adjacent) return false;
    const adjacentPlacement = layout?.layout.terminal_placements[adjacent.id];
    if (!adjacentPlacement) return false;
    return mutateBatch([
      { operation_id: operationId("placement"), type: "set_terminal_placement", terminal_key: context.terminalKey, placement: { ...context.placement, order: adjacentPlacement.order } },
      { operation_id: operationId("placement"), type: "set_terminal_placement", terminal_key: adjacent.id, placement: { ...adjacentPlacement, order: context.placement.order } },
    ], `Moved ${context.terminalKey} ${delta < 0 ? "earlier" : "later"}.`);
  }

  function setTerminalPlacementLocked(target: CircuitCanvasContextTarget | undefined, locked: boolean): boolean {
    const context = terminalContext(target);
    if (!context?.placement) return false;
    return mutate({ operation_id: operationId("placement"), type: "set_terminal_placement", terminal_key: context.terminalKey, placement: { ...context.placement, locked } }, `${locked ? "Locked" : "Unlocked"} ${context.terminalKey} placement.`);
  }

  function resetTerminalPlacement(target: CircuitCanvasContextTarget | undefined): boolean {
    const context = terminalContext(target);
    if (!context) return false;
    return mutate({ operation_id: operationId("placement"), type: "set_terminal_placement", terminal_key: context.terminalKey, placement: null }, `Reset ${context.terminalKey} to automatic placement.`);
  }

  function disconnectContextTerminal(target: CircuitCanvasContextTarget | undefined): boolean {
    const terminalKey = targetTerminalKey(target);
    const net = terminalKey ? document?.design.nets.find((item) => item.endpoints.some((endpoint) => endpointTerminalKey(endpoint) === terminalKey)) : undefined;
    const endpoint = net?.endpoints.find((item) => endpointTerminalKey(item) === terminalKey);
    if (!net || !endpoint) return false;
    if (net.endpoints.length > 2) return mutate({ operation_id: operationId("disconnect"), type: "disconnect_endpoint", net_id: net.id, endpoint }, `Disconnected ${terminalKey} from ${net.label || net.id}.`);
    setConfirmation({
      title: "Delete the connected net?",
      message: `Disconnecting ${terminalKey} would leave “${net.label || net.id}” with fewer than two endpoints. Delete the whole net instead?`,
      confirmLabel: "Delete net",
      onConfirm: () => {
        setConfirmation(undefined);
        if (mutate({ operation_id: operationId("delete_net"), type: "delete_net", net_id: net.id }, `Deleted net ${net.label || net.id}.`)) setSelection([]);
      },
    });
    return true;
  }

  function deleteBoundaryTarget(target: CircuitCanvasContextTarget | undefined): boolean {
    const item = target && selectionItemForTarget(target);
    if (!item || item.kind !== "boundary") return false;
    setConfirmation({
      title: "Delete boundary terminal?",
      message: `Delete boundary terminal “${item.id}” and explicitly cascade its connectivity?`,
      confirmLabel: "Delete boundary terminal",
      onConfirm: () => {
        setConfirmation(undefined);
        if (mutate({ operation_id: operationId("remove_boundary"), type: "remove_boundary_terminal", terminal_id: item.id, cascade: true }, `Deleted boundary terminal ${item.id}.`)) setSelection([]);
      },
    });
    return true;
  }

  function reportConnectionRejection(reason: "same_terminal" | "terminal_in_use" | "invalid_target"): void {
    setMessage(reason === "same_terminal"
      ? "Choose two different terminals."
      : reason === "terminal_in_use"
        ? "That terminal is already connected. Extending and merging nets are not available yet."
        : "Drop the connection on another free terminal.");
  }

  function isCommandEnabled(invocation: CircuitActionInvocation): boolean {
    const actionId = invocation.commandId;
    const contextualNetId = targetNetId(invocation.target) ?? selectedNet?.id;
    const contextualRoute = contextualNetId ? layout?.layout.net_routes[contextualNetId] : undefined;
    const contextualRouteLocked = Boolean(contextualRoute?.segments.some((segment) => segment.locked)
      || contextualRoute?.vertices.some((vertex) => vertex.locked));
    const terminal = terminalContext(invocation.target);
    const contextualInstanceId = invocation.target?.kind === "node" ? invocation.target.nodeId
      : invocation.target?.kind === "terminal" && invocation.target.owner.kind === "node" ? invocation.target.owner.id
        : selectedInstance?.id;
    const contextualInstance = document?.design.instances.find((instance) => instance.id === contextualInstanceId);
    const contextualCycleEdgeId = invocation.target?.kind === "cycle-edge" ? invocation.target.edgeId : selectedCycleEdge?.id;
    const contextualCycleEdge = timing.cycle_edges.find((edge) => edge.id === contextualCycleEdgeId);
    switch (actionId) {
      case "new-document": return !lease && !openingFile;
      case "open-document": return Boolean(snapshot) && !lease && !openingFile;
      case "save-document":
      case "cancel-changes": return Boolean(lease);
      case "download-json":
      case "export-svg":
      case "export-png": return Boolean(snapshot && layout) && !lease;
      case "begin-edit": return Boolean(snapshot) && !lease && Boolean(!linkedDocumentId || sourceBinding?.writable);
      case "undo": return Boolean(lease && draftRef.current?.canUndo);
      case "redo": return Boolean(lease && draftRef.current?.canRedo);
      case "delete-selection": return Boolean(lease && (selection.length || (invocation.target && selectionItemForTarget(invocation.target))));
      case "open-component-catalog": return Boolean(document);
      case "create-local-component": return Boolean(lease && document);
      case "review-proposals": return proposals.length > 0;
      case "open-child-design": return Boolean(contextualInstance && !draftRef.current?.dirty);
      case "select-all": return Boolean(graph);
      case "clear-selection": return Boolean(graph);
      case "center-selection": return Boolean(selection.length || (invocation.target && invocation.target.kind !== "canvas"));
      case "open-connect": return Boolean(lease);
      case "reroute-selected": return Boolean(lease && contextualNetId && !contextualRouteLocked);
      case "lock-selected-route": return Boolean(lease && contextualNetId && contextualRoute && !contextualRouteLocked);
      case "unlock-selected-route": return Boolean(lease && contextualNetId && contextualRoute && contextualRouteLocked);
      case "arrange-all": return Boolean(lease);
      case "add-cycle-edge": return Boolean(lease && document);
      case "open-clock-settings": return Boolean(lease && document);
      case "open-timing-analysis": return Boolean(document);
      case "edit-cycle-edge": return Boolean(lease && contextualCycleEdge);
      case "lock-cycle-edge": return Boolean(lease && contextualCycleEdge && !contextualCycleEdge.locked);
      case "unlock-cycle-edge": return Boolean(lease && contextualCycleEdge?.locked);
      case "delete-cycle-edge": return Boolean(lease && contextualCycleEdge);
      case "pan-up":
      case "pan-left":
      case "pan-down":
      case "pan-right":
      case "zoom-in":
      case "zoom-out":
      case "fit-circuit": return Boolean(graph && layout);
      case "run-primary-tool": return Boolean(snapshot && tools.length) && !lease;
      case "open-preferences":
      case "toggle-inspector":
      case "toggle-timing-overlay":
      case "getting-started":
      case "about": return true;
      case "pan-canvas": return false;
      case "add-bend-here": {
        if (!lease || invocation.target?.kind !== "route-segment" || !contextualRoute || !invocation.circuitPoint) return false;
        return JSON.stringify(insertRouteBend(contextualRoute, invocation.target.segmentId, invocation.circuitPoint, document?.layout.grid_size ?? 20)) !== JSON.stringify(contextualRoute);
      }
      case "remove-bend": {
        if (!lease || invocation.target?.kind !== "route-vertex" || invocation.target.vertexKind !== "bend" || !contextualRoute) return false;
        return JSON.stringify(removeRouteBend(contextualRoute, invocation.target.vertexId)) !== JSON.stringify(contextualRoute);
      }
      case "select-connected-net": return Boolean(contextualNetId);
      case "disconnect-port": return Boolean(lease && contextualNetId && terminal);
      case "delete-boundary-terminal": return Boolean(lease && invocation.target && selectionItemForTarget(invocation.target)?.kind === "boundary");
      case "terminal-side-north":
      case "terminal-side-east":
      case "terminal-side-south":
      case "terminal-side-west":
      case "terminal-lock-placement":
      case "terminal-unlock-placement": return Boolean(lease && terminal);
      case "terminal-move-earlier": return Boolean(lease && terminal && terminal.index > 0);
      case "terminal-move-later": return Boolean(lease && terminal && terminal.index >= 0 && terminal.index < terminal.sameSide.length - 1);
      case "terminal-reset-placement": return Boolean(lease && terminal && document?.layout.terminal_placements[terminal.terminalKey]);
    }
  }

  function executeCircuitAction(invocation: CircuitActionInvocation): boolean {
    if (!isCommandEnabled(invocation)) return false;
    const actionId = invocation.commandId;
    const contextualNetId = targetNetId(invocation.target) ?? selectedNet?.id;
    const contextualRoute = contextualNetId ? layout?.layout.net_routes[contextualNetId] : undefined;
    const contextualInstanceId = invocation.target?.kind === "node" ? invocation.target.nodeId
      : invocation.target?.kind === "terminal" && invocation.target.owner.kind === "node" ? invocation.target.owner.id
        : selectedInstance?.id;
    const contextualInstance = document?.design.instances.find((instance) => instance.id === contextualInstanceId);
    const contextualCycleEdgeId = invocation.target?.kind === "cycle-edge" ? invocation.target.edgeId : selectedCycleEdge?.id;
    const contextualCycleEdge = timing.cycle_edges.find((edge) => edge.id === contextualCycleEdgeId);
    switch (actionId) {
      case "new-document": newDocument(); return true;
      case "open-document": void openCircuitFile(); return true;
      case "save-document": void save(); return true;
      case "cancel-changes": void cancel(); return true;
      case "download-json": void download("json"); return true;
      case "export-svg": void download("svg"); return true;
      case "export-png": void download("png"); return true;
      case "begin-edit": void unlock(); return true;
      case "undo": undoDraft("undo"); return true;
      case "redo": undoDraft("redo"); return true;
      case "delete-selection": return deleteCurrentSelection(
        invocation.target ? selectionItemForTarget(invocation.target) : undefined,
        invocation.source === "context-menu" ? contextRequest?.selection : undefined,
      );
      case "open-preferences": setActivePage("actions"); return true;
      case "open-component-catalog": setDialog("catalog"); return true;
      case "create-local-component":
        setComponentCreationPoint(invocation.source === "context-menu" && invocation.target?.kind === "canvas" ? invocation.circuitPoint : undefined);
        setDialog("new-component");
        return true;
      case "review-proposals": setDialog("proposals"); return true;
      case "open-child-design":
        if (!contextualInstance) return false;
        void openHierarchy(contextualInstance.component_id);
        return true;
      case "select-all": selectAllCanvas(); return true;
      case "clear-selection":
        canvasRef.current?.cancelPendingConnection();
        setPlacingCycleEdge(false);
        setSelection([]);
        return true;
      case "center-selection":
        if (invocation.source === "context-menu" && contextRequest?.selection.length) {
          setSelection(contextRequest.selection);
          requestAnimationFrame(() => canvasRef.current?.centerSelection());
        } else canvasRef.current?.centerSelection();
        return true;
      case "open-connect":
        setEndpointA(targetTerminalKey(invocation.target) ?? "");
        setEndpointB("");
        setDialog("connect");
        return true;
      case "reroute-selected": {
        if (!graph || !layout || !contextualNetId) return false;
        const route = routeCircuitNets(graph, layout.layout, layout.boundary_geometry, [contextualNetId], false)[contextualNetId];
        if (route) saveRoute(contextualNetId, route);
        return Boolean(route);
      }
      case "lock-selected-route":
      case "unlock-selected-route":
        if (!contextualNetId || !contextualRoute) return false;
        saveRoute(contextualNetId, setAllRouteLocks(contextualRoute, actionId === "lock-selected-route"));
        return true;
      case "arrange-all": void autoLayout(); return true;
      case "add-cycle-edge":
        if (invocation.source === "context-menu" && invocation.circuitPoint) return addCycleEdgeAt(invocation.circuitPoint.x);
        setPlacingCycleEdge(true); setMessage("Click empty canvas to place a cycle edge. Press Escape to cancel."); return true;
      case "open-clock-settings": setDialog("clock-settings"); return true;
      case "open-timing-analysis": setDialog("timing-analysis"); return true;
      case "edit-cycle-edge":
        if (!contextualCycleEdge) return false;
        setSelection([{ kind: "cycle-edge", id: contextualCycleEdge.id }]); setDialog("cycle-edge"); return true;
      case "lock-cycle-edge": return contextualCycleEdge ? updateCycleEdge({ ...contextualCycleEdge, locked: true }) : false;
      case "unlock-cycle-edge": return contextualCycleEdge ? updateCycleEdge({ ...contextualCycleEdge, locked: false }) : false;
      case "delete-cycle-edge":
        if (!contextualCycleEdge) return false;
        return deleteCurrentSelection({ kind: "cycle-edge", id: contextualCycleEdge.id }, [{ kind: "cycle-edge", id: contextualCycleEdge.id }]);
      case "toggle-inspector":
        setPreferences((current) => ({ ...current, ui: { ...current.ui, inspector_open: !current.ui.inspector_open } }));
        return true;
      case "toggle-timing-overlay":
        setPreferences((current) => ({ ...current, ui: { ...current.ui, timing_overlay_visible: !current.ui.timing_overlay_visible } }));
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
      case "run-primary-tool": if (tools[0]) runTool(tools[0].id); return true;
      case "getting-started": setDialog("getting-started"); return true;
      case "about": setDialog("about"); return true;
      case "pan-canvas": return false;
      case "add-bend-here":
        if (!contextualNetId || !contextualRoute || invocation.target?.kind !== "route-segment" || !invocation.circuitPoint) return false;
        saveRoute(contextualNetId, insertRouteBend(contextualRoute, invocation.target.segmentId, invocation.circuitPoint, document?.layout.grid_size ?? 20));
        return true;
      case "remove-bend":
        if (!contextualNetId || !contextualRoute || invocation.target?.kind !== "route-vertex") return false;
        saveRoute(contextualNetId, removeRouteBend(contextualRoute, invocation.target.vertexId));
        return true;
      case "select-connected-net":
        if (!contextualNetId) return false;
        setSelection([{ kind: "net", id: contextualNetId }]);
        return true;
      case "disconnect-port": return disconnectContextTerminal(invocation.target);
      case "delete-boundary-terminal": return deleteBoundaryTarget(invocation.target);
      case "terminal-side-north": return setTerminalSide(invocation.target, "NORTH");
      case "terminal-side-east": return setTerminalSide(invocation.target, "EAST");
      case "terminal-side-south": return setTerminalSide(invocation.target, "SOUTH");
      case "terminal-side-west": return setTerminalSide(invocation.target, "WEST");
      case "terminal-move-earlier": return moveTerminalInOrder(invocation.target, -1);
      case "terminal-move-later": return moveTerminalInOrder(invocation.target, 1);
      case "terminal-lock-placement": return setTerminalPlacementLocked(invocation.target, true);
      case "terminal-unlock-placement": return setTerminalPlacementLocked(invocation.target, false);
      case "terminal-reset-placement": return resetTerminalPlacement(invocation.target);
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
      if (!action || !actionExecutorRef.current({ commandId: action.id, source: "shortcut" })) return;
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
    if (!actionId || !executeCircuitAction({ commandId: actionId, source: "mouse-binding" })) return;
    event.preventDefault();
  }

  function emptyCanvasPointer(event: ReactMouseEvent): boolean {
    return event.target instanceof Element && event.target.classList.contains("react-flow__pane");
  }

  const themeStyle = circuitThemeCssProperties(theme) as CSSProperties;

  return <main className="cd-app standalone-shell" ref={appRef} style={themeStyle}>
    <header className="topbar">
      <div className="brand"><span className="brand-mark">CD</span><h1>Circuit Designer</h1></div>
      <CircuitMenuBar
        bindings={actionBindings}
        dismissVersion={menubarDismissVersion}
        inspectorOpen={inspectorOpen}
        timingOverlayVisible={timingOverlayVisible}
        isActionEnabled={(commandId) => isCommandEnabled({ commandId, source: "menubar" })}
        onAction={(commandId) => { executeCircuitAction({ commandId, source: "menubar" }); }}
        onOpenChange={(open) => { if (open) closeContextMenu(false); }}
        proposalCount={proposals.length}
        sourceBound={Boolean(sourceBinding)}
        sourceSaveLabel={sourceBinding?.saveLabel}
        tools={tools}
        toolsEnabled={Boolean(snapshot) && !lease}
        onRunTool={runTool}
      />
      <div className="document-status" title={sourceDescription}>
        <strong>{document?.label ?? "Loading…"}</strong>
        <small>{sourceBinding ? sourceBinding.writable ? lease ? sourceBinding.draftLabel ?? "source draft" : sourceBinding.boundLabel ?? "source bound" : "source-owned read only" : lease ? "private draft" : `revision ${snapshot?.revision ?? "…"}`}</small>
      </div>
      {sourceBinding?.writable && lease && draftRef.current?.dirty && <button
        className="source-save-button"
        onClick={() => executeCircuitAction({ commandId: "save-document", source: "menubar" })}
        type="button"
      >{sourceBinding.saveLabel ?? "Save to Source"}</button>}
    </header>
    <div className="notice">
      <span className="local-dot" />
      {activePage === "actions" ? "Actions & shortcuts" : sourceBinding?.writable ? sourceBinding.label : linkedDocumentId ? "Source projection" : "Independent document"}
      <span>{activePage === "actions"
        ? `Shared preference file · ${preferenceStatus === "loading" ? "loading…" : preferenceStatus === "saving" ? "saving…" : preferenceStatus === "saved" ? "saved" : "save failed"}`
        : layoutProgress || message}</span>
      {sourceConflict && <span className="source-recovery">
        <button onClick={() => void reopenLatestSource()} type="button">Reopen Latest</button>
        <button onClick={() => { if (document) void downloadCircuitDocument(document); }} type="button">Download Draft JSON</button>
      </span>}
    </div>
    {activePage === "actions" ? <ActionSettingsPage
      onClose={() => setActivePage("canvas")}
      onPreferencesChange={setPreferences}
      preferences={preferences}
      preferenceStatus={preferenceStatus}
    /> : <section className={`workspace${inspectorOpen ? " workspace--inspector-open" : ""}`}>
      <div className="stage">
        <div
          className={`canvas-surface${placingCycleEdge ? " canvas-surface--placing-cycle-edge" : ""}`}
          onClick={(event) => {
            if (!placingCycleEdge && event.detail === 1 && emptyCanvasPointer(event)) runCanvasMouseShortcut("primary-click", event);
          }}
          onDoubleClick={(event) => {
            if (emptyCanvasPointer(event)) runCanvasMouseShortcut("primary-double-click", event);
          }}
          onAuxClick={(event) => {
            if (event.button === 1 && emptyCanvasPointer(event)) runCanvasMouseShortcut("middle-click", event);
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
            onContextMenuRequest={openCanvasContextMenu}
            fitViewOnInit={false}
            showInlineViewportControls={false}
            viewportPanMouseButtons={panMouseButtons(actionBindings["pan-canvas"].mouse)}
            viewportPanActivationKeyCode={reactFlowKeyCode(actionBindings["pan-canvas"].keyboard)}
            wheelZoomEnabled={standardWheelZoomEnabled(actionBindings)}
            useDefaultEscapeBinding={false}
            timing={timing}
            timingAnalysis={timingAnalysis}
            showTimingOverlay={timingOverlayVisible}
            onCycleEdgeChange={updateCycleEdge}
            onCanvasPointClick={(point) => {
              if (!placingCycleEdge) return;
              if (addCycleEdgeAt(point.x)) setPlacingCycleEdge(false);
            }}
            viewport={viewport}
            onViewportChange={setViewport}
          />}
          {layout && <div className="layout-time">Grid router · {layout.elapsed_ms} ms</div>}
        </div>
      </div>
      {inspectorOpen && <aside className="inspector">
        <p className="eyebrow">Inspector</p>
        {sourceBinding?.capabilities.includes("boundary-ports") && <button
          disabled={!lease}
          onClick={addBoundaryPort}
          type="button"
        >New Boundary Port</button>}
        {selection.length === 0 && <div className="empty-inspector"><span>⌁</span><p>Select an instance, boundary terminal, or net to inspect its properties.</p></div>}
        {selection.length > 1 && <div className="multi-inspector"><span className="kind">selection</span><h2>{selection.length} items selected</h2><p>{selection.filter((item) => item.kind === "node").length} instances · {selection.filter((item) => item.kind === "boundary").length} boundary terminals · {selection.filter((item) => item.kind === "net").length} nets</p></div>}
        {selectedInstance && document && <><span className="kind">instance</span><h2>{selectedInstance.label}</h2><code>{selectedInstance.id}</code>
          <label>{sourceBinding ? "Instance name" : "Label"}<input pattern={sourceIdentifierPattern} value={selectedInstance.label} onChange={(event) => {
            const label = event.target.value || selectedInstance.id;
            if (!isSourceIdentifier(label)) {
              setMessage(sourceBinding?.identifierHint ?? "Use a source-compatible instance name.");
              return;
            }
            mutate({ operation_id: operationId("label"), type: "update_instance", instance: { ...selectedInstance, label } }, "Instance name updated.");
          }} disabled={!lease} /></label>
          <details><summary>Canonical data</summary><pre>{JSON.stringify(selectedInstance, null, 2)}</pre></details>
        </>}
        {selectedBoundary && <><span className="kind">boundary terminal</span><h2>{selectedBoundary.label}</h2><code>{selectedBoundary.id}</code>
          <label>Name<input
            disabled={!lease}
            pattern={sourceIdentifierPattern}
            value={selectedBoundary.label}
            onChange={(event) => {
              const label = event.target.value || selectedBoundary.id;
              if (!isSourceIdentifier(label)) {
                setMessage(sourceBinding?.identifierHint ?? "Use a source-compatible boundary-port name.");
                return;
              }
              updateBoundaryPort({ ...selectedBoundary, label });
            }}
          /></label>
          <label>Direction<select
            disabled={!lease}
            value={selectedBoundary.direction}
            onChange={(event) => updateBoundaryPort({ ...selectedBoundary, direction: event.target.value as "input" | "output" | "inout" })}
          ><option value="input">Input</option><option value="output">Output</option><option value="inout">In/out</option></select></label>
          <label>Wire width or range<input
            disabled={!lease}
            value={String(selectedBoundary.width)}
            onChange={(event) => {
              const raw = event.target.value.trim();
              if (!raw) return;
              const width = /^\d+$/.test(raw)
                ? Math.max(1, Number(raw))
                : raw.startsWith("[") || !raw.includes(":") ? raw : `[${raw}]`;
              updateBoundaryPort({ ...selectedBoundary, width });
            }}
          /></label>
          <p className="draw-hint">Width reductions that invalidate connected slices are rejected.</p>
          <details><summary>Canonical data</summary><pre>{JSON.stringify(selectedBoundary, null, 2)}</pre></details>
        </>}
        {selectedNet && <><span className="kind">net</span><h2>{selectedNet.label || selectedNet.id}</h2><code>{selectedNet.id}</code>
          <p className="draw-hint">{selectedRouteLocked ? "Route locked. Use Route → Unlock Selected Route before editing." : "Drag highlighted segments or handles to edit this route."}</p>
          <p className="draw-hint">{selectedNet.endpoints.map((endpoint) => JSON.stringify(endpoint)).join("\n")}</p>
          <details><summary>Canonical data</summary><pre>{JSON.stringify(selectedNet, null, 2)}</pre></details>
        </>}
        {selectedCycleEdge && <><span className="kind">cycle edge</span><h2>{selectedCycleEdge.label ?? `Cycle edge ${timing.cycle_edges.findIndex((edge) => edge.id === selectedCycleEdge.id) + 1}`}</h2><code>x = {selectedCycleEdge.x}</code>
          <p className="draw-hint">Every same-domain path crossing this marker gains one cycle.</p>
          <button disabled={!lease} onClick={() => setDialog("cycle-edge")} type="button">Edit edge</button>
          <button disabled={!lease} onClick={() => updateCycleEdge({ ...selectedCycleEdge, locked: !selectedCycleEdge.locked })} type="button">{selectedCycleEdge.locked ? "Unlock edge" : "Lock edge"}</button>
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
      onClose={() => { setDialog(undefined); setComponentCreationPoint(undefined); }}
      onComponentNameChange={setComponentName}
      onCreateComponent={addLocalComponent}
      onPlaceComponent={placeCatalogComponent}
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
      sourceIdentifierPattern={sourceIdentifierPattern}
      sourceIdentifierHint={sourceBinding?.identifierHint}
      terminals={terminals}
      timing={timing}
      timingAnalysis={timingAnalysis}
      selectedCycleEdge={selectedCycleEdge}
      selectedTimingSubject={selectedTimingSubject}
      onSetClockDomain={setClockDomain}
      onRemoveClockDomain={removeClockDomain}
      onAssignClockDomain={assignClockDomain}
      onUpdateCycleEdge={updateCycleEdge}
    />
    {contextRequest && <CircuitContextMenu<CircuitCommandId>
      entries={contextEntries}
      isCommandEnabled={(commandId) => isCommandEnabled({
        commandId,
        source: "context-menu",
        target: contextRequest.target,
        clientPoint: contextRequest.clientPoint,
        circuitPoint: contextRequest.flowPoint,
      })}
      onCommand={(commandId) => { executeCircuitAction({
        commandId,
        source: "context-menu",
        target: contextRequest.target,
        clientPoint: contextRequest.clientPoint,
        circuitPoint: contextRequest.flowPoint,
      }); }}
      onDismiss={closeContextMenu}
      point={contextRequest.clientPoint}
      portalContainer={appRef.current ?? undefined}
      shortcutFor={(commandId) => commandId in actionBindings
        && actionBindings[commandId as CircuitActionId].keyboard
        ? formatKeyboardShortcut(actionBindings[commandId as CircuitActionId].keyboard)
        : undefined}
    />}
    {confirmation && <CircuitConfirmationDialog
      confirmLabel={confirmation.confirmLabel}
      message={confirmation.message}
      onCancel={() => setConfirmation(undefined)}
      onConfirm={confirmation.onConfirm}
      title={confirmation.title}
    />}
  </main>;
}

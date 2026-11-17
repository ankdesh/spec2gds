/** Reusable Circuit application orchestration over host-provided adapters.
 * Accepted snapshots, leased drafts, visual layout work and source-save receipts
 * have separate lifecycles. Follow draftRef for in-flight gesture state and the
 * source adapter for durable package writes; React rendering owns neither. */
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
  publicFilenameStem,
  availableHumanName,
  circuitTerminalLabel,
  circuitEndpointLabel,
  planConnection,
  ConnectionChoiceRequired,
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
  circuitThemeCssProperties,
  getCircuitTheme,
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
import { connectionEndpoint } from "./connection-input";
import { ActionSettingsPage } from "./ActionSettingsPage";
import { CircuitMenuBar } from "./CircuitMenuBar";
import { CircuitConfirmationDialog, CircuitSvDispositionDialog, CircuitDialogs, type CircuitDialogId } from "./CircuitDialogs";
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
const isLeaseConflict = (reason: unknown): boolean => Boolean(reason && typeof reason === "object"
  && (("status" in reason && reason.status === 423) || ("code" in reason && reason.code === "lock_conflict")));

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
  theme: hostTheme,
  tools = [],
  onLaunchChange,
}: CircuitDesignerAppProps) {
  const [activePage, setActivePage] = useState<"canvas" | "actions">("canvas");
  const initialCachedPreferences = useMemo(() => preferencesAdapter.readCached?.(), [preferencesAdapter]);
  const [preferences, setPreferences] = useState<CircuitDesignerPreferencesV1>(
    () => initialCachedPreferences ?? createDefaultCircuitDesignerPreferences(),
  );
  const theme = useMemo(() => hostTheme ?? getCircuitTheme(preferences.ui.theme_id), [hostTheme, preferences.ui.theme_id]);
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
  const [clientId] = useState(() => `circuit_${browserRandomUuid()}`);
  const [remoteLease, setRemoteLease] = useState<EditLease | null>(null);
  const [leaseLost, setLeaseLost] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [sourceBinding, setSourceBinding] = useState<CircuitSourceState>();
  const [svChoiceOpen, setSvChoiceOpen] = useState(false);
  const [sourceBusy, setSourceBusy] = useState(false);
  const savingRef = useRef(false);
  const transitioningRef = useRef(false);
  const transitionRequestRef = useRef<string>();
  const discardRequestRef = useRef<string>();
  const creationLeaseRef = useRef<string>();
  const sourceSaveRef = useRef<{ version: number; batch: ReturnType<CircuitDraft["toBatch"]>; disposition?: "retain_reference" | "remove"; leaseId: string }>();
  const [sourceConflict, setSourceConflict] = useState(false);
  const [layout, setLayout] = useState<LayoutResult>();
  const [layoutProgress, setLayoutProgress] = useState("");
  const [selection, setSelection] = useState<CircuitCanvasSelection>([]);
  const [message, setMessage] = useState("Ready. Unlock to make a private draft.");
  const [saveError, setSaveError] = useState("");
  useEffect(() => setSaveError(""), [snapshot?.document.document_id]);
  const [componentName, setComponentName] = useState("");
  const [endpointA, setEndpointA] = useState("");
  const [endpointB, setEndpointB] = useState("");
  const [netName, setNetName] = useState("");
  const [existingNetId, setExistingNetId] = useState<string | undefined>();
  const [connectionError, setConnectionError] = useState("");
  const [sliceLsb, setSliceLsb] = useState(0);
  const [sliceLsbB, setSliceLsbB] = useState(0);
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
  const layoutGraphRef = useRef<ReturnType<typeof projectDocument>>();
  const fittedDocumentRef = useRef<string>();
  const pendingArrangeFitRef = useRef<{ documentId: string; operations: string }>();
  const arrangeRequestRef = useRef(0);
  const draftChangeRef = useRef(0);
  const actionExecutorRef = useRef<(invocation: CircuitActionInvocation) => boolean>(() => false);
  const preferencesHydratedRef = useRef(false);
  const savedPreferencesRef = useRef("");
  const currentLeaseRef = useRef(lease);
  currentLeaseRef.current = lease;
  const currentSnapshotRef = useRef(snapshot);
  currentSnapshotRef.current = snapshot;
  const currentDocumentIdRef = useRef(snapshot?.document.document_id);
  currentDocumentIdRef.current = snapshot?.document.document_id;
  const acquiringRef = useRef(false);

  const actionBindings = preferences.action_bindings;
  const inspectorOpen = preferences.ui.inspector_open;
  const timingOverlayVisible = preferences.ui.timing_overlay_visible;
  useEffect(() => {
    if (!source?.checkAccess || !snapshot || !sourceBinding) return;
    let active = true;
    const documentId = snapshot.document.document_id;
    const check = async () => {
      try {
        if (!await source.checkAccess!(documentId) && active) {
          setSourceBinding(current => current ? { ...current, writable: false, capabilities: [], message: "Spec editing ended. Your private draft is preserved. Request new access from Spec Editor." } : current);
          setMessage("Spec editing ended. Your private draft is preserved; saving is disabled.");
        }
      } catch { /* A network error does not discard the draft or claim revocation. */ }
    };
    void check();
    const timer = window.setInterval(() => void check(), 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, [source, snapshot?.document.document_id, sourceBinding?.id]);
  const canEditCircuit = Boolean(lease && (!sourceBinding || sourceBinding.writable) && !sourceBusy && !sourceSaveRef.current);
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
            : binding?.message ?? `Read-only projection managed by ${binding?.label ?? "an external source"}.`);
          setMessage(binding?.writable
            ? `Opened ${next.document.label} for source editing.`
            : binding?.message ?? `Opened ${next.document.label}.`);
          draftRef.current = undefined;
          return;
        }
        let joined = false;
        let next: CircuitSnapshot | undefined;
        try {
          const known = await backend.listDocuments();
          initial.label = availableHumanName(initial.label, known.filter(item => item.document_id !== initial.document_id).map(item => item.label));
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
          ? `Joined ${next.document.label}.`
          : `Opened ${next.document.label}.`);
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
      if (active) {
        layoutGraphRef.current = graph;
        setLayout(result);
      }
    }).catch((reason) => {
      if (active) setMessage(`Layout failed: ${String(reason)}`);
    });
    return () => { active = false; };
  }, [graph]);

  useEffect(() => {
    if (!graph) return;
    const key = `${graph.document_id}:${graph.design.id}`;
    if (!graph.nodes.length && !graph.terminals.length) { fittedDocumentRef.current = key; return; }
    if (!layout || layoutGraphRef.current !== graph) return;
    const pending = pendingArrangeFitRef.current;
    const arrangeFit = pending?.documentId === graph.document_id
      && pending.operations === JSON.stringify(draftRef.current?.operations);
    if (fittedDocumentRef.current === key && !arrangeFit) return;
    const frame = requestAnimationFrame(() => {
      canvasRef.current?.fitView();
      fittedDocumentRef.current = key;
      if (arrangeFit) pendingArrangeFitRef.current = undefined;
    });
    return () => cancelAnimationFrame(frame);
  }, [graph, layout]);

  useEffect(() => {
    if (!snapshot || !backend) return;
    void backend.listProposals(snapshot.document.document_id).then(setProposals);
  }, [backend, snapshot]);

  useEffect(() => {
    if (!snapshot || !events) return;
    const documentId = snapshot.document.document_id;
    return events.subscribe(documentId, (event) => {
      if (event.kind === "lock.changed") {
        void inspectLease(documentId).catch(() => undefined);
        return;
      }
      if (event.kind === "proposal.changed") {
        void backend.listProposals(documentId).then(setProposals).catch(() => undefined);
        return;
      }
      if (event.kind !== "document.changed" || draftRef.current) return;
      void backend.get(documentId).then((next) => {
        if (currentDocumentIdRef.current !== documentId || draftRef.current) return;
        // A queued refresh can finish after a local save. Compare with the
        // current revision, not the snapshot captured by this subscription.
        if (next.revision === currentSnapshotRef.current?.revision) return;
        currentSnapshotRef.current = next;
        setSnapshot(next);
        setDocument(next.document);
        setSelection([]);
        setLayout(undefined);
        setMessage(`Updated ${next.document.label} from another client.`);
        if (source) void source.load(documentId).then(binding => {
          if (currentDocumentIdRef.current === documentId && !draftRef.current) setSourceBinding(binding);
        }).catch(() => undefined);
      }).catch((reason) => {
        setMessage(`Could not refresh the REST session: ${reason instanceof Error ? reason.message : String(reason)}`);
      });
    });
  }, [backend, events, lease, snapshot?.document.document_id, snapshot?.revision]);

  async function inspectLease(documentId: string): Promise<void> {
    if (transitioningRef.current) return;
    const held = currentLeaseRef.current;
    const current = await backend.getLease(documentId);
    if (transitioningRef.current || held !== currentLeaseRef.current || currentDocumentIdRef.current !== documentId) return;
    setRemoteLease(current);
    if (held && current?.lease_id !== held.lease_id) {
      currentLeaseRef.current = undefined;
      setLease(undefined);
      setLeaseLost(true);
      setMessage("Editing permission was lost. Your draft is preserved for download. Discard it before starting a new draft.");
    }
  }

  useEffect(() => {
    if (!snapshot) return;
    setLeaseLost(false);
    setRemoteLease(null);
    let active = true;
    void backend.getLease(snapshot.document.document_id).then(current => { if (active) setRemoteLease(current); }).catch(() => undefined);
    return () => { active = false; };
  }, [backend, snapshot?.document.document_id]);

  useEffect(() => {
    if (!lease || !snapshot) return;
    const documentId = snapshot.document.document_id;
    let active = true;
    const renew = async () => {
      try {
        const renewed = await backend.renewLease(documentId, lease.lease_id);
        if (active && currentLeaseRef.current?.lease_id === lease.lease_id) {
          currentLeaseRef.current = renewed;
          setLease(renewed);
          setRemoteLease(renewed);
        }
      } catch (reason) {
        if (!active) return;
        if (isLeaseConflict(reason)) await inspectLease(documentId).catch(() => undefined);
        else if (Date.parse(currentLeaseRef.current?.expires_at ?? "") <= Date.now()) {
          currentLeaseRef.current = undefined;
          setLease(undefined);
          setLeaseLost(true);
          setMessage("Editing permission expired. Your draft is preserved for download or discard.");
        } else setMessage("Could not renew editing permission. Your draft is preserved; saving still requires a valid lease.");
      }
    };
    const timer = window.setInterval(() => void renew(), 60_000);
    const resume = () => { if (globalThis.document.visibilityState === "visible") void renew(); };
    const release = () => backend.releaseLeaseOnExit?.(documentId, lease.lease_id);
    window.addEventListener("pagehide", release);
    globalThis.document.addEventListener("visibilitychange", resume);
    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener("pagehide", release);
      globalThis.document.removeEventListener("visibilitychange", resume);
      // The release compares lease IDs, so it cannot release a successor's lease.
      if (currentLeaseRef.current?.lease_id === lease.lease_id) release();
    };
  }, [backend, lease?.lease_id, snapshot?.document.document_id]);

  function mutate(operation: CircuitOperation, success: string): boolean {
    return mutateBatch([operation], success);
  }

  function mutateBatch(operations: CircuitOperation[], success: string): boolean {
    const draft = draftRef.current;
    if (!draft || !canEditCircuit || savingRef.current) {
      setMessage(sourceBinding && !sourceBinding.writable ? "Select Edit → Create internal Design before changing this Component." : "Begin editing before changing this circuit.");
      return false;
    }
    const diagnostics = draft.applyBatch(operations);
    const errors = diagnostics.filter((item) => item.severity === "error");
    if (errors.length) {
      setMessage(errors.map((item) => item.message).join(" · "));
      return false;
    }
    setDocument(draft.document);
    draftChangeRef.current += 1;
    setMessage(success);
    return true;
  }

  async function unlock(): Promise<void> {
    if (!snapshot || !backend || lease || acquiringRef.current) return;
    if (draftRef.current || recovering) { setMessage("Download or discard the preserved draft before starting another draft."); return; }
    acquiringRef.current = true;
    try {
      const nextLease = await backend.acquireLease(snapshot.document.document_id, clientId);
      const latest = await backend.get(snapshot.document.document_id);
      if (currentDocumentIdRef.current !== latest.document.document_id) {
        await backend.releaseLease(latest.document.document_id, nextLease.lease_id);
        return;
      }
      setSnapshot(latest);
      draftRef.current = new CircuitDraft(latest.document, latest.revision);
      setLease(nextLease);
      currentLeaseRef.current = nextLease;
      setRemoteLease(nextLease);
      setLeaseLost(false);
      setDocument(draftRef.current.document);
      setMessage(sourceBinding?.capabilities.includes("create-internal-design") ? "Editing permission acquired. Select Edit → Create internal Design." : "Private draft opened. Save commits atomically; Cancel discards it.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
      await inspectLease(snapshot.document.document_id).catch(() => undefined);
    } finally { acquiringRef.current = false; }
  }

  function confirmTakeover(): void {
    if (!snapshot || !remoteLease || lease || recovering || draftRef.current) return;
    const documentId = snapshot.document.document_id;
    const expectedLeaseId = remoteLease.lease_id;
    setConfirmation({
      title: "Take over editing?",
      message: "The other draft will lose permission to save. Its unsaved changes will not transfer. Your new draft will start from the latest saved source.",
      confirmLabel: "Take over editing",
      onConfirm: () => {
        setConfirmation(undefined);
        setRecovering(true);
        void (async () => {
          try {
            const result = sourceBinding
              ? await source?.recover?.(documentId, expectedLeaseId, clientId)
              : { lease: await backend.takeOverLease(documentId, expectedLeaseId, clientId), snapshot: await backend.get(documentId), state: undefined };
            if (!result) throw new Error("This host does not support source draft recovery.");
            if (currentDocumentIdRef.current !== documentId) {
              await backend.releaseLease(documentId, result.lease.lease_id);
              return;
            }
            setSnapshot(result.snapshot);
            setDocument(result.snapshot.document);
            setSourceBinding(result.state ?? sourceBinding);
            setLayout(undefined);
            setSelection([]);
            draftRef.current = new CircuitDraft(result.snapshot.document, result.snapshot.revision);
            currentLeaseRef.current = result.lease;
            setLease(result.lease);
            setRemoteLease(result.lease);
            setLeaseLost(false);
            setSourceConflict(false);
            setMessage("Editing taken over. The new draft uses the latest saved source.");
          } catch (reason) {
            setMessage(reason instanceof Error ? reason.message : String(reason));
            await inspectLease(documentId).catch(() => undefined);
          } finally { setRecovering(false); }
        })();
      },
    });
  }

  async function createInternalDesign(): Promise<void> {
    if (!snapshot || !lease || !source?.prepareInternalDesign || sourceBusy) return;
    transitionRequestRef.current ??= operationId("prepare_design");
    creationLeaseRef.current = lease.lease_id;
    setSourceBusy(true);
    transitioningRef.current = true;
    try {
      const result = await source.prepareInternalDesign(snapshot.document.document_id, lease.lease_id, transitionRequestRef.current);
      if (!result.accepted || !result.snapshot || !result.lease || !result.state) throw new Error(result.diagnostics.map(item => item.message).join(" · ") || "Could not prepare the internal Design.");
      currentSnapshotRef.current = result.snapshot;
      setSnapshot(result.snapshot);
      setDocument(result.snapshot.document);
      setSourceBinding(result.state);
      setSourceDescription(result.state.message ?? "Private internal Design. Save to Spec to create and assign it.");
      currentLeaseRef.current = result.lease;
      creationLeaseRef.current = result.lease.lease_id;
      setLease(result.lease);
      setRemoteLease(result.lease);
      setLeaseLost(false);
      draftRef.current = new CircuitDraft(result.snapshot.document, result.snapshot.revision);
      sourceSaveRef.current = undefined;
      transitionRequestRef.current = undefined;
      setLayout(undefined);
      setSelection([]);
      setMessage("Private internal Design opened. Save to Spec creates and assigns it. Cancel changes discards it.");
    } catch (reason) {
      setMessage(`Could not confirm Design preparation. Retry Create internal Design. ${reason instanceof Error ? reason.message : String(reason)}`);
    } finally { transitioningRef.current = false; setSourceBusy(false); }
  }

  async function save(disposition?: "retain_reference" | "remove"): Promise<void> {
    if (savingRef.current || sourceBusy) return;
    if (sourceBinding?.pendingInternalDesign && sourceBinding.svChoiceRequired && !disposition && !sourceSaveRef.current) {
      setSvChoiceOpen(true);
      return;
    }
    setSvChoiceOpen(false);
    setSaveError("");
    savingRef.current = true;
    setSourceBusy(true);
    try { await saveDraft(disposition); }
    catch (reason) {
      setSaveError(reason instanceof Error ? reason.message : String(reason));
      if (isLeaseConflict(reason) && snapshot) {
        await inspectLease(snapshot.document.document_id).catch(() => undefined);
        setMessage("Editing permission changed. Your draft is preserved for download or discard.");
      } else setMessage(`Save failed. The complete draft is preserved. ${reason instanceof Error ? reason.message : String(reason)}`);
    } finally { savingRef.current = false; setSourceBusy(false); }
  }

  async function saveDraft(disposition?: "retain_reference" | "remove"): Promise<void> {
    const draft = draftRef.current;
    const saveLeaseId = lease?.lease_id ?? sourceSaveRef.current?.leaseId;
    if (!snapshot || !backend || !saveLeaseId || !draft) return;
    if (!draft.dirty && !sourceBinding?.pendingInternalDesign) {
      await cancel();
      return;
    }
    if (sourceBinding) {
      if (!sourceBinding.writable) return;
      if (!layout || layoutGraphRef.current !== graph) {
        setSaveError("Wait for the circuit layout to finish, then save again.");
        setMessage("Wait for the visible circuit layout before saving to the source.");
        return;
      }
      // Persist the actual visible geometry alongside semantic edits. Generated
      // layout is not source state until it joins this revision-guarded save batch.
      const retry = sourceSaveRef.current?.version === draftChangeRef.current ? sourceSaveRef.current : undefined;
      const materialize: CircuitOperation[] = retry ? [] : [
        // Layout settings also give a blank Design a valid source-save batch.
        { operation_id: operationId("save_layout"), type: "set_layout_settings", direction: layout.layout.direction, grid_size: draft.document.layout.grid_size },
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
        setSaveError(materializeErrors.map((item) => item.message).join(" · "));
        setMessage(materializeErrors.map((item) => item.message).join(" · "));
        return;
      }
      setDocument(draft.document);
      if (!retry) draftChangeRef.current += 1;
      if (!source) {
        setSaveError("This host did not provide a writable source adapter.");
        setMessage("This host did not provide a writable source adapter.");
        return;
      }
      const pendingSave = retry ?? { version: draftChangeRef.current, batch: draft.toBatch(operationId("source_save")), disposition, leaseId: saveLeaseId };
      sourceSaveRef.current = pendingSave;
      let result;
      try {
        result = await source.commit(
          snapshot.document.document_id,
          pendingSave.batch,
          pendingSave.leaseId,
          stagedProposalId,
          pendingSave.disposition,
        );
      } catch (reason) {
        if (isLeaseConflict(reason)) throw reason;
        setSaveError(`The save response could not be confirmed. Retry Save to Spec. ${reason instanceof Error ? reason.message : String(reason)}`);
        setMessage(`The source save response was lost or failed. The complete draft is preserved; retry the save. ${reason instanceof Error ? reason.message : String(reason)}`);
        return;
      }
      if (!result.accepted || !result.snapshot) {
        sourceSaveRef.current = undefined;
        setSaveError(result.diagnostics.map((item) => item.message).join(" · ") || "The Spec service rejected the save.");
        const conflict = result.diagnostics.some((item) => item.code === "source_revision_conflict");
        setSourceConflict(conflict);
        setMessage(result.diagnostics.map((item) => item.message).join(" · ") || "Source save was rejected.");
        return;
      }
      // Close the private draft only after the adapter returns its authoritative
      // snapshot. Rejected or uncertain saves above preserve the complete draft.
      currentSnapshotRef.current = result.snapshot;
      sourceSaveRef.current = undefined;
      creationLeaseRef.current = undefined;
      draftRef.current = undefined;
      setLease(undefined);
      currentLeaseRef.current = undefined;
      setLeaseLost(false);
      setRemoteLease(null);
      setStagedProposalId(undefined);
      setSnapshot(result.snapshot);
      setDocument(result.snapshot.document);
      setSelection([]);
      setSourceBinding(result.state ?? { ...sourceBinding, revision: result.revision });
      setSourceConflict(false);
      setMessage("Changes saved to the source. Edit mode closed.");
      void backend.listProposals(snapshot.document.document_id).then(setProposals).catch(() => undefined);
      return;
    }
    const result = await backend.commit(
      snapshot.document.document_id,
      draft.toBatch(operationId("draft_save")),
      saveLeaseId,
    );
    if (result.status !== "accepted" || !result.snapshot) {
      setSaveError(result.diagnostics.map((item) => item.message).join(" · ") || "The Circuit service rejected the save.");
      setMessage(result.diagnostics.map((item) => item.message).join(" · "));
      return;
    }
    try { await backend.releaseLease(snapshot.document.document_id, saveLeaseId); }
    catch (reason) { if (!isLeaseConflict(reason)) throw reason; }
    currentSnapshotRef.current = result.snapshot;
    draftRef.current = undefined;
    setLease(undefined);
    currentLeaseRef.current = undefined;
    setLeaseLost(false);
    setRemoteLease(null);
    setSnapshot(result.snapshot);
    setDocument(result.snapshot.document);
    await downloadCircuitDocument(result.snapshot.document);
    setMessage(`Saved and downloaded ${circuitDocumentFilename(result.snapshot.document)}.`);
  }

  async function reopenLatestSource(): Promise<void> {
    if (!snapshot || !sourceBinding || !source) return;
    if (sourceBinding.pendingInternalDesign) { await cancel(); return; }
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
    setSaveError("");
    void backend.listProposals(snapshot.document.document_id).then(setProposals).catch(() => undefined);
    setMessage("Reopened the latest source revision. The previous unsaved draft was discarded.");
  }

  async function cancel(): Promise<void> {
    if (!snapshot || !backend) return;
    let releaseWarning = "";
    let restored: CircuitSnapshot | undefined;
    let releaseLease = lease;
    let displaced = false;
    if (sourceBinding?.pendingInternalDesign) {
      const current = await backend.getLease(snapshot.document.document_id);
      if (current && current.lease_id !== (lease?.lease_id ?? creationLeaseRef.current)) {
        // Discard only this client's preserved draft after takeover. The new
        // designer's lease and pending source state must remain intact.
        restored = await backend.get(snapshot.document.document_id);
        const latestState = await source?.load(snapshot.document.document_id);
        setSnapshot(restored);
        currentSnapshotRef.current = restored;
        setSourceBinding(latestState);
        setRemoteLease(current);
        setLayout(undefined);
        setSelection([]);
        releaseLease = undefined;
        displaced = true;
      }
    }
    if (!displaced && (sourceBinding?.pendingInternalDesign || transitionRequestRef.current)) {
      transitioningRef.current = true;
      try {
        let leaseId = lease?.lease_id ?? creationLeaseRef.current;
        if (!leaseId || !source?.discardInternalDesign) throw new Error("The source adapter cannot discard this pending Design.");
        let pending = sourceBinding?.pendingInternalDesign;
        if (transitionRequestRef.current && !pending) {
          const latestState = await source.load(snapshot.document.document_id);
          if (!latestState) throw new Error("Could not confirm whether Design preparation succeeded.");
          pending = latestState.pendingInternalDesign;
          if (pending) {
            try {
              const prepared = await source.prepareInternalDesign?.(snapshot.document.document_id, leaseId, transitionRequestRef.current);
              if (!prepared?.accepted || !prepared.lease) throw new Error("Retry Create internal Design to confirm preparation before discarding it.");
              leaseId = prepared.lease.lease_id;
              creationLeaseRef.current = leaseId;
              currentLeaseRef.current = prepared.lease;
            } catch (reason) {
              // An expired lease can still discard. A successor's lease will
              // reject the discard below and preserve this client's draft.
              if (!isLeaseConflict(reason)) throw reason;
            }
          } else setSourceBinding(latestState);
        }
        if (pending) {
          discardRequestRef.current ??= operationId("discard_design");
          const result = await source.discardInternalDesign(snapshot.document.document_id, leaseId, discardRequestRef.current);
          if (!result.accepted || !result.snapshot || !result.state) throw new Error(result.diagnostics.map(item => item.message).join(" · ") || "Could not discard the pending Design.");
          restored = result.snapshot;
          releaseLease = result.lease;
          currentLeaseRef.current = result.lease;
          setSnapshot(restored);
          currentSnapshotRef.current = restored;
          setSourceBinding(result.state);
          setSourceDescription(result.state.message ?? "Component interface preview.");
          setLayout(undefined);
          setSelection([]);
        }
      } catch (reason) {
        setMessage(`Discard failed. Your draft is preserved. ${reason instanceof Error ? reason.message : String(reason)}`);
        return;
      } finally { transitioningRef.current = false; }
    }
    sourceSaveRef.current = undefined;
    transitionRequestRef.current = undefined;
    discardRequestRef.current = undefined;
    creationLeaseRef.current = undefined;
    if (releaseLease) {
      try { await backend.releaseLease(snapshot.document.document_id, releaseLease.lease_id); }
      catch (reason) {
        if (!isLeaseConflict(reason)) {
          releaseWarning = ` Lease release failed; it will expire automatically. ${String(reason)}`;
        }
      }
    }
    draftRef.current?.cancel();
    draftRef.current = undefined;
    setLease(undefined);
    currentLeaseRef.current = undefined;
    setLeaseLost(false);
    setStagedProposalId(undefined);
    setDocument((restored ?? snapshot).document);
    setSaveError("");
    setSourceConflict(false);
    setMessage(`Draft cancelled. No changes were persisted.${releaseWarning}`);
    try {
      const latest = await backend.get(snapshot.document.document_id);
      if (currentDocumentIdRef.current === latest.document.document_id && !draftRef.current) {
        setSnapshot(latest);
        setDocument(latest.document);
        if (sourceBinding) {
          const binding = await source?.load(latest.document.document_id);
          if (currentDocumentIdRef.current === latest.document.document_id && !draftRef.current) setSourceBinding(binding);
        }
      }
    } catch { /* Retain the readable accepted snapshot if the service is unavailable. */ }
  }

  function undoDraft(direction: "undo" | "redo"): void {
    const draft = draftRef.current;
    if (!draft) return;
    setDocument(direction === "undo" ? draft.undo() : draft.redo());
    draftChangeRef.current += 1;
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
    const operations: CircuitOperation[] = [
      { operation_id: operationId("component"), type: "add_component", component },
      {
        operation_id: operationId("instance"),
        type: "add_instance",
        instance: { id: instanceId, label: sourceBinding ? instanceId : componentName.trim(), component_id: componentId, parameter_values: {} },
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

  function placeCatalogComponent(componentId: string, requestedName?: string): boolean {
    if (!document || !lease) return false;
    const component = document.components.find((item) => item.id === componentId);
    if (!component) return false;
    const instanceId = requestedName?.trim() || uniqueSlug(component.label, document.design.instances.map((item) => item.id));
    if (mutate({
      operation_id: operationId("instance"),
      type: "add_instance",
      instance: { id: instanceId, label: instanceId, component_id: component.id, parameter_values: {} },
    }, `Placed ${component.label} as ${instanceId}.`)) {
      setSelection([{ kind: "node", id: instanceId }]);
      return true;
    }
    return false;
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

  function createNet(source: string, target: string, requestedName = "", lsb = sliceLsb, width = sliceWidth, lsbB = lsb): boolean {
    if (!document || !source || !target || source === target) return false;
    const label = requestedName.trim() || `${sourceBinding ? "net_" : "net "}${document.design.nets.length + 1}`;
    if (!isSourceIdentifier(label)) {
      const error = sourceBinding?.identifierHint ?? "Use a source-compatible connection name.";
      setMessage(error);
      setConnectionError(error);
      return false;
    }
    const id = uniqueSlug(label, document.design.nets.map((item) => item.id));
    return applyConnection([
      connectionEndpoint(source, lsb, width, graph?.terminals.find(item => item.id === source)?.width),
      connectionEndpoint(target, lsbB, width, graph?.terminals.find(item => item.id === target)?.width),
    ], id, label);
  }

  function applyConnection(endpoints: NetEndpoint[], id: string, label: string, selectedNetId?: string): boolean {
    if (!document) return false;
    try {
      const operation = planConnection(document, endpoints, {
        operationId: operationId("net"), netId: id, label, existingNetId: selectedNetId,
        route: selectedNetId ? layout?.layout.net_routes[selectedNetId] : undefined,
      });
      if (!operation) {
        setConnectionError("");
        setMessage("These endpoints are already connected.");
        return true;
      }
      // Visible routes may not yet be materialized in the private draft.
      if (operation.type === "connect_endpoint") {
        const route = layout?.layout.net_routes[operation.net_id];
        if (route?.vertices.some(item => item.locked) || route?.segments.some(item => item.locked)) throw new Error("Unlock this net's route before adding an endpoint.");
      }
      // Freeze the visible placement and unrelated routes before changing
      // topology. Otherwise an automatic layout can move the whole diagram.
      const geometry: CircuitOperation[] = layout ? [
        ...Object.entries(layout.layout.node_geometry).filter(([id]) => document.design.instances.some(item => item.id === id))
          .map(([id, value]): CircuitOperation => ({ operation_id: operationId("connection_geometry"), type: "set_instance_geometry", instance_id: id, geometry: value })),
        ...Object.entries(layout.layout.terminal_placements).filter(([id]) => graph?.terminals.some(item => item.id === id))
          .map(([id, value]): CircuitOperation => ({ operation_id: operationId("connection_placement"), type: "set_terminal_placement", terminal_key: id, placement: value })),
        ...Object.entries(layout.layout.net_routes).filter(([id]) => document.design.nets.some(item => item.id === id))
          .map(([id, value]): CircuitOperation => ({ operation_id: operationId("connection_route"), type: "set_net_route", net_id: id, route: value })),
      ] : [];
      const changed = mutateBatch([...geometry, operation], operation.type === "connect_endpoint" ? "Endpoint added to the existing net." : `Created net “${label}”.`);
      if (!changed) return false;
      setConnectionError("");
      setSelection([{ kind: "net", id: operation.type === "connect_endpoint" ? operation.net_id : id }]);
      return true;
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : String(reason);
      setMessage(message);
      setConnectionError(message);
      if (reason instanceof ConnectionChoiceRequired) {
        setExistingNetId("");
        setEndpointA(endpointTerminalKey(endpoints[0]));
        setEndpointB(endpointTerminalKey(endpoints[1]));
        setDialog("connect");
      }
      return false;
    }
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
    return mutate({ operation_id: operationId("cycle_edge"), type: "update_cycle_edge", edge }, `Updated ${edge.label ?? "Timing relationship"}.`);
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
    const draft = draftRef.current;
    if (!document || !draft || !lease) {
      setMessage("Unlock before applying automatic layout.");
      return;
    }
    const requestId = ++arrangeRequestRef.current;
    const changeBefore = draftChangeRef.current;
    const leaseId = lease.lease_id;
    setLayoutProgress("Starting layout…");
    try {
      const task = createLayoutTask(document, {
        layout: { preserveNodeGeometry: "pinned" },
        onProgress: (phase, progress) => {
          if (arrangeRequestRef.current === requestId && draftRef.current === draft) setLayoutProgress(`${phase} · ${Math.round(progress * 100)}%`);
        },
      });
      const result = await task.result;
      if (arrangeRequestRef.current !== requestId || draftRef.current !== draft
        || currentLeaseRef.current?.lease_id !== leaseId || currentDocumentIdRef.current !== document.document_id
        || draftChangeRef.current !== changeBefore) return;
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
      if (mutateBatch(operations, `Automatic layout completed in ${result.elapsed_ms} ms.`)) {
        pendingArrangeFitRef.current = { documentId: document.document_id, operations: JSON.stringify(draft.operations) };
        setLayout(undefined);
      }
    } catch (reason) {
      if (draftRef.current === draft && arrangeRequestRef.current === requestId) setMessage(reason instanceof Error ? reason.message : String(reason));
    } finally {
      if (arrangeRequestRef.current === requestId) setLayoutProgress("");
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
      const options = { boundaryGeometry: layout.boundary_geometry, theme };
      const stem = publicFilenameStem(snapshot.document.label || snapshot.document.design.label || "Circuit");
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
      const displayName = parsed.document.label;
      telemetry.event("documents", "file_opened", "Opened circuit file", "info", { filename: opened.displayName, document: parsed.document });
      let joined = false;
      let next: CircuitSnapshot | undefined;
      try {
        next = (await backend.create(parsed.document, operationId("open_file"))).snapshot;
      } catch (reason) {
        if (!isConflictError(reason)) throw reason;
        const existing = await backend.get(parsed.document.document_id);
        if (exportCircuitJson(existing.document) !== exportCircuitJson(parsed.document)) {
          setMessage(
            `Could not open ${displayName}: this source identity is already bound to different contents.`,
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
        `${joined ? "Joined matching session for" : "Opened"} ${displayName}`
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
    // Source-bound Accept stages a leased private draft. Only Save to Spec
    // runs owner preview/commit; accepting a proposal is not a durable source save.
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
        nextLease = await backend.acquireLease(document.document_id, clientId);
        const draft = new CircuitDraft(snapshot.document, snapshot.revision);
        const diagnostics = draft.applyBatch(proposal.batch.operations);
        const errors = diagnostics.filter(item => item.severity === "error");
        if (errors.length) throw new Error(errors.map(item => item.message).join(" · "));
        draftRef.current = draft;
        setLease(nextLease);
        setStagedProposalId(proposalId);
        setDocument(draft.document);
        setMessage("Proposal staged in a private draft. Save to Spec to persist it, or Cancel to discard the draft.");
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
    if (target.kind === "terminal") return target.parent.kind === "node"
      ? { kind: "node", id: target.parent.id }
      : { kind: "boundary", id: target.parent.id };
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
    if (existingNetId === "") { setConnectionError("Choose an existing net."); return false; }
    const created = existingNetId
      ? applyConnection([connectionEndpoint(endpointB, sliceLsbB, sliceWidth, graph?.terminals.find(item => item.id === endpointB)?.width)], "", "", existingNetId)
      : createNet(endpointA, endpointB, netName, sliceLsb, sliceWidth, sliceLsbB);
    if (!created) return false;
    setNetName("");
    setEndpointA("");
    setEndpointB("");
    setSliceLsb(0);
    setSliceLsbB(0);
    setSliceWidth(0);
    setExistingNetId(undefined);
    setConnectionError("");
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
    const parentTerminals = graph.terminals.filter((item) => terminal.node_id ? item.node_id === terminal.node_id : !item.node_id);
    const placement = layout.layout.terminal_placements[terminalKey];
    const sameSide = parentTerminals
      .filter((item) => layout.layout.terminal_placements[item.id]?.side === placement?.side)
      .sort((left, right) => (layout.layout.terminal_placements[left.id]?.order ?? 0) - (layout.layout.terminal_placements[right.id]?.order ?? 0));
    return { terminalKey, terminal, parentTerminals, placement, sameSide, index: sameSide.findIndex((item) => item.id === terminalKey) };
  }

  function setTerminalSide(target: CircuitCanvasContextTarget | undefined, side: TerminalPlacement["side"]): boolean {
    const context = terminalContext(target);
    if (!context) return false;
    const orders = context.parentTerminals
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
    return mutate({ operation_id: operationId("placement"), type: "set_terminal_placement", terminal_key: context.terminalKey, placement: null }, `Reset ${document ? circuitTerminalLabel(document, context.terminalKey) : "Port"} to automatic placement.`);
  }

  function disconnectContextTerminal(target: CircuitCanvasContextTarget | undefined): boolean {
    const terminalKey = targetTerminalKey(target);
    const net = terminalKey ? document?.design.nets.find((item) => item.endpoints.some((endpoint) => endpointTerminalKey(endpoint) === terminalKey)) : undefined;
    const endpoint = net?.endpoints.find((item) => endpointTerminalKey(item) === terminalKey);
    if (!terminalKey || !net || !endpoint) return false;
    if (net.endpoints.length > 2) return mutate({ operation_id: operationId("disconnect"), type: "disconnect_endpoint", net_id: net.id, endpoint }, `Disconnected ${document ? circuitTerminalLabel(document, terminalKey) : "Port"} from ${net.label || "Net"}.`);
    setConfirmation({
      title: "Delete the connected net?",
      message: `Disconnecting ${document ? circuitTerminalLabel(document, terminalKey) : "Port"} would leave “${net.label || "Net"}” with fewer than two endpoints. Delete the whole net instead?`,
      confirmLabel: "Delete net",
      onConfirm: () => {
        setConfirmation(undefined);
        if (mutate({ operation_id: operationId("delete_net"), type: "delete_net", net_id: net.id }, `Deleted net ${net.label || "Net"}.`)) setSelection([]);
      },
    });
    return true;
  }

  function deleteBoundaryTarget(target: CircuitCanvasContextTarget | undefined): boolean {
    const item = target && selectionItemForTarget(target);
    if (!item || item.kind !== "boundary") return false;
    setConfirmation({
      title: "Delete boundary terminal?",
      message: `Delete boundary terminal “${document ? circuitTerminalLabel(document, `boundary:${item.id}`) : "Port"}” and explicitly cascade its connectivity?`,
      confirmLabel: "Delete boundary terminal",
      onConfirm: () => {
        setConfirmation(undefined);
        if (mutate({ operation_id: operationId("remove_boundary"), type: "remove_boundary_terminal", terminal_id: item.id, cascade: true }, "Deleted boundary terminal.")) setSelection([]);
      },
    });
    return true;
  }

  function reportConnectionRejection(reason: "same_terminal" | "terminal_in_use" | "invalid_target"): void {
    setMessage(reason === "same_terminal"
      ? "Choose two different terminals."
      : reason === "terminal_in_use"
        ? "Choose the existing net to extend this connection."
        : "Drop the connection on another free terminal.");
  }

  function isCommandEnabled(invocation: CircuitActionInvocation): boolean {
    if (recovering) return false;
    const actionId = invocation.commandId;
    const contextualNetId = targetNetId(invocation.target) ?? selectedNet?.id;
    const contextualRoute = contextualNetId ? layout?.layout.net_routes[contextualNetId] : undefined;
    const contextualRouteLocked = Boolean(contextualRoute?.segments.some((segment) => segment.locked)
      || contextualRoute?.vertices.some((vertex) => vertex.locked));
    const terminal = terminalContext(invocation.target);
    const contextualInstanceId = invocation.target?.kind === "node" ? invocation.target.nodeId
      : invocation.target?.kind === "terminal" && invocation.target.parent.kind === "node" ? invocation.target.parent.id
        : selectedInstance?.id;
    const contextualInstance = document?.design.instances.find((instance) => instance.id === contextualInstanceId);
    const contextualCycleEdgeId = invocation.target?.kind === "cycle-edge" ? invocation.target.edgeId : selectedCycleEdge?.id;
    const contextualCycleEdge = timing.cycle_edges.find((edge) => edge.id === contextualCycleEdgeId);
    switch (actionId) {
      case "new-document": return !lease && !draftRef.current && !openingFile;
      case "open-document": return Boolean(snapshot) && !lease && !draftRef.current && !openingFile;
      case "save-document": return Boolean((canEditCircuit || (sourceSaveRef.current && sourceBinding?.writable)) && !sourceBusy && (!sourceBinding || (layout && layoutGraphRef.current === graph)));
      case "cancel-changes": return Boolean(lease || draftRef.current) && !sourceBusy;
      case "download-json":
      case "export-svg":
      case "export-png": return Boolean(snapshot && layout && layoutGraphRef.current === graph) && !lease;
      case "begin-edit": return Boolean(snapshot) && !lease && !draftRef.current && Boolean(!linkedDocumentId || sourceBinding?.writable || sourceBinding?.capabilities.includes("create-internal-design")) && !sourceBusy;
      case "create-internal-design": return Boolean(lease && source?.prepareInternalDesign && sourceBinding?.capabilities.includes("create-internal-design") && !sourceBinding.pendingInternalDesign && !sourceBusy);
      case "undo": return Boolean(canEditCircuit && draftRef.current?.canUndo);
      case "redo": return Boolean(canEditCircuit && draftRef.current?.canRedo);
      case "delete-selection": return Boolean(canEditCircuit && (selection.length || (invocation.target && selectionItemForTarget(invocation.target))));
      case "open-component-catalog": return Boolean(document);
      case "create-local-component": return Boolean(canEditCircuit && document);
      case "review-proposals": return proposals.length > 0;
      case "open-child-design": return Boolean(contextualInstance && !draftRef.current?.dirty && !sourceBinding?.pendingInternalDesign && !sourceBinding?.interfacePreview);
      case "select-all": return Boolean(graph);
      case "clear-selection": return Boolean(graph);
      case "center-selection": return Boolean(selection.length || (invocation.target && invocation.target.kind !== "canvas"));
      case "open-connect": return Boolean(canEditCircuit);
      case "reroute-selected": return Boolean(canEditCircuit && contextualNetId && !contextualRouteLocked);
      case "lock-selected-route": return Boolean(canEditCircuit && contextualNetId && contextualRoute && !contextualRouteLocked);
      case "unlock-selected-route": return Boolean(canEditCircuit && contextualNetId && contextualRoute && contextualRouteLocked);
      case "arrange-all": return Boolean(canEditCircuit);
      case "add-cycle-edge": return Boolean(canEditCircuit && document);
      case "open-clock-settings": return Boolean(canEditCircuit && document);
      case "open-timing-analysis": return Boolean(document);
      case "edit-cycle-edge": return Boolean(canEditCircuit && contextualCycleEdge);
      case "lock-cycle-edge": return Boolean(canEditCircuit && contextualCycleEdge && !contextualCycleEdge.locked);
      case "unlock-cycle-edge": return Boolean(canEditCircuit && contextualCycleEdge?.locked);
      case "delete-cycle-edge": return Boolean(canEditCircuit && contextualCycleEdge);
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
        if (!canEditCircuit || invocation.target?.kind !== "route-segment" || !contextualRoute || !invocation.circuitPoint) return false;
        return JSON.stringify(insertRouteBend(contextualRoute, invocation.target.segmentId, invocation.circuitPoint, document?.layout.grid_size ?? 20)) !== JSON.stringify(contextualRoute);
      }
      case "remove-bend": {
        if (!canEditCircuit || invocation.target?.kind !== "route-vertex" || invocation.target.vertexKind !== "bend" || !contextualRoute) return false;
        return JSON.stringify(removeRouteBend(contextualRoute, invocation.target.vertexId)) !== JSON.stringify(contextualRoute);
      }
      case "select-connected-net": return Boolean(contextualNetId);
      case "disconnect-port": return Boolean(canEditCircuit && contextualNetId && terminal);
      case "delete-boundary-terminal": return Boolean(canEditCircuit && invocation.target && selectionItemForTarget(invocation.target)?.kind === "boundary");
      case "terminal-side-north":
      case "terminal-side-east":
      case "terminal-side-south":
      case "terminal-side-west":
      case "terminal-lock-placement":
      case "terminal-unlock-placement": return Boolean(canEditCircuit && terminal);
      case "terminal-move-earlier": return Boolean(canEditCircuit && terminal && terminal.index > 0);
      case "terminal-move-later": return Boolean(canEditCircuit && terminal && terminal.index >= 0 && terminal.index < terminal.sameSide.length - 1);
      case "terminal-reset-placement": return Boolean(canEditCircuit && terminal && document?.layout.terminal_placements[terminal.terminalKey]);
    }
  }

  function executeCircuitAction(invocation: CircuitActionInvocation): boolean {
    if (!isCommandEnabled(invocation)) return false;
    const actionId = invocation.commandId;
    const contextualNetId = targetNetId(invocation.target) ?? selectedNet?.id;
    const contextualRoute = contextualNetId ? layout?.layout.net_routes[contextualNetId] : undefined;
    const contextualInstanceId = invocation.target?.kind === "node" ? invocation.target.nodeId
      : invocation.target?.kind === "terminal" && invocation.target.parent.kind === "node" ? invocation.target.parent.id
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
      case "create-internal-design": void createInternalDesign(); return true;
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
        setExistingNetId(undefined);
        setConnectionError("");
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

  // Preserve exact diagnostics for inspection; resolve presentation from this
  // selected document only, without turning labels into selection values.
  const readableMessage = (() => {
    let value = message;
    const labels = document ? [
      [document.document_id, document.label],
      ...document.components.map(item => [item.id, item.label]),
      ...document.design.nets.map(item => [item.id, item.label || "Connection"]),
    ] : [];
    for (const [key, label] of labels.sort((a, b) => b[0].length - a[0].length)) {
      if (key && label && key !== label) value = value.split(key).join(label);
    }
    return value.replace(/sha256:[a-f0-9]{16,}/gi, "source revision")
      .replace(/\b[a-f0-9]{24,}\b/gi, "internal reference");
  })();
  const themeStyle = { ...circuitThemeCssProperties(theme), colorScheme: theme.color_scheme } as CSSProperties;

  return <main className="cd-app standalone-shell" data-theme={theme.id} ref={appRef} style={themeStyle}>
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
        createInternalDesignHint={sourceBinding?.pendingInternalDesign ? "Save or cancel the pending Design first."
          : !sourceBinding?.capabilities.includes("create-internal-design") ? sourceBinding?.interfacePreview ? "Spec edit access is required." : "Select a Component without an internal Design in Spec Editor."
          : !source?.prepareInternalDesign ? "Creation is unavailable in this view."
          : !lease ? "Select Begin editing first."
          : sourceBusy ? "Wait for the current action to finish." : undefined}
        tools={tools}
        toolsEnabled={Boolean(snapshot) && !lease && !draftRef.current && !recovering}
        onRunTool={runTool}
      />
      <div className="document-status" title={sourceDescription}>
        <strong>{document?.label ?? "Loading…"}</strong>
        {!sourceBinding && lease && document && <button type="button" onClick={() => {
          const name = window.prompt("Document name", document.label);
          if (name?.trim()) mutate({ operation_id: operationId("rename_document"), type: "set_document_label", label: name }, "Document renamed.");
        }}>Rename</button>}
        <small>{sourceBinding ? sourceBinding.writable ? lease ? sourceBinding.draftLabel ?? "source draft" : sourceBinding.boundLabel ?? "source bound" : "source read-only" : lease ? "private draft" : "saved circuit"}</small>
      </div>
      <button
        aria-label={`Switch theme (currently ${theme.id === "obsidian" ? "Dark" : "Light"})`}
        className="theme-quick-toggle"
        onClick={() => {
          const nextThemeId = theme.id === "obsidian" ? "blueprint-slate" : "obsidian";
          setPreferences((prev) => ({
            ...prev,
            ui: { ...prev.ui, theme_id: nextThemeId },
          }));
        }}
        title={`Switch to ${theme.id === "obsidian" ? "Blueprint Slate (Clean Light)" : "Obsidian (Dark Canvas)"}`}
        type="button"
      >
        <span aria-hidden="true">{theme.id === "obsidian" ? "☀️" : "🌙"}</span>
      </button>
      {sourceBinding && (lease || sourceSaveRef.current) && (draftRef.current?.dirty || sourceBinding.pendingInternalDesign) && <button
        className="source-save-button"
        disabled={!sourceBinding.writable || sourceBusy || !layout || layoutGraphRef.current !== graph}
        onClick={() => executeCircuitAction({ commandId: "save-document", source: "menubar" })}
        type="button"
      >{sourceBinding.saveLabel ?? "Save to Spec"}</button>}
    </header>
    <div className="circuit-feedback">
    <div className="notice">
      <span className="local-dot" />
      {activePage === "actions" ? "Actions & shortcuts" : sourceBinding?.writable ? sourceBinding.label : linkedDocumentId ? "Source projection" : "Independent document"}
      <span>{activePage === "actions"
        ? `Shared preference file · ${preferenceStatus === "loading" ? "loading…" : preferenceStatus === "saving" ? "saving…" : preferenceStatus === "saved" ? "saved" : "save failed"}`
        : layoutProgress || readableMessage}</span>
      {readableMessage !== message && <details><summary>Technical details</summary><pre>{message}</pre><button type="button" onClick={() => void navigator.clipboard.writeText(message)}>Copy details</button></details>}
      {sourceConflict && <span className="source-recovery">
        <button onClick={() => void reopenLatestSource()} type="button">Reopen Latest</button>
        <button onClick={() => { if (document) void downloadCircuitDocument(document); }} type="button">Download Draft JSON</button>
      </span>}
      {!lease && remoteLease && !leaseLost && !draftRef.current && <button disabled={recovering} onClick={confirmTakeover} type="button">{recovering ? "Recovering…" : "Take over editing"}</button>}
      {leaseLost && <span className="source-recovery">
        <button onClick={() => { if (document) void downloadCircuitDocument(document); }} type="button">Download Draft JSON</button>
        <button onClick={() => void cancel()} type="button">Discard preserved draft</button>
      </span>}
    </div>
    {saveError && <div className="save-error" role="alert">
      <strong>{draftRef.current ? "Save failed. Your draft is still open." : "The saved Circuit could not be downloaded."}</strong>
      <p>{saveError}</p>
      {draftRef.current && <p>Save or cancel the draft before exporting the saved Circuit.</p>}
    </div>}
    </div>
    {activePage === "actions" ? <ActionSettingsPage
      onClose={() => setActivePage("canvas")}
      onPreferencesChange={setPreferences}
      preferences={preferences}
      preferenceStatus={preferenceStatus}
    /> : <section className={`workspace${inspectorOpen ? " workspace--inspector-open" : ""}`}>
      <div className="stage">
        <div className="canvas-actions" aria-label="Circuit view controls">
          <button type="button" disabled={!layout} onClick={() => executeCircuitAction({ commandId: "fit-circuit", source: "menubar" })}>Fit circuit</button>
          <button type="button" disabled={!canEditCircuit || !layout || Boolean(layoutProgress)} onClick={() => executeCircuitAction({ commandId: "arrange-all", source: "menubar" })}>Arrange</button>
          <button type="button" aria-pressed={inspectorOpen} onClick={() => executeCircuitAction({ commandId: "toggle-inspector", source: "menubar" })}>{inspectorOpen ? "Hide Inspector" : "Show Inspector"}</button>
        </div>
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
            componentLabels={Object.fromEntries(document?.components.map(component => [component.id, component.label]) ?? [])}
            layout={layout.layout}
            boundaryGeometry={layout.boundary_geometry}
            editable={canEditCircuit}
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
          {layout && <details className="layout-time"><summary>Layout diagnostics</summary>Grid router · {layout.elapsed_ms} ms</details>}
        </div>
      </div>
      {inspectorOpen && <aside className="inspector">
        <p className="eyebrow">Inspector</p>
        {sourceBinding?.capabilities.includes("boundary-ports") && <button
          disabled={!canEditCircuit}
          onClick={addBoundaryPort}
          type="button"
        >New Boundary Port</button>}
        {selection.length === 0 && <div className="empty-inspector"><span>⌁</span><p>Select an instance, boundary terminal, or net to inspect its properties.</p></div>}
        {selection.length > 1 && <div className="multi-inspector"><span className="kind">selection</span><h2>{selection.length} items selected</h2><p>{selection.filter((item) => item.kind === "node").length} instances · {selection.filter((item) => item.kind === "boundary").length} boundary terminals · {selection.filter((item) => item.kind === "net").length} nets</p></div>}
        {selectedInstance && document && <><span className="kind">instance</span><h2>{selectedInstance.label}</h2>
          <label>{sourceBinding ? "Instance name" : "Label"}<input pattern={sourceIdentifierPattern} value={selectedInstance.label} onChange={(event) => {
            const label = event.target.value || selectedInstance.id;
            if (!isSourceIdentifier(label)) {
              setMessage(sourceBinding?.identifierHint ?? "Use a source-compatible instance name.");
              return;
            }
            mutate({ operation_id: operationId("label"), type: "update_instance", instance: { ...selectedInstance, label } }, "Instance name updated.");
          }} disabled={!canEditCircuit} /></label>
          <details><summary>Technical details</summary><pre>{JSON.stringify(selectedInstance, null, 2)}</pre></details>
        </>}
        {selectedBoundary && <><span className="kind">boundary terminal</span><h2>{selectedBoundary.label}</h2>
          <label>Name<input
            disabled={!canEditCircuit}
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
            disabled={!canEditCircuit}
            value={selectedBoundary.direction}
            onChange={(event) => updateBoundaryPort({ ...selectedBoundary, direction: event.target.value as "input" | "output" | "inout" })}
          ><option value="input">Input</option><option value="output">Output</option><option value="inout">In/out</option></select></label>
          <label>Wire width or range<input
            disabled={!canEditCircuit}
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
          <details><summary>Technical details</summary><pre>{JSON.stringify(selectedBoundary, null, 2)}</pre></details>
        </>}
        {selectedNet && <><span className="kind">net</span><h2>{selectedNet.label || "Net"}</h2>
          <p className="draw-hint">{selectedRouteLocked ? "Route locked. Use Route → Unlock Selected Route before editing." : "Drag highlighted segments or handles to edit this route."}</p>
          <p className="draw-hint">{selectedNet.endpoints.map((endpoint) => document ? circuitEndpointLabel(document, endpoint) : "Port").join("\n")}</p>
          <details><summary>Technical details</summary><pre>{JSON.stringify(selectedNet, null, 2)}</pre></details>
        </>}
        {selectedCycleEdge && <><span className="kind">cycle edge</span><h2>{selectedCycleEdge.label ?? `Cycle edge ${timing.cycle_edges.findIndex((edge) => edge.id === selectedCycleEdge.id) + 1}`}</h2><code>x = {selectedCycleEdge.x}</code>
          <p className="draw-hint">Every same-domain path crossing this marker gains one cycle.</p>
          <button disabled={!canEditCircuit} onClick={() => setDialog("cycle-edge")} type="button">Edit edge</button>
          <button disabled={!canEditCircuit} onClick={() => updateCycleEdge({ ...selectedCycleEdge, locked: !selectedCycleEdge.locked })} type="button">{selectedCycleEdge.locked ? "Unlock edge" : "Lock edge"}</button>
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
      onRenameComponent={lease ? (id, name) => { const component = document?.components.find(item => item.id === id); if (component) mutate({ operation_id: operationId("rename_component"), type: "update_component", component: { ...component, label: name } }, "Component renamed."); } : undefined}
      onPlaceComponent={placeCatalogComponent}
      onCreateConnection={createConnectionFromDialog}
      onDecideProposal={(proposalId, decision) => void decideProposal(proposalId, decision)}
      onEndpointAChange={setEndpointA}
      onEndpointBChange={setEndpointB}
      onNetNameChange={setNetName}
      onSliceLsbChange={setSliceLsb}
      onSliceLsbBChange={setSliceLsbB}
      onSliceWidthChange={setSliceWidth}
      proposals={proposals}
      sliceLsb={sliceLsb}
      sliceLsbB={sliceLsbB}
      sliceWidth={sliceWidth}
      sourceDescription={sourceDescription}
      sourceIdentifierPattern={sourceIdentifierPattern}
      sourceIdentifierHint={sourceBinding?.identifierHint}
      existingNetId={existingNetId}
      connectionError={connectionError}
      onExistingNetChange={(id) => {
        setExistingNetId(id);
        setConnectionError("");
        if (id && document) {
          const net = document.design.nets.find(item => item.id === id);
          const endpoint = net?.endpoints[0];
          const terminal = endpoint && graph?.terminals.find(item => item.id === endpointTerminalKey(endpoint));
          setSliceWidth(endpoint?.slice?.width ?? (typeof terminal?.width === "number" ? terminal.width : 0));
          setSliceLsbB(0);
        }
      }}
      terminals={terminals.map(terminal => ({ ...terminal, label: document ? circuitTerminalLabel(document, terminal.id) : "Port" }))}
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
    {svChoiceOpen && <CircuitSvDispositionDialog onCancel={() => setSvChoiceOpen(false)} onSave={(choice) => void save(choice)} />}
    {confirmation && <CircuitConfirmationDialog
      confirmLabel={confirmation.confirmLabel}
      message={confirmation.message}
      onCancel={() => setConfirmation(undefined)}
      onConfirm={confirmation.onConfirm}
      title={confirmation.title}
    />}
  </main>;
}

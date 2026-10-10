/** Spec Editor host: coherent Spec service views, drafts, menus and service launches.
 * The visible document and a permanently bound Assistant package are distinct.
 * Spec service events invalidate projections; request ordering prevents a late response
 * for an older selection/revision from replacing the current view. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  A2UIDocumentSurface,
  SPEC_HARDWARE_ACTION_EVENT,
  SPEC_LAUNCH_ACTIVITY_EVENT,
  SPEC_OPEN_CIRCUIT_EVENT,
  type SpecDocumentEditController,
  type SpecLaunchActivityEventDetail,
  type SpecOpenCircuitEventDetail,
} from "@spec2gds/document-a2ui-react";
import {
  SpecEditorHttpError,
  SpecEditorHttpClient,
  type A2UIDocumentBatch,
  type ActivityState,
  type ComponentInstanceInput,
  type ComponentPortInput,
  type ComponentPortUpdateInput,
  type DocumentSnapshot,
  type DocumentView,
  type EditorTransactionOperation,
  type EntityMetadataInput,
  type EntityAction,
  type EntityActivity,
  type EntityRef,
  type SourceChangeEvent,
} from "@spec2gds/document-core";

import EditorMenuBar, { type EditorView } from "./EditorMenuBar";
import { acceptsView, draftRevisions, saveBaseRevision } from "./revision-guards";
import { browserRandomUuid } from "@spec2gds/circuit-app-react";
import { BrowserLogger } from "@spec2gds/observability/browser";

type ActionDialogState = {
  ref: EntityRef;
  name?: string;
  actions: EntityAction[];
  loading: boolean;
  runningId: string;
} | null;

type ActivityDialogState = {
  ref: EntityRef;
  activities: EntityActivity[];
  loading: boolean;
  runningId: string;
} | null;

function text(value: unknown, fallback = "—"): string {
  if (typeof value === "string") return value || fallback;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? value as Record<string, unknown> : {};
}

export default function App() {
  const client = useMemo(
    () => new SpecEditorHttpClient(import.meta.env.DEV ? "/api" : ""),
    [],
  );
  const [path, setPath] = useState("");
  const [snapshot, setSnapshot] = useState<DocumentSnapshot | null>(null);
  const [batch, setBatch] = useState<A2UIDocumentBatch | null>(null);
  const [activity, setActivity] = useState<ActivityState>({
    executions: [],
    artifacts: [],
    proposals: [],
    assistant_changes: [],
  });
  const [view, setView] = useState<EditorView>(() => new URLSearchParams(window.location.search).get("view") === "activity" ? "activity" : "document");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionDialog, setActionDialog] = useState<ActionDialogState>(null);
  const [activityDialog, setActivityDialog] = useState<ActivityDialogState>(null);
  const [launchingCircuit, setLaunchingCircuit] = useState(false);
  const [launchingAssistant, setLaunchingAssistant] = useState(false);
  const [externalChange, setExternalChange] = useState<SourceChangeEvent | null>(null);
  const [inlineEditActive, setInlineEditActive] = useState(false);
  const documentEpoch = useRef(0);
  const activeKey = useRef<string | null>(null);
  const currentRevision = useRef("");
  const editing = useRef(false);
  const draftRevision = useRef<string | null>(null);
  const reviewedRevision = useRef<string | null>(null);
  const [reviewSource, setReviewSource] = useState<DocumentSnapshot | null>(null);
  const [approvalPolicy, setApprovalPolicy] = useState<"automatic" | "review">("review");
  const [syncState, setSyncState] = useState("Disconnected");
  const eventCursor = useRef(0);
  const [viewCursor, setViewCursor] = useState(0);
  const viewRequest = useRef(0);
  const [browserLogger, setBrowserLogger] = useState<BrowserLogger | null>(null);

  const loadView = useCallback(async () => {
    const request = ++viewRequest.current;
    const epoch = documentEpoch.current;
    const key = activeKey.current;
    if (!key) return;
    let next: DocumentView;
    try { next = await client.getDocumentView(key); }
    catch (caught) {
      if (epoch !== documentEpoch.current || key !== activeKey.current) return;
      throw caught;
    }
    if (!acceptsView({ request, epoch, key }, {
      request: viewRequest.current, epoch: documentEpoch.current, key: activeKey.current,
    })) return;
    eventCursor.current = next.event_cursor;
    setViewCursor(next.event_cursor);
    setApprovalPolicy(next.approval_policy);
    setActivity(next.activity);
    if (editing.current) {
      if (next.source_revision_hash !== currentRevision.current) {
        setExternalChange({ sequence: next.event_cursor, owner_document_key: key,
          document_id: next.snapshot.document_id, source_revision_hash: next.source_revision_hash,
          origin: "external", affected_entities: [] });
        setSyncState("Saved updates pending · draft preserved");
      }
      return;
    }
    currentRevision.current = next.source_revision_hash;
    setSnapshot(next.snapshot);
    setBatch(next.a2ui);
    setExternalChange(null);
    setSyncState("Up to date");
  }, [client]);

  const initialDocumentKey = useRef(new URLSearchParams(window.location.search).get("owner_document_key"));
  useEffect(() => {
    const key = initialDocumentKey.current;
    if (!key) return;
    initialDocumentKey.current = null;
    activeKey.current = key;
    client.bindDocument(key);
    void loadView().catch(caught => setError(caught instanceof Error ? caught.message : String(caught)));
  }, [client, loadView]);
  useEffect(() => { if (snapshot?.source_path) setPath(snapshot.source_path); }, [snapshot?.source_path]);

  const editingChanged = useCallback((value: boolean) => {
    editing.current = value;
    setInlineEditActive(value);
    const revisions = draftRevisions(value, currentRevision.current);
    draftRevision.current = revisions.draft;
    reviewedRevision.current = revisions.reviewed;
    if (!value) {
      setReviewSource(null);
      void loadView().catch(caught => setError(String(caught)));
    }
  }, [loadView]);

  const refreshActivity = useCallback(async () => {
    await loadView();
  }, [loadView]);

  useEffect(() => {
    void client.getServiceDirectory()
      .then((directory) => {
        setBrowserLogger(new BrowserLogger(`${import.meta.env.DEV ? "/api" : ""}/logs/events`, directory.logging));
      })
      .catch(() => undefined);
  }, [client]);

  useEffect(() => browserLogger?.captureGlobalErrors(), [browserLogger]);

  const openDocument = useCallback(async (nextPath: string) => {
    if (!nextPath) return false;
    if (editing.current) { setError("Save or cancel your draft before opening another Spec."); return false; }
    const epoch = ++documentEpoch.current;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const nextSnapshot = await client.openDocument(nextPath);
      if (epoch !== documentEpoch.current) return false;
      activeKey.current = nextSnapshot.owner_document_key;
      client.bindDocument(nextSnapshot.owner_document_key);
      await loadView();
      if (epoch !== documentEpoch.current) return false;
      setPath(nextSnapshot.source_path || nextPath);
      setView("document");
      setExternalChange(null);
      browserLogger?.event("documents", "opened", "Opened specification", "info", { path: nextPath, snapshot: nextSnapshot });
      return true;
    } catch (caught) {
      if (epoch === documentEpoch.current) {
        setError(caught instanceof Error ? caught.message : String(caught));
        browserLogger?.event("documents", "open_failed", "Could not open specification", "error", { path: nextPath, error: String(caught) });
      }
      return false;
    } finally {
      if (epoch === documentEpoch.current) setLoading(false);
    }
  }, [browserLogger, client, loadView]);

  useEffect(() => {
    if (!snapshot) return;
    const key = snapshot.owner_document_key;
    const epoch = documentEpoch.current;
    const events = new EventSource(client.activityEventsUrl());
    const updateExecution = (event: MessageEvent<string>) => {
      if (epoch !== documentEpoch.current || key !== activeKey.current) return;
      try {
        const execution = JSON.parse(event.data) as Record<string, unknown>;
        const executionId = text(execution.execution_id, "");
        if (!executionId) return;
        setActivity((current) => {
          const existing = current.executions.findIndex(
            (item) => text(record(item).execution_id, "") === executionId,
          );
          const executions = [...current.executions];
          if (existing >= 0) executions[existing] = execution;
          else executions.push(execution);
          return { ...current, executions };
        });
      } catch {
        // Reconnect recovery fetches the authoritative execution list.
      }
    };
    events.addEventListener("activity.execution.changed", updateExecution as EventListener);
    events.onerror = () => void refreshActivity().catch(() => {
      if (epoch === documentEpoch.current && key === activeKey.current) setSyncState("Disconnected · reconnecting");
    });
    return () => events.close();
  }, [client, refreshActivity, snapshot?.owner_document_key]);

  const pendingCreation = useRef<{ path: string; title: string; requestId: string } | null>(null);
  const createDocument = useCallback(async (nextPath: string, title: string) => {
    if (!nextPath || !title.trim()) return false;
    if (editing.current) { setError("Save or cancel your draft before creating another specification."); return false; }
    const epoch = ++documentEpoch.current;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const name = title.trim();
      if (pendingCreation.current?.path !== nextPath || pendingCreation.current.title !== name) {
        pendingCreation.current = { path: nextPath, title: name, requestId: browserRandomUuid() };
      }
      const nextSnapshot = await client.createDocument(nextPath, name, pendingCreation.current.requestId);
      if (epoch !== documentEpoch.current) return false;
      activeKey.current = nextSnapshot.owner_document_key;
      client.bindDocument(nextSnapshot.owner_document_key);
      await loadView();
      if (epoch !== documentEpoch.current) return false;
      setPath(nextPath);
      setView("document");
      setExternalChange(null);
      setNotice("Created a new .spec file.");
      browserLogger?.event("documents", "created", "Created specification", "info", { path: nextPath, title, snapshot: nextSnapshot });
      return true;
    } catch (caught) {
      if (epoch === documentEpoch.current) {
        setError(caught instanceof Error ? caught.message : String(caught));
        browserLogger?.event("documents", "create_failed", "Could not create specification", "error", { path: nextPath, title, error: String(caught) });
      }
      return false;
    } finally {
      if (epoch === documentEpoch.current) setLoading(false);
    }
  }, [browserLogger, client, loadView]);

  useEffect(() => {
    if (!snapshot) return;
    const key = snapshot.owner_document_key;
    const epoch = documentEpoch.current;
    const source = new EventSource(client.eventsUrl(eventCursor.current));
    let timer: ReturnType<typeof setTimeout> | undefined;
    const schedule = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        if (epoch === documentEpoch.current) void loadView().catch(() => setSyncState("Reconnecting"));
      }, 100);
    };
    const onChange = (event: MessageEvent<string>) => {
      try {
        const change = JSON.parse(event.data) as SourceChangeEvent;
        if (epoch !== documentEpoch.current || change.owner_document_key !== key) return;
        if (change.source_revision_hash !== currentRevision.current && editing.current) {
          setExternalChange(change);
          setSyncState("Saved updates pending · draft preserved");
        } else if (!editing.current) {
          schedule();
        }
      } catch {
        schedule(); // Recover from authoritative state, rather than trusting notifications.
      }
    };
    source.addEventListener("source.changed", onChange as EventListener);
    source.addEventListener("source.resync", onChange as EventListener);
    source.addEventListener("assistant.submission.changed", schedule);
    source.addEventListener("source.unavailable", () => setSyncState("Bound package unavailable"));
    source.onopen = () => { setSyncState(editing.current ? "Editing draft" : "Synchronizing"); schedule(); };
    source.onerror = () => setSyncState("Disconnected · reconnecting");
    return () => { source.close(); if (timer) clearTimeout(timer); };
  }, [client, loadView, snapshot?.owner_document_key]);

  useEffect(() => {
    const onEntityAction = (event: Event) => {
      const ref = (event as CustomEvent<{ entityRef: EntityRef }>).detail.entityRef;
      setActionDialog({ ref, actions: [], loading: true, runningId: "" });
      client.listEntityActions(ref)
        .then(({ actions }) => setActionDialog({
          ref,
          actions,
          loading: false,
          runningId: "",
        }))
        .catch((caught) => {
          setActionDialog(null);
          setError(caught instanceof Error ? caught.message : String(caught));
        });
    };
    window.addEventListener(SPEC_HARDWARE_ACTION_EVENT, onEntityAction);
    return () => window.removeEventListener(SPEC_HARDWARE_ACTION_EVENT, onEntityAction);
  }, [client]);

  const executeAction = async (action: EntityAction) => {
    if (!actionDialog) return;
    const ref = actionDialog.ref;
    setActionDialog({ ...actionDialog, runningId: action.action_id });
    try {
      const execution = await client.executeEntityAction(ref, action.action_id);
      await refreshActivity();
      setActionDialog(null);
      setNotice(`Action ${action.action_id} ${text(execution.status, "completed")}.`);
      setView("activity");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setActionDialog({ ...actionDialog, runningId: "" });
    }
  };

  const reviewProposal = async (proposalId: string, decision: "accept" | "reject") => {
    if (!snapshot) return;
    try {
      const result = await client.reviewProposal(
        proposalId,
        decision,
        snapshot.source_revision_hash,
      );
      const nextSnapshot = record(result.snapshot) as unknown as DocumentSnapshot;
      if (result.snapshot) {
        setSnapshot(nextSnapshot);
        setBatch(await client.getA2UIBatch());
      }
      await refreshActivity();
      setNotice(`Proposal ${decision === "accept" ? "accepted" : "rejected"}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  };

  const launchCircuitDesigner = useCallback(async (
    entityKind: "component" | "design",
    entityId: string,
  ) => {
    if (launchingCircuit) return;
    const pendingWindow = window.open("about:blank", "_blank");
    if (pendingWindow) {
      pendingWindow.opener = null;
      pendingWindow.document.title = "Opening Circuit Designer…";
      pendingWindow.document.body.textContent = "Projecting the selected design…";
    }
    setLaunchingCircuit(true);
    setError("");
    try {
      const launch = await client.launchCircuitDesigner(entityKind, entityId);
      if (pendingWindow) pendingWindow.location.replace(launch.editor_url);
      else window.open(launch.editor_url, "_blank", "noopener,noreferrer");
      const omittedBuses = launch.omitted_bus_items.length;
      const omittedPorts = launch.omitted_ports.length;
      const entity = [...(snapshot?.designs ?? []), ...(snapshot?.components ?? [])]
        .find((item) => item.ref.entity_id === entityId);
      setNotice(
        `Opened ${entity?.display_name || entityName(entity?.vlnv)} in Circuit Designer`
        + (omittedBuses || omittedPorts
          ? `; omitted ${[
            omittedBuses ? `${omittedBuses} bus item${omittedBuses === 1 ? "" : "s"}` : "",
            omittedPorts ? `${omittedPorts} non-wire port${omittedPorts === 1 ? "" : "s"}` : "",
          ].filter(Boolean).join(" and ")} from the wire-only projection.`
          : "."),
      );
    } catch (caught) {
      pendingWindow?.close();
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLaunchingCircuit(false);
    }
  }, [client, launchingCircuit, snapshot]);

  useEffect(() => {
    const onOpenCircuit = (event: Event) => {
      const { entityRef } = (event as CustomEvent<SpecOpenCircuitEventDetail>).detail;
      if (entityRef.entity_kind === "design" || entityRef.entity_kind === "component") {
        void launchCircuitDesigner(entityRef.entity_kind, entityRef.entity_id);
      }
    };
    window.addEventListener(SPEC_OPEN_CIRCUIT_EVENT, onOpenCircuit);
    return () => window.removeEventListener(SPEC_OPEN_CIRCUIT_EVENT, onOpenCircuit);
  }, [launchCircuitDesigner]);

  useEffect(() => {
    const onLaunchActivity = (event: Event) => {
      const { entityRef } = (event as CustomEvent<SpecLaunchActivityEventDetail>).detail;
      setActivityDialog({ ref: entityRef, activities: [], loading: true, runningId: "" });
      void client.listEntityActivities(entityRef).then((response) => {
        setActivityDialog((current) => current?.ref.entity_id === entityRef.entity_id
          ? { ...current, activities: response.activities, loading: false }
          : current);
      }).catch((caught) => {
        setActivityDialog(null);
        setError(caught instanceof Error ? caught.message : String(caught));
      });
    };
    window.addEventListener(SPEC_LAUNCH_ACTIVITY_EVENT, onLaunchActivity);
    return () => window.removeEventListener(SPEC_LAUNCH_ACTIVITY_EVENT, onLaunchActivity);
  }, [client]);

  const executeActivity = async (item: EntityActivity) => {
    if (!activityDialog || !snapshot) return;
    const ref = activityDialog.ref;
    setActivityDialog({ ...activityDialog, runningId: item.definition.activity_id });
    try {
      await client.launchEntityActivity(
        ref,
        item.definition.activity_id,
        snapshot.source_revision_hash,
      );
      await refreshActivity();
      setActivityDialog(null);
      setNotice(`Queued ${item.definition.title} for ${referenceName(snapshot, ref)}.`);
      setView("activity");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setActivityDialog({ ...activityDialog, runningId: "" });
    }
  };

  const cancelActivity = async (executionId: string) => {
    try {
      await client.cancelExecution(executionId);
      await refreshActivity();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  };

  const launchAssistant = async (target: EntityRef) => {
    if (launchingAssistant) return;
    const pendingWindow = window.open("about:blank", "_blank");
    if (pendingWindow) {
      pendingWindow.opener = null;
      pendingWindow.document.title = "Opening AI Assistant…";
      pendingWindow.document.body.textContent = "Creating a new AI Assistant conversation for this Component or Design…";
    }
    setLaunchingAssistant(true);
    setError("");
    try {
      const launch = await client.launchAssistant(target);
      if (pendingWindow) pendingWindow.location.replace(launch.assistant_url);
      else window.open(launch.assistant_url, "_blank", "noopener,noreferrer");
      setActionDialog(null);
      setNotice(`Opened a new AI Assistant conversation for ${referenceName(snapshot, target)}.`);
    } catch (caught) {
      pendingWindow?.close();
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLaunchingAssistant(false);
    }
  };

  const launchDocumentAssistant = async () => {
    if (launchingAssistant) return;
    const pendingWindow = window.open("about:blank", "_blank");
    if (pendingWindow) {
      pendingWindow.opener = null;
      pendingWindow.document.title = "Opening AI Assistant…";
      pendingWindow.document.body.textContent = snapshot
        ? "Connecting to the active Spec…"
        : "Opening the AI Assistant without a specification…";
    }
    setLaunchingAssistant(true);
    setError("");
    try {
      const launch = await client.launchDocumentAssistant(snapshot !== null);
      if (pendingWindow) pendingWindow.location.replace(launch.assistant_url);
      else window.open(launch.assistant_url, "_blank", "noopener,noreferrer");
      setNotice(launch.scope === "document"
        ? `Opened a read-only AI Assistant chat for ${snapshot?.narrative.title || "this specification"}.`
        : "Opened the AI Assistant without an attached specification.");
    } catch (caught) {
      pendingWindow?.close();
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLaunchingAssistant(false);
    }
  };

  const refreshExternalChange = async () => {
    setError("");
    try {
      if (editing.current) {
        const key = activeKey.current;
        const epoch = documentEpoch.current;
        const latest = await client.getDocumentView(key);
        if (epoch === documentEpoch.current && editing.current) setReviewSource(latest.snapshot);
      } else {
        await loadView();
        setNotice("Loaded the latest saved specification.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  };

  const commitEditorOperations = useCallback(async (
    operations: EditorTransactionOperation[],
    successNotice: string,
  ) => {
    if (!snapshot) throw new Error("No specification is open.");
    const epoch = documentEpoch.current;
    const key = snapshot.owner_document_key;
    try {
      const base = saveBaseRevision(reviewedRevision.current, draftRevision.current, snapshot.source_revision_hash);
      const result = await client.applyTransaction(base, operations);
      if (epoch !== documentEpoch.current || key !== activeKey.current) return;
      ++viewRequest.current;
      currentRevision.current = result.snapshot.source_revision_hash;
      setSnapshot(result.snapshot);
      setExternalChange(null);
      setError("");
      setNotice(successNotice);
      try {
        const savedView = await client.getDocumentView(key);
        if (epoch !== documentEpoch.current || key !== activeKey.current) return;
        ++viewRequest.current;
        currentRevision.current = savedView.source_revision_hash;
        eventCursor.current = savedView.event_cursor;
        setViewCursor(savedView.event_cursor);
        setSnapshot(savedView.snapshot);
        setBatch(savedView.a2ui);
        setActivity(savedView.activity);
        setApprovalPolicy(savedView.approval_policy);
        setSyncState("Up to date");
        setExternalChange(null);
      } catch (refreshError) {
        if (epoch !== documentEpoch.current || key !== activeKey.current) return;
        setError(
          `The change was saved, but the document view could not refresh: ${refreshError instanceof Error ? refreshError.message : String(refreshError)}`,
        );
      }
    } catch (caught) {
      if (epoch !== documentEpoch.current || key !== activeKey.current) return;
      if (caught instanceof SpecEditorHttpError && caught.status === 409) {
        const latest = await client.getSnapshot();
        if (epoch !== documentEpoch.current || key !== activeKey.current) return;
        reviewedRevision.current = null;
        setReviewSource(latest);
        setExternalChange({ sequence: eventCursor.current, document_id: latest.document_id,
          owner_document_key: latest.owner_document_key, source_revision_hash: latest.source_revision_hash,
          origin: "external", affected_entities: [] });
        throw new Error("The saved source changed. Review the current source below before resubmitting your preserved draft.");
      }
      throw caught;
    }
  }, [client, snapshot]);

  const editController = useMemo<SpecDocumentEditController | undefined>(() => {
    if (!snapshot) return undefined;
    return {
      async updateDocumentTitle(title: string) {
        await commitEditorOperations(
          [{ type: "set_document_title", title }],
          `Spec name changed to ${title} and saved automatically.`,
        );
      },
      async createEntity(kind: "component" | "design", name: string) {
        await commitEditorOperations(
          [{ type: "create_entity", kind, name }],
          `${kind === "component" ? "Component" : "Entry design"} ${name} created and saved automatically.`,
        );
      },
      async addComponentInstance(design: EntityRef, value: ComponentInstanceInput) {
        await commitEditorOperations(
          [{ type: "upsert_instance", design, instance: value }],
          `Component instance ${value.name} added and saved automatically.`,
        );
      },
      componentInstanceOptions() {
        return snapshot.components.map((component) => ({
          label: component.display_name || entityName(component.vlnv),
          vlnv: component.vlnv,
        }));
      },
      async updateEntityMetadata(ref: EntityRef, value: EntityMetadataInput) {
        await commitEditorOperations(
          [{ type: "set_entity_metadata", entity: ref, ...value }],
          `${ref.entity_kind === "component" ? "Component" : "Design"} details saved automatically.`,
        );
      },
      async renameNarrativeSection(blockId: string, name: string) {
        const find = (blocks: DocumentSnapshot["narrative"]["blocks"]): DocumentSnapshot["narrative"]["blocks"][number] | undefined => {
          for (const block of blocks) {
            if (block.block_id === blockId) return block;
            const nested = find(block.children);
            if (nested) return nested;
          }
          return undefined;
        };
        const block = find(snapshot.narrative.blocks);
        if (!block || block.type !== "section") throw new Error("The section is no longer available. Refresh the source.");
        await commitEditorOperations([{ type: "upsert_narrative_block", block: { ...block, text: name } }], `Section renamed to ${name}.`);
      },
      async addComponentPort(ref: EntityRef, value: ComponentPortInput) {
        await commitEditorOperations(
          [{ type: "add_component_port", component: ref, port: value }],
          `Port ${value.name} added and saved automatically.`,
        );
      },
      async updateComponentPort(ref: EntityRef, name: string, value: ComponentPortUpdateInput) {
        await commitEditorOperations(
          [{ type: "update_component_port", component: ref, name, port: value }],
          `Port ${name} updated and saved automatically.`,
        );
      },
      async upsertEntitySection(ref: EntityRef, content: string, sectionId?: string) {
        await commitEditorOperations(
          [{
            type: "upsert_entity_section",
            parent: ref,
            section_type: "sv",
            type_version: 1,
            section_id: sectionId,
            payload: { content },
          }],
          "SystemVerilog section validated and saved automatically.",
        );
      },
      async deleteEntitySection(ref: EntityRef, sectionId?: string) {
        await commitEditorOperations(
          [{ type: "delete_entity_section", parent: ref, section_type: "sv", section_id: sectionId }],
          "SystemVerilog section deleted and saved automatically.",
        );
      },
      portEditingAvailability(ref: EntityRef) {
        const composite = snapshot.component_compositions.some(
          (composition) => composition.component.entity_id === ref.entity_id,
        );
        return composite
          ? {
            enabled: false,
            reason: "Edit composite boundary ports in the source-bound Circuit Designer.",
          }
          : { enabled: true, reason: "" };
      },
    };
  }, [commitEditorOperations, snapshot]);

  const sourceDiagnostics = snapshot?.diagnostics.source ?? [];
  const artifactDiagnostics = snapshot?.diagnostics.artifacts ?? [];
  const sectionDiagnostics = snapshot?.section_validation?.flatMap((result) =>
    result.diagnostics.map((item) =>
      `${snapshot && snapshot.entity_sections.find(section => section.section_id === result.section_id) ? referenceName(snapshot, snapshot.entity_sections.find(section => section.section_id === result.section_id)!.parent) : "Document"} › ${snapshot?.entity_sections.find(section => section.section_id === result.section_id)?.section_type === "sv" ? "SystemVerilog" : "Section"} · ${item.code}${item.line ? ` · ${item.line}${item.column ? `:${item.column}` : ""}` : ""}: ${item.message}`,
    ),
  ) ?? [];

  return (
    <div className="app-shell">
      <EditorMenuBar
        activityCount={activity.executions.length + activity.proposals.length + activity.assistant_changes.length}
        diagnosticCount={sourceDiagnostics.length + artifactDiagnostics.length + sectionDiagnostics.length}
        launchingAssistant={launchingAssistant}
        launchingCircuit={launchingCircuit}
        loading={loading}
        onBrowseDirectories={(directory) => client.browseDirectories(directory)}
        onCreate={createDocument}
        onCreateDirectory={(parent, name) => client.createDirectory(parent, name)}
        onError={setError}
        onOpen={openDocument}
        onOpenAssistant={launchDocumentAssistant}
        onOpenCircuit={launchCircuitDesigner}
        onViewChange={setView}
        path={path}
        snapshot={snapshot}
        view={view}
      />

      {notice && <div className="app-notice" role="status">{notice}<button aria-label="Dismiss notice" onClick={() => setNotice("")}>×</button></div>}
      {snapshot && <div className="spec-status-bar" aria-label="Spec status">
        <span role="status">{syncState}</span>
        <span>Assistant: {approvalPolicy === "automatic" ? "automatic submission" : "designer approval required"}</span>
      </div>}
      {externalChange && (
        <div className="app-refresh-notice" role="status">
          <span>Saved updates are pending. Your draft and its original revision are preserved.</span>
          <button type="button" onClick={() => void refreshExternalChange()}>{inlineEditActive ? "Review current source" : "Refresh"}</button>
        </div>
      )}
      {reviewSource && <aside className="app-refresh-notice">
        <details open><summary>Review saved source</summary>
          <details><summary>Technical details</summary><code>{reviewSource.source_revision_hash}</code></details>
          <p>Draft began at {draftRevision.current}. Compare the saved values with your draft before saving again.</p>
          <pre style={{ maxHeight: 300, overflow: "auto" }}>{JSON.stringify(reviewSource, null, 2)}</pre>
        </details>
        <button type="button" onClick={() => {
          reviewedRevision.current = reviewSource.source_revision_hash;
          setReviewSource(null);
          setNotice("Current source reviewed. Save your draft to resubmit against that revision, or cancel to load it.");
        }}>Use reviewed revision for next save</button>
      </aside>}
      {error && <div className="app-error" role="alert">{error}<button aria-label="Dismiss error" onClick={() => setError("")}>×</button></div>}

      <main>
        {loading && <LoadingState />}
        {!loading && batch && <div style={{ display: view === "document" ? undefined : "none" }}>
          <A2UIDocumentSurface
            batch={batch}
            editController={editController}
            onEditingChange={editingChanged}
          />
        </div>}
        {!loading && view === "activity" && (
          <ActivityView
            history={<AssistantHistory key={snapshot?.owner_document_key} client={client} documentKey={snapshot?.owner_document_key ?? ""} revision={`${snapshot?.source_revision_hash ?? ""}:${viewCursor}`} onChanged={loadView} />}
            activity={activity}
            snapshot={snapshot}
            onCancel={cancelActivity}
            onRefresh={refreshActivity}
            onReview={reviewProposal}
          />
        )}
        {!loading && view === "diagnostics" && (
          <DiagnosticsView source={sourceDiagnostics} artifacts={artifactDiagnostics} sections={sectionDiagnostics} />
        )}
        {!loading && !batch && !error && (
          <div className="empty-state">
            <h1>Start a specification</h1>
            <p>Use <strong>File → New Spec</strong> or <strong>File → Open Spec</strong> with a server-local <code>.spec</code> path.</p>
          </div>
        )}
      </main>

      {actionDialog && (
        <ActionDialog
          state={{ ...actionDialog, name: referenceName(snapshot, actionDialog.ref) }}
          onClose={() => setActionDialog(null)}
          onExecute={executeAction}
          onExplore={launchAssistant}
          exploring={launchingAssistant}
        />
      )}
      {activityDialog && (
        <ActivityDialog
          state={activityDialog}
          onClose={() => setActivityDialog(null)}
          onExecute={executeActivity}
        />
      )}
    </div>
  );
}

function AssistantHistory({ client, documentKey, revision, onChanged }: {
  client: SpecEditorHttpClient; documentKey: string; revision: string; onChanged: () => Promise<void>;
}) {
  const [page, setPage] = useState<{ items: Array<Record<string, unknown>>; next_cursor: number | null }>({ items: [], next_cursor: null });
  const [details, setDetails] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const epoch = useRef(0);
  const fetchPage = useCallback(async (before?: number) => {
    const token = ++epoch.current;
    try {
      const value = await client.getAssistantHistory(before);
      if (token === epoch.current) { setPage(value); setError(""); setDetails(null); }
    } catch (caught) { if (token === epoch.current) setError(String(caught)); }
  }, [client]);
  useEffect(() => { if (documentKey) void fetchPage(); return () => { ++epoch.current; }; }, [documentKey, revision, fetchPage]);
  const decide = async (id: string, decision: "approve" | "reject") => {
    const token = epoch.current;
    try {
      await client.decideAssistantSubmission(id, decision);
      if (token !== epoch.current) return;
      await onChanged(); await fetchPage();
    }
    catch (caught) { if (token === epoch.current) setError(String(caught)); }
  };
  return <UtilityPanel title="AI Assistant submission history" count={page.items.length}>
    {error && <p role="alert">{error}</p>}
    <button onClick={() => void fetchPage()}>Latest submissions</button>
    {page.items.map(item => <article className="activity-item" key={text(item.proposal_id)}>
      <strong>{text(item.title)}</strong><p>{text(item.summary)}</p>
      <p>{text(item.state)} · Proposal {String(item.ordinal)} · {text(item.created_at)}</p>
      <details><summary>Technical details</summary><p>Proposal {text(item.proposal_id)} · conversation {text(item.session_id)}</p><small>Base {text(item.base_source_revision_hash)} → saved {text(record((item.service_result ?? item.owner_result)).source_revision_hash)}</small></details>
      <button onClick={() => {
        const token = epoch.current;
        void client.getAssistantSubmission(text(item.proposal_id)).then(value => {
          if (token === epoch.current) setDetails(value);
        }).catch(caught => { if (token === epoch.current) setError(String(caught)); });
      }}>Details and diff</button>
      {item.state === "ready" && <>
        <button onClick={() => void decide(text(item.proposal_id), "approve")}>Approve</button>
        <button onClick={() => void decide(text(item.proposal_id), "reject")}>Reject</button>
      </>}
    </article>)}
    {details && <pre style={{ maxHeight: 400, overflow: "auto" }}>{JSON.stringify(details, null, 2)}</pre>}
    {page.next_cursor !== null && <button onClick={() => void fetchPage(page.next_cursor!)}>Older submissions</button>}
    {!page.items.length && <p>No AI Assistant submissions.</p>}
  </UtilityPanel>;
}

function referenceName(snapshot: DocumentSnapshot | null, ref: EntityRef): string {
  const entity = [...(snapshot?.components ?? []), ...(snapshot?.designs ?? [])].find(item => item.ref.entity_id === ref.entity_id);
  if (entity) return entity.display_name || entityName(entity.vlnv);
  const find = (blocks: DocumentSnapshot["narrative"]["blocks"]): string => {
    for (const block of blocks) {
      if (block.block_id === ref.entity_id) return block.text.split("\n")[0] || "Note";
      const name = find(block.children); if (name) return name;
    }
    return "";
  };
  return find(snapshot?.narrative.blocks ?? []) || ref.entity_kind.replaceAll("_", " ");
}

function entityName(vlnv?: string): string {
  return vlnv?.split(":")[2] || "source";
}

function TechnicalDetails({ value }: { value: unknown }) {
  const content = JSON.stringify(value, null, 2);
  return <details><summary>Technical details</summary><pre>{content}</pre><button type="button" onClick={() => void navigator.clipboard.writeText(content)}>Copy details</button></details>;
}

function LoadingState() {
  return (
    <div className="loading-state" role="status">
      <span />
      <p>Validating package and composing A2UI document…</p>
    </div>
  );
}

function ActivityView({
  history,
  activity,
  snapshot,
  onCancel,
  onRefresh,
  onReview,
}: {
  history: React.ReactNode;
  activity: ActivityState;
  snapshot: DocumentSnapshot | null;
  onCancel: (id: string) => Promise<void>;
  onRefresh: () => Promise<void>;
  onReview: (id: string, decision: "accept" | "reject") => Promise<void>;
}) {
  return (
    <div className="utility-page">
      <header className="utility-heading">
        <h1>Activity</h1>
        <button type="button" onClick={onRefresh}>Refresh</button>
      </header>
      <div className="activity-history">{history}</div>
      <div className="activity-grid">
        <UtilityPanel title="Action executions" count={activity.executions.length}>
          {activity.executions.slice().reverse().map((value) => {
            const item = record(value);
            const report = record(item.report);
            const diagnostics = Array.isArray(item.presentation_diagnostics) ? item.presentation_diagnostics : Array.isArray(item.diagnostics) ? item.diagnostics : [];
            const activityExecution = text(item.execution_type, "action") === "activity";
            const executionId = text(item.execution_id);
            const status = text(item.status, "unknown");
            const cancelling = Boolean(item.cancel_requested) && ["queued", "running"].includes(status);
            const warnings = Array.isArray(item.presentation_warnings) ? item.presentation_warnings : Array.isArray(report.warnings) ? report.warnings : [];
            const files = Array.isArray(report.files) ? report.files : [];
            return (
              <article className="activity-item" key={executionId}>
                <span className={`status status--${cancelling ? "running" : status}`}>
                  {cancelling ? "cancelling" : status}
                </span>
                <strong>{text(item.title, activityExecution ? "Activity" : "Action")}</strong>
                <p>{text(item.target_name, "")}</p>
                <TechnicalDetails value={item} />
                <p>{text(item.presentation_summary, text(report.summary, text(diagnostics[0], "No report summary")))}</p>
                {activityExecution && text(item.workspace_output_path, "") && (
                  <p><strong>Server path:</strong> <code>{text(item.workspace_output_path)}</code></p>
                )}
                {activityExecution && text(report.top_module, "") && (
                  <p>Top module: <code>{text(report.top_module)}</code> · {files.length} generated files</p>
                )}
                {warnings.map((warning, index) => <p className="activity-warning" key={index}>{String(warning)}</p>)}
                {activityExecution && ["queued", "running"].includes(status) && (
                  <div className="button-row">
                    <button disabled={cancelling} onClick={() => void onCancel(executionId)}>
                      {cancelling ? "Cancelling…" : "Cancel"}
                    </button>
                  </div>
                )}
              </article>
            );
          })}
          {!activity.executions.length && <p className="empty-copy">Run an action from a document section.</p>}
        </UtilityPanel>
        <UtilityPanel title="Artifacts" count={activity.artifacts.length}>
          {activity.artifacts.slice().reverse().map((value) => {
            const item = record(value);
            return (
              <article className="activity-item" key={text(item.artifact_id)}>
                <strong>{text(item.role, "Artifact")}</strong>
                <TechnicalDetails value={item} />
                <p>{text(item.media_type)} · {text(item.byte_length, "0")} bytes</p>
              </article>
            );
          })}
          {!activity.artifacts.length && <p className="empty-copy">No generated artifacts.</p>}
        </UtilityPanel>
        <UtilityPanel title="Change proposals" count={activity.proposals.length}>
          {activity.proposals.slice().reverse().map((value) => {
            const item = record(value);
            const proposalId = text(item.proposal_id);
            const status = text(item.review_status, "pending");
            const operations = Array.isArray(item.operations) ? item.operations : [];
            return (
              <article className="activity-item" key={proposalId}>
                <span className={`status status--${status}`}>{status}</span>
                <strong>{text(item.rationale, "Change proposal")}</strong>
                <small>{operations.length} proposed {operations.length === 1 ? "operation" : "operations"}</small>
                {status === "pending" && (
                  <div className="button-row">
                    <button onClick={() => onReview(proposalId, "accept")}>Accept</button>
                    <button className="secondary" onClick={() => onReview(proposalId, "reject")}>Reject</button>
                  </div>
                )}
              </article>
            );
          })}
          {!activity.proposals.length && <p className="empty-copy">No proposals awaiting review.</p>}
        </UtilityPanel>
        <UtilityPanel title="Accepted AI Assistant changes" count={activity.assistant_changes.length}>
          {activity.assistant_changes.slice().reverse().map((value) => {
            const item = record(value);
            const target = record(item.target);
            const documentScope = text(item.scope) === "document";
            const operations = Array.isArray(item.operations) ? item.operations : [];
            return (
              <article className="activity-item" key={text(item.proposal_id)}>
                <span className="status status--succeeded">accepted</span>
                <strong>
                  {documentScope
                    ? snapshot?.narrative.title || "Specification"
                    : referenceName(snapshot, target as unknown as EntityRef)}
                </strong>
                <TechnicalDetails value={item} />
                <p>{operations.length} applied {operations.length === 1 ? "operation" : "operations"}</p>
              </article>
            );
          })}
          {!activity.assistant_changes.length && <p className="empty-copy">No AI Assistant changes have been applied.</p>}
        </UtilityPanel>
      </div>
    </div>
  );
}

function ActivityDialog({
  state,
  onClose,
  onExecute,
}: {
  state: NonNullable<ActivityDialogState>;
  onClose: () => void;
  onExecute: (activity: EntityActivity) => Promise<void>;
}) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        aria-labelledby="activity-dialog-title"
        aria-modal="true"
        className="action-dialog"
        role="dialog"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p className="utility-kicker">{state.ref.entity_kind.replaceAll("_", " ")}</p>
            <h2 id="activity-dialog-title">Launch activity</h2>
          </div>
          <button aria-label="Close" className="icon-button" onClick={onClose}>×</button>
        </header>
        {state.loading && <p>Checking Activity availability…</p>}
        {!state.loading && !state.activities.length && <p>No Activities support this entity.</p>}
        {state.activities.map((item) => {
          const diagnostics = item.availability.diagnostics;
          return (
            <article className="action-option" key={item.definition.activity_id}>
              <div>
                <strong>{item.definition.title}</strong>
                <small>Version {item.definition.version}</small>
                <TechnicalDetails value={{ activity: item.definition.activity_id, version: item.definition.version }} />
                <p>{item.definition.description}</p>
                {diagnostics.map((diagnostic, index) => (
                  <p className={item.availability.available ? "activity-warning" : "diagnostic"} key={index}>
                    {diagnostic}
                  </p>
                ))}
              </div>
              <button
                disabled={!item.availability.available || Boolean(state.runningId)}
                onClick={() => void onExecute(item)}
              >
                {state.runningId === item.definition.activity_id ? "Queueing…" : "Run"}
              </button>
            </article>
          );
        })}
      </section>
    </div>
  );
}

function UtilityPanel({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section className="utility-panel">
      <header><h2>{title}</h2><span>{count}</span></header>
      <div>{children}</div>
    </section>
  );
}

function DiagnosticsView({
  source,
  artifacts,
  sections,
}: {
  source: string[];
  artifacts: string[];
  sections: string[];
}) {
  const count = source.length + artifacts.length + sections.length;
  return (
    <div className="utility-page utility-page--narrow">
      <header className="utility-heading">
        <h1>Diagnostics</h1>
        <span className={count ? "health health--warning" : "health"}>
          {count ? "Needs attention" : "Source valid"}
        </span>
      </header>
      <UtilityPanel title="Source package" count={source.length}>
        {source.map((item, index) => <p className="diagnostic" key={index}>{item}</p>)}
        {!source.length && <p className="diagnostic diagnostic--ok">No source diagnostics.</p>}
      </UtilityPanel>
      <UtilityPanel title="Entity sections" count={sections.length}>
        {sections.map((item, index) => <p className="diagnostic" key={index}>{item}</p>)}
        {!sections.length && <p className="diagnostic diagnostic--ok">No entity-section diagnostics.</p>}
      </UtilityPanel>
      <UtilityPanel title="Artifact sidecar" count={artifacts.length}>
        {artifacts.map((item, index) => <p className="diagnostic" key={index}>{item}</p>)}
        {!artifacts.length && <p className="diagnostic diagnostic--ok">No artifact diagnostics.</p>}
      </UtilityPanel>
    </div>
  );
}

function ActionDialog({
  state,
  onClose,
  onExecute,
  onExplore,
  exploring,
}: {
  state: NonNullable<ActionDialogState>;
  onClose: () => void;
  onExecute: (action: EntityAction) => Promise<void>;
  onExplore: (target: EntityRef) => Promise<void>;
  exploring: boolean;
}) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        aria-labelledby="action-dialog-title"
        aria-modal="true"
        className="action-dialog"
        role="dialog"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p className="utility-kicker">{state.ref.entity_kind.replaceAll("_", " ")}</p>
            <h2 id="action-dialog-title">Actions for {state.name || state.ref.entity_kind.replaceAll("_", " ")}</h2>
          </div>
          <button aria-label="Close" className="icon-button" onClick={onClose}>×</button>
        </header>
        <article className="action-option action-option--assistant">
          <div>
            <strong>Explore with AI Assistant</strong>
            <small>Creates a new conversation bound to this Component or Design</small>
            <p>Discuss ideas first, then request a typed proposal when ready.</p>
          </div>
          <button
            disabled={exploring || Boolean(state.runningId)}
            onClick={() => void onExplore(state.ref)}
          >
            {exploring ? "Opening…" : "Explore"}
          </button>
        </article>
        {state.loading && <p>Checking available actions…</p>}
        {!state.loading && !state.actions.length && <p>No actions target this Component or Design.</p>}
        {state.actions.map((action) => (
          <article className="action-option" key={action.action_id}>
            <div>
              <strong>{action.title}</strong>
              <small>{action.action_id} · v{action.version}</small>
              <p>Produces: {action.produced_artifact_roles.join(", ") || "review proposal"}</p>
            </div>
            <button
              disabled={Boolean(state.runningId)}
              onClick={() => onExecute(action)}
            >
              {state.runningId === action.action_id ? "Executing…" : "Execute"}
            </button>
          </article>
        ))}
      </section>
    </div>
  );
}

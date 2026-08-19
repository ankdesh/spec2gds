import { useCallback, useEffect, useMemo, useState } from "react";

import {
  A2UIDocumentSurface,
  SPEC_ENTITY_ACTION_EVENT,
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
  type EditorTransactionOperation,
  type EntityMetadataInput,
  type EntityAction,
  type EntityActivity,
  type EntityRef,
  type SourceChangeEvent,
} from "@spec2gds/document-core";

import EditorMenuBar, { type EditorView } from "./EditorMenuBar";
import { BrowserLogger } from "@spec2gds/observability/browser";

type ActionDialogState = {
  ref: EntityRef;
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
  const [view, setView] = useState<EditorView>("document");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionDialog, setActionDialog] = useState<ActionDialogState>(null);
  const [activityDialog, setActivityDialog] = useState<ActivityDialogState>(null);
  const [launchingCircuit, setLaunchingCircuit] = useState(false);
  const [launchingAssistant, setLaunchingAssistant] = useState(false);
  const [externalChange, setExternalChange] = useState<SourceChangeEvent | null>(null);
  const [browserLogger, setBrowserLogger] = useState<BrowserLogger | null>(null);

  const refreshActivity = useCallback(async () => {
    setActivity(await client.getActivity());
  }, [client]);

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
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const nextSnapshot = await client.openDocument(nextPath);
      const [nextBatch, nextActivity] = await Promise.all([
        client.getA2UIBatch(),
        client.getActivity(),
      ]);
      setSnapshot(nextSnapshot);
      setBatch(nextBatch);
      setActivity(nextActivity);
      setPath(nextPath);
      setView("document");
      setExternalChange(null);
      browserLogger?.event("documents", "opened", "Opened specification", "info", { path: nextPath, snapshot: nextSnapshot });
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      browserLogger?.event("documents", "open_failed", "Could not open specification", "error", { path: nextPath, error: String(caught) });
      return false;
    } finally {
      setLoading(false);
    }
  }, [browserLogger, client]);

  useEffect(() => {
    if (!snapshot) return;
    const events = new EventSource(client.activityEventsUrl());
    const updateExecution = (event: MessageEvent<string>) => {
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
    events.onerror = () => void refreshActivity();
    return () => events.close();
  }, [client, refreshActivity, snapshot]);

  const createDocument = useCallback(async (nextPath: string, title: string) => {
    if (!nextPath || !title.trim()) return false;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const nextSnapshot = await client.createDocument(nextPath, title.trim());
      const [nextBatch, nextActivity] = await Promise.all([
        client.getA2UIBatch(),
        client.getActivity(),
      ]);
      setSnapshot(nextSnapshot);
      setBatch(nextBatch);
      setActivity(nextActivity);
      setPath(nextPath);
      setView("document");
      setExternalChange(null);
      setNotice("Created a new specification package.");
      browserLogger?.event("documents", "created", "Created specification", "info", { path: nextPath, title, snapshot: nextSnapshot });
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      browserLogger?.event("documents", "create_failed", "Could not create specification", "error", { path: nextPath, title, error: String(caught) });
      return false;
    } finally {
      setLoading(false);
    }
  }, [browserLogger, client]);

  useEffect(() => {
    if (!snapshot) return;
    const source = new EventSource(client.eventsUrl());
    const onChange = (event: MessageEvent<string>) => {
      try {
        const change = JSON.parse(event.data) as SourceChangeEvent;
        if (
          change.document_id === snapshot.document_id
          && change.source_revision_hash !== snapshot.source_revision_hash
        ) {
          setExternalChange(change);
        }
      } catch {
        // Ignore malformed optional notifications; normal refresh remains available.
      }
    };
    source.addEventListener("source.changed", onChange as EventListener);
    return () => source.close();
  }, [client, snapshot?.document_id, snapshot?.source_revision_hash]);

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
    window.addEventListener(SPEC_ENTITY_ACTION_EVENT, onEntityAction);
    return () => window.removeEventListener(SPEC_ENTITY_ACTION_EVENT, onEntityAction);
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
        `Opened ${entityName(entity?.vlnv)} in Circuit Designer`
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
      const execution = await client.launchEntityActivity(
        ref,
        item.definition.activity_id,
        snapshot.source_revision_hash,
      );
      await refreshActivity();
      setActivityDialog(null);
      setNotice(`Queued ${item.definition.title} as ${text(execution.execution_id)}.`);
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
      pendingWindow.document.body.textContent = "Creating a new entity-bound AI Assistant chat…";
    }
    setLaunchingAssistant(true);
    setError("");
    try {
      const launch = await client.launchAssistant(target);
      if (pendingWindow) pendingWindow.location.replace(launch.assistant_url);
      else window.open(launch.assistant_url, "_blank", "noopener,noreferrer");
      setActionDialog(null);
      setNotice(`Opened a new AI Assistant chat for ${target.entity_id}.`);
    } catch (caught) {
      pendingWindow?.close();
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLaunchingAssistant(false);
    }
  };

  const launchDocumentAssistant = async () => {
    if (launchingAssistant || !snapshot) return;
    const pendingWindow = window.open("about:blank", "_blank");
    if (pendingWindow) {
      pendingWindow.opener = null;
      pendingWindow.document.title = "Opening AI Assistant…";
      pendingWindow.document.body.textContent = "Connecting to the active specification…";
    }
    setLaunchingAssistant(true);
    setError("");
    try {
      const launch = await client.launchDocumentAssistant();
      if (pendingWindow) pendingWindow.location.replace(launch.assistant_url);
      else window.open(launch.assistant_url, "_blank", "noopener,noreferrer");
      setNotice(`Opened a read-only AI Assistant chat for ${launch.document_id}.`);
    } catch (caught) {
      pendingWindow?.close();
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLaunchingAssistant(false);
    }
  };

  const refreshExternalChange = async () => {
    setLoading(true);
    setError("");
    try {
      const [nextSnapshot, nextBatch, nextActivity] = await Promise.all([
        client.getSnapshot(),
        client.getA2UIBatch(),
        client.getActivity(),
      ]);
      setSnapshot(nextSnapshot);
      setBatch(nextBatch);
      setActivity(nextActivity);
      setExternalChange(null);
      setNotice("Loaded the latest saved specification.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  };

  const commitEditorOperations = useCallback(async (
    operations: EditorTransactionOperation[],
    successNotice: string,
  ) => {
    if (!snapshot) throw new Error("No specification is open.");
    try {
      const result = await client.applyTransaction(snapshot.source_revision_hash, operations);
      setSnapshot(result.snapshot);
      setExternalChange(null);
      setError("");
      setNotice(successNotice);
      try {
        setBatch(await client.getA2UIBatch());
      } catch (refreshError) {
        setError(
          `The change was saved, but the document view could not refresh: ${refreshError instanceof Error ? refreshError.message : String(refreshError)}`,
        );
      }
    } catch (caught) {
      if (caught instanceof SpecEditorHttpError && caught.status === 409) {
        const latest = await client.getSnapshot();
        setSnapshot(latest);
        setExternalChange(null);
        throw new Error("The specification changed on disk. Your draft was preserved; review it and save again.");
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
          `Specification name changed to ${title} and saved automatically.`,
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
          label: entityName(component.vlnv),
          vlnv: component.vlnv,
        }));
      },
      async updateEntityMetadata(ref: EntityRef, value: EntityMetadataInput) {
        await commitEditorOperations(
          [{ type: "set_entity_metadata", entity: ref, ...value }],
          `${ref.entity_kind === "component" ? "Component" : "Design"} details saved automatically.`,
        );
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
            owner: ref,
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
          [{ type: "delete_entity_section", owner: ref, section_type: "sv", section_id: sectionId }],
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
            reason: "Ports on components with internal designs are read-only until boundary editing is supported.",
          }
          : { enabled: true, reason: "" };
      },
    };
  }, [commitEditorOperations, snapshot]);

  const sourceDiagnostics = snapshot?.diagnostics.source ?? [];
  const artifactDiagnostics = snapshot?.diagnostics.artifacts ?? [];
  const sectionDiagnostics = snapshot?.section_validation?.flatMap((result) =>
    result.diagnostics.map((item) =>
      `${result.section_id} · ${item.code}${item.line ? ` · ${item.line}${item.column ? `:${item.column}` : ""}` : ""}: ${item.message}`,
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
        onCreate={createDocument}
        onError={setError}
        onOpen={openDocument}
        onOpenAssistant={launchDocumentAssistant}
        onOpenCircuit={launchCircuitDesigner}
        onViewChange={setView}
        path={path}
        snapshot={snapshot}
        view={view}
      />

      {notice && <div className="app-notice" role="status">{notice}<button onClick={() => setNotice("")}>×</button></div>}
      {externalChange && (
        <div className="app-refresh-notice" role="status">
          <span>Document changed by AI Assistant. Your current view has not been replaced.</span>
          <button type="button" onClick={() => void refreshExternalChange()}>Refresh</button>
          <button type="button" aria-label="Dismiss" onClick={() => setExternalChange(null)}>×</button>
        </div>
      )}
      {error && <div className="app-error" role="alert">{error}<button onClick={() => setError("")}>×</button></div>}

      <main>
        {loading && <LoadingState />}
        {!loading && view === "document" && batch && (
          <A2UIDocumentSurface batch={batch} editController={editController} />
        )}
        {!loading && view === "activity" && (
          <ActivityView
            activity={activity}
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
            <p>Use <strong>File → New Specification</strong> or <strong>File → Open Specification</strong> with a server-local <code>.spec</code> path.</p>
          </div>
        )}
      </main>

      {actionDialog && (
        <ActionDialog
          state={actionDialog}
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

function entityName(vlnv?: string): string {
  return vlnv?.split(":")[2] || "source";
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
  activity,
  onCancel,
  onRefresh,
  onReview,
}: {
  activity: ActivityState;
  onCancel: (id: string) => Promise<void>;
  onRefresh: () => Promise<void>;
  onReview: (id: string, decision: "accept" | "reject") => Promise<void>;
}) {
  return (
    <div className="utility-page">
      <header className="utility-heading">
        <div><p className="utility-kicker">Immutable provenance</p><h1>Activity</h1></div>
        <button type="button" onClick={onRefresh}>Refresh</button>
      </header>
      <div className="activity-grid">
        <UtilityPanel title="Action executions" count={activity.executions.length}>
          {activity.executions.slice().reverse().map((value) => {
            const item = record(value);
            const report = record(item.report);
            const diagnostics = Array.isArray(item.diagnostics) ? item.diagnostics : [];
            const activityExecution = text(item.execution_type, "action") === "activity";
            const executionId = text(item.execution_id);
            const status = text(item.status, "unknown");
            const cancelling = Boolean(item.cancel_requested) && ["queued", "running"].includes(status);
            const warnings = Array.isArray(report.warnings) ? report.warnings : [];
            const files = Array.isArray(report.files) ? report.files : [];
            return (
              <article className="activity-item" key={executionId}>
                <span className={`status status--${cancelling ? "running" : status}`}>
                  {cancelling ? "cancelling" : status}
                </span>
                <strong>{text(item.activity_id, text(item.action_id))}</strong>
                <small>{executionId}</small>
                <p>{text(report.summary, text(diagnostics[0], "No report summary"))}</p>
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
                <small>{text(item.artifact_id)}</small>
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
                    ? "document · top-level creation"
                    : `${text(target.entity_kind, "entity")} · ${text(target.entity_id)}`}
                </strong>
                <small>{text(item.proposal_id)}</small>
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
                <small>{item.definition.activity_id} · v{item.definition.version}</small>
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
        <div><p className="utility-kicker">Validation status</p><h1>Diagnostics</h1></div>
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
            <h2 id="action-dialog-title">Actions for {state.ref.entity_id}</h2>
          </div>
          <button aria-label="Close" className="icon-button" onClick={onClose}>×</button>
        </header>
        <article className="action-option action-option--assistant">
          <div>
            <strong>Explore with AI Assistant</strong>
            <small>Creates a new chat bound to this entity</small>
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
        {!state.loading && !state.actions.length && <p>No actions target this entity kind.</p>}
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

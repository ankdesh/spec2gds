import {
  ComposerPrimitive,
  MessagePrimitive,
  ThreadListItemPrimitive,
  ThreadListPrimitive,
  ThreadPrimitive,
  useAuiState,
} from "@assistant-ui/react";
import { CircuitProposalDiffViewer } from "../../../circuit-designer/packages/react/src/index";
import type { CircuitDiff, CircuitDocument, Diagnostic } from "@spec2gds/circuit-core";
import { DocumentSectionView } from "@spec2gds/document-a2ui-react";
import type { DocumentSectionData } from "@spec2gds/document-core";
import {
  Archive,
  ArrowLeft,
  Bot,
  Check,
  ChevronDown,
  CircleAlert,
  Cpu,
  FileText,
  MessageSquarePlus,
  Send,
  Trash2,
  User,
  X,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { BrowserLogger } from "@spec2gds/observability/browser";

import { ApiError, assistantApi } from "./api";
import { useAssistantApp } from "./runtime";
import type {
  AssistantThread,
  ProposalReview,
  ServiceDirectory,
  SpecDiffEntry,
} from "./types";

export function App() {
  const [browserLogger, setBrowserLogger] = useState<BrowserLogger | null>(null);
  useEffect(() => {
    void assistantApi.getServices().then((directory) => {
      setBrowserLogger(new BrowserLogger("/api/logs/events", directory.logging));
    }).catch(() => undefined);
  }, []);
  useEffect(() => browserLogger?.captureGlobalErrors(), [browserLogger]);

  return (
    <main className="app-shell">
      <aside className="thread-sidebar">
        <header className="brand">
          <span className="brand-mark"><Cpu size={20} /></span>
          <span><strong>AI Assistant</strong><small>spec2gds</small></span>
        </header>
        <ThreadListPrimitive.Root className="thread-list">
          <ThreadListPrimitive.New className="new-thread">
            <MessageSquarePlus size={17} /> New assistant chat
          </ThreadListPrimitive.New>
          <div className="thread-list-items">
            <ThreadListPrimitive.Items components={{ ThreadListItem }} />
          </div>
          <details className="archived">
            <summary><Archive size={14} /> Archived</summary>
            <ThreadListPrimitive.Items
              archived
              components={{ ThreadListItem: ArchivedThreadListItem }}
            />
          </details>
        </ThreadListPrimitive.Root>
        <footer className="sidebar-note">
          Independent tool · Circuit Designer and Spec Editor remain usable without it.
        </footer>
      </aside>
      <Conversation />
    </main>
  );
}

function ThreadListItem() {
  const id = useAuiState((state) => state.threadListItem.remoteId ?? state.threadListItem.id);
  const { threads } = useAssistantApp();
  const domain = threads[id]?.domain;
  return (
    <ThreadListItemPrimitive.Root className="thread-item">
      <ThreadListItemPrimitive.Trigger className="thread-trigger">
        {domain && threads[id]?.document_id && <span className={`domain-badge domain-badge--${domain}`}>{domain}</span>}
        <ThreadListItemPrimitive.Title fallback="New assistant chat" />
      </ThreadListItemPrimitive.Trigger>
      <ThreadListItemPrimitive.Archive className="icon-button" title="Archive chat">
        <Archive size={14} />
      </ThreadListItemPrimitive.Archive>
      <ThreadListItemPrimitive.Delete className="icon-button danger" title="Delete chat">
        <Trash2 size={14} />
      </ThreadListItemPrimitive.Delete>
    </ThreadListItemPrimitive.Root>
  );
}

function ArchivedThreadListItem() {
  const id = useAuiState((state) => state.threadListItem.remoteId ?? state.threadListItem.id);
  const { threads } = useAssistantApp();
  const domain = threads[id]?.domain;
  return (
    <ThreadListItemPrimitive.Root className="thread-item">
      <ThreadListItemPrimitive.Trigger className="thread-trigger">
        {domain && threads[id]?.document_id && <span className={`domain-badge domain-badge--${domain}`}>{domain}</span>}
        <ThreadListItemPrimitive.Title fallback="Archived assistant chat" />
      </ThreadListItemPrimitive.Trigger>
      <ThreadListItemPrimitive.Unarchive className="icon-button" title="Restore chat">
        <Archive size={14} />
      </ThreadListItemPrimitive.Unarchive>
      <ThreadListItemPrimitive.Delete className="icon-button danger" title="Delete chat">
        <Trash2 size={14} />
      </ThreadListItemPrimitive.Delete>
    </ThreadListItemPrimitive.Root>
  );
}

function Conversation() {
  const threadId = useAuiState(
    (state) => state.threadListItem.remoteId ?? state.threadListItem.id,
  );
  const {
    threads,
    errors,
    refreshThread,
    refreshReviews,
    setThread,
    setError,
  } = useAssistantApp();
  const thread = threads[threadId];

  useEffect(() => {
    if (!threadId) return;
    void (async () => {
      try {
        await refreshThread(threadId);
      } catch (reason) {
        if (reason instanceof ApiError && reason.status === 404) {
          setThread(await assistantApi.createThread(threadId));
        } else {
          throw reason;
        }
      }
      await refreshReviews(threadId);
    })().catch((reason: unknown) => {
      setError(threadId, reason instanceof Error ? reason.message : String(reason));
    });
  }, [
    threadId,
    refreshThread,
    refreshReviews,
    setThread,
    setError,
  ]);

  return (
    <section className="conversation">
      <DomainHeader threadId={threadId} thread={thread} />
      {!thread?.document_id ? (
        <ConnectionSetup threadId={threadId} thread={thread} />
      ) : (
        <ThreadPrimitive.Root className="thread-root">
          <ThreadPrimitive.Viewport className="thread-viewport">
            <ThreadPrimitive.Empty>
              <Welcome thread={thread} />
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages
              components={{ UserMessage, AssistantMessage }}
            />
            {errors[threadId] && (
              <p className="inline-error"><CircleAlert size={16} /> {errors[threadId]}</p>
            )}
            <ThreadPrimitive.ViewportFooter className="composer-footer">
              <ComposerPrimitive.Root className="composer">
                <ComposerPrimitive.Input
                  className="composer-input"
                  placeholder={thread.domain === "spec"
                    ? "Explore the selected specification…"
                    : "Describe the circuit change you want to propose…"}
                  aria-label={thread.domain === "spec" ? "Spec exploration request" : "Circuit edit request"}
                />
                <ComposerPrimitive.Send className="send-button" title="Send request">
                  <Send size={18} />
                </ComposerPrimitive.Send>
              </ComposerPrimitive.Root>
              {thread.domain === "spec" && (
                <ThreadPrimitive.Suggestion
                  className="prepare-proposal"
                  prompt="Prepare a formal proposal based on our conversation."
                  method="replace"
                  autoSend
                >
                  Prepare proposal
                </ThreadPrimitive.Suggestion>
              )}
              <small>
                {thread.domain === "spec"
                  ? "Explore freely. A typed change is created only when you request a proposal."
                  : "The agent creates a proposal. Nothing reaches Circuit Designer until you review and send it."}
              </small>
            </ThreadPrimitive.ViewportFooter>
          </ThreadPrimitive.Viewport>
        </ThreadPrimitive.Root>
      )}
    </section>
  );
}

function DomainHeader({
  threadId,
  thread,
}: {
  threadId: string;
  thread?: AssistantThread;
}) {
  const { setThread } = useAssistantApp();
  const togglePng = async () => {
    if (!thread) return;
    setThread(
      await assistantApi.updateThread(threadId, {
        include_png: !thread.include_png,
      }),
    );
  };
  return (
    <header className="conversation-header">
      <div>
        <span className="eyebrow">
          {!thread?.document_id
            ? "Choose a workspace"
            : thread.domain === "spec"
              ? "Spec exploration agent"
              : "Circuit editing agent"}
        </span>
        <h1>{thread?.document_id ? thread.title : "Connect AI Assistant"}</h1>
      </div>
      {thread?.document_id && (
        <div className="circuit-identity">
          <span>
            <i className="status-dot" /> {thread.document_id}
            {thread.domain === "spec" && thread.entity_id
              ? ` · ${thread.entity_kind?.replaceAll("_", " ")} · ${thread.entity_id}`
              : ""}
          </span>
          {thread.domain === "circuit" && (
            <button
              className={thread.include_png ? "toggle active" : "toggle"}
              type="button"
              onClick={() => void togglePng()}
              aria-pressed={thread.include_png}
            >
              Include PNG context
            </button>
          )}
        </div>
      )}
    </header>
  );
}

type ConnectionTarget = "circuit" | "spec";

const fallbackServices: ServiceDirectory = {
  schema_version: 2,
  services: {
    spec_editor: {
      service_url: "http://127.0.0.1:8000",
      ui_url: "http://127.0.0.1:8000/editor",
      available: false,
      detail: "Not checked",
    },
    circuit_designer: {
      service_url: "http://127.0.0.1:4100/api/circuit-designer/v1",
      ui_url: "http://127.0.0.1:4180",
      available: false,
      detail: "Not checked",
    },
    ai_assistant: {
      service_url: window.location.origin,
      ui_url: window.location.origin,
      available: true,
      detail: "Available",
    },
  },
  logging: { enabled: false, level: "info" },
};

function ConnectionSetup({
  threadId,
  thread,
}: {
  threadId: string;
  thread?: AssistantThread;
}) {
  const requestedWorkspace = new URLSearchParams(window.location.search).get("workspace");
  const [target, setTarget] = useState<ConnectionTarget | null>(
    thread?.domain === "spec" || requestedWorkspace === "spec"
      ? "spec"
      : requestedWorkspace === "circuit"
        ? "circuit"
        : null,
  );
  const [services, setServices] = useState<ServiceDirectory>(fallbackServices);
  const [checkingServices, setCheckingServices] = useState(true);

  useEffect(() => {
    setCheckingServices(true);
    void assistantApi.getServices()
      .then(setServices)
      .catch(() => undefined)
      .finally(() => setCheckingServices(false));
  }, []);

  useEffect(() => {
    if (thread?.domain === "spec") setTarget("spec");
  }, [thread?.domain]);

  if (target === "circuit") {
    return <ConnectCircuit
      threadId={threadId}
      onBack={() => setTarget(null)}
      serviceUrl={services.services.circuit_designer.service_url}
      serviceStatus={services.services.circuit_designer}
    />;
  }
  if (target === "spec") {
    return <ConnectSpec
      threadId={threadId}
      onBack={() => setTarget(null)}
      service={services.services.spec_editor}
    />;
  }
  return (
    <div className="connect-stage">
      <section className="connect-card connection-picker" aria-labelledby="connection-heading">
        <span className="eyebrow">New assistant chat</span>
        <h2 id="connection-heading">What do you want to work with?</h2>
        <p>
          Each chat connects to one target. Choose the owning application so the assistant loads the right context and proposal workflow.
        </p>
        <div className="connection-options">
          <button type="button" onClick={() => setTarget("circuit")}>
            <span className="connection-option-icon"><Cpu size={24} /></span>
            <strong>Circuit Designer</strong>
            <small>Work with circuit instances, nets, and connectivity.</small>
            <ServiceStatus available={services.services.circuit_designer.available} checking={checkingServices} />
            <span className="connection-option-action">Connect a circuit</span>
          </button>
          <button type="button" onClick={() => setTarget("spec")}>
            <span className="connection-option-icon"><FileText size={24} /></span>
            <strong>Spec Editor</strong>
            <small>Explore an IP-XACT entity and prepare reviewed source changes.</small>
            <ServiceStatus available={services.services.spec_editor.available} checking={checkingServices} />
            <span className="connection-option-action">Connect a specification</span>
          </button>
        </div>
      </section>
    </div>
  );
}

function ServiceStatus({ available, checking }: { available: boolean; checking: boolean }) {
  return (
    <span className={`service-status${available ? " service-status--available" : ""}`}>
      <i /> {checking ? "Checking…" : available ? "Available" : "Not detected"}
    </span>
  );
}

function ConnectCircuit({
  threadId,
  onBack,
  serviceUrl,
  serviceStatus,
}: {
  threadId: string;
  onBack(): void;
  serviceUrl: string;
  serviceStatus: ServiceDirectory["services"]["circuit_designer"];
}) {
  const { setThread, setError, errors } = useAssistantApp();
  const [baseUrl, setBaseUrl] = useState(serviceUrl);
  const [documentId, setDocumentId] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => setBaseUrl(serviceUrl), [serviceUrl]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(threadId);
    try {
      const result = await assistantApi.bindCircuit(threadId, baseUrl, documentId);
      setThread(result.thread);
    } catch (reason) {
      setError(threadId, reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="connect-stage">
      <form className="connect-card" onSubmit={(event) => void submit(event)}>
        <button className="back-action" type="button" onClick={onBack}>
          <ArrowLeft size={15} /> Change workspace
        </button>
        <span className="connect-icon"><Cpu size={26} /></span>
        <span className="eyebrow">Circuit Designer · One-time connection</span>
        <h2>Connect this chat to a circuit</h2>
        <p>
          The binding is fixed for the life of this chat, keeping its history and proposals tied to one design.
        </p>
        <ServiceStatus available={serviceStatus.available} checking={false} />
        <label>
          Circuit service URL
          <input
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            required
          />
        </label>
        <label>
          Document ID
          <input
            value={documentId}
            onChange={(event) => setDocumentId(event.target.value)}
            placeholder="my-circuit"
            required
          />
        </label>
        {errors[threadId] && <p className="form-error">{errors[threadId]}</p>}
        <button className="primary-action" type="submit" disabled={busy}>
          {busy ? "Connecting…" : "Connect circuit"}
        </button>
      </form>
    </div>
  );
}

function ConnectSpec({
  threadId,
  onBack,
  service,
}: {
  threadId: string;
  onBack(): void;
  service: ServiceDirectory["services"]["spec_editor"];
}) {
  const { setThread, setError, errors } = useAssistantApp();
  const [baseUrl, setBaseUrl] = useState(service.service_url);
  const [documentId, setDocumentId] = useState("");
  const [entityKind, setEntityKind] = useState<Exclude<AssistantThread["entity_kind"], null>>("component");
  const [entityId, setEntityId] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => setBaseUrl(service.service_url), [service.service_url]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(threadId);
    try {
      const result = await assistantApi.bindSpec(
        threadId,
        baseUrl,
        documentId,
        entityKind,
        entityId,
      );
      setThread(result.thread);
    } catch (reason) {
      setError(threadId, reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="connect-stage">
      <form className="connect-card" onSubmit={(event) => void submit(event)}>
        <button className="back-action" type="button" onClick={onBack}>
          <ArrowLeft size={15} /> Change workspace
        </button>
        <span className="connect-icon"><FileText size={26} /></span>
        <span className="eyebrow">Spec Editor · Entity-bound connection</span>
        <h2>Connect this chat to a specification</h2>
        <p>
          A Spec chat is tied to one entity so its context and proposed changes remain precise.
        </p>
        <div className="connection-guidance">
          <strong>Recommended</strong>
          <span>
            In Spec Editor, open an entity's <b>Options</b> menu, choose <b>More actions…</b>, then <b>Explore with AI Assistant</b>. The editor fills in these identifiers automatically.
          </span>
          <ServiceStatus available={service.available} checking={false} />
          <a href={service.ui_url} target="_blank" rel="noreferrer">
            Open Spec Editor
          </a>
        </div>
        <details className="manual-connection">
          <summary>Connect manually</summary>
          <label>
            Spec Editor service URL
            <input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              required
            />
          </label>
          <label>
            Document ID
            <input
              value={documentId}
              onChange={(event) => setDocumentId(event.target.value)}
              placeholder="spec_document_id"
              required
            />
          </label>
          <label>
            Entity type
            <select
              value={entityKind}
              onChange={(event) => setEntityKind(event.target.value as Exclude<AssistantThread["entity_kind"], null>)}
            >
              <option value="component">Component</option>
              <option value="design">Design</option>
              <option value="bus_definition">Bus definition</option>
              <option value="abstraction_definition">Abstraction definition</option>
              <option value="narrative_block">Narrative block</option>
            </select>
          </label>
          <label>
            Entity ID
            <input
              value={entityId}
              onChange={(event) => setEntityId(event.target.value)}
              placeholder="entity_id"
              required
            />
          </label>
          {errors[threadId] && <p className="form-error" role="alert">{errors[threadId]}</p>}
          <button className="primary-action" type="submit" disabled={busy}>
            {busy ? "Connecting…" : "Connect Spec Editor"}
          </button>
        </details>
      </form>
    </div>
  );
}

function Welcome({ thread }: { thread: AssistantThread }) {
  if (thread.domain === "spec") {
    return (
      <div className="welcome">
        <span className="welcome-icon"><Bot size={26} /></span>
        <h2>Explore {thread.entity_id}</h2>
        <p>
          Discuss intent, interfaces, internal structure, and connected context. The agent will not create a formal change until you ask for a proposal.
        </p>
        <div className="suggestion-grid">
          <ThreadPrimitive.Suggestion
            prompt="Explain this entity's current role, connections, and design constraints."
            method="replace"
            autoSend
          >
            Explain the current design
          </ThreadPrimitive.Suggestion>
          <ThreadPrimitive.Suggestion
            prompt="Explore alternatives for improving this entity without preparing a proposal yet."
            method="replace"
            autoSend
          >
            Explore improvement ideas
          </ThreadPrimitive.Suggestion>
        </div>
      </div>
    );
  }
  return (
    <div className="welcome">
      <span className="welcome-icon"><Bot size={26} /></span>
      <h2>What should change in {thread.document_id}?</h2>
      <p>
        Ask for instance or connectivity changes. The agent uses the current circuit snapshot and prepares an explicit operation proposal for your review.
      </p>
      <div className="suggestion-grid">
        <ThreadPrimitive.Suggestion
          prompt="Add two instances of the main processing block and connect their inputs in parallel."
          method="replace"
          autoSend
        >
          Add parallel processing blocks
        </ThreadPrimitive.Suggestion>
        <ThreadPrimitive.Suggestion
          prompt="Review the current connectivity and propose a clean fan-out from the source output."
          method="replace"
          autoSend
        >
          Propose a source fan-out
        </ThreadPrimitive.Suggestion>
      </div>
    </div>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="message user-message">
      <span className="avatar"><User size={16} /></span>
      <div className="message-body">
        <span className="message-label">You</span>
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  const threadId = useAuiState(
    (state) => state.threadListItem.remoteId ?? state.threadListItem.id,
  );
  const { threads } = useAssistantApp();
  return (
    <MessagePrimitive.Root className="message assistant-message">
      <span className="avatar agent"><Bot size={16} /></span>
      <div className="message-body">
        <span className="message-label">{threads[threadId]?.domain === "spec" ? "Spec agent" : "Circuit agent"}</span>
        <MessagePrimitive.Parts />
        <div className="inline-error"><MessagePrimitive.Error /></div>
        <MessagePrimitive.If last>
          <ProposalFeed />
        </MessagePrimitive.If>
      </div>
    </MessagePrimitive.Root>
  );
}

function ProposalFeed() {
  const threadId = useAuiState(
    (state) => state.threadListItem.remoteId ?? state.threadListItem.id,
  );
  const { reviews } = useAssistantApp();
  const items = reviews[threadId] ?? [];
  if (!items.length) return null;
  const visibleItems = items.at(-1)?.artifact.kind === "spec_change_proposal"
    ? [items.at(-1)!]
    : items;
  return (
    <div className="proposal-feed">
      {visibleItems.map((review) => (
        <ProposalCard key={review.proposal_id} threadId={threadId} review={review} />
      ))}
    </div>
  );
}

function ProposalCard({
  threadId,
  review,
}: {
  threadId: string;
  review: ProposalReview;
}) {
  const { setReview, setError } = useAssistantApp();
  const [busy, setBusy] = useState(false);
  const diagnostics = Array.isArray(review.diagnostics)
    ? review.diagnostics
    : review.diagnostics
      ? [review.diagnostics]
      : [];
  const isSpec = review.artifact.kind === "spec_change_proposal";
  const canReview =
    review.state === "ready" &&
    review.base_document &&
    review.candidate &&
    review.diff;
  const stateLabel = useMemo(
    () =>
      ({
        draft: "Preparing",
        invalid: "Needs revision",
        ready: "Ready for review",
        stale: isSpec ? "Specification changed" : "Circuit changed",
        discarded: "Discarded",
        sent: "Sent to Circuit Designer",
        applied: "Applied to Spec Editor",
      })[review.state],
    [review.state, isSpec],
  );

  const act = async (action: "apply" | "send" | "discard") => {
    setBusy(true);
    setError(threadId);
    try {
      const updated =
        action === "discard"
          ? await assistantApi.discardReview(threadId, review.proposal_id)
          : action === "apply"
            ? await assistantApi.applySpecProposal(threadId, review.proposal_id)
            : await assistantApi.submitProposal(threadId, review.proposal_id);
      setReview(threadId, updated);
    } catch (reason) {
      setError(threadId, reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className={`proposal-card proposal-${review.state}`}>
      <header>
        <div>
          <span className="proposal-state">{stateLabel}</span>
          <h3>{review.artifact.title}</h3>
          <p>{review.artifact.summary}</p>
        </div>
        <span className="operation-count">
          {operationCount(review.artifact)} operations
        </span>
      </header>
      {canReview && !isSpec && (
        <CircuitProposalDiffViewer
          before={review.base_document as CircuitDocument}
          after={review.candidate as CircuitDocument}
          diff={review.diff as CircuitDiff}
          diagnostics={diagnostics as Diagnostic[]}
          height={360}
        />
      )}
      {canReview && isSpec && (
        <SpecProposalDiffViewer
          before={review.base_document as DocumentSectionData[]}
          after={review.candidate as DocumentSectionData[]}
          diff={review.diff as SpecDiffEntry[]}
          diagnostics={diagnostics}
        />
      )}
      <div className="proposal-details">
        <details open>
          <summary><ChevronDown size={15} /> Reasoning and assumptions</summary>
          <p>{review.artifact.rationale}</p>
          {review.artifact.assumptions.length > 0 && (
            <ul>
              {review.artifact.assumptions.map((assumption) => (
                <li key={assumption}>{assumption}</li>
              ))}
            </ul>
          )}
        </details>
        <details>
          <summary><ChevronDown size={15} /> Exact operations</summary>
          <pre>{JSON.stringify(proposalOperations(review.artifact), null, 2)}</pre>
        </details>
      </div>
      {review.state === "invalid" && (
        <p className="proposal-warning">
          <CircleAlert size={16} /> {isSpec ? "Spec Editor" : "Circuit Designer"} rejected this preview. Ask the agent for a corrected proposal.
        </p>
      )}
      {review.state === "stale" && (
        <p className="proposal-warning">
          <CircleAlert size={16} /> The {isSpec ? "Spec source" : "circuit revision"} changed. Request a fresh proposal before {isSpec ? "applying" : "sending"}.
        </p>
      )}
      {review.state === "ready" && (
        <footer>
          <button
            type="button"
            className="secondary-action"
            disabled={busy}
            onClick={() => void act("discard")}
          >
            <X size={16} /> Discard
          </button>
          <button
            type="button"
            className="primary-action"
            disabled={busy}
            onClick={() => void act(isSpec ? "apply" : "send")}
          >
            <Check size={16} /> {isSpec ? "Approve and apply" : "Send to Circuit Designer"}
          </button>
        </footer>
      )}
    </article>
  );
}

function operationCount(artifact: ProposalReview["artifact"]): number {
  return artifact.kind === "spec_change_proposal"
    ? artifact.operations.length
    : artifact.batch.operations.length;
}

function proposalOperations(artifact: ProposalReview["artifact"]): unknown[] {
  return artifact.kind === "spec_change_proposal"
    ? artifact.operations
    : artifact.batch.operations;
}

function SpecProposalDiffViewer({
  before,
  after,
  diff,
  diagnostics,
}: {
  before: DocumentSectionData[];
  after: DocumentSectionData[];
  diff: SpecDiffEntry[];
  diagnostics: unknown[];
}) {
  const paths = diff.map((item) => item.path);
  const byId = new Map(before.map((section) => [section.section_id, section]));
  const candidateById = new Map(after.map((section) => [section.section_id, section]));
  const sectionIds = Array.from(new Set([...byId.keys(), ...candidateById.keys()]));
  return (
    <div className="spec-proposal-diff">
      {diagnostics.length > 0 && (
        <div className="spec-proposal-diagnostics">
          {diagnostics.map((item, index) => (
            <p key={index}><CircleAlert size={14} /> {diagnosticText(item)}</p>
          ))}
        </div>
      )}
      <div className="spec-proposal-columns">
        <div><h4>Current</h4></div>
        <div><h4>Proposed</h4></div>
        {sectionIds.map((sectionId) => (
          <div className="spec-proposal-section-pair" key={sectionId}>
            <div>
              {byId.get(sectionId)
                ? <DocumentSectionView section={byId.get(sectionId)!} label="Current" />
                : <p className="empty-copy">Section will be added.</p>}
            </div>
            <div>
              {candidateById.get(sectionId)
                ? <DocumentSectionView section={candidateById.get(sectionId)!} changedPaths={paths} label="Proposed" />
                : <p className="empty-copy">Section will be removed.</p>}
            </div>
          </div>
        ))}
      </div>
      <details className="spec-field-diff">
        <summary><ChevronDown size={15} /> Changed fields ({diff.length})</summary>
        <ul>
          {diff.map((item, index) => (
            <li key={`${item.path}-${index}`}>
              <code>{item.path}</code>
              <span>{readableValue(item.before)} → {readableValue(item.after)}</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function readableValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value || "—";
  return JSON.stringify(value);
}

function diagnosticText(value: unknown): string {
  if (typeof value === "string") return value;
  if (value && typeof value === "object" && "message" in value) {
    return String((value as { message: unknown }).message);
  }
  return JSON.stringify(value);
}

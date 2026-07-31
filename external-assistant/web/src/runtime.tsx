import {
  AssistantRuntimeProvider,
  RuntimeAdapterProvider,
  type ThreadHistoryAdapter,
  type ThreadMessage,
  useAuiState,
  useRemoteThreadListRuntime,
  type RemoteThreadListAdapter,
} from "@assistant-ui/react";
import {
  A2AClient,
  type A2AArtifact,
  type A2AMessage,
  type A2ASendMessageConfiguration,
  type A2AStreamEvent,
  useA2ARuntime,
} from "@assistant-ui/react-a2a";
import { createAssistantStream } from "assistant-stream";
import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

import { assistantApi, deserializeMessage } from "./api";
import type {
  AssistantThread,
  CircuitProposalArtifact,
  ProposalReview,
  SpecProposalArtifact,
} from "./types";

interface AssistantAppContextValue {
  threads: Record<string, AssistantThread>;
  reviews: Record<string, ProposalReview[]>;
  errors: Record<string, string | undefined>;
  refreshThread(id: string): Promise<void>;
  refreshReviews(id: string): Promise<void>;
  setThread(thread: AssistantThread): void;
  setReview(threadId: string, review: ProposalReview): void;
  setError(threadId: string, error?: string): void;
}

const AssistantAppContext = createContext<AssistantAppContextValue | null>(null);

export function useAssistantApp(): AssistantAppContextValue {
  const context = useContext(AssistantAppContext);
  if (!context) throw new Error("AssistantAppProvider is missing.");
  return context;
}

class DomainAwareA2AClient extends A2AClient {
  constructor(private readonly getContext: () => Promise<{ thread: AssistantThread; context: unknown }>) {
    super({ baseUrl: window.location.origin, basePath: "/a2a" });
  }

  private async withDomainContext(message: A2AMessage): Promise<A2AMessage> {
    const { thread, context } = await this.getContext();
    const proposalRequested = thread.domain === "spec" && message.parts.some((part) => {
      const text = (part as { text?: string }).text ?? "";
      return /\b(prepare|create|generate|make|turn\s+this\s+into)\b.{0,30}\bproposal\b|\bpropose\s+(the\s+)?changes?\b/i.test(text);
    });
    return {
      ...message,
      parts: [
        ...message.parts,
        {
          data: {
            kind: thread.domain === "spec" ? "spec_context" : "circuit_context",
            ...(context as object),
            proposal_requested: proposalRequested,
          },
        },
      ],
    };
  }

  override async sendMessage(
    message: A2AMessage,
    configuration?: A2ASendMessageConfiguration,
    metadata?: Record<string, unknown>,
    signal?: AbortSignal,
  ) {
    return super.sendMessage(
      await this.withDomainContext(message),
      configuration,
      metadata,
      signal,
    );
  }

  override async *streamMessage(
    message: A2AMessage,
    configuration?: A2ASendMessageConfiguration,
    metadata?: Record<string, unknown>,
    signal?: AbortSignal,
  ): AsyncGenerator<A2AStreamEvent> {
    yield* super.streamMessage(
      await this.withDomainContext(message),
      configuration,
      metadata,
      signal,
    );
  }
}

function titleFromMessages(messages: readonly ThreadMessage[]): string {
  const firstUser = messages.find((message) => message.role === "user");
  const text = firstUser?.content
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join(" ")
    .trim();
  return text ? text.slice(0, 60) : "New design chat";
}

export function AssistantAppProvider({ children }: PropsWithChildren) {
  const [threads, setThreads] = useState<Record<string, AssistantThread>>({});
  const [reviews, setReviews] = useState<Record<string, ProposalReview[]>>({});
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});

  const setThread = useCallback((thread: AssistantThread) => {
    setThreads((current) => ({ ...current, [thread.id]: thread }));
  }, []);
  const setReview = useCallback((threadId: string, review: ProposalReview) => {
    setReviews((current) => {
      const previous = current[threadId] ?? [];
      return {
        ...current,
        [threadId]: [
          ...previous.filter((item) => item.proposal_id !== review.proposal_id),
          review,
        ],
      };
    });
  }, []);
  const setError = useCallback((threadId: string, error?: string) => {
    setErrors((current) => ({ ...current, [threadId]: error }));
  }, []);
  const refreshThread = useCallback(async (id: string) => {
    setThread(await assistantApi.getThread(id));
  }, [setThread]);
  const refreshReviews = useCallback(async (id: string) => {
    const nextReviews = await assistantApi.listReviews(id);
    setReviews((current) => ({ ...current, [id]: nextReviews }));
  }, []);

  const value = useMemo(
    () => ({
      threads,
      reviews,
      errors,
      refreshThread,
      refreshReviews,
      setThread,
      setReview,
      setError,
    }),
    [
      threads,
      reviews,
      errors,
      refreshThread,
      refreshReviews,
      setThread,
      setReview,
      setError,
    ],
  );
  return (
    <AssistantAppContext.Provider value={value}>
      <RuntimeRoot>{children}</RuntimeRoot>
    </AssistantAppContext.Provider>
  );
}

function RuntimeRoot({ children }: PropsWithChildren) {
  const { setThread } = useAssistantApp();
  const launchedThreadId = useMemo(
    () => new URLSearchParams(window.location.search).get("thread") ?? undefined,
    [],
  );
  const threadAdapter = useMemo<RemoteThreadListAdapter>(
    () => ({
      async list() {
        const items = await assistantApi.listThreads();
        items.forEach(setThread);
        return {
          threads: items.map((item) => ({
            remoteId: item.id,
            status: item.status,
            title: item.title,
          })),
        };
      },
      async initialize(threadId) {
        const thread = await assistantApi.createThread(threadId);
        return { remoteId: thread.id, externalId: undefined };
      },
      async fetch(threadId) {
        const item = await assistantApi.getThread(threadId);
        return { remoteId: item.id, status: item.status, title: item.title };
      },
      async rename(remoteId, newTitle) {
        await assistantApi.updateThread(remoteId, { title: newTitle });
      },
      archive: (remoteId) => assistantApi.archiveThread(remoteId),
      unarchive: (remoteId) => assistantApi.unarchiveThread(remoteId),
      delete: (remoteId) => assistantApi.deleteThread(remoteId),
      async generateTitle(remoteId, messages) {
        const title = titleFromMessages(messages);
        await assistantApi.updateThread(remoteId, { title });
        return createAssistantStream((controller) => controller.appendText(title));
      },
      unstable_Provider: ThreadRuntimeProvider,
    }),
    [setThread],
  );
  const runtime = useRemoteThreadListRuntime({
    runtimeHook: useThreadRuntime,
    adapter: threadAdapter,
    threadId: launchedThreadId,
  });
  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>;
}

function ThreadRuntimeProvider({ children }: PropsWithChildren) {
  const threadId = useCurrentRuntimeThreadId();
  const history = useMemo<ThreadHistoryAdapter>(
    () => ({
      async load() {
        const messages = await assistantApi.listMessages(threadId);
        return {
          headId: messages.at(-1)?.id ?? null,
          messages: messages.map((item) => ({
            parentId: item.parent_id,
            message: deserializeMessage(item.content),
          })),
        };
      },
      async append(item) {
        await assistantApi.appendMessage(threadId, {
          parentId: item.parentId,
          message: item.message,
        });
      },
    }),
    [threadId],
  );
  return (
    <RuntimeAdapterProvider adapters={{ history }}>
      {children}
    </RuntimeAdapterProvider>
  );
}

function useThreadRuntime() {
  const { setReview, setError } = useAssistantApp();
  const threadId = useCurrentRuntimeThreadId();
  const client = useMemo(
    () =>
      new DomainAwareA2AClient(async () => {
        if (!threadId) throw new Error("Create or select a chat first.");
        const thread = await assistantApi.getThread(threadId);
        const context = thread.domain === "spec"
          ? await assistantApi.getSpecContext(threadId)
          : await assistantApi.getCircuitContext(threadId);
        return { thread, context };
      }),
    [threadId],
  );
  return useA2ARuntime({
    client,
    contextId: threadId || undefined,
    onError: (error) => setError(threadId, error.message),
    onArtifactComplete: (artifact: A2AArtifact) => {
      const value = artifact.parts.find((part) => part.data)?.data;
      if (!threadId) return;
      const preview = isCircuitProposal(value)
        ? assistantApi.previewProposal(threadId, value)
        : isSpecProposal(value)
          ? assistantApi.previewSpecProposal(threadId, value)
          : null;
      if (!preview) return;
      void preview
        .then((review) => setReview(threadId, review))
        .catch((reason: Error) => setError(threadId, reason.message));
    },
  });
}

function isSpecProposal(value: unknown): value is SpecProposalArtifact {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<SpecProposalArtifact>;
  return (
    candidate.kind === "spec_change_proposal"
    && candidate.schema_version === "1.0"
    && typeof candidate.proposal_id === "string"
  );
}

function useCurrentRuntimeThreadId(): string {
  return useAuiState(
    (state) =>
      state.threadListItem.remoteId ?? state.threadListItem.id,
  );
}

function isCircuitProposal(value: unknown): value is CircuitProposalArtifact {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<CircuitProposalArtifact>;
  return (
    candidate.kind === "circuit_change_proposal" &&
    candidate.schema_version === "1" &&
    typeof candidate.proposal_id === "string"
  );
}

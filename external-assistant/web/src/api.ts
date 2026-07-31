import type { ThreadMessage } from "@assistant-ui/react";

import type {
  AssistantThread,
  CircuitProposalArtifact,
  CircuitSnapshot,
  ProposalReview,
  SpecProposalArtifact,
  StoredMessage,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new ApiError(`Request failed (${response.status})`, response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const assistantApi = {
  async listThreads(): Promise<AssistantThread[]> {
    return (await request<{ threads: AssistantThread[] }>("/api/threads")).threads;
  },
  createThread(localId: string, domain: "circuit" | "spec" = "circuit"): Promise<AssistantThread> {
    return request("/api/threads", {
      method: "POST",
      body: JSON.stringify({
        local_id: localId,
        domain,
        title: domain === "spec" ? "New Spec chat" : "New circuit chat",
      }),
    });
  },
  getThread(id: string): Promise<AssistantThread> {
    return request(`/api/threads/${encodeURIComponent(id)}`);
  },
  updateThread(
    id: string,
    patch: { title?: string; include_png?: boolean },
  ): Promise<AssistantThread> {
    return request(`/api/threads/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  archiveThread(id: string): Promise<void> {
    return request(`/api/threads/${encodeURIComponent(id)}/archive`, { method: "POST" });
  },
  unarchiveThread(id: string): Promise<void> {
    return request(`/api/threads/${encodeURIComponent(id)}/unarchive`, { method: "POST" });
  },
  deleteThread(id: string): Promise<void> {
    return request(`/api/threads/${encodeURIComponent(id)}`, { method: "DELETE" });
  },
  async listMessages(id: string): Promise<StoredMessage[]> {
    return (
      await request<{ messages: StoredMessage[] }>(
        `/api/threads/${encodeURIComponent(id)}/messages`,
      )
    ).messages;
  },
  appendMessage(
    threadId: string,
    item: { parentId: string | null; message: ThreadMessage },
  ): Promise<StoredMessage> {
    return request(`/api/threads/${encodeURIComponent(threadId)}/messages`, {
      method: "POST",
      body: JSON.stringify({
        id: item.message.id,
        parent_id: item.parentId,
        role: item.message.role,
        content: serializeMessage(item.message),
      }),
    });
  },
  bindCircuit(
    threadId: string,
    baseUrl: string,
    documentId: string,
  ): Promise<{ thread: AssistantThread; snapshot: CircuitSnapshot }> {
    return request(`/api/threads/${encodeURIComponent(threadId)}/circuit`, {
      method: "PUT",
      body: JSON.stringify({ base_url: baseUrl, document_id: documentId }),
    });
  },
  getCircuitContext(
    threadId: string,
  ): Promise<{ snapshot: CircuitSnapshot; svg: string; png_base64: string | null }> {
    return request(
      `/api/threads/${encodeURIComponent(threadId)}/circuit/context`,
    );
  },
  getSpecContext(threadId: string): Promise<{
    context: Record<string, unknown>;
    conversation: {
      summary: string | null;
      summarized_message_count: number;
      recent_messages: StoredMessage[];
    };
  }> {
    return request(`/api/threads/${encodeURIComponent(threadId)}/spec/context`);
  },
  async listReviews(threadId: string): Promise<ProposalReview[]> {
    return (
      await request<{ reviews: ProposalReview[] }>(
        `/api/threads/${encodeURIComponent(threadId)}/reviews`,
      )
    ).reviews;
  },
  async previewProposal(
    threadId: string,
    artifact: CircuitProposalArtifact,
    messageId?: string,
  ): Promise<ProposalReview> {
    return (
      await request<{ review: ProposalReview }>(
        `/api/threads/${encodeURIComponent(threadId)}/circuit/preview`,
        {
          method: "POST",
          body: JSON.stringify({
            proposal_id: artifact.proposal_id,
            message_id: messageId ?? null,
            artifact,
          }),
        },
      )
    ).review;
  },
  async previewSpecProposal(
    threadId: string,
    artifact: SpecProposalArtifact,
    messageId?: string,
  ): Promise<ProposalReview> {
    return (
      await request<{ review: ProposalReview }>(
        `/api/threads/${encodeURIComponent(threadId)}/spec/preview`,
        {
          method: "POST",
          body: JSON.stringify({
            proposal_id: artifact.proposal_id,
            message_id: messageId ?? null,
            artifact,
          }),
        },
      )
    ).review;
  },
  async discardReview(threadId: string, proposalId: string): Promise<ProposalReview> {
    return request(
      `/api/threads/${encodeURIComponent(threadId)}/reviews/${encodeURIComponent(proposalId)}`,
      {
        method: "PATCH",
        body: JSON.stringify({ state: "discarded" }),
      },
    );
  },
  async submitProposal(
    threadId: string,
    proposalId: string,
  ): Promise<ProposalReview> {
    return (
      await request<{ review: ProposalReview }>(
        `/api/threads/${encodeURIComponent(threadId)}/circuit/proposals`,
        {
          method: "POST",
          body: JSON.stringify({ proposal_id: proposalId }),
        },
      )
    ).review;
  },
  async applySpecProposal(
    threadId: string,
    proposalId: string,
  ): Promise<ProposalReview> {
    return (
      await request<{ review: ProposalReview }>(
        `/api/threads/${encodeURIComponent(threadId)}/spec/proposals`,
        {
          method: "POST",
          body: JSON.stringify({ proposal_id: proposalId }),
        },
      )
    ).review;
  },
};

function serializeMessage(message: ThreadMessage): object {
  return {
    ...message,
    createdAt: message.createdAt.toISOString(),
  };
}

export function deserializeMessage(value: unknown): ThreadMessage {
  const message = value as ThreadMessage & { createdAt: string | Date };
  return {
    ...message,
    createdAt:
      message.createdAt instanceof Date
        ? message.createdAt
        : new Date(message.createdAt),
  } as ThreadMessage;
}

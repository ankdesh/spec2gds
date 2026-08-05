import { afterEach, describe, expect, it, vi } from "vitest";

import { assistantApi } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("assistant connection API", () => {
  it("loads hosted-service availability", async () => {
    const directory = {
      schema_version: 2,
      services: { spec_editor: { available: true } },
      logging: { enabled: false, level: "info" },
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(directory));
    vi.stubGlobal("fetch", fetchMock);

    await expect(assistantApi.getServices()).resolves.toEqual(directory);
    expect(fetchMock).toHaveBeenCalledWith("/api/services", {
      headers: {},
    });
  });

  it("creates a neutral unbound chat", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: "thread-1" }));
    vi.stubGlobal("fetch", fetchMock);

    await assistantApi.createThread("thread-1");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({
      local_id: "thread-1",
      domain: "circuit",
      title: "New assistant chat",
    });
  });

  it("sends the complete Spec Editor binding", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ thread: {}, context: {} }));
    vi.stubGlobal("fetch", fetchMock);

    await assistantApi.bindSpec(
      "thread/1",
      "http://127.0.0.1:8000",
      "spec-demo",
      "component",
      "component-id",
    );

    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/threads/thread%2F1/spec");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toEqual({
      base_url: "http://127.0.0.1:8000",
      document_id: "spec-demo",
      entity_kind: "component",
      entity_id: "component-id",
    });
  });
});

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

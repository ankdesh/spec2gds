import { describe, expect, it } from "vitest";
import { assistantUrl, resolveAssistantLinks } from "../src/assistant-links";

const local = { apiBase: "/api/circuit-designer/v1", origin: "http://localhost:5173", hostname: "localhost" };

describe("standalone Assistant links", () => {
  it("uses explicit HTTPS URLs with custom ports and base paths", () => {
    const links = resolveAssistantLinks({ ...local,
      assistantUiUrl: "https://assistant.example:7443/workspace",
      circuitServiceUrl: "https://circuit.example:8443/proxy/api/circuit-designer/v1",
    });
    const launched = new URL(assistantUrl(links.uiUrl, links.serviceUrl, "design a"));
    expect(launched.origin).toBe("https://assistant.example:7443");
    expect(launched.pathname).toBe("/workspace/launch/circuit");
    expect(launched.searchParams.get("service_base_url")).toBe("https://circuit.example:8443/proxy/api/circuit-designer/v1");
    expect(launched.searchParams.get("document_id")).toBe("design a");
  });

  it("uses the directory and waits for an Assistant address", () => {
    const directory = { services: {
      ai_assistant: { ui_url: "https://assistant.example/ui" },
      circuit_designer: { service_url: "https://circuit.example:9443/api/circuit-designer/v1" },
    } };
    expect(resolveAssistantLinks({ ...local, directory })).toMatchObject({
      uiUrl: "https://assistant.example/ui",
      serviceUrl: "https://circuit.example:9443/api/circuit-designer/v1",
    });
    expect(resolveAssistantLinks(local)).toMatchObject({
      uiUrl: "",
      serviceUrl: "http://localhost:5173/api/circuit-designer/v1",
    });
  });
});

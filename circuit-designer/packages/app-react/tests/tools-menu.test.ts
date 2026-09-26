import { expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createDefaultActionBindings } from "../src/action-bindings";
import { CircuitMenuBar, toolMenuEntries } from "../src/CircuitMenuBar";
import type { CircuitToolContribution } from "../src/adapters";

it("renders every contributed tool with a distinct dispatch ID", () => {
  const tools = [
    { id: "assistant", label: "AI Assistant" },
    { id: "inspect", label: "Inspect netlist" },
  ] as CircuitToolContribution[];
  expect(toolMenuEntries(tools)).toEqual([
    { kind: "action", commandId: "tool:assistant", label: "AI Assistant" },
    { kind: "action", commandId: "tool:inspect", label: "Inspect netlist" },
  ]);
  expect(toolMenuEntries([])).toEqual([]);
});


it("hides the Tools top-level menu without contributions", () => {
  const markup = renderToStaticMarkup(createElement(CircuitMenuBar, {
    bindings: createDefaultActionBindings(), inspectorOpen: false, timingOverlayVisible: false,
    proposalCount: 0, isActionEnabled: () => true, onAction: () => undefined,
    tools: [], toolsEnabled: true, onRunTool: () => undefined,
  }));
  expect(markup).not.toContain("circuit-tools-menu-trigger");
  expect(markup).toContain("circuit-help-menu-trigger");
});

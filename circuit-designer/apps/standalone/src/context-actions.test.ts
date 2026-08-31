import { describe, expect, test } from "vitest";
import { buildCircuitContextMenu, type CircuitCommandId } from "./context-actions";
import type { CircuitMenuEntry } from "./CircuitActionMenu";

function commandIds(entries: CircuitMenuEntry<CircuitCommandId>[]): CircuitCommandId[] {
  return entries.flatMap((entry) => entry.kind === "action" ? [entry.commandId] : entry.kind === "submenu" ? commandIds(entry.entries) : []);
}

describe("Circuit Designer context menu composition", () => {
  test("composes the empty canvas and selection-wide menus", () => {
    expect(commandIds(buildCircuitContextMenu({ target: { kind: "canvas" }, inspectorOpen: false }))).toEqual([
      "begin-edit", "create-local-component", "open-connect", "add-cycle-edge", "select-all", "toggle-inspector", "fit-circuit",
    ]);
    expect(commandIds(buildCircuitContextMenu({ target: { kind: "node", nodeId: "a" }, inspectorOpen: false, selectionWide: true }))).toEqual([
      "center-selection", "delete-selection", "clear-selection",
    ]);
  });

  test("offers marker-specific edit, lock, and delete commands", () => {
    expect(commandIds(buildCircuitContextMenu({
      target: { kind: "cycle-edge", edgeId: "edge_1" }, inspectorOpen: false, cycleEdgeLocked: false,
    }))).toEqual(["edit-cycle-edge", "lock-cycle-edge", "delete-cycle-edge"]);
    expect(commandIds(buildCircuitContextMenu({
      target: { kind: "cycle-edge", edgeId: "edge_1" }, inspectorOpen: false, cycleEdgeLocked: true,
    }))).toEqual(["edit-cycle-edge", "unlock-cycle-edge", "delete-cycle-edge"]);
  });

  test("keeps exact route subparts ahead of whole-net commands", () => {
    const segment = commandIds(buildCircuitContextMenu({ target: { kind: "route-segment", netId: "n", segmentId: "s" }, inspectorOpen: false }));
    const bend = commandIds(buildCircuitContextMenu({ target: { kind: "route-vertex", netId: "n", vertexId: "b", vertexKind: "bend" }, inspectorOpen: false, routeLocked: true }));
    const junction = commandIds(buildCircuitContextMenu({ target: { kind: "route-vertex", netId: "n", vertexId: "j", vertexKind: "junction" }, inspectorOpen: false }));
    expect(segment[0]).toBe("add-bend-here");
    expect(bend.slice(0, 3)).toEqual(["remove-bend", "reroute-selected", "unlock-selected-route"]);
    expect(junction).not.toContain("remove-bend");
  });

  test("switches port connection commands and includes complete placement controls", () => {
    const free = commandIds(buildCircuitContextMenu({
      target: { kind: "terminal", terminalId: "u:a", owner: { kind: "node", id: "u" } },
      inspectorOpen: false,
      terminalSide: "EAST",
    }));
    const connectedBoundary = commandIds(buildCircuitContextMenu({
      target: { kind: "boundary", terminalId: "input" },
      inspectorOpen: false,
      terminalConnected: true,
      terminalPlacementLocked: true,
    }));
    expect(free).toContain("open-connect");
    expect(free).toEqual(expect.arrayContaining(["terminal-side-north", "terminal-side-east", "terminal-move-earlier", "terminal-lock-placement", "terminal-reset-placement"]));
    expect(connectedBoundary).toEqual(expect.arrayContaining(["select-connected-net", "disconnect-port", "terminal-unlock-placement", "delete-boundary-terminal"]));
  });
});

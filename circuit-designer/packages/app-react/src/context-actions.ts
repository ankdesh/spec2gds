/* Reusable Circuit Designer application shell. */
import type { CircuitCanvasContextTarget } from "@spec2gds/circuit-react";
import type { CircuitActionId } from "./action-bindings";
import type { CircuitMenuEntry } from "./CircuitActionMenu";

export type CircuitContextCommandId =
  | "add-bend-here"
  | "remove-bend"
  | "select-connected-net"
  | "disconnect-port"
  | "delete-boundary-terminal"
  | "terminal-side-north"
  | "terminal-side-east"
  | "terminal-side-south"
  | "terminal-side-west"
  | "terminal-move-earlier"
  | "terminal-move-later"
  | "terminal-lock-placement"
  | "terminal-unlock-placement"
  | "terminal-reset-placement";

export type CircuitCommandId = CircuitActionId | CircuitContextCommandId;
export type CircuitActionInvocationSource = "menubar" | "shortcut" | "mouse-binding" | "context-menu";

export interface CircuitActionInvocation {
  commandId: CircuitCommandId;
  source: CircuitActionInvocationSource;
  target?: CircuitCanvasContextTarget;
  clientPoint?: { x: number; y: number };
  circuitPoint?: { x: number; y: number };
}

const labels: Record<CircuitContextCommandId, string> = {
  "add-bend-here": "Add bend here",
  "remove-bend": "Remove bend",
  "select-connected-net": "Select connected net",
  "disconnect-port": "Disconnect port",
  "delete-boundary-terminal": "Delete boundary terminal…",
  "terminal-side-north": "North",
  "terminal-side-east": "East",
  "terminal-side-south": "South",
  "terminal-side-west": "West",
  "terminal-move-earlier": "Move earlier",
  "terminal-move-later": "Move later",
  "terminal-lock-placement": "Lock placement",
  "terminal-unlock-placement": "Unlock placement",
  "terminal-reset-placement": "Reset to automatic placement",
};

type ActionEntry = Extract<CircuitMenuEntry<CircuitCommandId>, { kind: "action" }>;
const action = (commandId: CircuitCommandId, label: string): ActionEntry => ({ kind: "action", commandId, label });
const contextAction = (commandId: CircuitContextCommandId): ActionEntry => action(commandId, labels[commandId]);
const separator: CircuitMenuEntry<CircuitCommandId> = { kind: "separator" };

export interface CircuitContextMenuOptions {
  target: CircuitCanvasContextTarget;
  selectionWide?: boolean;
  inspectorOpen: boolean;
  terminalConnected?: boolean;
  terminalSide?: "NORTH" | "EAST" | "SOUTH" | "WEST";
  terminalPlacementLocked?: boolean;
  routeLocked?: boolean;
  cycleEdgeLocked?: boolean;
}

function placementMenu(options: CircuitContextMenuOptions): CircuitMenuEntry<CircuitCommandId> {
  const side = options.terminalSide;
  const sideEntry = (commandId: CircuitContextCommandId, value: CircuitContextMenuOptions["terminalSide"]): CircuitMenuEntry<CircuitCommandId> => ({
    ...contextAction(commandId), checked: side === value, checkType: "radio",
  });
  return { kind: "submenu", id: "placement", label: "Placement", entries: [
    { kind: "submenu", id: "placement-side", label: "Side", entries: [
      sideEntry("terminal-side-north", "NORTH"),
      sideEntry("terminal-side-east", "EAST"),
      sideEntry("terminal-side-south", "SOUTH"),
      sideEntry("terminal-side-west", "WEST"),
    ] },
    separator,
    contextAction("terminal-move-earlier"),
    contextAction("terminal-move-later"),
    separator,
    contextAction(options.terminalPlacementLocked ? "terminal-unlock-placement" : "terminal-lock-placement"),
    contextAction("terminal-reset-placement"),
  ] };
}

const selectionCommands = (): CircuitMenuEntry<CircuitCommandId>[] => [
  action("center-selection", "Center selection"),
  action("delete-selection", "Delete selected"),
  action("clear-selection", "Clear selection"),
];

const routeCommands = (locked: boolean): CircuitMenuEntry<CircuitCommandId>[] => [
  action("reroute-selected", "Reroute"),
  action(locked ? "unlock-selected-route" : "lock-selected-route", locked ? "Unlock whole route" : "Lock whole route"),
  separator,
  action("center-selection", "Center selection"),
  action("delete-selection", "Delete selected"),
];

export function buildCircuitContextMenu(options: CircuitContextMenuOptions): CircuitMenuEntry<CircuitCommandId>[] {
  const { target } = options;
  if (options.selectionWide && ["node", "boundary", "net", "canvas"].includes(target.kind)) return selectionCommands();
  if (target.kind === "canvas") return [
    action("begin-edit", "Begin editing"),
    separator,
    action("create-local-component", "New local component…"),
    action("open-connect", "New connection…"),
    action("add-cycle-edge", "Add cycle edge here"),
    separator,
    action("select-all", "Select all"),
    { ...action("toggle-inspector", "Show Inspector"), checked: options.inspectorOpen, checkType: "checkbox" },
    action("fit-circuit", "Fit circuit"),
  ];
  if (target.kind === "cycle-edge") return [
    action("edit-cycle-edge", "Edit cycle edge…"),
    action(options.cycleEdgeLocked ? "unlock-cycle-edge" : "lock-cycle-edge", options.cycleEdgeLocked ? "Unlock cycle edge" : "Lock cycle edge"),
    separator,
    action("delete-cycle-edge", "Delete cycle edge…"),
  ];
  if (target.kind === "node") return [
    action("open-child-design", "Open selected child design"),
    action("center-selection", "Center selection"),
    separator,
    action("delete-selection", "Delete selected"),
  ];
  if (target.kind === "net") return routeCommands(Boolean(options.routeLocked));
  if (target.kind === "route-segment") return [contextAction("add-bend-here"), separator, ...routeCommands(Boolean(options.routeLocked))];
  if (target.kind === "route-vertex") return target.vertexKind === "bend"
    ? [contextAction("remove-bend"), separator, ...routeCommands(Boolean(options.routeLocked))]
    : routeCommands(Boolean(options.routeLocked));
  const portCommands: CircuitMenuEntry<CircuitCommandId>[] = options.terminalConnected
    ? [contextAction("select-connected-net"), contextAction("disconnect-port")]
    : [action("open-connect", "New connection…")];
  portCommands.push(separator, placementMenu(options));
  if (target.kind === "boundary" || target.owner.kind === "boundary") {
    portCommands.push(separator, contextAction("delete-boundary-terminal"));
  }
  return portCommands;
}

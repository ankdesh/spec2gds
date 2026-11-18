/** Circuit canvas presentation and input gestures over public document/layout types.
 * Selection and transient drag previews are UI state. Emit requested edits to
 * the host instead of treating screen coordinates as authoritative connectivity.
 * Stable terminal/net IDs connect rendered geometry back to logical elements. */
import {
  Fragment,
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type ForwardedRef,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type RefObject,
} from "react";
import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  Handle,
  getViewportForBounds,
  Position,
  ViewportPortal,
  ReactFlow,
  SelectionMode,
  useReactFlow,
  useNodesInitialized,
  useUpdateNodeInternals,
  type Edge,
  type EdgeChange,
  type EdgeProps,
  type Node,
  type NodeChange,
  type NodeProps,
  type ReactFlowInstance,
  type Viewport,
} from "@xyflow/react";
import type {
  CircuitDiff,
  CircuitDocument,
  CircuitGraphView as CircuitGraphSnapshot,
  CircuitNodeView as CircuitNode,
  CircuitTerminalView as CircuitTerminal,
  DiagramLayoutView as DiagramLayout,
  NetRoute,
  NodeGeometry,
  TerminalPlacement,
  Diagnostic,
  CircuitTimingV1,
  CycleEdgeMarkerV1,
  CircuitTimingAnalysis,
} from "@spec2gds/circuit-core";
import {
  ensureRouteIds,
  insertRouteBend,
  moveRouteSegment,
  moveRouteVertex,
  removeRouteBend,
  projectDocument,
  circuitTerminalDisplayLabel,
  compactCircuitTerminalLabel,
  compactCircuitInstanceLabel,
  sortedCycleEdges,
  stageLabel,
  circuitFrameGeometry,
  CIRCUIT_FRAME_HEADER_HEIGHT,
  type CircuitContainerPresentation,
} from "@spec2gds/circuit-core";
import { layoutCircuitDocument } from "@spec2gds/circuit-layout";

export type CircuitCanvasSelectionItem = { kind: "node" | "boundary" | "net" | "cycle-edge"; id: string };
export type CircuitCanvasSelection = CircuitCanvasSelectionItem[];
export type CircuitConnectionRejectionReason = "same_terminal" | "terminal_in_use" | "invalid_target";
export type CircuitCanvasPoint = { x: number; y: number };

export type CircuitCanvasContextTarget =
  | { kind: "canvas" }
  | { kind: "node"; nodeId: string }
  | { kind: "boundary"; terminalId: string }
  | { kind: "terminal"; terminalId: string; parent: { kind: "node" | "boundary"; id: string } }
  | { kind: "net"; netId: string }
  | { kind: "route-segment"; netId: string; segmentId: string }
  | { kind: "route-vertex"; netId: string; vertexId: string; vertexKind: "bend" | "junction" }
  | { kind: "cycle-edge"; edgeId: string };

export interface CircuitCanvasContextMenuRequest {
  target: CircuitCanvasContextTarget;
  clientPoint: CircuitCanvasPoint;
  flowPoint: CircuitCanvasPoint;
  keyboard: boolean;
  focusTarget?: HTMLElement | SVGElement;
}

export interface CircuitDesignerCanvasHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  fitView: () => void;
  centerSelection: () => void;
  pan: (direction: "left" | "right" | "up" | "down") => void;
  cancelPendingConnection: () => void;
}

export function circuitSelectionsEqual(left: CircuitCanvasSelection, right: CircuitCanvasSelection): boolean {
  if (left.length !== right.length) return false;
  const keys = new Set(left.map((item) => `${item.kind}:${item.id}`));
  return right.every((item) => keys.has(`${item.kind}:${item.id}`));
}

export function terminalDisplayLabel(terminal: Pick<CircuitTerminal, "label" | "width">): string {
  return circuitTerminalDisplayLabel(terminal);
}

export interface CircuitDesignerCanvasProps {
  graph: CircuitGraphSnapshot;
  layout: DiagramLayout;
  boundaryGeometry?: Record<string, NodeGeometry>;
  containerGeometry?: NodeGeometry;
  container?: CircuitContainerPresentation | false;
  onAddBoundaryPort?: () => void;
  canAddBoundaryPort?: boolean;
  addBoundaryPortDisabledReason?: string;
  componentLabels?: Record<string, string>;
  selection?: CircuitCanvasSelection;
  onSelectionChange?: (selection: CircuitCanvasSelection) => void;
  editable?: boolean;
  onNodeGeometryChanges?: (changes: Record<string, NodeGeometry>) => void;
  onConnectTerminals?: (sourceTerminalId: string, targetTerminalId: string) => void;
  onConnectionRejected?: (reason: CircuitConnectionRejectionReason) => void;
  gridSize?: number;
  allowViewportNavigation?: boolean;
  fitViewOnInit?: boolean;
  onNetRouteChange?: (netId: string, route: NetRoute) => void;
  rendererRegistry?: CircuitCanvasRendererRegistry;
  elementStatus?: {
    nodes?: Record<string, "added" | "removed" | "changed">;
    nets?: Record<string, "added" | "removed" | "changed">;
  };
  viewport?: Viewport;
  onViewportChange?: (viewport: Viewport) => void;
  showInlineViewportControls?: boolean;
  viewportPanMouseButtons?: Array<0 | 1 | 2>;
  viewportPanActivationKeyCode?: string | string[] | null;
  wheelZoomEnabled?: boolean;
  useDefaultEscapeBinding?: boolean;
  onContextMenuRequest?: (request: CircuitCanvasContextMenuRequest) => void;
  timing?: CircuitTimingV1;
  showTimingOverlay?: boolean;
  onCycleEdgeChange?: (edge: CycleEdgeMarkerV1) => void;
  onCanvasPointClick?: (point: CircuitCanvasPoint) => void;
  timingAnalysis?: CircuitTimingAnalysis;
}

type CircuitNodeData = {
  circuitNode: CircuitNode;
  componentLabel?: string;
  geometry: NodeGeometry;
  terminals: CircuitTerminal[];
  placements: Record<string, TerminalPlacement>;
  rendererRegistry?: CircuitCanvasRendererRegistry;
  editable: boolean;
  occupiedTerminalIds: Set<string>;
  pendingTerminalId?: string;
  onTerminalActivate: (terminalId: string) => void;
  contextTarget: Extract<CircuitCanvasContextTarget, { kind: "node" | "boundary" }>;
  onTerminalContextMenu: (
    target: Extract<CircuitCanvasContextTarget, { kind: "terminal" }>,
    anchor: CircuitContextAnchor,
  ) => void;
};

type CircuitContextAnchor = {
  clientPoint: { x: number; y: number };
  focusTarget?: HTMLElement | SVGElement;
  keyboard: boolean;
};

type CircuitFlowNode = Node<CircuitNodeData, "circuit">;
type CircuitEdgeData = {
  route: NetRoute;
  label: string;
  kind: string;
  routeEditable: boolean;
  gridSize: number;
  onRouteChange?: (route: NetRoute) => void;
  onContextMenu?: (
    target: Extract<CircuitCanvasContextTarget, { kind: "route-segment" | "route-vertex" }>,
    anchor: CircuitContextAnchor,
  ) => void;
};
type CircuitFlowEdge = Edge<CircuitEdgeData, "circuit">;

const positions = { NORTH: Position.Top, EAST: Position.Right, SOUTH: Position.Bottom, WEST: Position.Left };

export interface CircuitCanvasRendererProps {
  node: CircuitNode;
}

export class CircuitCanvasRendererRegistry {
  private readonly renderers = new Map<string, (props: CircuitCanvasRendererProps) => ReactNode>();

  register(key: string, renderer: (props: CircuitCanvasRendererProps) => ReactNode): void {
    this.renderers.set(key, renderer);
  }

  renderer(key: string): ((props: CircuitCanvasRendererProps) => ReactNode) | undefined {
    return this.renderers.get(key);
  }
}

export const defaultCircuitCanvasRenderers = new CircuitCanvasRendererRegistry();
for (const key of ["and", "nand", "or", "nor", "xor", "xnor", "not", "buffer", "mux", "register", "constant", "splitter", "combiner"]) {
  defaultCircuitCanvasRenderers.register(key, ({ node }) => <span className={`cd-node__symbol cd-node__symbol--${key}`}>{node.label}</span>);
}

function CircuitNodeView({ data, id, selected }: NodeProps<CircuitFlowNode>) {
  const updateNodeInternals = useUpdateNodeInternals();
  useEffect(() => updateNodeInternals(id), [id, selected, data.terminals, data.placements, data.geometry.width, data.geometry.height, updateNodeInternals]);
  const rendererKey = data.circuitNode.component_vlnv ?? "generic";
  const customRenderer = data.rendererRegistry?.renderer(rendererKey)
    ?? defaultCircuitCanvasRenderers.renderer(rendererKey);
  const fullTitle = data.circuitNode.display_name ?? data.circuitNode.label;
  const shortTitle = compactCircuitInstanceLabel(fullTitle, Math.max(4, Math.floor((data.geometry.width - 30) / 8)));
  const instanceSuffix = fullTitle.match(/_\d+$/)?.[0] ?? "";
  return (
    <div className={data.contextTarget.kind === "boundary" ? "cd-node cd-node--boundary" : "cd-node"}>
      {data.contextTarget.kind !== "boundary" && <><div className="cd-node__eyebrow" title={data.componentLabel}>{data.componentLabel || "Component"}</div>
      <div className="cd-node__title" tabIndex={0} title={fullTitle}>{customRenderer
        ? customRenderer({ node: data.circuitNode })
        : <><span className="cd-node__instance-name">{instanceSuffix ? shortTitle.slice(0, -instanceSuffix.length) : shortTitle}</span>{instanceSuffix && <span className="cd-node__instance-suffix">{instanceSuffix}</span>}</>}</div></>}
      {data.terminals.map((terminal) => {
        const placement = data.placements[terminal.id];
        const side = placement?.side ?? "SOUTH";
        const requestedOffset = 60 + (placement?.order ?? 0) * 20;
        const offset = side === "EAST" || side === "WEST"
          ? Math.min(requestedOffset, data.geometry.height - 20)
          : Math.min(requestedOffset, data.geometry.width - 20);
        const style = side === "EAST" || side === "WEST" ? { top: offset } : { left: offset };
        const displayLabel = terminalDisplayLabel(terminal);
        const labelLimit = data.contextTarget.kind === "boundary" ? 26 : 13;
        const widthLabel = compactCircuitTerminalLabel({ ...terminal, label: "" }, labelLimit);
        const shortLabel = compactCircuitTerminalLabel(terminal, labelLimit);
        const occupied = data.occupiedTerminalIds.has(terminal.id);
        const pending = data.pendingTerminalId === terminal.id;
        const activateFromKeyboard = (event: ReactKeyboardEvent<HTMLDivElement>) => {
          if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
            event.preventDefault();
            event.stopPropagation();
            const bounds = event.currentTarget.getBoundingClientRect();
            data.onTerminalContextMenu({
              kind: "terminal",
              terminalId: terminal.id,
              parent: data.contextTarget.kind === "node"
                ? { kind: "node", id: data.contextTarget.nodeId }
                : { kind: "boundary", id: data.contextTarget.terminalId },
            }, {
              clientPoint: { x: bounds.left + bounds.width / 2, y: bounds.top + bounds.height / 2 },
              focusTarget: event.currentTarget,
              keyboard: true,
            });
            return;
          }
          if (event.key !== "Enter" || !data.editable) return;
          event.preventDefault();
          event.stopPropagation();
          data.onTerminalActivate(terminal.id);
        };
        return <Fragment key={terminal.id}>
          <span className={`cd-node__port-label cd-node__port-label--${side.toLowerCase()}`} style={style} title={displayLabel} aria-label={displayLabel} tabIndex={0}>
            <span className="cd-node__port-name">{shortLabel.slice(0, shortLabel.length - widthLabel.length)}</span>
            <span className="cd-node__port-width">{widthLabel}</span>
          </span>
          <Handle
            id={terminalHandleId(terminal.id)}
            type="source"
            position={positions[side]}
            style={{ ...style, pointerEvents: "all" }}
            className={[occupied && "cd-terminal--occupied", pending && "cd-terminal--pending"].filter(Boolean).join(" ") || undefined}
            title={occupied ? `${displayLabel} · drag to extend its net` : `${displayLabel} · drag to connect`}
            aria-label={occupied ? `${displayLabel}, already connected` : `${displayLabel}, connection terminal`}
            aria-disabled={!data.editable}
            role="button"
            tabIndex={0}
            isConnectable={data.editable}
            onKeyDown={activateFromKeyboard}
            data-terminal-id={terminal.id}
            onContextMenu={(event) => {
              event.preventDefault();
              event.stopPropagation();
              data.onTerminalContextMenu({
                kind: "terminal",
                terminalId: terminal.id,
                parent: data.contextTarget.kind === "node"
                  ? { kind: "node", id: data.contextTarget.nodeId }
                  : { kind: "boundary", id: data.contextTarget.terminalId },
              }, {
                clientPoint: { x: event.clientX, y: event.clientY },
                focusTarget: event.currentTarget,
                keyboard: false,
              });
            }}
          />
        </Fragment>;
      })}
    </div>
  );
}

export function terminalHandleId(terminalId: string, _type?: "source" | "target"): string {
  return terminalId;
}

export function terminalIdFromHandle(handleId: string | null | undefined): string | undefined {
  return handleId || undefined;
}

export interface BuildCircuitFlowEdgeOptions {
  routeEditableNetId?: string;
  gridSize?: number;
  onNetRouteChange?: (netId: string, route: NetRoute) => void;
}

export function buildCircuitFlowEdges(graph: CircuitGraphSnapshot, netRoutes: Record<string, NetRoute>, options: BuildCircuitFlowEdgeOptions = {}): CircuitFlowEdge[] {
  const nodeId = (terminalId: string) => graph.terminals.find((terminal) => terminal.id === terminalId)?.node_id
    ?? (terminalId.startsWith("boundary:") ? terminalId : `boundary:${terminalId}`);
  return graph.nets.flatMap((net) => {
    const route = netRoutes[net.id];
    if (!route || net.endpoints.length < 2) return [];
    const sourceTerminalId = net.endpoints[0].terminal_id;
    const targetTerminalId = net.endpoints[1].terminal_id;
    return [{
      id: net.id,
      type: "circuit",
      source: nodeId(sourceTerminalId),
      target: nodeId(targetTerminalId),
      sourceHandle: terminalHandleId(sourceTerminalId, "source"),
      targetHandle: terminalHandleId(targetTerminalId, "target"),
      data: {
        route: ensureRouteIds(route), label: net.label, kind: net.kind,
        routeEditable: options.routeEditableNetId === net.id,
        gridSize: options.gridSize ?? 20,
        onRouteChange: options.onNetRouteChange ? (nextRoute) => options.onNetRouteChange?.(net.id, nextRoute) : undefined,
      },
      selectable: true,
    }];
  });
}

function CircuitEdgeView({ id: netId, data, selected }: EdgeProps<CircuitFlowEdge>) {
  if (!data) return null;
  const { screenToFlowPosition } = useReactFlow();
  const [draft, setDraft] = useState(() => ensureRouteIds(data.route));
  const draftRef = useRef(draft);
  const drag = useRef<{ kind: "segment" | "vertex"; id: string; pointerId: number; startRoute: NetRoute }>();
  useEffect(() => {
    const next = ensureRouteIds(data.route);
    setDraft(next); draftRef.current = next;
  }, [data.route]);
  const updateDraft = (next: NetRoute) => { draftRef.current = next; setDraft(next); };
  const vertices = new Map(draft.vertices.map((vertex) => [vertex.id, vertex]));
  const degrees = new Map(draft.vertices.map((vertex) => [vertex.id, 0]));
  for (const segment of draft.segments) {
    degrees.set(segment.from_vertex, (degrees.get(segment.from_vertex) ?? 0) + 1);
    degrees.set(segment.to_vertex, (degrees.get(segment.to_vertex) ?? 0) + 1);
  }
  const flowPoint = (event: { clientX: number; clientY: number }) => screenToFlowPosition({ x: event.clientX, y: event.clientY });
  const openContextMenu = (
    event: ReactMouseEvent<SVGElement> | ReactKeyboardEvent<SVGElement>,
    target: Extract<CircuitCanvasContextTarget, { kind: "route-segment" | "route-vertex" }>,
    keyboard: boolean,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    const bounds = event.currentTarget.getBoundingClientRect();
    const clientPoint = keyboard
      ? { x: bounds.left + bounds.width / 2, y: bounds.top + bounds.height / 2 }
      : { x: (event as ReactMouseEvent<SVGElement>).clientX, y: (event as ReactMouseEvent<SVGElement>).clientY };
    data.onContextMenu?.(target, { clientPoint, focusTarget: event.currentTarget, keyboard });
  };
  const contextKey = (event: ReactKeyboardEvent<SVGElement>, target: Extract<CircuitCanvasContextTarget, { kind: "route-segment" | "route-vertex" }>) => {
    if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) openContextMenu(event, target, true);
  };
  const startDrag = (event: ReactPointerEvent<SVGElement>, kind: "segment" | "vertex", id: string, locked = false) => {
    if (!data.routeEditable || locked) return;
    event.stopPropagation(); event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { kind, id, pointerId: event.pointerId, startRoute: draftRef.current };
  };
  const moveDrag = (event: ReactPointerEvent<SVGElement>) => {
    if (!drag.current || drag.current.pointerId !== event.pointerId) return;
    const point = flowPoint(event);
    const next = drag.current.kind === "segment"
      ? moveRouteSegment(drag.current.startRoute, drag.current.id, (() => {
          const segment = drag.current!.startRoute.segments.find((item) => item.id === drag.current?.id)!;
          const start = drag.current!.startRoute.vertices.find((vertex) => vertex.id === segment.from_vertex)!;
          const end = drag.current!.startRoute.vertices.find((vertex) => vertex.id === segment.to_vertex)!;
          return start.point.y === end.point.y ? point.y : point.x;
        })(), data.gridSize)
      : moveRouteVertex(drag.current.startRoute, drag.current.id, point, data.gridSize);
    updateDraft(next);
  };
  const endDrag = (event: ReactPointerEvent<SVGElement>) => {
    if (!drag.current || drag.current.pointerId !== event.pointerId) return;
    event.stopPropagation(); drag.current = undefined;
    data.onRouteChange?.(draftRef.current);
  };
  return (
    <g className={selected ? "cd-net cd-net--selected" : "cd-net"}>
      {draft.segments.map((segment, index) => {
        const start = vertices.get(segment.from_vertex)!.point;
        const end = vertices.get(segment.to_vertex)!.point;
        const movable = !segment.locked
          && vertices.get(segment.from_vertex)?.kind !== "endpoint"
          && vertices.get(segment.to_vertex)?.kind !== "endpoint";
        const segmentId = segment.id ?? `segment:${index}`;
        return <Fragment key={segmentId}>
          <path d={`M ${start.x} ${start.y} L ${end.x} ${end.y}`} className={segment.locked ? "cd-net__segment cd-net__segment--locked" : "cd-net__segment"} />
          <path
            d={`M ${start.x} ${start.y} L ${end.x} ${end.y}`}
            aria-label={`Route segment ${segmentId}`}
            className={data.routeEditable ? "cd-net__hit-segment" : "cd-net__hit-segment cd-net__hit-segment--readonly"}
            data-segment-id={segmentId}
            data-movable={movable}
            onContextMenu={(event) => openContextMenu(event, { kind: "route-segment", netId, segmentId }, false)}
            onKeyDown={(event) => contextKey(event, { kind: "route-segment", netId, segmentId })}
            onPointerDown={(event) => startDrag(event, "segment", segmentId, segment.locked)}
            onPointerMove={moveDrag}
            onPointerUp={endDrag}
            role="button"
            tabIndex={0}
            onDoubleClick={(event) => {
              if (!data.routeEditable) return;
              event.stopPropagation();
              const next = insertRouteBend(draftRef.current, segmentId, flowPoint(event), data.gridSize);
              updateDraft(next); data.onRouteChange?.(next);
            }}
          />
        </Fragment>;
      })}
      {draft.vertices.filter((vertex) => vertex.kind === "junction" && (degrees.get(vertex.id) ?? 0) >= 3).map((vertex) => (
        <circle
          aria-label={`Route junction ${vertex.id}`}
          className="cd-net__junction"
          cx={vertex.point.x}
          cy={vertex.point.y}
          key={vertex.id}
          onContextMenu={(event) => openContextMenu(event, { kind: "route-vertex", netId, vertexId: vertex.id, vertexKind: "junction" }, false)}
          onKeyDown={(event) => contextKey(event, { kind: "route-vertex", netId, vertexId: vertex.id, vertexKind: "junction" })}
          r="3.5"
          role="button"
          tabIndex={0}
        />
      ))}
      {!selected && draft.vertices.filter((vertex) => vertex.kind === "bend").map((vertex) => (
        <circle
          aria-label={`Route bend ${vertex.id}`}
          className="cd-net__vertex-context-target"
          cx={vertex.point.x}
          cy={vertex.point.y}
          key={`context:${vertex.id}`}
          onContextMenu={(event) => openContextMenu(event, { kind: "route-vertex", netId, vertexId: vertex.id, vertexKind: "bend" }, false)}
          onKeyDown={(event) => contextKey(event, { kind: "route-vertex", netId, vertexId: vertex.id, vertexKind: "bend" })}
          r="7"
          role="button"
          tabIndex={0}
        />
      ))}
      {selected && draft.vertices.filter((vertex) => vertex.kind !== "endpoint").map((vertex) => (
        <circle
          aria-label={`Route ${vertex.kind} ${vertex.id}`}
          key={`handle:${vertex.id}`}
          cx={vertex.point.x} cy={vertex.point.y} r="5"
          className={vertex.locked || !data.routeEditable ? "cd-net__route-handle cd-net__route-handle--locked" : "cd-net__route-handle"}
          data-vertex-id={vertex.id}
          onContextMenu={(event) => openContextMenu(event, { kind: "route-vertex", netId, vertexId: vertex.id, vertexKind: vertex.kind as "bend" | "junction" }, false)}
          onKeyDown={(event) => contextKey(event, { kind: "route-vertex", netId, vertexId: vertex.id, vertexKind: vertex.kind as "bend" | "junction" })}
          onPointerDown={(event) => startDrag(event, "vertex", vertex.id, vertex.locked)}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          role="button"
          tabIndex={0}
          onDoubleClick={(event) => {
            if (!data.routeEditable) return;
            event.stopPropagation();
            const next = removeRouteBend(draftRef.current, vertex.id);
            updateDraft(next); data.onRouteChange?.(next);
          }}
        />
      ))}
    </g>
  );
}

export function connectionRejectionReason(
  graph: CircuitGraphSnapshot,
  sourceTerminalId: string,
  targetTerminalId: string,
): CircuitConnectionRejectionReason | undefined {
  if (sourceTerminalId === targetTerminalId) return "same_terminal";
  const terminalIds = new Set(graph.terminals.map((terminal) => terminal.id));
  if (!terminalIds.has(sourceTerminalId) || !terminalIds.has(targetTerminalId)) return "invalid_target";
  // The application resolves existing-net membership and numeric slices. A
  // connected pin is also a valid starting point for a fan-out gesture.
  return undefined;
}

interface CycleEdgeOverlayProps {
  timing: CircuitTimingV1;
  viewport: Viewport;
  editable: boolean;
  selectedId?: string;
  gridSize: number;
  canvasRef: RefObject<HTMLDivElement | null>;
  onSelect: (edgeId: string) => void;
  onChange?: (edge: CycleEdgeMarkerV1) => void;
  onContextMenu: (target: CircuitCanvasContextTarget, anchor: CircuitContextAnchor) => void;
  analysis?: CircuitTimingAnalysis;
  layout: DiagramLayout;
}

function CycleEdgeOverlay({ timing, viewport, editable, selectedId, gridSize, canvasRef, onSelect, onChange, onContextMenu, analysis, layout }: CycleEdgeOverlayProps) {
  const drag = useRef<{ pointerId: number; edge: CycleEdgeMarkerV1 }>();
  const [preview, setPreview] = useState<Record<string, number>>({});
  const edges = sortedCycleEdges(timing);
  const clientToFlowX = (clientX: number) => {
    const bounds = canvasRef.current?.getBoundingClientRect();
    return Math.round(((clientX - (bounds?.left ?? 0) - viewport.x) / viewport.zoom) / gridSize) * gridSize;
  };
  const pathLabels = new Map<string, CircuitTimingAnalysis["paths"][number]>();
  for (const path of analysis?.paths ?? []) {
    const current = pathLabels.get(path.net_id);
    if (!current || path.status !== "ready" || (path.cycles ?? 0) > (current.cycles ?? 0)) pathLabels.set(path.net_id, path);
  }
  return <div className="cd-cycle-edges" aria-label="Cycle edges">
    {edges.length ? <span className="cd-cycle-edge__leading-stage" style={{ left: viewport.x + 8 }}>
      {stageLabel(timing, 0)}
    </span> : null}
    {edges.map((edge, index) => {
      const x = preview[edge.id] ?? edge.x;
      const selected = selectedId === edge.id;
      return <button
        aria-label={`${edge.label ?? `Cycle edge ${index + 1}`}, starts ${edge.next_stage_label ?? `Stage ${index + 1}`}`}
        aria-pressed={selected}
        className={`cd-cycle-edge${selected ? " cd-cycle-edge--selected" : ""}${edge.locked ? " cd-cycle-edge--locked" : ""}`}
        data-cycle-edge-id={edge.id}
        key={edge.id}
        onClick={(event) => { event.stopPropagation(); onSelect(edge.id); }}
        onContextMenu={(event) => {
          event.preventDefault(); event.stopPropagation(); onSelect(edge.id);
          onContextMenu({ kind: "cycle-edge", edgeId: edge.id }, {
            clientPoint: { x: event.clientX, y: event.clientY }, focusTarget: event.currentTarget, keyboard: false,
          });
        }}
        onKeyDown={(event) => {
          if (event.key !== "ContextMenu" && !(event.shiftKey && event.key === "F10")) return;
          event.preventDefault(); event.stopPropagation();
          const bounds = event.currentTarget.getBoundingClientRect();
          onContextMenu({ kind: "cycle-edge", edgeId: edge.id }, {
            clientPoint: { x: bounds.left + bounds.width / 2, y: bounds.top + 28 }, focusTarget: event.currentTarget, keyboard: true,
          });
        }}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.stopPropagation(); onSelect(edge.id);
          if (!editable || edge.locked || !onChange) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          drag.current = { pointerId: event.pointerId, edge };
        }}
        onPointerMove={(event) => {
          if (drag.current?.pointerId !== event.pointerId) return;
          setPreview((current) => ({ ...current, [edge.id]: clientToFlowX(event.clientX) }));
        }}
        onPointerUp={(event) => {
          if (drag.current?.pointerId !== event.pointerId) return;
          event.stopPropagation();
          const nextX = clientToFlowX(event.clientX);
          drag.current = undefined;
          setPreview((current) => { const next = { ...current }; delete next[edge.id]; return next; });
          onChange?.({ ...edge, x: nextX });
        }}
        style={{ left: x * viewport.zoom + viewport.x }}
        type="button"
      >
        <span className="cd-cycle-edge__line" />
        <span className="cd-cycle-edge__label">{edge.label ?? `Cycle edge ${index + 1}`}</span>
        <span className="cd-cycle-edge__stage">{edge.next_stage_label ?? `Stage ${index + 1}`}</span>
      </button>;
    })}
    {[...pathLabels.values()].flatMap((path) => {
      const points = layout.net_routes?.[path.net_id]?.vertices.map((vertex) => vertex.point) ?? [];
      if (!points.length || (path.status === "ready" && !(path.cycles ?? 0))) return [];
      const x = points.reduce((sum, point) => sum + point.x, 0) / points.length;
      const y = Math.min(...points.map((point) => point.y));
      const label = path.status === "ready" ? `+${path.cycles} cycle${path.cycles === 1 ? "" : "s"}` : path.status === "cdc" ? "CDC" : "Timing warning";
      return [<span className={`cd-latency-label cd-latency-label--${path.status}`} key={`${path.net_id}:${path.target}`} style={{ left: x * viewport.zoom + viewport.x, top: y * viewport.zoom + viewport.y }}>{label}</span>];
    })}
  </div>;
}

function CanvasMeasurementStatus({ onReady }: { onReady: (ready: boolean) => void }) {
  const ready = useNodesInitialized();
  useEffect(() => onReady(ready), [ready, onReady]);
  return null;
}

function CircuitDesignerCanvasInner({ graph, layout, boundaryGeometry: suppliedBoundaryGeometry, containerGeometry: suppliedContainerGeometry, container, onAddBoundaryPort, canAddBoundaryPort = false, addBoundaryPortDisabledReason, componentLabels = {}, selection = [], onSelectionChange, editable = false, onNodeGeometryChanges, onConnectTerminals, onConnectionRejected, gridSize = 20, allowViewportNavigation = true, fitViewOnInit = true, onNetRouteChange, rendererRegistry, elementStatus, viewport, onViewportChange, showInlineViewportControls = true, viewportPanMouseButtons = [0], viewportPanActivationKeyCode = "Space", wheelZoomEnabled = true, useDefaultEscapeBinding = true, onContextMenuRequest, timing, showTimingOverlay = true, onCycleEdgeChange, onCanvasPointClick, timingAnalysis }: CircuitDesignerCanvasProps, forwardedRef: ForwardedRef<CircuitDesignerCanvasHandle>) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<ReactFlowInstance<CircuitFlowNode, CircuitFlowEdge>>();
  const [fitRequest, setFitRequest] = useState(fitViewOnInit ? 1 : 0);
  const completedFit = useRef(0);
  const [canvasReady, setCanvasReady] = useState(false);
  const [nodesInitialized, setNodesInitialized] = useState(false);
  const secondaryDragRef = useRef<{ x: number; y: number; moved: boolean }>();
  const [pendingTerminalId, setPendingTerminalId] = useState<string>();
  const emitContextMenu = (target: CircuitCanvasContextTarget, anchor: CircuitContextAnchor) => {
    if (!anchor.keyboard && secondaryDragRef.current?.moved) {
      secondaryDragRef.current = undefined;
      return;
    }
    secondaryDragRef.current = undefined;
    const flowPoint = instanceRef.current?.screenToFlowPosition(anchor.clientPoint) ?? anchor.clientPoint;
    onContextMenuRequest?.({ target, flowPoint, ...anchor });
  };
  const nodeGeometry = layout.node_geometry ?? {};
  const terminalPlacements = layout.terminal_placements ?? {};
  const netRoutes = layout.net_routes ?? {};
  const derivedFrame = circuitFrameGeometry(graph, nodeGeometry, terminalPlacements, netRoutes, gridSize);
  const boundaryGeometry = suppliedBoundaryGeometry ?? derivedFrame.boundary_geometry;
  const containerGeometry = suppliedContainerGeometry ?? derivedFrame.container_geometry;
  const containerPresentation = container === false ? undefined : container ?? {
    label: graph.design.label,
    description: `Design${graph.terminals.some(terminal => !terminal.node_id) ? "" : " · No ports defined"}`,
  };
  const selectedKeys = useMemo(
    () => new Set(selection.map((item) => `${item.kind}:${item.id}`)),
    [selection],
  );
  const selectionRef = useRef(selection);
  selectionRef.current = selection;
  const applyControlledSelectionChanges = (
    kind: "node" | "net",
    changes: Array<NodeChange<CircuitFlowNode> | EdgeChange<CircuitFlowEdge>>,
  ) => {
    let next = [...selectionRef.current];
    for (const change of changes) {
      if (change.type !== "select") continue;
      const item: CircuitCanvasSelectionItem = kind === "net"
        ? { kind: "net", id: change.id }
        : change.id.startsWith("boundary:")
          ? { kind: "boundary", id: change.id.slice("boundary:".length) }
          : { kind: "node", id: change.id };
      next = next.filter((selected) => selected.kind !== item.kind || selected.id !== item.id);
      if (change.selected) next.push(item);
    }
    if (circuitSelectionsEqual(selectionRef.current, next)) return;
    selectionRef.current = next;
    onSelectionChange?.(next);
  };
  const selectedNetId = selection.length === 1 && selection[0].kind === "net" ? selection[0].id : undefined;
  const occupiedTerminalIds = useMemo(
    () => new Set(graph.nets.flatMap((net) => net.endpoints.map((endpoint) => endpoint.terminal_id))),
    [graph.nets],
  );
  const rejectConnection = (reason: CircuitConnectionRejectionReason) => onConnectionRejected?.(reason);
  const completeConnection = (sourceTerminalId: string, targetTerminalId: string) => {
    const rejection = connectionRejectionReason(graph, sourceTerminalId, targetTerminalId);
    if (rejection) rejectConnection(rejection);
    else onConnectTerminals?.(sourceTerminalId, targetTerminalId);
  };
  const activateTerminal = (terminalId: string) => {
    if (!pendingTerminalId) {
      setPendingTerminalId(terminalId);
      return;
    }
    completeConnection(pendingTerminalId, terminalId);
    setPendingTerminalId(undefined);
  };
  const terminalsByNode = useMemo(() => {
    const result = new Map<string, CircuitTerminal[]>();
    for (const terminal of graph.terminals) {
      if (!terminal.node_id) continue;
      const values = result.get(terminal.node_id) ?? [];
      values.push(terminal);
      result.set(terminal.node_id, values);
    }
    return result;
  }, [graph]);
  const nodes: CircuitFlowNode[] = graph.nodes.flatMap((node) => {
    const geometry = nodeGeometry[node.id];
    if (!geometry) return [];
    return [{
      id: node.id,
      type: "circuit",
      position: { x: geometry.x, y: geometry.y },
      width: geometry.width,
      height: geometry.height,
      // Preserve handle measurements when controlled nodes are projected again.
      measured: { width: geometry.width, height: geometry.height },
      style: { width: geometry.width, height: geometry.height },
      data: {
        circuitNode: node,
        componentLabel: componentLabels[node.component_id],
        geometry,
        terminals: terminalsByNode.get(node.id) ?? [],
        placements: terminalPlacements,
        rendererRegistry,
        editable: editable && Boolean(onConnectTerminals),
        occupiedTerminalIds,
        pendingTerminalId,
        onTerminalActivate: activateTerminal,
        contextTarget: { kind: "node", nodeId: node.id },
        onTerminalContextMenu: emitContextMenu,
      },
      draggable: editable && Boolean(onNodeGeometryChanges),
      className: elementStatus?.nodes?.[node.id] ? `cd-element--${elementStatus.nodes[node.id]}` : undefined,
      selected: selectedKeys.has(`node:${node.id}`),
    }];
  });
  for (const terminal of graph.terminals.filter((item) => !item.node_id)) {
    const boundaryId = terminal.id.startsWith("boundary:") ? terminal.id.slice("boundary:".length) : terminal.id;
    const geometry = boundaryGeometry[terminal.id] ?? boundaryGeometry[boundaryId];
    if (!geometry) continue;
    nodes.push({
      id: `boundary:${boundaryId}`,
      type: "circuit",
      position: { x: geometry.x, y: geometry.y },
      width: geometry.width,
      height: geometry.height,
      measured: { width: geometry.width, height: geometry.height },
      style: { width: geometry.width, height: geometry.height },
      data: {
        circuitNode: { id: terminal.id, label: terminal.label, component_id: "boundary", terminal_ids: [terminal.id], configuration_values: {} },
        geometry,
        terminals: [terminal],
        placements: terminalPlacements,
        rendererRegistry,
        editable: editable && Boolean(onConnectTerminals),
        occupiedTerminalIds,
        pendingTerminalId,
        onTerminalActivate: activateTerminal,
        contextTarget: { kind: "boundary", terminalId: boundaryId },
        onTerminalContextMenu: emitContextMenu,
      },
      draggable: false,
      className: elementStatus?.nodes?.[terminal.id] ? `cd-element--${elementStatus.nodes[terminal.id]}` : undefined,
      selected: selectedKeys.has(`boundary:${boundaryId}`),
    });
  }
  const edges = buildCircuitFlowEdges(graph, netRoutes, {
    routeEditableNetId: editable && onNetRouteChange ? selectedNetId : undefined,
    gridSize,
    onNetRouteChange,
  });
  for (const edge of edges) {
    const status = elementStatus?.nets?.[edge.id];
    if (status) edge.className = `cd-element--${status}`;
    edge.selected = selectedKeys.has(`net:${edge.id}`);
    if (edge.data) edge.data.onContextMenu = emitContextMenu;
  }

  function fitCanvas(): void {
    const canvas = canvasRef.current;
    const instance = instanceRef.current;
    if (!canvas || !instance || !canvas.clientWidth || !canvas.clientHeight) return;
    const geometry = [...Object.values(nodeGeometry), ...Object.values(boundaryGeometry), ...(containerPresentation ? [containerGeometry] : [])];
    const points = [
      ...geometry.flatMap(box => [{ x: box.x, y: box.y }, { x: box.x + box.width, y: box.y + box.height }]),
      ...Object.values(netRoutes).flatMap(route => route.vertices.map(vertex => vertex.point)),
    ];
    if (!points.length) return;
    // Boundary labels sit outside their small port boxes. Include them and
    // route bends, and use the current canvas size after a window resize.
    const x = Math.min(...points.map(point => point.x)) - 160;
    const y = Math.min(...points.map(point => point.y)) - 40;
    const next = getViewportForBounds({ x, y,
      width: Math.max(...points.map(point => point.x)) - x + 160,
      height: Math.max(...points.map(point => point.y)) - y + 40,
    }, canvas.clientWidth, canvas.clientHeight, 0.08, 2.5, 0.1);
    void instance.setViewport(next);
    onViewportChange?.(next);
  }

  // Fit after React Flow has committed and measured the accepted layout.
  // Consume each explicit request once; ordinary edits retain the manual view.
  useEffect(() => {
    if (!canvasReady || (!nodesInitialized && nodes.length > 0) || fitRequest === completedFit.current) return;
    const frame = requestAnimationFrame(() => {
      fitCanvas();
      completedFit.current = fitRequest;
    });
    return () => cancelAnimationFrame(frame);
  }, [canvasReady, nodesInitialized, fitRequest, nodeGeometry, boundaryGeometry, netRoutes]);

  useImperativeHandle(forwardedRef, () => ({
    zoomIn: () => { void instanceRef.current?.zoomIn({ duration: 140 }); },
    zoomOut: () => { void instanceRef.current?.zoomOut({ duration: 140 }); },
    fitView: () => setFitRequest(request => request + 1),
    cancelPendingConnection: () => setPendingTerminalId(undefined),
    centerSelection: () => {
      const instance = instanceRef.current;
      if (!instance) return;
      const selectedNodeIds = new Set(selection.flatMap((item) => {
        if (item.kind === "node") return [item.id];
        if (item.kind === "boundary") return [`boundary:${item.id}`];
        return [];
      }));
      const selectedNodes = instance.getNodes().filter((node) => selectedNodeIds.has(node.id));
      if (selectedNodes.length) {
        void instance.fitView({ nodes: selectedNodes, padding: 0.3, duration: 180 });
        return;
      }
      const routePoints = selection
        .filter((item) => item.kind === "net")
        .flatMap((item) => netRoutes[item.id]?.vertices.map((vertex) => vertex.point) ?? []);
      if (!routePoints.length) return;
      const xs = routePoints.map((point) => point.x);
      const ys = routePoints.map((point) => point.y);
      void instance.fitBounds({
        x: Math.min(...xs), y: Math.min(...ys),
        width: Math.max(1, Math.max(...xs) - Math.min(...xs)),
        height: Math.max(1, Math.max(...ys) - Math.min(...ys)),
      }, { padding: 0.3, duration: 180 });
    },
    pan: (direction) => {
      const instance = instanceRef.current;
      const canvas = canvasRef.current;
      if (!instance || !canvas) return;
      const horizontal = canvas.clientWidth * 0.2;
      const vertical = canvas.clientHeight * 0.2;
      const delta = direction === "left" ? { x: horizontal, y: 0 }
        : direction === "right" ? { x: -horizontal, y: 0 }
          : direction === "up" ? { x: 0, y: vertical }
            : { x: 0, y: -vertical };
      const current = instance.getViewport();
      void instance.setViewport({ ...current, x: current.x + delta.x, y: current.y + delta.y }, { duration: 140 });
    },
  }), [netRoutes, selection, nodeGeometry, boundaryGeometry, onViewportChange]);

  const onCanvasKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const target = event.target;
    const typing = target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement;
    if (typing) return;
    if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
      event.preventDefault();
      const element = target instanceof Element ? target : event.currentTarget;
      const nodeElement = element.closest<HTMLElement>(".react-flow__node");
      const edgeElement = element.closest<HTMLElement>(".react-flow__edge");
      let selectedElement: HTMLElement | SVGElement | null = null;
      let contextTarget: CircuitCanvasContextTarget = { kind: "canvas" };
      if (nodeElement?.dataset.id?.startsWith("boundary:")) {
        contextTarget = { kind: "boundary", terminalId: nodeElement.dataset.id.slice("boundary:".length) };
      } else if (nodeElement?.dataset.id) {
        contextTarget = { kind: "node", nodeId: nodeElement.dataset.id };
      } else if (edgeElement?.dataset.id) {
        contextTarget = { kind: "net", netId: edgeElement.dataset.id };
      } else if (selection.length === 1) {
        const item = selection[0];
        contextTarget = item.kind === "node" ? { kind: "node", nodeId: item.id }
          : item.kind === "boundary" ? { kind: "boundary", terminalId: item.id }
            : item.kind === "cycle-edge" ? { kind: "cycle-edge", edgeId: item.id }
              : { kind: "net", netId: item.id };
        const flowId = item.kind === "boundary" ? `boundary:${item.id}` : item.id;
        selectedElement = canvasRef.current?.querySelector<HTMLElement | SVGElement>(
          item.kind === "cycle-edge" ? `[data-cycle-edge-id="${CSS.escape(item.id)}"]`
            : item.kind === "net" ? `.react-flow__edge[data-id="${CSS.escape(flowId)}"]`
              : `.react-flow__node[data-id="${CSS.escape(flowId)}"]`,
        ) ?? null;
      }
      const bounds = (nodeElement ?? edgeElement ?? selectedElement ?? canvasRef.current)?.getBoundingClientRect();
      emitContextMenu(contextTarget, {
        clientPoint: bounds
          ? { x: bounds.left + bounds.width / 2, y: bounds.top + bounds.height / 2 }
          : { x: window.innerWidth / 2, y: window.innerHeight / 2 },
        focusTarget: element instanceof HTMLElement || element instanceof SVGElement ? element : undefined,
        keyboard: true,
      });
      return;
    }
    if (event.key === "Escape" && useDefaultEscapeBinding) {
      if (pendingTerminalId) setPendingTerminalId(undefined);
      else onSelectionChange?.([]);
      return;
    }
    const selectedCycleEdge = selection.length === 1 && selection[0].kind === "cycle-edge"
      ? timing?.cycle_edges.find((edge) => edge.id === selection[0].id)
      : undefined;
    if (event.key.startsWith("Arrow") && selectedCycleEdge && editable && onCycleEdgeChange && !selectedCycleEdge.locked) {
      const delta = gridSize * (event.shiftKey ? 5 : 1);
      const x = selectedCycleEdge.x + (event.key === "ArrowLeft" ? -delta : event.key === "ArrowRight" ? delta : 0);
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault(); onCycleEdgeChange({ ...selectedCycleEdge, x });
      }
      return;
    }
    if (!event.key.startsWith("Arrow") || !editable || !onNodeGeometryChanges) return;
    const delta = gridSize * (event.shiftKey ? 10 : 1);
    const offset = event.key === "ArrowLeft" ? { x: -delta, y: 0 }
      : event.key === "ArrowRight" ? { x: delta, y: 0 }
        : event.key === "ArrowUp" ? { x: 0, y: -delta }
          : { x: 0, y: delta };
    const changes = Object.fromEntries(selection.flatMap((item) => {
      if (item.kind !== "node") return [];
      const geometry = nodeGeometry[item.id];
      if (!geometry) return [];
      return [[item.id, { ...geometry, x: geometry.x + offset.x, y: geometry.y + offset.y, pinned: true }]];
    }));
    if (!Object.keys(changes).length) return;
    event.preventDefault();
    onNodeGeometryChanges(changes);
  };

  return (
    <div
      className="cd-canvas"
      data-testid="circuit-canvas"
      ref={canvasRef}
      onKeyDown={onCanvasKeyDown}
      onPointerDownCapture={(event) => {
        if (event.button === 2) secondaryDragRef.current = { x: event.clientX, y: event.clientY, moved: false };
      }}
      onPointerMoveCapture={(event) => {
        const drag = secondaryDragRef.current;
        if (drag && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) > 5) drag.moved = true;
      }}
      onPointerUpCapture={() => window.setTimeout(() => { secondaryDragRef.current = undefined; }, 100)}
      tabIndex={0}
    >
      <ReactFlow<CircuitFlowNode, CircuitFlowEdge>
        nodes={nodes}
        edges={edges}
        nodeTypes={{ circuit: CircuitNodeView }}
        edgeTypes={{ circuit: CircuitEdgeView }}
        fitView={false}
        onInit={(instance) => { instanceRef.current = instance; setCanvasReady(true); }}
        defaultViewport={{ x: gridSize, y: gridSize, zoom: 1 }}
        {...(viewport ? { viewport } : {})}
        minZoom={0.08}
        maxZoom={2.5}
        nodesDraggable={editable && Boolean(onNodeGeometryChanges)}
        nodesConnectable={editable && Boolean(onConnectTerminals)}
        elementsSelectable
        connectionMode={ConnectionMode.Loose}
        connectOnClick={false}
        isValidConnection={(connection) => {
          const source = terminalIdFromHandle(connection.sourceHandle);
          const target = terminalIdFromHandle(connection.targetHandle);
          return Boolean(source && target && !connectionRejectionReason(graph, source, target));
        }}
        snapToGrid
        snapGrid={[gridSize, gridSize]}
        panOnDrag={allowViewportNavigation && viewportPanMouseButtons.length ? viewportPanMouseButtons : false}
        panActivationKeyCode={allowViewportNavigation ? viewportPanActivationKeyCode : null}
        zoomOnScroll={allowViewportNavigation && wheelZoomEnabled}
        zoomOnPinch={allowViewportNavigation}
        zoomOnDoubleClick={false}
        selectionKeyCode="Shift"
        selectionOnDrag={false}
        selectionMode={SelectionMode.Partial}
        multiSelectionKeyCode={["Shift", "Meta", "Control"]}
        deleteKeyCode={null}
        autoPanOnNodeDrag={allowViewportNavigation}
        autoPanOnConnect={allowViewportNavigation}
        onMove={(_, nextViewport) => onViewportChange?.(nextViewport)}
        onPaneClick={(event) => onCanvasPointClick?.(instanceRef.current?.screenToFlowPosition({ x: event.clientX, y: event.clientY }) ?? { x: event.clientX, y: event.clientY })}
        onNodesChange={(changes) => applyControlledSelectionChanges("node", changes)}
        onEdgesChange={(changes) => applyControlledSelectionChanges("net", changes)}
        onPaneContextMenu={(event) => {
          event.preventDefault();
          emitContextMenu({ kind: "canvas" }, {
            clientPoint: { x: event.clientX, y: event.clientY },
            focusTarget: event.currentTarget instanceof HTMLElement || event.currentTarget instanceof SVGElement ? event.currentTarget : undefined,
            keyboard: false,
          });
        }}
        onNodeContextMenu={(event, node) => {
          event.preventDefault();
          const contextTarget: CircuitCanvasContextTarget = node.id.startsWith("boundary:")
            ? { kind: "boundary", terminalId: node.id.slice("boundary:".length) }
            : { kind: "node", nodeId: node.id };
          emitContextMenu(contextTarget, {
            clientPoint: { x: event.clientX, y: event.clientY },
            focusTarget: event.currentTarget instanceof HTMLElement || event.currentTarget instanceof SVGElement ? event.currentTarget : undefined,
            keyboard: false,
          });
        }}
        onEdgeContextMenu={(event, edge) => {
          event.preventDefault();
          emitContextMenu({ kind: "net", netId: edge.id }, {
            clientPoint: { x: event.clientX, y: event.clientY },
            focusTarget: event.currentTarget instanceof HTMLElement || event.currentTarget instanceof SVGElement ? event.currentTarget : undefined,
            keyboard: false,
          });
        }}
        onConnect={(connection) => {
          const sourceTerminalId = terminalIdFromHandle(connection.sourceHandle);
          const targetTerminalId = terminalIdFromHandle(connection.targetHandle);
          if (sourceTerminalId && targetTerminalId) completeConnection(sourceTerminalId, targetTerminalId);
          setPendingTerminalId(undefined);
        }}
        onConnectEnd={(_, state) => {
          if (state.fromHandle && !state.isValid) rejectConnection("invalid_target");
        }}
        onNodeDragStop={(_, node, draggedNodes) => {
          const values = draggedNodes.length ? draggedNodes : [node];
          const changes = Object.fromEntries(values.flatMap((value) => {
            const original = nodeGeometry[value.id];
            if (!original) return [];
            return [[value.id, {
              x: Math.round(value.position.x / gridSize) * gridSize,
              y: Math.round(value.position.y / gridSize) * gridSize,
              width: original.width,
              height: original.height,
              pinned: true,
            }]];
          }));
          if (Object.keys(changes).length) onNodeGeometryChanges?.(changes);
        }}
      >
        <CanvasMeasurementStatus onReady={setNodesInitialized} />
        {containerPresentation && <ViewportPortal>
          <div className="cd-design-frame" data-testid="circuit-design-frame" style={{ left: containerGeometry.x, top: containerGeometry.y, width: containerGeometry.width, height: containerGeometry.height }}>
            <div className="cd-design-frame__header nopan nodrag" style={{ height: CIRCUIT_FRAME_HEADER_HEIGHT }}
              onContextMenu={(event) => {
                event.preventDefault(); event.stopPropagation();
                emitContextMenu({ kind: "canvas" }, { clientPoint: { x: event.clientX, y: event.clientY }, focusTarget: event.currentTarget, keyboard: false });
              }}>
              <div className="cd-design-frame__heading"><strong title={containerPresentation.label}>{containerPresentation.label}</strong><span>{containerPresentation.description}</span></div>
              {onAddBoundaryPort && <button type="button" className="nodrag nopan" disabled={!canAddBoundaryPort} title={!canAddBoundaryPort ? addBoundaryPortDisabledReason : undefined} onClick={onAddBoundaryPort}>Add port</button>}
            </div>
          </div>
        </ViewportPortal>}
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        {showInlineViewportControls && <Controls showInteractive={false} />}
      </ReactFlow>
      {timing && showTimingOverlay && <CycleEdgeOverlay
        timing={timing}
        viewport={viewport ?? { x: gridSize, y: gridSize, zoom: 1 }}
        editable={editable}
        selectedId={selection.length === 1 && selection[0].kind === "cycle-edge" ? selection[0].id : undefined}
        gridSize={gridSize}
        canvasRef={canvasRef}
        onSelect={(edgeId) => onSelectionChange?.([{ kind: "cycle-edge", id: edgeId }])}
        onChange={onCycleEdgeChange}
        onContextMenu={emitContextMenu}
        analysis={timingAnalysis}
        layout={layout}
      />}
    </div>
  );
}

export const CircuitDesignerCanvas = forwardRef<CircuitDesignerCanvasHandle, CircuitDesignerCanvasProps>(CircuitDesignerCanvasInner);

export interface CircuitProposalDiffViewerProps {
  before: CircuitDocument;
  after: CircuitDocument;
  diff: CircuitDiff;
  diagnostics?: Diagnostic[];
  height?: number;
}

interface DiffCanvasState {
  graph: CircuitGraphSnapshot;
  layout: DiagramLayout;
  boundaryGeometry: Record<string, NodeGeometry>;
}

export function CircuitProposalDiffViewer({
  before,
  after,
  diff,
  diagnostics = [],
  height = 430,
}: CircuitProposalDiffViewerProps) {
  const [beforeState, setBeforeState] = useState<DiffCanvasState>();
  const [afterState, setAfterState] = useState<DiffCanvasState>();
  const [selection, setSelection] = useState<CircuitCanvasSelection>([]);
  const [viewport, setViewport] = useState<Viewport>();

  useEffect(() => {
    let active = true;
    void Promise.all([
      layoutCircuitDocument(before, { preserveNodeGeometry: "all" }),
      layoutCircuitDocument(after, { preserveNodeGeometry: "all" }),
    ]).then(([left, right]) => {
      if (!active) return;
      setBeforeState({
        graph: projectDocument(left.document, "proposal-before"),
        layout: left.layout,
        boundaryGeometry: left.boundary_geometry,
      });
      setAfterState({
        graph: projectDocument(right.document, "proposal-after"),
        layout: right.layout,
        boundaryGeometry: right.boundary_geometry,
      });
    });
    return () => { active = false; };
  }, [before, after]);

  const beforeStatus = useMemo(() => diffElementStatus(diff, "before"), [diff]);
  const afterStatus = useMemo(() => diffElementStatus(diff, "after"), [diff]);
  const errorCount = diagnostics.filter((item) => item.severity === "error").length;
  const warningCount = diagnostics.filter((item) => item.severity === "warning").length;

  return (
    <section className="cd-proposal-diff" aria-label="Circuit proposal before and after">
      <header className="cd-proposal-diff__header">
        <span>{diff.added.length} added</span>
        <span>{diff.changed.length} changed</span>
        <span>{diff.removed.length} removed</span>
        <span>{diff.connections_changed.length} connections changed</span>
        {(errorCount > 0 || warningCount > 0) && (
          <span>{errorCount} errors · {warningCount} warnings</span>
        )}
      </header>
      <div className="cd-proposal-diff__grid" style={{ height }}>
        <div className="cd-proposal-diff__pane">
          <strong>Before</strong>
          {beforeState ? (
            <CircuitDesignerCanvas
              graph={beforeState.graph}
              layout={beforeState.layout}
              boundaryGeometry={beforeState.boundaryGeometry}
              elementStatus={beforeStatus}
              selection={selection}
              onSelectionChange={setSelection}
              viewport={viewport}
              onViewportChange={setViewport}
              editable={false}
            />
          ) : <div className="cd-proposal-diff__loading">Preparing layout…</div>}
        </div>
        <div className="cd-proposal-diff__pane">
          <strong>After</strong>
          {afterState ? (
            <CircuitDesignerCanvas
              graph={afterState.graph}
              layout={afterState.layout}
              boundaryGeometry={afterState.boundaryGeometry}
              elementStatus={afterStatus}
              selection={selection}
              onSelectionChange={setSelection}
              viewport={viewport}
              onViewportChange={setViewport}
              editable={false}
            />
          ) : <div className="cd-proposal-diff__loading">Preparing layout…</div>}
        </div>
      </div>
      {diagnostics.length > 0 && (
        <details className="cd-proposal-diff__diagnostics">
          <summary>Diagnostics</summary>
          <ul>{diagnostics.map((item, index) => (
            <li key={`${item.code}:${item.element_key ?? index}`} data-severity={item.severity}>
              <code>{item.code}</code> {item.message}
            </li>
          ))}</ul>
        </details>
      )}
    </section>
  );
}

function diffElementStatus(
  diff: CircuitDiff,
  side: "before" | "after",
): NonNullable<CircuitDesignerCanvasProps["elementStatus"]> {
  const nodes: Record<string, "added" | "removed" | "changed"> = {};
  const nets: Record<string, "added" | "removed" | "changed"> = {};
  const assign = (
    kind: "instance" | "boundary_terminal" | "net",
    id: string,
    status: "added" | "removed" | "changed",
  ) => {
    if (kind === "net") nets[id] = status;
    else nodes[id] = status;
  };
  if (side === "before") {
    for (const item of diff.removed) {
      if (item.kind === "instance" || item.kind === "boundary_terminal" || item.kind === "net") assign(item.kind, item.id, "removed");
    }
  } else {
    for (const item of diff.added) {
      if (item.kind === "instance" || item.kind === "boundary_terminal" || item.kind === "net") assign(item.kind, item.id, "added");
    }
  }
  for (const item of diff.changed) {
    if (item.kind === "instance" || item.kind === "boundary_terminal" || item.kind === "net") assign(item.kind, item.id, "changed");
  }
  for (const netId of diff.connections_changed) nets[netId] = "changed";
  return { nodes, nets };
}

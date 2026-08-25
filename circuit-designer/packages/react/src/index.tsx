import {
  Fragment,
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ForwardedRef,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  Handle,
  Position,
  ReactFlow,
  SelectionMode,
  useReactFlow,
  useUpdateNodeInternals,
  type Edge,
  type EdgeProps,
  type Node,
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
} from "@spec2gds/circuit-core";
import {
  ensureRouteIds,
  insertRouteBend,
  moveRouteSegment,
  moveRouteVertex,
  removeRouteBend,
  projectDocument,
} from "@spec2gds/circuit-core";
import { layoutCircuitDocument } from "@spec2gds/circuit-layout";

export type CircuitCanvasSelectionItem = { kind: "node" | "boundary" | "net"; id: string };
export type CircuitCanvasSelection = CircuitCanvasSelectionItem[];
export type CircuitConnectionRejectionReason = "same_terminal" | "terminal_in_use" | "invalid_target";

export interface CircuitDesignerCanvasHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  fitView: () => void;
  centerSelection: () => void;
  pan: (direction: "left" | "right" | "up" | "down") => void;
}

export function circuitSelectionsEqual(left: CircuitCanvasSelection, right: CircuitCanvasSelection): boolean {
  if (left.length !== right.length) return false;
  const keys = new Set(left.map((item) => `${item.kind}:${item.id}`));
  return right.every((item) => keys.has(`${item.kind}:${item.id}`));
}

export function terminalDisplayLabel(terminal: Pick<CircuitTerminal, "label" | "width">): string {
  return typeof terminal.width === "string" ? `${terminal.label} ${terminal.width}` : terminal.label;
}

export interface CircuitDesignerCanvasProps {
  graph: CircuitGraphSnapshot;
  layout: DiagramLayout;
  boundaryGeometry?: Record<string, NodeGeometry>;
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
}

type CircuitNodeData = {
  circuitNode: CircuitNode;
  terminals: CircuitTerminal[];
  placements: Record<string, TerminalPlacement>;
  rendererRegistry?: CircuitCanvasRendererRegistry;
  editable: boolean;
  occupiedTerminalIds: Set<string>;
  pendingTerminalId?: string;
  onTerminalActivate: (terminalId: string) => void;
};

type CircuitFlowNode = Node<CircuitNodeData, "circuit">;
type CircuitEdgeData = {
  route: NetRoute;
  label: string;
  kind: string;
  routeEditable: boolean;
  gridSize: number;
  onRouteChange?: (route: NetRoute) => void;
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
  useEffect(() => updateNodeInternals(id), [id, selected, updateNodeInternals]);
  const rendererKey = data.circuitNode.component_vlnv ?? "generic";
  const customRenderer = data.rendererRegistry?.renderer(rendererKey)
    ?? defaultCircuitCanvasRenderers.renderer(rendererKey);
  return (
    <div className="cd-node">
      <div className="cd-node__eyebrow">{data.circuitNode.component_vlnv ?? data.circuitNode.component_id}</div>
      <div className="cd-node__title">{customRenderer
        ? customRenderer({ node: data.circuitNode })
        : data.circuitNode.display_name ?? data.circuitNode.label}</div>
      {data.terminals.map((terminal) => {
        const placement = data.placements[terminal.id];
        const side = placement?.side ?? "SOUTH";
        const offset = 60 + (placement?.order ?? 0) * 20;
        const style = side === "EAST" || side === "WEST" ? { top: offset } : { left: offset };
        const displayLabel = terminalDisplayLabel(terminal);
        const occupied = data.occupiedTerminalIds.has(terminal.id);
        const pending = data.pendingTerminalId === terminal.id;
        const activateFromKeyboard = (event: ReactKeyboardEvent<HTMLDivElement>) => {
          if (event.key !== "Enter" || occupied || !data.editable) return;
          event.preventDefault();
          event.stopPropagation();
          data.onTerminalActivate(terminal.id);
        };
        return <Fragment key={terminal.id}>
          <span className={`cd-node__port-label cd-node__port-label--${side.toLowerCase()}`} style={style}>{displayLabel}</span>
          <Handle
            id={terminalHandleId(terminal.id)}
            type="source"
            position={positions[side]}
            style={style}
            className={occupied ? "cd-terminal--occupied" : pending ? "cd-terminal--pending" : undefined}
            title={occupied ? `${displayLabel} · already connected` : `${displayLabel} · drag to connect`}
            aria-label={occupied ? `${displayLabel}, already connected` : `${displayLabel}, connection terminal`}
            aria-disabled={occupied || !data.editable}
            role="button"
            tabIndex={data.editable ? 0 : -1}
            isConnectable={data.editable && !occupied}
            onKeyDown={activateFromKeyboard}
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
  return graph.nets.flatMap((net) => {
    const route = netRoutes[net.id];
    if (!route || net.endpoints.length < 2) return [];
    const sourceTerminalId = net.endpoints[0].terminal_id;
    const targetTerminalId = net.endpoints[1].terminal_id;
    return [{
      id: net.id,
      type: "circuit",
      source: graph.terminals.find((terminal) => terminal.id === sourceTerminalId)?.node_id ?? `boundary:${sourceTerminalId}`,
      target: graph.terminals.find((terminal) => terminal.id === targetTerminalId)?.node_id ?? `boundary:${targetTerminalId}`,
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

function CircuitEdgeView({ data, selected }: EdgeProps<CircuitFlowEdge>) {
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
        const id = segment.id ?? `segment:${index}`;
        return <Fragment key={id}>
          <path d={`M ${start.x} ${start.y} L ${end.x} ${end.y}`} className={segment.locked ? "cd-net__segment cd-net__segment--locked" : "cd-net__segment"} />
          {data.routeEditable && <path
            d={`M ${start.x} ${start.y} L ${end.x} ${end.y}`}
            className="cd-net__hit-segment"
            data-segment-id={id}
            data-movable={movable}
            onPointerDown={(event) => startDrag(event, "segment", id, segment.locked)}
            onPointerMove={moveDrag}
            onPointerUp={endDrag}
            onDoubleClick={(event) => {
              event.stopPropagation();
              const next = insertRouteBend(draftRef.current, id, flowPoint(event), data.gridSize);
              updateDraft(next); data.onRouteChange?.(next);
            }}
          />}
        </Fragment>;
      })}
      {draft.vertices.filter((vertex) => vertex.kind === "junction" && (degrees.get(vertex.id) ?? 0) >= 3).map((vertex) => (
        <circle key={vertex.id} cx={vertex.point.x} cy={vertex.point.y} r="3.5" className="cd-net__junction" />
      ))}
      {data.routeEditable && draft.vertices.filter((vertex) => vertex.kind !== "endpoint").map((vertex) => (
        <circle
          key={`handle:${vertex.id}`}
          cx={vertex.point.x} cy={vertex.point.y} r="5"
          className={vertex.locked ? "cd-net__route-handle cd-net__route-handle--locked" : "cd-net__route-handle"}
          data-vertex-id={vertex.id}
          onPointerDown={(event) => startDrag(event, "vertex", vertex.id, vertex.locked)}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          onDoubleClick={(event) => {
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
  const occupied = new Set(graph.nets.flatMap((net) => net.endpoints.map((endpoint) => endpoint.terminal_id)));
  if (occupied.has(sourceTerminalId) || occupied.has(targetTerminalId)) return "terminal_in_use";
  return undefined;
}

function CircuitDesignerCanvasInner({ graph, layout, boundaryGeometry = {}, selection = [], onSelectionChange, editable = false, onNodeGeometryChanges, onConnectTerminals, onConnectionRejected, gridSize = 20, allowViewportNavigation = true, fitViewOnInit = true, onNetRouteChange, rendererRegistry, elementStatus, viewport, onViewportChange, showInlineViewportControls = true }: CircuitDesignerCanvasProps, forwardedRef: ForwardedRef<CircuitDesignerCanvasHandle>) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<ReactFlowInstance<CircuitFlowNode, CircuitFlowEdge>>();
  const [pendingTerminalId, setPendingTerminalId] = useState<string>();
  const nodeGeometry = layout.node_geometry ?? {};
  const terminalPlacements = layout.terminal_placements ?? {};
  const netRoutes = layout.net_routes ?? {};
  const selectedKeys = useMemo(
    () => new Set(selection.map((item) => `${item.kind}:${item.id}`)),
    [selection],
  );
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
      style: { width: geometry.width, height: geometry.height },
      data: {
        circuitNode: node,
        terminals: terminalsByNode.get(node.id) ?? [],
        placements: terminalPlacements,
        rendererRegistry,
        editable: editable && Boolean(onConnectTerminals),
        occupiedTerminalIds,
        pendingTerminalId,
        onTerminalActivate: activateTerminal,
      },
      draggable: editable && Boolean(onNodeGeometryChanges),
      className: elementStatus?.nodes?.[node.id] ? `cd-element--${elementStatus.nodes[node.id]}` : undefined,
      selected: selectedKeys.has(`node:${node.id}`),
    }];
  });
  for (const terminal of graph.terminals.filter((item) => !item.node_id)) {
    const geometry = boundaryGeometry[terminal.id];
    if (!geometry) continue;
    nodes.push({
      id: `boundary:${terminal.id}`,
      type: "circuit",
      position: { x: geometry.x, y: geometry.y },
      width: geometry.width,
      height: geometry.height,
      style: { width: geometry.width, height: geometry.height },
      data: {
        circuitNode: { id: terminal.id, label: terminal.label, component_id: "boundary", terminal_ids: [terminal.id], configuration_values: {} },
        terminals: [terminal],
        placements: terminalPlacements,
        rendererRegistry,
        editable: editable && Boolean(onConnectTerminals),
        occupiedTerminalIds,
        pendingTerminalId,
        onTerminalActivate: activateTerminal,
      },
      draggable: false,
      className: elementStatus?.nodes?.[terminal.id] ? `cd-element--${elementStatus.nodes[terminal.id]}` : undefined,
      selected: selectedKeys.has(`boundary:${terminal.id}`),
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
  }

  useImperativeHandle(forwardedRef, () => ({
    zoomIn: () => { void instanceRef.current?.zoomIn({ duration: 140 }); },
    zoomOut: () => { void instanceRef.current?.zoomOut({ duration: 140 }); },
    fitView: () => { void instanceRef.current?.fitView({ padding: 0.2, duration: 180 }); },
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
  }), [netRoutes, selection]);

  const onCanvasKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const target = event.target;
    const typing = target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement;
    if (typing) return;
    if (event.key === "Escape") {
      if (pendingTerminalId) setPendingTerminalId(undefined);
      else onSelectionChange?.([]);
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
    <div className="cd-canvas" data-testid="circuit-canvas" ref={canvasRef} onKeyDown={onCanvasKeyDown}>
      <ReactFlow<CircuitFlowNode, CircuitFlowEdge>
        nodes={nodes}
        edges={edges}
        nodeTypes={{ circuit: CircuitNodeView }}
        edgeTypes={{ circuit: CircuitEdgeView }}
        fitView={fitViewOnInit}
        onInit={(instance) => { instanceRef.current = instance; }}
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
        panOnDrag={allowViewportNavigation ? [1] : false}
        panActivationKeyCode={allowViewportNavigation ? "Space" : null}
        zoomOnScroll={allowViewportNavigation}
        zoomOnPinch={allowViewportNavigation}
        zoomOnDoubleClick={false}
        selectionOnDrag
        selectionMode={SelectionMode.Partial}
        multiSelectionKeyCode={["Shift", "Meta", "Control"]}
        deleteKeyCode={null}
        autoPanOnNodeDrag={allowViewportNavigation}
        autoPanOnConnect={allowViewportNavigation}
        onMove={(_, nextViewport) => onViewportChange?.(nextViewport)}
        onSelectionChange={({ nodes: selectedNodes, edges: selectedEdges }) => {
          const next = [
            ...selectedNodes.map((node): CircuitCanvasSelectionItem => node.id.startsWith("boundary:")
            ? { kind: "boundary", id: node.id.slice("boundary:".length) }
            : { kind: "node", id: node.id }),
            ...selectedEdges.map((edge): CircuitCanvasSelectionItem => ({ kind: "net", id: edge.id })),
          ];
          if (!circuitSelectionsEqual(selection, next)) onSelectionChange?.(next);
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
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        {showInlineViewportControls && <Controls showInteractive={false} />}
      </ReactFlow>
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

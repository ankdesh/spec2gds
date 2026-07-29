import { Fragment, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  Handle,
  Position,
  ReactFlow,
  useReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import type {
  CircuitGraphView as CircuitGraphSnapshot,
  CircuitNodeView as CircuitNode,
  CircuitTerminalView as CircuitTerminal,
  DiagramLayoutView as DiagramLayout,
  NetRoute,
  NodeGeometry,
  TerminalPlacement,
} from "@spec2gds/circuit-core";
import {
  ensureRouteIds,
  insertRouteBend,
  moveRouteSegment,
  moveRouteVertex,
  removeRouteBend,
  toggleRouteSegmentLock,
  toggleRouteVertexLock,
} from "@spec2gds/circuit-core";

export type CircuitCanvasMode = "select" | "connect" | "route" | "pan";

export interface CircuitInteractionPolicy {
  nodesDraggable: boolean;
  nodesConnectable: boolean;
  elementsSelectable: boolean;
  routeEditable: boolean;
  panOnDrag: boolean;
  zoomEnabled: boolean;
}

export function interactionPolicy(mode: CircuitCanvasMode, editable: boolean): CircuitInteractionPolicy {
  return {
    nodesDraggable: editable && mode === "select",
    nodesConnectable: editable && mode === "connect",
    elementsSelectable: mode !== "pan",
    routeEditable: editable && mode === "route",
    panOnDrag: mode === "pan",
    zoomEnabled: mode === "pan",
  };
}

export interface CircuitDesignerCanvasProps {
  graph: CircuitGraphSnapshot;
  layout: DiagramLayout;
  boundaryGeometry?: Record<string, NodeGeometry>;
  onSelect?: (selection: { kind: "node" | "net"; id: string } | null) => void;
  editable?: boolean;
  onNodeGeometryChange?: (nodeId: string, geometry: NodeGeometry) => void;
  onConnectTerminals?: (sourceTerminalId: string, targetTerminalId: string) => void;
  gridSize?: number;
  allowViewportNavigation?: boolean;
  fitViewOnInit?: boolean;
  mode?: CircuitCanvasMode;
  onNetRouteChange?: (netId: string, route: NetRoute) => void;
  rendererRegistry?: CircuitCanvasRendererRegistry;
}

type CircuitNodeData = {
  circuitNode: CircuitNode;
  terminals: CircuitTerminal[];
  placements: Record<string, TerminalPlacement>;
  rendererRegistry?: CircuitCanvasRendererRegistry;
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

function CircuitNodeView({ data }: NodeProps<CircuitFlowNode>) {
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
        return <Fragment key={terminal.id}>
          <span className={`cd-node__port-label cd-node__port-label--${side.toLowerCase()}`} style={style}>{terminal.label}</span>
          <Handle id={terminalHandleId(terminal.id, "source")} type="source" position={positions[side]} style={style} title={terminal.label} />
          <Handle id={terminalHandleId(terminal.id, "target")} type="target" position={positions[side]} style={style} title={terminal.label} />
        </Fragment>;
      })}
    </div>
  );
}

export function terminalHandleId(terminalId: string, type: "source" | "target"): string {
  return `${terminalId}:${type}`;
}

export function terminalIdFromHandle(handleId: string | null | undefined): string | undefined {
  return handleId?.replace(/:(source|target)$/, "");
}

export interface BuildCircuitFlowEdgeOptions {
  routeEditable?: boolean;
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
        routeEditable: options.routeEditable ?? false,
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
            onClick={(event) => {
              if (!event.shiftKey) return;
              event.stopPropagation();
              const next = toggleRouteSegmentLock(draftRef.current, id);
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
          onClick={(event) => {
            if (!event.shiftKey) return;
            event.stopPropagation();
            const next = toggleRouteVertexLock(draftRef.current, vertex.id);
            updateDraft(next); data.onRouteChange?.(next);
          }}
        />
      ))}
    </g>
  );
}

export function CircuitDesignerCanvas({ graph, layout, boundaryGeometry = {}, onSelect, editable = false, onNodeGeometryChange, onConnectTerminals, gridSize = 20, allowViewportNavigation = true, fitViewOnInit = true, mode = "select", onNetRouteChange, rendererRegistry }: CircuitDesignerCanvasProps) {
  const policy = interactionPolicy(mode, editable);
  const nodeGeometry = layout.node_geometry ?? {};
  const terminalPlacements = layout.terminal_placements ?? {};
  const netRoutes = layout.net_routes ?? {};
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
      style: { width: geometry.width, height: geometry.height },
      data: { circuitNode: node, terminals: terminalsByNode.get(node.id) ?? [], placements: terminalPlacements, rendererRegistry },
      draggable: policy.nodesDraggable,
    }];
  });
  for (const terminal of graph.terminals.filter((item) => !item.node_id)) {
    const geometry = boundaryGeometry[terminal.id];
    if (!geometry) continue;
    nodes.push({
      id: `boundary:${terminal.id}`,
      type: "circuit",
      position: { x: geometry.x, y: geometry.y },
      style: { width: geometry.width, height: geometry.height },
      data: {
        circuitNode: { id: terminal.id, label: terminal.label, component_id: "boundary", terminal_ids: [terminal.id], configuration_values: {} },
        terminals: [terminal], placements: terminalPlacements, rendererRegistry,
      },
      draggable: false,
    });
  }
  const edges = buildCircuitFlowEdges(graph, netRoutes, { routeEditable: policy.routeEditable, gridSize, onNetRouteChange });
  return (
    <div className="cd-canvas" data-testid="circuit-canvas">
      <ReactFlow<CircuitFlowNode, CircuitFlowEdge>
        nodes={nodes}
        edges={edges}
        nodeTypes={{ circuit: CircuitNodeView }}
        edgeTypes={{ circuit: CircuitEdgeView }}
        fitView={fitViewOnInit}
        defaultViewport={{ x: gridSize, y: gridSize, zoom: 1 }}
        minZoom={0.08}
        maxZoom={2.5}
        nodesDraggable={policy.nodesDraggable}
        nodesConnectable={policy.nodesConnectable && Boolean(onConnectTerminals)}
        elementsSelectable={policy.elementsSelectable}
        connectionMode={ConnectionMode.Loose}
        snapToGrid
        snapGrid={[gridSize, gridSize]}
        panOnDrag={allowViewportNavigation && policy.panOnDrag}
        zoomOnScroll={allowViewportNavigation && policy.zoomEnabled}
        zoomOnPinch={allowViewportNavigation && policy.zoomEnabled}
        zoomOnDoubleClick={allowViewportNavigation && policy.zoomEnabled}
        autoPanOnNodeDrag={false}
        autoPanOnConnect={false}
        onPaneClick={() => onSelect?.(null)}
        onNodeClick={(_, node) => onSelect?.({ kind: "node", id: node.id.replace(/^boundary:/, "") })}
        onEdgeClick={(_, edge) => onSelect?.({ kind: "net", id: edge.id })}
        onConnect={(connection) => {
          const sourceTerminalId = terminalIdFromHandle(connection.sourceHandle);
          const targetTerminalId = terminalIdFromHandle(connection.targetHandle);
          if (sourceTerminalId && targetTerminalId && sourceTerminalId !== targetTerminalId) onConnectTerminals?.(sourceTerminalId, targetTerminalId);
        }}
        onNodeDragStop={(_, node) => {
          const original = nodeGeometry[node.id];
          if (!original) return;
          onNodeGeometryChange?.(node.id, {
            x: Math.round(node.position.x / gridSize) * gridSize,
            y: Math.round(node.position.y / gridSize) * gridSize,
            width: original.width,
            height: original.height,
            pinned: true,
          });
        }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

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
  toggleRouteSegmentLock,
  toggleRouteVertexLock,
  projectDocument,
} from "@spec2gds/circuit-core";
import { layoutCircuitDocument } from "@spec2gds/circuit-layout";

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

export function terminalDisplayLabel(terminal: Pick<CircuitTerminal, "label" | "width">): string {
  return typeof terminal.width === "string" ? `${terminal.label} ${terminal.width}` : terminal.label;
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
  elementStatus?: {
    nodes?: Record<string, "added" | "removed" | "changed">;
    nets?: Record<string, "added" | "removed" | "changed">;
  };
  selectedElement?: { kind: "node" | "net"; id: string } | null;
  viewport?: Viewport;
  onViewportChange?: (viewport: Viewport) => void;
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
        const displayLabel = terminalDisplayLabel(terminal);
        return <Fragment key={terminal.id}>
          <span className={`cd-node__port-label cd-node__port-label--${side.toLowerCase()}`} style={style}>{displayLabel}</span>
          <Handle id={terminalHandleId(terminal.id, "source")} type="source" position={positions[side]} style={style} title={displayLabel} />
          <Handle id={terminalHandleId(terminal.id, "target")} type="target" position={positions[side]} style={style} title={displayLabel} />
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

export function CircuitDesignerCanvas({ graph, layout, boundaryGeometry = {}, onSelect, editable = false, onNodeGeometryChange, onConnectTerminals, gridSize = 20, allowViewportNavigation = true, fitViewOnInit = true, mode = "select", onNetRouteChange, rendererRegistry, elementStatus, selectedElement, viewport, onViewportChange }: CircuitDesignerCanvasProps) {
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
      className: elementStatus?.nodes?.[node.id] ? `cd-element--${elementStatus.nodes[node.id]}` : undefined,
      selected: selectedElement?.kind === "node" && selectedElement.id === node.id,
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
      className: elementStatus?.nodes?.[terminal.id] ? `cd-element--${elementStatus.nodes[terminal.id]}` : undefined,
      selected: selectedElement?.kind === "node" && selectedElement.id === terminal.id,
    });
  }
  const edges = buildCircuitFlowEdges(graph, netRoutes, { routeEditable: policy.routeEditable, gridSize, onNetRouteChange });
  for (const edge of edges) {
    const status = elementStatus?.nets?.[edge.id];
    if (status) edge.className = `cd-element--${status}`;
    edge.selected = selectedElement?.kind === "net" && selectedElement.id === edge.id;
  }
  return (
    <div className="cd-canvas" data-testid="circuit-canvas">
      <ReactFlow<CircuitFlowNode, CircuitFlowEdge>
        nodes={nodes}
        edges={edges}
        nodeTypes={{ circuit: CircuitNodeView }}
        edgeTypes={{ circuit: CircuitEdgeView }}
        fitView={fitViewOnInit}
        defaultViewport={{ x: gridSize, y: gridSize, zoom: 1 }}
        {...(viewport ? { viewport } : {})}
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
        onMove={(_, nextViewport) => onViewportChange?.(nextViewport)}
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
  const [selection, setSelection] = useState<{ kind: "node" | "net"; id: string } | null>(null);
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
              selectedElement={selection}
              onSelect={setSelection}
              viewport={viewport}
              onViewportChange={setViewport}
              editable={false}
              mode="pan"
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
              selectedElement={selection}
              onSelect={setSelection}
              viewport={viewport}
              onViewportChange={setViewport}
              editable={false}
              mode="pan"
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

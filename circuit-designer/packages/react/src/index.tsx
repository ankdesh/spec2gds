import { Fragment, useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import type {
  CircuitGraphSnapshot,
  CircuitNode,
  CircuitTerminal,
  DiagramLayout,
  NetRoute,
  NodeGeometry,
  TerminalPlacement,
} from "@spec2gds/circuit-core";

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
}

type CircuitNodeData = {
  circuitNode: CircuitNode;
  terminals: CircuitTerminal[];
  placements: Record<string, TerminalPlacement>;
};

type CircuitFlowNode = Node<CircuitNodeData, "circuit">;
type CircuitEdgeData = { route: NetRoute; label: string; kind: string };
type CircuitFlowEdge = Edge<CircuitEdgeData, "circuit">;

const positions = { NORTH: Position.Top, EAST: Position.Right, SOUTH: Position.Bottom, WEST: Position.Left };

function CircuitNodeView({ data }: NodeProps<CircuitFlowNode>) {
  return (
    <div className="cd-node">
      <div className="cd-node__eyebrow">{data.circuitNode.component_vlnv ?? data.circuitNode.component_id}</div>
      <div className="cd-node__title">{data.circuitNode.display_name ?? data.circuitNode.label}</div>
      {data.terminals.map((terminal) => {
        const placement = data.placements[terminal.id];
        const side = placement?.side ?? "SOUTH";
        const offset = 62 + (placement?.order ?? 0) * 18;
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

export function buildCircuitFlowEdges(graph: CircuitGraphSnapshot, netRoutes: Record<string, NetRoute>): CircuitFlowEdge[] {
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
      data: { route, label: net.label, kind: net.kind },
      selectable: true,
    }];
  });
}

function CircuitEdgeView({ data, selected }: EdgeProps<CircuitFlowEdge>) {
  if (!data) return null;
  const vertices = new Map(data.route.vertices.map((vertex) => [vertex.id, vertex]));
  return (
    <g className={selected ? "cd-net cd-net--selected" : "cd-net"}>
      {data.route.segments.map((segment, index) => {
        const start = vertices.get(segment.from_vertex)!.point;
        const end = vertices.get(segment.to_vertex)!.point;
        return <path key={index} d={`M ${start.x} ${start.y} L ${end.x} ${end.y}`} className="cd-net__segment" />;
      })}
      {data.route.vertices.filter((vertex) => vertex.kind === "junction").map((vertex) => (
        <circle key={vertex.id} cx={vertex.point.x} cy={vertex.point.y} r="3.5" className="cd-net__junction" />
      ))}
    </g>
  );
}

export function CircuitDesignerCanvas({ graph, layout, boundaryGeometry = {}, onSelect, editable = false, onNodeGeometryChange, onConnectTerminals, gridSize = 20, allowViewportNavigation = true, fitViewOnInit = true }: CircuitDesignerCanvasProps) {
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
      data: { circuitNode: node, terminals: terminalsByNode.get(node.id) ?? [], placements: terminalPlacements },
      draggable: editable,
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
        circuitNode: { id: terminal.id, label: terminal.label, component_id: "boundary", terminal_ids: [terminal.id], configuration_values: {}, source_ref: terminal.source_ref },
        terminals: [terminal], placements: terminalPlacements,
      },
      draggable: false,
    });
  }
  const edges = buildCircuitFlowEdges(graph, netRoutes);
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
        nodesDraggable={editable}
        nodesConnectable={editable && Boolean(onConnectTerminals)}
        connectionMode={ConnectionMode.Loose}
        snapToGrid
        snapGrid={[gridSize, gridSize]}
        panOnDrag={allowViewportNavigation}
        zoomOnScroll={allowViewportNavigation}
        zoomOnPinch={allowViewportNavigation}
        zoomOnDoubleClick={allowViewportNavigation}
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

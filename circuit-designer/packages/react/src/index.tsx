import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
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
        const offset = 22 + (placement?.order ?? 0) * 15;
        const style = side === "EAST" || side === "WEST" ? { top: offset } : { left: offset };
        return <Handle key={terminal.id} id={terminal.id} type="source" position={positions[side]} style={style} title={terminal.label} />;
      })}
    </div>
  );
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

export function CircuitDesignerCanvas({ graph, layout, boundaryGeometry = {}, onSelect }: CircuitDesignerCanvasProps) {
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
  const nodes: CircuitFlowNode[] = graph.nodes.map((node) => {
    const geometry = nodeGeometry[node.id];
    return {
      id: node.id,
      type: "circuit",
      position: { x: geometry.x, y: geometry.y },
      style: { width: geometry.width, height: geometry.height },
      data: { circuitNode: node, terminals: terminalsByNode.get(node.id) ?? [], placements: terminalPlacements },
      draggable: false,
    };
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
  const edges: CircuitFlowEdge[] = graph.nets.map((net) => ({
    id: net.id,
    type: "circuit",
    source: graph.terminals.find((terminal) => terminal.id === net.endpoints[0].terminal_id)?.node_id ?? `boundary:${net.endpoints[0].terminal_id}`,
    target: graph.terminals.find((terminal) => terminal.id === net.endpoints[1].terminal_id)?.node_id ?? `boundary:${net.endpoints[1].terminal_id}`,
    data: { route: netRoutes[net.id], label: net.label, kind: net.kind },
    selectable: true,
  }));
  return (
    <div className="cd-canvas" data-testid="circuit-canvas">
      <ReactFlow<CircuitFlowNode, CircuitFlowEdge>
        nodes={nodes}
        edges={edges}
        nodeTypes={{ circuit: CircuitNodeView }}
        edgeTypes={{ circuit: CircuitEdgeView }}
        fitView
        minZoom={0.08}
        maxZoom={2.5}
        nodesDraggable={false}
        nodesConnectable={false}
        onPaneClick={() => onSelect?.(null)}
        onNodeClick={(_, node) => onSelect?.({ kind: "node", id: node.id.replace(/^boundary:/, "") })}
        onEdgeClick={(_, edge) => onSelect?.({ kind: "net", id: edge.id })}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

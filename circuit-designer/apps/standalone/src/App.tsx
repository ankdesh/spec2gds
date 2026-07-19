import { useEffect, useMemo, useState } from "react";
import { LocalCircuitDesignerApi } from "@spec2gds/circuit-client-local";
import type {
  CircuitGraphSnapshot,
  CircuitHistoryStatus,
  CommandBatch,
  DesignerCommand,
  EditLease,
  NodeGeometry,
} from "@spec2gds/circuit-core";
import { layoutCircuitGraphInWorker } from "@spec2gds/circuit-layout-elk/browser";
import { CircuitDesignerCanvas } from "@spec2gds/circuit-react";
import { standaloneExamples, type StandaloneExampleId } from "./examples";
import { graphLayoutKey, matchingLayout, type KeyedLayoutResult } from "./layout-state";

type Selection = { kind: "node" | "net"; id: string } | null;

export function App() {
  const [exampleId, setExampleId] = useState<StandaloneExampleId>("subsystem");
  const api = useMemo(() => new LocalCircuitDesignerApi(standaloneExamples[exampleId].build()), [exampleId]);
  const [graph, setGraph] = useState<CircuitGraphSnapshot>();
  const [lease, setLease] = useState<EditLease>();
  const [history, setHistory] = useState<CircuitHistoryStatus>({ can_undo: false, can_redo: false });
  const [keyedLayout, setKeyedLayout] = useState<KeyedLayoutResult>();
  const [selection, setSelection] = useState<Selection>(null);
  const [message, setMessage] = useState("Ready — all changes stay in this browser tab.");
  const [newName, setNewName] = useState("");
  const [netName, setNetName] = useState("");
  const [endpointA, setEndpointA] = useState("");
  const [endpointB, setEndpointB] = useState("");
  const [selectedLabel, setSelectedLabel] = useState("");
  const [portName, setPortName] = useState("");
  const [portDirection, setPortDirection] = useState<"in" | "out" | "inout">("in");

  useEffect(() => {
    let active = true;
    Promise.all([api.getGraph(standaloneExamples[exampleId].build().design.id), api.acquireLease("standalone-ui", "human")])
      .then(([nextGraph, nextLease]) => { if (active) { setGraph(nextGraph); setLease(nextLease); setHistory({ can_undo: false, can_redo: false }); setSelection(null); } });
    return () => { active = false; };
  }, [api, exampleId]);

  useEffect(() => {
    if (!graph) { setKeyedLayout(undefined); return; }
    let active = true;
    const graphKey = graphLayoutKey(graph);
    layoutCircuitGraphInWorker(graph).then((result) => { if (active) setKeyedLayout({ graphKey, result }); }).catch((reason: unknown) => {
      if (active) setMessage(`Layout failed: ${String(reason)}`);
    });
    return () => { active = false; };
  }, [graph]);

  const layoutResult = matchingLayout(graph, keyedLayout);

  const selected = selection?.kind === "node"
    ? graph?.nodes.find((item) => item.id === selection.id)
    : graph?.nets.find((item) => item.id === selection?.id);

  useEffect(() => { setSelectedLabel(selected?.label ?? ""); }, [selected]);

  async function apply(commands: DesignerCommand[], success: string) {
    if (!graph || !lease || commands.length === 0) return;
    const batch: CommandBatch = {
      batch_id: `local_${crypto.randomUUID()}`,
      expected_source_revision_hash: graph.source_revision_hash,
      commands: commands as CommandBatch["commands"],
    };
    const result = await api.apply(batch, lease.lease_id);
    if (!result.candidate) { setMessage(result.diagnostics.map((item) => item.message).join(" · ")); return; }
    setGraph(result.candidate); setHistory(await api.getHistory()); setMessage(success);
  }

  async function travel(direction: "undo" | "redo") {
    if (!graph || !lease) return;
    try {
      const result = direction === "undo" ? await api.undo(lease.lease_id, graph.design.id) : await api.redo(lease.lease_id, graph.design.id);
      setGraph(result.graph); setHistory(result); setSelection(null); setMessage(direction === "undo" ? "Undid the last local change." : "Redid the local change.");
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); }
  }

  function moveNode(nodeId: string, geometry: NodeGeometry) {
    if (!graph) return;
    void apply([{ type: "set_node_geometry", command_id: `move_${crypto.randomUUID()}`, design_id: graph.design.id, node_id: nodeId, geometry }], "Node position saved locally.");
  }

  function pinCurrentGeometry(): DesignerCommand[] {
    if (!graph || !layoutResult) return [];
    return graph.nodes.flatMap((node) => {
      const geometry = layoutResult.layout.node_geometry?.[node.id];
      return geometry ? [{ type: "set_node_geometry" as const, command_id: `pin_${crypto.randomUUID()}`, design_id: graph.design.id, node_id: node.id, geometry: { ...geometry, pinned: true } }] : [];
    });
  }

  function addBlock() {
    if (!graph || !layoutResult || !newName.trim()) return;
    const nodeId = `local-node:${crypto.randomUUID()}`;
    const componentId = `local-component:${crypto.randomUUID()}`;
    const geometries = Object.values(layoutResult.layout.node_geometry ?? {});
    const x = Math.ceil(((geometries.length ? Math.max(...geometries.map((item) => item.x + item.width)) : 20) + 60) / 20) * 20;
    const y = Math.ceil((geometries.length ? Math.min(...geometries.map((item) => item.y)) : 20) / 20) * 20;
    void apply([
      ...pinCurrentGeometry(),
      { type: "add_instance", command_id: crypto.randomUUID(), design_id: graph.design.id, node_id: nodeId, name: newName.trim(), component_id: componentId },
      { type: "set_node_geometry", command_id: crypto.randomUUID(), design_id: graph.design.id, node_id: nodeId, geometry: { x, y, width: 180, height: 84, pinned: true } },
    ], `Created component “${newName.trim()}”.`);
    setNewName("");
  }

  function addPort(nodeId: string) {
    if (!graph || !portName.trim()) return;
    const terminalId = `${nodeId}:port:${crypto.randomUUID()}`;
    const side = portDirection === "out" ? "EAST" : portDirection === "in" ? "WEST" : "SOUTH";
    const order = graph.terminals.filter((terminal) => terminal.node_id === nodeId && (portDirection === "out" ? terminal.direction === "out" : portDirection === "in" ? terminal.direction === "in" : terminal.direction === "inout")).length;
    void apply([
      ...pinCurrentGeometry(),
      { type: "add_terminal", command_id: crypto.randomUUID(), design_id: graph.design.id, node_id: nodeId, terminal_id: terminalId, name: portName.trim(), kind: "port", direction: portDirection },
      { type: "set_terminal_placement", command_id: crypto.randomUUID(), design_id: graph.design.id, terminal_id: terminalId, placement: { side, order } },
    ], `Created ${portDirection} port “${portName.trim()}”.`);
    setPortName("");
  }

  function createInterconnect(firstTerminalId: string, secondTerminalId: string, requestedName?: string) {
    if (!graph) return;
    const first = graph.terminals.find((item) => item.id === firstTerminalId);
    const second = graph.terminals.find((item) => item.id === secondTerminalId);
    if (!first || !second) { setMessage("One of the selected ports no longer exists."); return; }
    const interfaceNet = first.kind.includes("interface") && second.kind.includes("interface");
    const portNet = first.kind.includes("port") && second.kind.includes("port");
    if (!interfaceNet && !portNet) { setMessage("Connect two interface terminals or two physical ports."); return; }
    const kind = interfaceNet ? "interface" : "ad_hoc";
    const name = requestedName?.trim() || `net_${graph.nets.length + 1}`;
    void apply([
      ...pinCurrentGeometry(),
      { type: "create_net", command_id: crypto.randomUUID(), design_id: graph.design.id, net_id: `local-net:${crypto.randomUUID()}`, name, kind, terminal_ids: [firstTerminalId, secondTerminalId] },
    ], `Created interconnect “${name}”.`);
  }

  function createNet() {
    if (!graph || !netName || !endpointA || !endpointB) return;
    createInterconnect(endpointA, endpointB, netName);
    setNetName(""); setEndpointA(""); setEndpointB("");
  }

  async function resetExample() {
    const reset = await api.reset(); setGraph(reset); setHistory({ can_undo: false, can_redo: false }); setSelection(null); setMessage("Example restored to its original state.");
  }

  function downloadGraph() {
    const blob = new Blob([JSON.stringify(api.exportGraph(), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `${graph?.design.id ?? "circuit"}.circuit.json`; anchor.click(); URL.revokeObjectURL(url);
    setMessage("Exported the renderer-neutral circuit document.");
  }

  const terminals = graph?.terminals.filter((terminal) => terminal.node_id) ?? [];

  return <main className="standalone-shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark">CD</span><div><span>Standalone lab</span><h1>Circuit Designer</h1></div></div>
      <label className="example-picker">Example<select aria-label="Example" value={exampleId} onChange={(event) => setExampleId(event.target.value as StandaloneExampleId)}>
        {Object.entries(standaloneExamples).map(([id, example]) => <option key={id} value={id}>{example.title}</option>)}
      </select></label>
      <div className="toolbar"><button disabled={!history.can_undo} onClick={() => void travel("undo")}>Undo</button><button disabled={!history.can_redo} onClick={() => void travel("redo")}>Redo</button><button onClick={() => void resetExample()}>Reset</button><button onClick={downloadGraph}>Export JSON</button></div>
    </header>
    <div className="notice"><span className="local-dot" />Independent mode · no FastAPI, Python, SpecIR, or IP-XACT session<span>{message}</span></div>
    <section className="workspace">
      <aside className="library">
        <p className="eyebrow">Example circuit</p><h2>{standaloneExamples[exampleId].title}</h2><p>{standaloneExamples[exampleId].summary}</p>
        <div className="metrics"><div><b>{graph?.nodes.length ?? 0}</b><span>Blocks</span></div><div><b>{graph?.nets.length ?? 0}</b><span>Nets</span></div></div>
        {graph && <><div className="section"><h3>Layout</h3><div className="segmented"><button className={graph.layout?.direction !== "DOWN" ? "active" : ""} onClick={() => void apply([{ type: "set_layout_direction", command_id: crypto.randomUUID(), design_id: graph.design.id, direction: "RIGHT" }], "Layout direction changed.")}>Horizontal</button><button className={graph.layout?.direction === "DOWN" ? "active" : ""} onClick={() => void apply([{ type: "set_layout_direction", command_id: crypto.randomUUID(), design_id: graph.design.id, direction: "DOWN" }], "Layout direction changed.")}>Vertical</button></div></div>
          <div className="section"><h3>Draw component</h3><label>Name<input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="alu_0" onKeyDown={(event) => { if (event.key === "Enter") addBlock(); }} /></label><button className="primary" disabled={!newName.trim()} onClick={addBlock}>Create component</button></div>
          <div className="section"><h3>Connect terminals</h3><label>Net name<input value={netName} onChange={(event) => setNetName(event.target.value)} placeholder="data_path" /></label><label>Endpoint A<select value={endpointA} onChange={(event) => setEndpointA(event.target.value)}><option value="">Choose…</option>{terminals.map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.node_id} · {terminal.label}</option>)}</select></label><label>Endpoint B<select value={endpointB} onChange={(event) => setEndpointB(event.target.value)}><option value="">Choose…</option>{terminals.filter((terminal) => terminal.id !== endpointA).map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.node_id} · {terminal.label}</option>)}</select></label><button className="primary" disabled={!netName || !endpointA || !endpointB} onClick={createNet}>Create net</button></div></>}
      </aside>
      <div className="stage">
        {!layoutResult && <div className="loading">Computing orthogonal ELK layout…</div>}
        {graph && layoutResult && <CircuitDesignerCanvas graph={graph} layout={layoutResult.layout} boundaryGeometry={layoutResult.boundary_geometry} editable onSelect={setSelection} onNodeGeometryChange={moveNode} onConnectTerminals={(source, target) => createInterconnect(source, target)} gridSize={20} allowViewportNavigation={false} fitViewOnInit={false} />}
        {layoutResult && <div className="layout-time" data-testid="layout-time">ELK · {layoutResult.elapsed_ms} ms</div>}
      </div>
      <aside className="inspector" data-testid="inspector"><p className="eyebrow">Inspector</p>
        {!selection && <div className="empty-inspector"><span>⌁</span><p>Select a block or net. Drag blocks to pin their position.</p></div>}
        {selection && selected && graph && <><span className="kind">{selection.kind}</span><h2>{selected.label}</h2><code>{selection.id}</code><label>Label<input value={selectedLabel} onChange={(event) => setSelectedLabel(event.target.value)} /></label>{selection.kind === "net" ? <><button disabled={!selectedLabel || selectedLabel === selected.label} onClick={() => void apply([{ type: "rename_net", command_id: crypto.randomUUID(), design_id: graph.design.id, net_id: selection.id, name: selectedLabel }], "Net renamed.")}>Save label</button><button className="danger" onClick={() => void apply([{ type: "delete_net", command_id: crypto.randomUUID(), design_id: graph.design.id, net_id: selection.id }], "Net deleted.")}>Delete net</button></> : <><button onClick={() => void apply([{ type: "update_instance", command_id: crypto.randomUUID(), design_id: graph.design.id, node_id: selection.id, name: selectedLabel }], "Block label updated.")}>Save label</button><button onClick={() => void apply([...pinCurrentGeometry(), { type: "duplicate_instances", command_id: crypto.randomUUID(), design_id: graph.design.id, node_ids: [selection.id], offset: { x: 40, y: 40 } }], "Block duplicated.")}>Duplicate block</button><button className="danger" onClick={() => void apply([{ type: "delete_instance", command_id: crypto.randomUUID(), design_id: graph.design.id, node_id: selection.id, cascade: true }], "Block and connected nets deleted.")}>Delete block</button><div className="port-editor"><h3>Ports</h3>{graph.terminals.filter((terminal) => terminal.node_id === selection.id).map((terminal) => <div className="port-row" key={terminal.id}><span>{terminal.label}<small>{terminal.direction ?? terminal.kind}</small></span><button className="danger" title={`Delete ${terminal.label}`} onClick={() => void apply([{ type: "delete_terminal", command_id: crypto.randomUUID(), design_id: graph.design.id, terminal_id: terminal.id, cascade: true }], `Deleted port “${terminal.label}”.`)}>×</button></div>)}<label>Name<input value={portName} onChange={(event) => setPortName(event.target.value)} placeholder="data_in" /></label><label>Direction<select value={portDirection} onChange={(event) => setPortDirection(event.target.value as typeof portDirection)}><option value="in">Input · left</option><option value="out">Output · right</option><option value="inout">Inout · bottom</option></select></label><button disabled={!portName.trim()} onClick={() => addPort(selection.id)}>Create port</button><p className="draw-hint">Drag from one port handle to another to draw an interconnect.</p></div></>}
          <details><summary>Contract data</summary><pre>{JSON.stringify(selected, null, 2)}</pre></details></>}
      </aside>
    </section>
  </main>;
}

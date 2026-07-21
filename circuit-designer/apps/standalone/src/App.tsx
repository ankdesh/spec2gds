import { useEffect, useMemo, useRef, useState } from "react";
import { LocalCircuitDesignerApi } from "@spec2gds/circuit-client-local";
import { resetRouteBranch, setAllRouteLocks } from "@spec2gds/circuit-core";
import type {
  CircuitGraphSnapshot,
  CircuitHistoryStatus,
  CommandBatch,
  DesignerCommand,
  EditLease,
  NodeGeometry,
  NetRoute,
  TerminalPlacement,
} from "@spec2gds/circuit-core";
import { autoSizeNodeGeometry, layoutCircuitGraph, reanchorRoutesForNode, routeCircuitNets } from "@spec2gds/circuit-layout";
import { CircuitDesignerCanvas, type CircuitCanvasMode } from "@spec2gds/circuit-react";
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
  const [mode, setMode] = useState<CircuitCanvasMode>("select");
  const priorMode = useRef<CircuitCanvasMode>("select");

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
    layoutCircuitGraph(graph).then((result) => { if (active) setKeyedLayout({ graphKey, result }); }).catch((reason: unknown) => {
      if (active) setMessage(`Layout failed: ${String(reason)}`);
    });
    return () => { active = false; };
  }, [graph]);

  const layoutResult = matchingLayout(graph, keyedLayout);

  const selected = selection?.kind === "node"
    ? graph?.nodes.find((item) => item.id === selection.id)
    : graph?.nets.find((item) => item.id === selection?.id);
  const selectedNet = selection?.kind === "net" ? graph?.nets.find((item) => item.id === selection.id) : undefined;

  useEffect(() => { setSelectedLabel(selected?.label ?? ""); }, [selected]);

  useEffect(() => {
    const typing = (target: EventTarget | null) => target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement;
    const down = (event: KeyboardEvent) => {
      if (typing(event.target)) return;
      if (event.key === "Escape") { setMode("select"); return; }
      if (event.code === "Space" && !event.repeat) { event.preventDefault(); priorMode.current = mode; setMode("pan"); }
    };
    const up = (event: KeyboardEvent) => {
      if (event.code === "Space" && !typing(event.target)) { event.preventDefault(); setMode(priorMode.current); }
    };
    window.addEventListener("keydown", down); window.addEventListener("keyup", up);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); };
  }, [mode]);

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

  function routeCommands(routes: Record<string, NetRoute>): DesignerCommand[] {
    if (!graph) return [];
    return Object.entries(routes).map(([netId, route]) => ({ type: "set_net_route", command_id: `route_${crypto.randomUUID()}`, design_id: graph.design.id, net_id: netId, route }));
  }

  function moveNode(nodeId: string, geometry: NodeGeometry) {
    if (!graph || !layoutResult) return;
    const routes = reanchorRoutesForNode(graph, layoutResult.layout, layoutResult.boundary_geometry, nodeId, geometry);
    void apply([
      { type: "set_node_geometry", command_id: `move_${crypto.randomUUID()}`, design_id: graph.design.id, node_id: nodeId, geometry },
      ...routeCommands(routes),
    ], `Moved block and rerouted ${Object.keys(routes).length} unlocked connected net${Object.keys(routes).length === 1 ? "" : "s"}.`);
  }

  function setNodePinned(nodeId: string, pinned: boolean) {
    if (!graph || !layoutResult) return;
    const current = layoutResult.layout.node_geometry?.[nodeId];
    if (!current) return;
    const geometry = { ...current, pinned };
    const routes = reanchorRoutesForNode(graph, layoutResult.layout, layoutResult.boundary_geometry, nodeId, geometry);
    void apply([
      { type: "set_node_geometry", command_id: `pin_${crypto.randomUUID()}`, design_id: graph.design.id, node_id: nodeId, geometry },
      ...routeCommands(routes),
    ], pinned ? "Block pinned in place." : "Block unpinned for automatic arrangement.");
  }

  function saveRoute(netId: string, route: NetRoute, message = "Manual route saved locally.") {
    if (!graph) return;
    void apply([{ type: "set_net_route", command_id: `route_${crypto.randomUUID()}`, design_id: graph.design.id, net_id: netId, route }], message);
  }

  function optimizeRoutes(netIds: string[], preserveConstraints = true, message = "Routes optimized without moving blocks.") {
    if (!graph || !layoutResult || !netIds.length) return;
    const routes = routeCircuitNets(graph, layoutResult.layout, layoutResult.boundary_geometry, netIds, preserveConstraints);
    void apply(routeCommands(routes), message);
  }

  async function autoLayout() {
    if (!graph) return;
    const source = structuredClone(graph);
    source.layout = {
      ...source.layout,
      node_geometry: Object.fromEntries(Object.entries(source.layout?.node_geometry ?? {}).filter(([, geometry]) => geometry.pinned)),
      net_routes: {},
    };
    const result = await layoutCircuitGraph(source, { preserveNodeGeometry: "pinned" });
    const commands: DesignerCommand[] = [
      ...graph.nodes.flatMap((node) => {
        const geometry = result.layout.node_geometry?.[node.id];
        return geometry ? [{ type: "set_node_geometry" as const, command_id: `layout_${crypto.randomUUID()}`, design_id: graph.design.id, node_id: node.id, geometry }] : [];
      }),
      ...routeCommands(result.layout.net_routes ?? {}),
    ];
    await apply(commands, "Automatic layout completed; pinned blocks were preserved.");
  }

  function pinCurrentGeometry(): DesignerCommand[] {
    if (!graph || !layoutResult) return [];
    const geometryCommands = graph.nodes.flatMap((node) => {
      const geometry = layoutResult.layout.node_geometry?.[node.id];
      return geometry ? [{ type: "set_node_geometry" as const, command_id: `pin_${crypto.randomUUID()}`, design_id: graph.design.id, node_id: node.id, geometry: { ...geometry, pinned: true } }] : [];
    });
    return [...geometryCommands, ...routeCommands(layoutResult.layout.net_routes ?? {})];
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

  function updatePortPlacement(terminalId: string, side: TerminalPlacement["side"], requestedOrder: number) {
    if (!graph || !layoutResult) return;
    const terminal = graph.terminals.find((item) => item.id === terminalId);
    if (!terminal?.node_id) return;
    const placements = { ...(layoutResult.layout.terminal_placements ?? {}) };
    const originalSide = placements[terminalId]?.side;
    const siblings = graph.terminals
      .filter((item) => item.node_id === terminal.node_id && item.id !== terminalId && placements[item.id]?.side === side)
      .sort((a, b) => (placements[a.id]?.order ?? 0) - (placements[b.id]?.order ?? 0));
    const ordered = [...siblings];
    ordered.splice(Math.max(0, Math.min(requestedOrder, ordered.length)), 0, terminal);
    const placementCommands: DesignerCommand[] = ordered.map((item, order) => {
      const placement = { side, order, locked: true } satisfies TerminalPlacement;
      placements[item.id] = placement;
      return { type: "set_terminal_placement", command_id: `port_${crypto.randomUUID()}`, design_id: graph.design.id, terminal_id: item.id, placement };
    });
    if (originalSide && originalSide !== side) {
      graph.terminals
        .filter((item) => item.node_id === terminal.node_id && item.id !== terminalId && placements[item.id]?.side === originalSide)
        .sort((a, b) => (placements[a.id]?.order ?? 0) - (placements[b.id]?.order ?? 0))
        .forEach((item, order) => {
          const placement = { side: originalSide, order, locked: true } satisfies TerminalPlacement;
          placements[item.id] = placement;
          placementCommands.push({ type: "set_terminal_placement", command_id: `port_${crypto.randomUUID()}`, design_id: graph.design.id, terminal_id: item.id, placement });
        });
    }
    const draftLayout = { ...layoutResult.layout, terminal_placements: placements };
    const geometry = autoSizeNodeGeometry(graph, draftLayout, terminal.node_id);
    if (geometry) draftLayout.node_geometry = { ...(draftLayout.node_geometry ?? {}), [terminal.node_id]: geometry };
    const changedTerminalIds = new Set(placementCommands.flatMap((command) => command.type === "set_terminal_placement" ? [command.terminal_id] : []));
    const ownerTerminalIds = new Set(graph.terminals.filter((item) => item.node_id === terminal.node_id).map((item) => item.id));
    const affectedNetIds = graph.nets.filter((net) => net.endpoints.some((endpoint) => changedTerminalIds.has(endpoint.terminal_id) || ownerTerminalIds.has(endpoint.terminal_id))).map((net) => net.id);
    const routes = routeCircuitNets(graph, draftLayout, layoutResult.boundary_geometry, affectedNetIds, true);
    void apply([
      ...placementCommands,
      ...(geometry ? [{ type: "set_node_geometry" as const, command_id: `size_${crypto.randomUUID()}`, design_id: graph.design.id, node_id: terminal.node_id, geometry }] : []),
      ...routeCommands(routes),
    ], `Moved port “${terminal.label}” to ${side.toLowerCase()} side.`);
  }

  function useAutomaticPortPlacement(terminalId: string) {
    if (!graph) return;
    void apply([{ type: "set_terminal_placement", command_id: `port_auto_${crypto.randomUUID()}`, design_id: graph.design.id, terminal_id: terminalId, placement: null }], "Port returned to automatic placement.");
  }

  function resetSelectedBranch(netId: string, terminalId: string) {
    if (!graph || !layoutResult) return;
    const current = layoutResult.layout.net_routes?.[netId];
    const automatic = routeCircuitNets(graph, layoutResult.layout, layoutResult.boundary_geometry, [netId], false)[netId];
    if (current && automatic) saveRoute(netId, resetRouteBranch(current, automatic, terminalId), "Selected endpoint branch reset.");
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
        {graph && <><div className="section"><h3>Layout</h3><div className="segmented"><button className={graph.layout?.direction !== "DOWN" ? "active" : ""} onClick={() => void apply([{ type: "set_layout_direction", command_id: crypto.randomUUID(), design_id: graph.design.id, direction: "RIGHT" }], "Layout direction changed.")}>Horizontal</button><button className={graph.layout?.direction === "DOWN" ? "active" : ""} onClick={() => void apply([{ type: "set_layout_direction", command_id: crypto.randomUUID(), design_id: graph.design.id, direction: "DOWN" }], "Layout direction changed.")}>Vertical</button></div><div className="layout-actions"><button onClick={() => void autoLayout()}>Arrange unpinned blocks</button><button disabled={!layoutResult || !graph.nets.length} onClick={() => optimizeRoutes(graph.nets.map((net) => net.id))}>Reroute unlocked nets</button></div><p className="draw-hint">Fix block and port positions first, then reroute. Blocks and locked routes are treated as obstacles.</p></div>
          <div className="section"><h3>Draw component</h3><label>Name<input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="alu_0" onKeyDown={(event) => { if (event.key === "Enter") addBlock(); }} /></label><button className="primary" disabled={!newName.trim()} onClick={addBlock}>Create component</button></div>
          <div className="section"><h3>Connect terminals</h3><label>Net name<input value={netName} onChange={(event) => setNetName(event.target.value)} placeholder="data_path" /></label><label>Endpoint A<select value={endpointA} onChange={(event) => setEndpointA(event.target.value)}><option value="">Choose…</option>{terminals.map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.node_id} · {terminal.label}</option>)}</select></label><label>Endpoint B<select value={endpointB} onChange={(event) => setEndpointB(event.target.value)}><option value="">Choose…</option>{terminals.filter((terminal) => terminal.id !== endpointA).map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.node_id} · {terminal.label}</option>)}</select></label><button className="primary" disabled={!netName || !endpointA || !endpointB} onClick={createNet}>Create net</button></div></>}
      </aside>
      <div className="stage">
        <div className="mode-toolbar" aria-label="Canvas mode">
          {(["select", "connect", "route", "pan"] as CircuitCanvasMode[]).map((item) => <button key={item} className={mode === item ? "active" : ""} aria-pressed={mode === item} onClick={() => setMode(item)}>{item[0].toUpperCase() + item.slice(1)}</button>)}
        </div>
        {!layoutResult && <div className="loading">Computing orthogonal layout…</div>}
        {graph && layoutResult && <CircuitDesignerCanvas graph={graph} layout={layoutResult.layout} boundaryGeometry={layoutResult.boundary_geometry} editable mode={mode} onSelect={setSelection} onNodeGeometryChange={moveNode} onConnectTerminals={(source, target) => createInterconnect(source, target)} onNetRouteChange={saveRoute} gridSize={20} allowViewportNavigation fitViewOnInit={false} />}
        {layoutResult && <div className="layout-time" data-testid="layout-time">Grid router · {layoutResult.elapsed_ms} ms</div>}
      </div>
      <aside className="inspector" data-testid="inspector"><p className="eyebrow">Inspector</p>
        {!selection && <div className="empty-inspector"><span>⌁</span><p>Select a block or net. Drag blocks to pin their position.</p></div>}
        {selection && selected && graph && <><span className="kind">{selection.kind}</span><h2>{selected.label}</h2><code>{selection.id}</code><label>Label<input value={selectedLabel} onChange={(event) => setSelectedLabel(event.target.value)} /></label>{selection.kind === "net" ? <>
          <button disabled={!selectedLabel || selectedLabel === selected.label} onClick={() => void apply([{ type: "rename_net", command_id: crypto.randomUUID(), design_id: graph.design.id, net_id: selection.id, name: selectedLabel }], "Net renamed.")}>Save label</button>
          <div className="route-editor"><h3>Route</h3><button onClick={() => optimizeRoutes([selection.id], true, "Selected route optimized; locked geometry was preserved.")}>Optimize route</button><button onClick={() => optimizeRoutes([selection.id], false, "Selected route reset to its automatic geometry.")}>Reset net</button>{layoutResult?.layout.net_routes?.[selection.id] && <><button onClick={() => saveRoute(selection.id, setAllRouteLocks(layoutResult.layout.net_routes![selection.id], true), "All route segments and junctions locked.")}>Lock all</button><button onClick={() => saveRoute(selection.id, setAllRouteLocks(layoutResult.layout.net_routes![selection.id], false), "All route constraints removed.")}>Unlock all</button></>}<p className="draw-hint">In Route mode, drag segments or junctions. Double-click a segment to add a bend; double-click an unlocked bend to remove it. Shift-click toggles a lock.</p>{selectedNet?.endpoints.map((endpoint) => { const terminal = graph.terminals.find((item) => item.id === endpoint.terminal_id); return <button className="branch-button" key={endpoint.terminal_id} onClick={() => resetSelectedBranch(selection.id, endpoint.terminal_id)}>Reset branch · {terminal?.label ?? endpoint.terminal_id}</button>; })}</div>
          <button className="danger" onClick={() => void apply([{ type: "delete_net", command_id: crypto.randomUUID(), design_id: graph.design.id, net_id: selection.id }], "Net deleted.")}>Delete net</button>
        </> : <>
          <button onClick={() => void apply([{ type: "update_instance", command_id: crypto.randomUUID(), design_id: graph.design.id, node_id: selection.id, name: selectedLabel }], "Block label updated.")}>Save label</button>
          <button onClick={() => void apply([...pinCurrentGeometry(), { type: "duplicate_instances", command_id: crypto.randomUUID(), design_id: graph.design.id, node_ids: [selection.id], offset: { x: 40, y: 40 } }], "Block duplicated.")}>Duplicate block</button>
          <button disabled={!graph.nets.some((net) => net.endpoints.some((endpoint) => graph.terminals.find((terminal) => terminal.id === endpoint.terminal_id)?.node_id === selection.id))} onClick={() => optimizeRoutes(graph.nets.filter((net) => net.endpoints.some((endpoint) => graph.terminals.find((terminal) => terminal.id === endpoint.terminal_id)?.node_id === selection.id)).map((net) => net.id), true, "Connected routes optimized without moving blocks.")}>Optimize connected routes</button>
          {layoutResult?.layout.node_geometry?.[selection.id] && <button onClick={() => setNodePinned(selection.id, !layoutResult.layout.node_geometry![selection.id].pinned)}>{layoutResult.layout.node_geometry[selection.id].pinned ? "Unpin block" : "Pin block"}</button>}
          <button className="danger" onClick={() => void apply([{ type: "delete_instance", command_id: crypto.randomUUID(), design_id: graph.design.id, node_id: selection.id, cascade: true }], "Block and connected nets deleted.")}>Delete block</button>
          <div className="port-editor"><h3>Ports</h3>{graph.terminals.filter((terminal) => terminal.node_id === selection.id).map((terminal) => { const placement = layoutResult?.layout.terminal_placements?.[terminal.id]; return <div className="port-card" key={terminal.id}><div className="port-row"><span>{terminal.label}<small>{terminal.direction ?? terminal.kind} · {placement?.side.toLowerCase()} {placement?.order}</small></span><button className="danger" title={`Delete ${terminal.label}`} onClick={() => void apply([{ type: "delete_terminal", command_id: crypto.randomUUID(), design_id: graph.design.id, terminal_id: terminal.id, cascade: true }], `Deleted port “${terminal.label}”.`)}>×</button></div><select aria-label={`${terminal.label} side`} value={placement?.side ?? "SOUTH"} onChange={(event) => updatePortPlacement(terminal.id, event.target.value as TerminalPlacement["side"], placement?.order ?? 0)}><option value="WEST">Left · West</option><option value="EAST">Right · East</option><option value="NORTH">Top · North</option><option value="SOUTH">Bottom · South</option></select><div className="port-actions"><button disabled={(placement?.order ?? 0) === 0} onClick={() => updatePortPlacement(terminal.id, placement?.side ?? "SOUTH", Math.max(0, (placement?.order ?? 0) - 1))}>Move up</button><button onClick={() => updatePortPlacement(terminal.id, placement?.side ?? "SOUTH", (placement?.order ?? 0) + 1)}>Move down</button><button className={placement?.locked ? "active" : ""} onClick={() => placement?.locked ? useAutomaticPortPlacement(terminal.id) : updatePortPlacement(terminal.id, placement?.side ?? "SOUTH", placement?.order ?? 0)}>{placement?.locked ? "Unlock" : "Lock"}</button></div></div>; })}<label>Name<input value={portName} onChange={(event) => setPortName(event.target.value)} placeholder="data_in" /></label><label>Direction<select value={portDirection} onChange={(event) => setPortDirection(event.target.value as typeof portDirection)}><option value="in">Input · left</option><option value="out">Output · right</option><option value="inout">Inout · bottom</option></select></label><button disabled={!portName.trim()} onClick={() => addPort(selection.id)}>Create port</button><p className="draw-hint">Switch to Connect mode, then drag between port handles.</p></div>
        </>}
          <details><summary>Contract data</summary><pre>{JSON.stringify(selected, null, 2)}</pre></details></>}
      </aside>
    </section>
  </main>;
}

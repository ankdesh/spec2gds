import { useEffect, useMemo, useState } from "react";
import {
  fixtures,
  type AgentProposal,
  type CircuitDesignCatalog,
  type CircuitGraphSnapshot,
  type CircuitHistoryStatus,
  type CommandBatch,
  type DesignerCommand,
  type EditLease,
  type NodeGeometry,
} from "@spec2gds/circuit-core";
import { HttpCircuitDesignerReadApi } from "@spec2gds/circuit-client-http";
import { layoutCircuitGraph, type LayoutResult } from "@spec2gds/circuit-layout";
import { CircuitDesignerCanvas } from "@spec2gds/circuit-react";

type FixtureName = keyof typeof fixtures;
type DataSource = "fixtures" | "server";
type Selection = { kind: "node" | "net"; id: string } | null;
const serverApi = new HttpCircuitDesignerReadApi({ baseUrl: import.meta.env.DEV ? "/api/circuit-designer" : "/circuit-designer" });

export function App() {
  const [dataSource, setDataSource] = useState<DataSource>("fixtures");
  const [fixtureName, setFixtureName] = useState<FixtureName>("mixed");
  const [catalog, setCatalog] = useState<CircuitDesignCatalog>();
  const [designId, setDesignId] = useState("");
  const [liveGraph, setLiveGraph] = useState<CircuitGraphSnapshot>();
  const [refresh, setRefresh] = useState(0);
  const [lease, setLease] = useState<EditLease>();
  const [history, setHistory] = useState<CircuitHistoryStatus>({ can_undo: false, can_redo: false });
  const [proposals, setProposals] = useState<AgentProposal[]>([]);
  const [newInstanceName, setNewInstanceName] = useState("");
  const [newComponentId, setNewComponentId] = useState("");
  const [selectedName, setSelectedName] = useState("");
  const [replacementComponentId, setReplacementComponentId] = useState("");
  const [newNetName, setNewNetName] = useState("");
  const [firstTerminalId, setFirstTerminalId] = useState("");
  const [secondTerminalId, setSecondTerminalId] = useState("");
  const [layoutResult, setLayoutResult] = useState<LayoutResult>();
  const [selection, setSelection] = useState<Selection>(null);
  const [loadError, setLoadError] = useState<string>();
  const [layoutError, setLayoutError] = useState<string>();
  const fixtureGraph = useMemo(() => fixtures[fixtureName](), [fixtureName]);
  const graph = dataSource === "fixtures" ? fixtureGraph : liveGraph;
  const ownsLease = lease?.owner_id === "browser-ui" && lease.owner_kind === "human";

  useEffect(() => {
    if (dataSource !== "server") return;
    const controller = new AbortController();
    setCatalog(undefined); setLiveGraph(undefined); setLoadError(undefined);
    serverApi.getCatalog({ signal: controller.signal }).then((nextCatalog) => {
      setCatalog(nextCatalog);
      const preferred = nextCatalog.entry_design_ids?.[0] ?? nextCatalog.designs[0]?.id ?? "";
      setDesignId((current) => nextCatalog.designs.some((design) => design.id === current) ? current : preferred);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setLoadError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => controller.abort();
  }, [dataSource, refresh]);

  useEffect(() => {
    if (dataSource !== "server") { setLease(undefined); setProposals([]); return; }
    Promise.all([serverApi.getLease(), serverApi.getHistory(), serverApi.listProposals()]).then(([nextLease, nextHistory, nextProposals]) => {
      setLease(nextLease ?? undefined); setHistory(nextHistory); setProposals(nextProposals);
    }).catch(() => undefined);
  }, [dataSource, refresh]);

  useEffect(() => {
    if (dataSource !== "server" || !catalog) return;
    const timer = window.setInterval(() => {
      serverApi.getCatalog().then((latest) => {
        if (latest.source_revision_hash !== catalog.source_revision_hash) setRefresh((value) => value + 1);
      }).catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [dataSource, catalog]);

  useEffect(() => {
    if (!ownsLease || !lease) return;
    const timer = window.setInterval(() => {
      serverApi.acquireLease("browser-ui", "human").then(setLease).catch((reason: unknown) => {
        setLease(undefined); setLoadError(reason instanceof Error ? reason.message : String(reason));
      });
    }, 120000);
    return () => window.clearInterval(timer);
  }, [lease?.lease_id]);

  useEffect(() => {
    if (dataSource !== "server" || !designId) return;
    const controller = new AbortController();
    setLiveGraph(undefined); setLoadError(undefined); setSelection(null);
    serverApi.getGraph(designId, { signal: controller.signal }).then(setLiveGraph).catch((reason: unknown) => {
      if (!controller.signal.aborted) setLoadError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => controller.abort();
  }, [dataSource, designId, refresh]);

  useEffect(() => {
    if (!graph) { setLayoutResult(undefined); return; }
    let active = true;
    setLayoutResult(undefined); setSelection(null); setLayoutError(undefined);
    layoutCircuitGraph(graph).then((result) => active && setLayoutResult(result)).catch((reason: unknown) => active && setLayoutError(String(reason)));
    return () => { active = false; };
  }, [graph]);
  const selected = selection?.kind === "node" ? graph?.nodes.find((item) => item.id === selection.id) : graph?.nets.find((item) => item.id === selection?.id);
  useEffect(() => {
    setSelectedName(selected?.label ?? "");
    setReplacementComponentId(selection?.kind === "node" && "component_id" in (selected ?? {}) ? String((selected as { component_id: string }).component_id) : "");
  }, [selection, selected]);

  async function applyCommands(commands: DesignerCommand[]) {
    if (!graph || !lease || !ownsLease || !commands.length) return;
    setLoadError(undefined);
    const batch: CommandBatch = {
      batch_id: `ui_${crypto.randomUUID()}`,
      expected_source_revision_hash: graph.source_revision_hash,
      commands: commands as CommandBatch["commands"],
    };
    try {
      const result = await serverApi.apply(batch, lease.lease_id);
      if (!result.candidate) throw new Error(result.diagnostics.map((item) => item.message).join("\n") || "Command validation failed.");
      setLiveGraph(result.candidate);
      setHistory(await serverApi.getHistory());
    } catch (reason) {
      setLoadError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function acquireLease() {
    try { setLease(await serverApi.acquireLease("browser-ui", "human")); }
    catch (reason) { setLoadError(reason instanceof Error ? reason.message : String(reason)); }
  }

  async function releaseLease() {
    if (!lease) return;
    await serverApi.releaseLease(lease.lease_id); setLease(undefined);
  }

  async function changeHistory(action: "undo" | "redo") {
    if (!lease || !graph) return;
    try {
      const result = action === "undo" ? await serverApi.undo(lease.lease_id, graph.design.id) : await serverApi.redo(lease.lease_id, graph.design.id);
      setLiveGraph(result.graph); setHistory(result);
    } catch (reason) { setLoadError(reason instanceof Error ? reason.message : String(reason)); }
  }

  function saveNodeGeometry(nodeId: string, geometry: NodeGeometry) {
    if (!graph) return;
    void applyCommands([{ type: "set_node_geometry", command_id: `move_${crypto.randomUUID()}`, design_id: graph.design.id, node_id: nodeId, geometry }]);
  }

  function createNet() {
    if (!graph || !newNetName || !firstTerminalId || !secondTerminalId) return;
    const first = graph.terminals.find((terminal) => terminal.id === firstTerminalId);
    const second = graph.terminals.find((terminal) => terminal.id === secondTerminalId);
    const interfaceNet = first?.kind.includes("interface") && second?.kind.includes("interface");
    const portNet = first?.kind.includes("port") && second?.kind.includes("port");
    if (!interfaceNet && !portNet) { setLoadError("Both endpoints must be interfaces or both must be ports."); return; }
    const kind = interfaceNet ? "interface" : "ad_hoc";
    void applyCommands([{ type: "create_net", command_id: `net_${crypto.randomUUID()}`, design_id: graph.design.id, net_id: `net:${kind}:${newNetName}`, name: newNetName, kind, terminal_ids: [firstTerminalId, secondTerminalId] }]);
    setNewNetName(""); setFirstTerminalId(""); setSecondTerminalId("");
  }

  async function decideProposal(proposalId: string, decision: "accepted" | "rejected") {
    try {
      await serverApi.decideProposal(proposalId, decision, lease?.lease_id);
      setProposals(await serverApi.listProposals());
      if (decision === "accepted") setRefresh((value) => value + 1);
    } catch (reason) { setLoadError(reason instanceof Error ? reason.message : String(reason)); }
  }
  return (
    <main className="app-shell">
      <header className="topbar">
        <div><span className="phase">DESIGN WORKBENCH</span><h1>Circuit Designer</h1></div>
        <div className="source-controls">
          <label>Source<select aria-label="Source" value={dataSource} onChange={(event) => { if (event.target.value === "fixtures" && ownsLease) void releaseLease(); setDataSource(event.target.value as DataSource); }}>
            <option value="fixtures">Fixtures</option><option value="server">Active SpecIR session</option>
          </select></label>
          {dataSource === "fixtures" && <label>Fixture<select aria-label="Fixture" value={fixtureName} onChange={(event) => setFixtureName(event.target.value as FixtureName)}>
            {Object.keys(fixtures).map((name) => <option key={name}>{name}</option>)}
          </select></label>}
          {dataSource === "server" && <><label>Design<select aria-label="Design" value={designId} disabled={!catalog} onChange={(event) => setDesignId(event.target.value)}>
            {(catalog?.designs ?? []).map((design) => <option key={design.id} value={design.id}>{design.label}</option>)}
          </select></label><button type="button" onClick={() => setRefresh((value) => value + 1)}>Refresh</button>{ownsLease ? <button type="button" onClick={() => void releaseLease()}>End edit</button> : lease ? <span className="lock-owner">Locked by {lease.owner_kind} · {lease.owner_id}</span> : <button type="button" onClick={() => void acquireLease()}>Start editing</button>}</>}
        </div>
      </header>
      <section className="workspace">
        <aside className="rail">
          <h2>Design</h2><strong>{graph?.design.label ?? "No design loaded"}</strong><small>{graph?.design.vlnv}</small>
          <dl><div><dt>Instances</dt><dd>{graph?.nodes.length ?? "—"}</dd></div><div><dt>Nets</dt><dd>{graph?.nets.length ?? "—"}</dd></div></dl>
          <h2>Contract</h2><code>{graph?.protocol_version ?? "circuit-designer.v1"}</code><span className="readonly">{ownsLease ? "Human edit lease" : "Read-only"}</span>
          {dataSource === "server" && catalog && <><h2>Source revision</h2><code>{catalog.source_revision_hash}</code></>}
          {dataSource === "server" && catalog && graph && <div className="hierarchy-nav"><h2>Hierarchy</h2>
            {(catalog.hierarchy_links ?? []).filter((link) => link.internal_design_id === graph.design.id).flatMap((link) => link.parent_design_ids ?? []).map((parentId) => <button key={`up:${parentId}`} onClick={() => setDesignId(parentId)}>↑ {catalog.designs.find((item) => item.id === parentId)?.label ?? parentId}</button>)}
            {(catalog.hierarchy_links ?? []).filter((link) => link.parent_design_ids?.includes(graph.design.id)).map((link) => <button key={`down:${link.internal_design_id}`} onClick={() => setDesignId(link.internal_design_id)}>↓ {catalog.designs.find((item) => item.id === link.internal_design_id)?.label ?? link.internal_design_id}</button>)}
          </div>}
          {dataSource === "server" && ownsLease && graph && <div className="edit-panel">
            <h2>Edit</h2>
            <div className="history-buttons"><button disabled={!history.can_undo} onClick={() => void changeHistory("undo")}>Undo</button><button disabled={!history.can_redo} onClick={() => void changeHistory("redo")}>Redo</button></div>
            <label>Component<select value={newComponentId} onChange={(event) => setNewComponentId(event.target.value)}><option value="">Select…</option>{graph.components.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
            <label>Instance name<input value={newInstanceName} onChange={(event) => setNewInstanceName(event.target.value)} /></label>
            <button disabled={!newComponentId || !newInstanceName} onClick={() => {
              void applyCommands([{ type: "add_instance", command_id: `add_${crypto.randomUUID()}`, design_id: graph.design.id, node_id: `instance:${newInstanceName}`, name: newInstanceName, component_id: newComponentId }]);
              setNewInstanceName("");
            }}>Add instance</button>
            <button className="danger" disabled={selection?.kind !== "node"} onClick={() => selection?.kind === "node" && void applyCommands([{ type: "delete_instance", command_id: `delete_${crypto.randomUUID()}`, design_id: graph.design.id, node_id: selection.id, cascade: true }])}>Delete selected</button>
            <h2>New net</h2>
            <label>Name<input value={newNetName} onChange={(event) => setNewNetName(event.target.value)} /></label>
            <label>Endpoint A<select value={firstTerminalId} onChange={(event) => setFirstTerminalId(event.target.value)}><option value="">Select…</option>{graph.terminals.map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.node_id ? `${terminal.node_id} · ` : "boundary · "}{terminal.label}</option>)}</select></label>
            <label>Endpoint B<select value={secondTerminalId} onChange={(event) => setSecondTerminalId(event.target.value)}><option value="">Select…</option>{graph.terminals.filter((terminal) => terminal.id !== firstTerminalId).map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.node_id ? `${terminal.node_id} · ` : "boundary · "}{terminal.label}</option>)}</select></label>
            <button disabled={!newNetName || !firstTerminalId || !secondTerminalId} onClick={createNet}>Create net</button>
          </div>}
        </aside>
        <div className="stage">
          {!layoutResult && !loadError && !layoutError && <div className="loading">{graph ? "Computing orthogonal layout…" : "Loading circuit graph…"}</div>}
          {(loadError || layoutError) && <div className="error"><strong>{graph ? "Circuit operation failed" : "Unable to load circuit"}</strong><span>{loadError ?? layoutError}</span>{dataSource === "server" && loadError && !graph && <small>Open a .spec package in the spec2gds editor, then refresh.</small>}{graph && <button onClick={() => { setLoadError(undefined); setLayoutError(undefined); }}>Dismiss</button>}</div>}
          {graph && layoutResult && <CircuitDesignerCanvas graph={graph} layout={layoutResult.layout} boundaryGeometry={layoutResult.boundary_geometry} onSelect={setSelection} editable={Boolean(ownsLease && dataSource === "server")} onNodeGeometryChange={saveNodeGeometry} />}
          {layoutResult && <div className="layout-time" data-testid="layout-time">Grid router {layoutResult.elapsed_ms} ms</div>}
        </div>
        <aside className="inspector" data-testid="inspector">
          <h2>Inspector</h2>
          {!selection && <p>Select a component or net on the canvas.</p>}
          {selection && <><span className="kind">{selection.kind}</span><h3>{selected?.label ?? selection.id}</h3><code>{selection.id}</code><pre>{JSON.stringify(selected, null, 2)}</pre></>}
          {selection && ownsLease && graph && <div className="selection-editor"><h2>Selected item</h2>
            {selection.kind === "net" && <><label>Net name<input value={selectedName} onChange={(event) => setSelectedName(event.target.value)} /></label><button disabled={!selectedName || selectedName === selected?.label} onClick={() => void applyCommands([{ type: "rename_net", command_id: `rename_${crypto.randomUUID()}`, design_id: graph.design.id, net_id: selection.id, name: selectedName }])}>Rename net</button><button className="danger" onClick={() => void applyCommands([{ type: "delete_net", command_id: `delete_net_${crypto.randomUUID()}`, design_id: graph.design.id, net_id: selection.id }])}>Delete net</button></>}
            {selection.kind === "node" && <><label>Component<select value={replacementComponentId} onChange={(event) => setReplacementComponentId(event.target.value)}>{graph.components.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label><button disabled={!replacementComponentId || replacementComponentId === (selected as { component_id?: string })?.component_id} onClick={() => void applyCommands([{ type: "update_instance", command_id: `replace_${crypto.randomUUID()}`, design_id: graph.design.id, node_id: selection.id, component_id: replacementComponentId }])}>Replace component</button></>}
          </div>}
          {dataSource === "server" && <div className="proposal-list"><h2>Agent proposals</h2>{proposals.length === 0 && <p>No proposals.</p>}{proposals.map((proposal) => <article key={proposal.proposal_id}><strong>{proposal.title}</strong><small>{proposal.status}</small>{proposal.status === "pending" && <div><button disabled={!ownsLease} onClick={() => void decideProposal(proposal.proposal_id, "accepted")}>Accept</button><button onClick={() => void decideProposal(proposal.proposal_id, "rejected")}>Reject</button></div>}</article>)}</div>}
        </aside>
      </section>
    </main>
  );
}

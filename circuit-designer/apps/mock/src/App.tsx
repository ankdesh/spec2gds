import { useEffect, useMemo, useState } from "react";
import { fixtures, type CircuitDesignCatalog, type CircuitGraphSnapshot } from "@spec2gds/circuit-core";
import { HttpCircuitDesignerReadApi } from "@spec2gds/circuit-client-http";
import type { LayoutResult } from "@spec2gds/circuit-layout-elk";
import { layoutCircuitGraphInWorker } from "@spec2gds/circuit-layout-elk/browser";
import { CircuitDesignerCanvas } from "@spec2gds/circuit-react";

type FixtureName = keyof typeof fixtures;
type DataSource = "fixtures" | "server";
type Selection = { kind: "node" | "net"; id: string } | null;
const serverApi = new HttpCircuitDesignerReadApi();

export function App() {
  const [dataSource, setDataSource] = useState<DataSource>("fixtures");
  const [fixtureName, setFixtureName] = useState<FixtureName>("mixed");
  const [catalog, setCatalog] = useState<CircuitDesignCatalog>();
  const [designId, setDesignId] = useState("");
  const [liveGraph, setLiveGraph] = useState<CircuitGraphSnapshot>();
  const [refresh, setRefresh] = useState(0);
  const [layoutResult, setLayoutResult] = useState<LayoutResult>();
  const [selection, setSelection] = useState<Selection>(null);
  const [loadError, setLoadError] = useState<string>();
  const [layoutError, setLayoutError] = useState<string>();
  const fixtureGraph = useMemo(() => fixtures[fixtureName](), [fixtureName]);
  const graph = dataSource === "fixtures" ? fixtureGraph : liveGraph;

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
    layoutCircuitGraphInWorker(graph).then((result) => active && setLayoutResult(result)).catch((reason: unknown) => active && setLayoutError(String(reason)));
    return () => { active = false; };
  }, [graph]);
  const selected = selection?.kind === "node" ? graph?.nodes.find((item) => item.id === selection.id) : graph?.nets.find((item) => item.id === selection?.id);
  return (
    <main className="app-shell">
      <header className="topbar">
        <div><span className="phase">PHASE 1</span><h1>Circuit Designer</h1></div>
        <div className="source-controls">
          <label>Source<select aria-label="Source" value={dataSource} onChange={(event) => setDataSource(event.target.value as DataSource)}>
            <option value="fixtures">Fixtures</option><option value="server">Active SpecIR session</option>
          </select></label>
          {dataSource === "fixtures" && <label>Fixture<select aria-label="Fixture" value={fixtureName} onChange={(event) => setFixtureName(event.target.value as FixtureName)}>
            {Object.keys(fixtures).map((name) => <option key={name}>{name}</option>)}
          </select></label>}
          {dataSource === "server" && <><label>Design<select aria-label="Design" value={designId} disabled={!catalog} onChange={(event) => setDesignId(event.target.value)}>
            {(catalog?.designs ?? []).map((design) => <option key={design.id} value={design.id}>{design.label}</option>)}
          </select></label><button type="button" onClick={() => setRefresh((value) => value + 1)}>Refresh</button></>}
        </div>
      </header>
      <section className="workspace">
        <aside className="rail">
          <h2>Design</h2><strong>{graph?.design.label ?? "No design loaded"}</strong><small>{graph?.design.vlnv}</small>
          <dl><div><dt>Instances</dt><dd>{graph?.nodes.length ?? "—"}</dd></div><div><dt>Nets</dt><dd>{graph?.nets.length ?? "—"}</dd></div></dl>
          <h2>Contract</h2><code>{graph?.protocol_version ?? "circuit-designer.v1"}</code><span className="readonly">Read-only adapter</span>
          {dataSource === "server" && catalog && <><h2>Source revision</h2><code>{catalog.source_revision_hash}</code></>}
        </aside>
        <div className="stage">
          {!layoutResult && !loadError && !layoutError && <div className="loading">{graph ? "Computing orthogonal layout…" : "Loading circuit graph…"}</div>}
          {(loadError || layoutError) && <div className="error"><strong>Unable to load circuit</strong><span>{loadError ?? layoutError}</span>{dataSource === "server" && loadError && <small>Open a .spec package in the spec2gds editor, then refresh.</small>}</div>}
          {graph && layoutResult && <CircuitDesignerCanvas graph={graph} layout={layoutResult.layout} boundaryGeometry={layoutResult.boundary_geometry} onSelect={setSelection} />}
          {layoutResult && <div className="layout-time" data-testid="layout-time">ELK {layoutResult.elapsed_ms} ms</div>}
        </div>
        <aside className="inspector" data-testid="inspector">
          <h2>Inspector</h2>
          {!selection && <p>Select a component or net on the canvas.</p>}
          {selection && <><span className="kind">{selection.kind}</span><h3>{selected?.label ?? selection.id}</h3><code>{selection.id}</code><pre>{JSON.stringify(selected, null, 2)}</pre></>}
        </aside>
      </section>
    </main>
  );
}

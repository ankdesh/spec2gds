import { useEffect, useMemo, useState } from "react";
import { fixtures, type CircuitGraphSnapshot } from "@spec2gds/circuit-core";
import type { LayoutResult } from "@spec2gds/circuit-layout-elk";
import { layoutCircuitGraphInWorker } from "@spec2gds/circuit-layout-elk/browser";
import { CircuitDesignerCanvas } from "@spec2gds/circuit-react";

type FixtureName = keyof typeof fixtures;
type Selection = { kind: "node" | "net"; id: string } | null;

export function App() {
  const [fixtureName, setFixtureName] = useState<FixtureName>("mixed");
  const [layoutResult, setLayoutResult] = useState<LayoutResult>();
  const [selection, setSelection] = useState<Selection>(null);
  const [error, setError] = useState<string>();
  const graph: CircuitGraphSnapshot = useMemo(() => fixtures[fixtureName](), [fixtureName]);
  useEffect(() => {
    let active = true;
    setLayoutResult(undefined); setSelection(null); setError(undefined);
    layoutCircuitGraphInWorker(graph).then((result) => active && setLayoutResult(result)).catch((reason: unknown) => active && setError(String(reason)));
    return () => { active = false; };
  }, [graph]);
  const selected = selection?.kind === "node" ? graph.nodes.find((item) => item.id === selection.id) : graph.nets.find((item) => item.id === selection?.id);
  return (
    <main className="app-shell">
      <header className="topbar">
        <div><span className="phase">PHASE 0</span><h1>Circuit Designer</h1></div>
        <label>Fixture<select aria-label="Fixture" value={fixtureName} onChange={(event) => setFixtureName(event.target.value as FixtureName)}>
          {Object.keys(fixtures).map((name) => <option key={name}>{name}</option>)}
        </select></label>
      </header>
      <section className="workspace">
        <aside className="rail">
          <h2>Design</h2><strong>{graph.design.label}</strong><small>{graph.design.vlnv}</small>
          <dl><div><dt>Instances</dt><dd>{graph.nodes.length}</dd></div><div><dt>Nets</dt><dd>{graph.nets.length}</dd></div></dl>
          <h2>Contract</h2><code>{graph.protocol_version}</code><span className="readonly">Read-only adapter</span>
        </aside>
        <div className="stage">
          {!layoutResult && !error && <div className="loading">Computing orthogonal layout…</div>}
          {error && <div className="error">{error}</div>}
          {layoutResult && <CircuitDesignerCanvas graph={graph} layout={layoutResult.layout} boundaryGeometry={layoutResult.boundary_geometry} onSelect={setSelection} />}
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

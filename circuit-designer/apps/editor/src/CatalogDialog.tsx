import { useEffect, useRef, useState } from "react";
import { SpecEditorHttpClient, type CatalogComponent, type CatalogVersion, type CatalogImportPreview, type CatalogImportRequest, type EntityRef } from "@spec2gds/document-core";
import "./catalog.css";

export function CatalogDialog({ client, documentKey, revision, onClose, onImported }: {
  client: SpecEditorHttpClient; documentKey: string; revision: string; onClose(): void; onImported(root: EntityRef, reused: boolean): Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [baseRevision, setBaseRevision] = useState(revision);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [implementation, setImplementation] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<CatalogComponent[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState("");
  const [versions, setVersions] = useState<CatalogComponent[]>([]);
  const [version, setVersion] = useState("");
  const [details, setDetails] = useState<CatalogVersion | null>(null);
  const [preview, setPreview] = useState<CatalogImportPreview | null>(null);
  const [renamed, setRenamed] = useState(false);
  const [renames, setRenames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const previewSequence = useRef(0);
  const priorSelection = useRef("");
  const request = (): CatalogImportRequest => ({ component_key: selected, version, package_sha256: details!.package_sha256, expected_source_revision_hash: baseRevision, renames, renamed_copy: renamed });
  useEffect(() => { dialog.current?.showModal(); void client.catalogCapabilities().then(c => setCategories(c.categories)).catch(() => {}); return () => dialog.current?.close(); }, []);
  useEffect(() => {
    let current = true;
    const timer = setTimeout(() => {
      setLoading(true); setError("");
      void client.listCatalogComponents({ q, category, implementation, functional_status: status, offset: String(offset), limit: "25" }).then(result => {
        if (current) { setItems(result.items); setTotal(result.total); }
      }).catch(caught => { if (current) setError(String(caught.message ?? caught)); }).finally(() => { if (current) setLoading(false); });
    }, 150);
    return () => { current = false; clearTimeout(timer); };
  }, [q, category, implementation, status, offset, retry]);
  useEffect(() => {
    let current = true;
    if (priorSelection.current !== selected) { setDetails(null); setPreview(null); setVersions([]); setVersion(""); setRenames({}); setRenamed(false); }
    priorSelection.current = selected;
    if (selected) void client.getCatalogComponent(selected).then(result => {
      if (current) { setVersions(result.versions); setVersion(value => result.versions.some(v => v.version === value) ? value : result.versions[0]?.version ?? ""); }
    }).catch(caught => { if (current) setError(caught.message); });
    return () => { current = false; };
  }, [selected, retry]);
  useEffect(() => {
    let current = true;
    setDetails(null); setPreview(null); setRenames({}); setRenamed(false);
    if (selected && version) void client.getCatalogVersion(selected, version).then(result => { if (current) setDetails(result); }).catch(caught => { if (current) setError(caught.message); });
    return () => { current = false; };
  }, [selected, version, retry]);
  useEffect(() => setBaseRevision(revision), [revision]);
  useEffect(() => { setPreview(p => p ? { ...p, can_import: false } : null); previewSequence.current++; }, [renamed, renames, baseRevision]);
  const review = async () => {
    const sequence = ++previewSequence.current;
    setBusy(true); setError("");
    try { const result = await client.previewCatalogImport(request(), documentKey); if (sequence === previewSequence.current) setPreview(result); }
    catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
    finally { setBusy(false); }
  };
  const save = async () => {
    if (busy || !preview?.can_import) return;
    setBusy(true); setError("");
    try { const result = await client.importCatalogComponent(request(), documentKey); await onImported(result.root, result.reused); }
    catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); setPreview(null); }
    finally { setBusy(false); }
  };
  return <dialog className="spec-catalog-dialog" ref={dialog} aria-labelledby="catalog-title" onCancel={event => { if (busy) event.preventDefault(); else onClose(); }}>
    <header><h2 id="catalog-title">Import from catalog</h2><button type="button" disabled={busy} onClick={onClose}>Close</button></header>
    <p>Import an editable Component definition into the loaded Spec. Parameter defaults come from the selected release.</p>
    <div className="spec-catalog-filters">
      <label>Search catalog<input autoFocus type="search" value={q} onChange={e => { setQ(e.target.value); setOffset(0); }} /></label>
      <label>Category<select value={category} onChange={e => { setCategory(e.target.value); setOffset(0); }}><option value="">All categories</option>{categories.map(c => <option key={c}>{c}</option>)}</select></label>
      <label>Implementation<select value={implementation} onChange={e => { setImplementation(e.target.value); setOffset(0); }}><option value="">All implementations</option><option value="body_sv">SystemVerilog</option><option value="composite">Composite</option></select></label>
      <label>Recorded verification<select value={status} onChange={e => { setStatus(e.target.value); setOffset(0); }}><option value="">All results</option><option value="reported_pass">Reported pass</option><option value="reported_fail">Reported fail</option><option value="reported_incomplete">Incomplete</option><option value="unreported">Unreported</option></select></label>
    </div>
    {error && <div role="alert"><p>{error}</p><button type="button" disabled={busy} onClick={() => setRetry(n => n + 1)}>Retry catalog request</button><button type="button" disabled={busy} onClick={() => { void client.getDocumentView(documentKey).then(view => { setBaseRevision(view.source_revision_hash); setPreview(null); setError(""); }).catch(caught => setError(caught.message)); }}>Refresh Spec for a new preview</button></div>}
    <div className="spec-catalog-columns"><aside aria-label="Catalog results" aria-busy={loading}>
      <p role="status">{loading ? "Loading catalog…" : `${total} published Components`}</p>
      {items.map(item => <button className="spec-catalog-result" aria-pressed={selected === item.key} key={item.key} type="button" disabled={busy} onClick={() => setSelected(item.key)}><strong>{item.id}</strong><span>{item.summary}</span><small>{item.category} · {item.version}</small></button>)}
      {!loading && !items.length && <p>No published Components match these filters.</p>}
      <nav aria-label="Catalog pages"><button type="button" disabled={!offset || loading} onClick={() => setOffset(n => Math.max(0, n - 25))}>Previous</button><span>{Math.min(offset + 1, total)}–{Math.min(offset + 25, total)} of {total}</span><button type="button" disabled={offset + 25 >= total || loading} onClick={() => setOffset(n => n + 25)}>Next</button></nav>
    </aside><section aria-label="Selected Component">
      {!selected && <p>Select a Component to inspect its interface and release evidence.</p>}
      {selected && <label>Version<select value={version} disabled={busy} onChange={e => setVersion(e.target.value)}>{versions.map(v => <option key={v.version}>{v.version}</option>)}</select></label>}
      {details && <><h3>{details.id}</h3><p>{details.summary}</p><p>Recorded verification: {details.functional_status.replaceAll("_", " ")}. Imported source requires verification in this Spec.</p>
        <h4>Ports</h4><table><thead><tr><th>ID</th><th>Direction</th><th>Range</th></tr></thead><tbody>{details.ports.map(p => <tr key={p.name}><td>{p.name}</td><td>{p.direction}</td><td>{p.width ?? "Scalar"}</td></tr>)}</tbody></table>
        <h4>Parameters</h4>{details.parameters.map(p => <p key={p.name}><code>{p.name}: {p.rtl_type} = {p.value}</code> {p.description}</p>)}
        <details><summary>Presets and timing</summary><h4>Presets</h4><table><thead><tr><th>Preset</th><th>Parameter values</th></tr></thead><tbody>{Object.entries(details.metadata.presets).map(([name, values]) => <tr key={name}><td>{name}</td><td>{Object.entries(values).map(([key, value]) => `${key}=${value}`).join(", ") || "Default parameters"}</td></tr>)}</tbody></table><dl>{Object.entries(details.metadata.timing).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl></details>
        <p>Licence: {details.metadata.licence}</p><ul>{details.metadata.limitations.map((item, i) => <li key={i}>{item}</li>)}</ul>
        <details><summary>Usage</summary><pre>{details.usage_markdown || details.metadata.summary}</pre></details>
        <details><summary>Recorded evidence ({details.evidence.length})</summary><p>These records describe the published release.</p>{details.evidence.map((value, index) => <EvidenceRecord key={index} value={value} />)}</details>
        <label><input type="checkbox" checked={renamed} disabled={busy} onChange={e => { setRenamed(e.target.checked); setRenames({}); }} /> Import as a renamed copy</label>
        <div className="spec-catalog-actions"><button type="button" disabled={busy} onClick={() => void review()}>{busy ? "Working…" : "Review import"}</button></div>
        {preview && <section aria-label="Import preview"><h4>Import preview</h4>{preview.reused && <p>The matching local import is unchanged and will be reused.</p>}{preview.definitions.map(row => <div key={row.source_id}><strong>{row.name}</strong><small> {row.reused ? "Reuse existing" : "Add definition"}</small>{renamed && !row.reused && <label>Local name for {row.source_id}<input value={renames[row.source_id] ?? row.name} onChange={e => setRenames(values => ({ ...values, [row.source_id]: e.target.value }))} /></label>}</div>)}
          {preview.conflicts.map(c => <p key={c.source_id} role="status">{c.name}: {c.reason} Suggested name: {c.suggested_name}. Select “Import as a renamed copy” and review again.</p>)}
        </section>}
        <button type="button" disabled={busy || !preview?.can_import} onClick={() => void save()}>Import into Spec</button>
      </>}
    </section></div>
  </dialog>;
}

function EvidenceRecord({ value }: { value: unknown }) {
  try {
    const record = value as { received_at: string; report: { checks: Array<{ kind: string; preset?: string; status: string; summary: string }>; tools: Record<string, string> } };
    const evidence = record.report;
    return <section><p>Received: {record.received_at}</p><table><thead><tr><th>Check</th><th>Preset</th><th>Result</th><th>Details</th></tr></thead><tbody>{evidence.checks.map((check, i) => <tr key={i}><td>{check.kind}</td><td>{check.preset ?? "All"}</td><td>{check.status}</td><td>{check.summary}</td></tr>)}</tbody></table><details><summary>Tool versions</summary><dl>{Object.entries(evidence.tools).map(([name, version]) => <div key={name}><dt>{name}</dt><dd>{version}</dd></div>)}</dl></details></section>;
  } catch { return <p>This evidence record could not be displayed.</p>; }
}

import { useEffect, useRef, useState } from "react";
import { SpecEditorHttpClient, SpecEditorHttpError, type CatalogComponent, type CatalogVersion, type CatalogImportPreview, type CatalogImportRequest, type EntityRef } from "@spec2gds/document-core";
import "./catalog.css";

const message = (error: unknown) => error instanceof Error ? error.message : String(error);

export function CatalogDialog({ client, documentKey, revision, onClose, onImported }: {
  client: SpecEditorHttpClient; documentKey: string; revision: string; onClose(): void; onImported(root: EntityRef, reused: boolean): Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const resultsList = useRef<HTMLDivElement>(null);
  const detailScroll = useRef<HTMLDivElement>(null);
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const previewHeading = useRef<HTMLHeadingElement>(null);
  const listPosition = useRef(0);
  const pending = useRef(false);
  const mounted = useRef(false);
  const previewSequence = useRef(0);
  const [baseRevision, setBaseRevision] = useState(revision);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [implementation, setImplementation] = useState("");
  const [status, setStatus] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<CatalogComponent[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState("");
  const [versions, setVersions] = useState<CatalogComponent[]>([]);
  const [version, setVersion] = useState("");
  const [details, setDetails] = useState<CatalogVersion | null>(null);
  const [preview, setPreview] = useState<CatalogImportPreview | null>(null);
  const [previewKey, setPreviewKey] = useState("");
  const [renamed, setRenamed] = useState(false);
  const [renames, setRenames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<"review" | "import" | "refresh" | null>(null);
  const [resultsError, setResultsError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [importError, setImportError] = useState("");
  const [capabilityError, setCapabilityError] = useState("");
  const [staleSpec, setStaleSpec] = useState(false);
  const [listRetry, setListRetry] = useState(0);
  const [detailRetry, setDetailRetry] = useState(0);
  const [capabilityRetry, setCapabilityRetry] = useState(0);
  const [compact, setCompact] = useState(() => window.matchMedia("(max-width: 899px)").matches);
  const [mobileDetails, setMobileDetails] = useState(false);
  const busy = action !== null;
  const ready = details !== null && details.key === selected && details.version === version;
  const inputsKey = JSON.stringify([selected, version, details?.package_sha256, renamed, renames, baseRevision, revision]);
  const canImport = ready && !!preview?.can_import && previewKey === inputsKey;
  const selectedName = details?.id || items.find(item => item.key === selected)?.id || "Component";
  const filterCount = [category, implementation, status].filter(Boolean).length;
  const request = (): CatalogImportRequest => ({ component_key: selected, version, package_sha256: details!.package_sha256, expected_source_revision_hash: baseRevision, renames, renamed_copy: renamed });

  useEffect(() => {
    mounted.current = true;
    const element = dialog.current!;
    const previousOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    element.showModal();
    element.querySelector<HTMLInputElement>("input[type='search']")?.focus();
    const media = window.matchMedia("(max-width: 899px)");
    const resize = () => setCompact(media.matches);
    media.addEventListener("change", resize);
    return () => {
      mounted.current = false;
      ++previewSequence.current;
      media.removeEventListener("change", resize);
      element.close();
      document.documentElement.style.overflow = previousOverflow;
    };
  }, []);
  useEffect(() => {
    let current = true;
    setCapabilityError("");
    void client.catalogCapabilities().then(result => { if (current) setCategories(result.categories); })
      .catch(error => { if (current) setCapabilityError(message(error)); });
    return () => { current = false; };
  }, [client, capabilityRetry]);
  useEffect(() => {
    let current = true;
    setLoading(true);
    setResultsError("");
    const timer = setTimeout(() => {
      void client.listCatalogComponents({ q, category, implementation, functional_status: status, offset: String(offset), limit: "25" })
        .then(result => { if (current) { setItems(result.items); setTotal(result.total); if (resultsList.current) resultsList.current.scrollTop = 0; } })
        .catch(error => { if (current) setResultsError(message(error)); })
        .finally(() => { if (current) setLoading(false); });
    }, 150);
    return () => { current = false; clearTimeout(timer); };
  }, [client, q, category, implementation, status, offset, listRetry]);
  useEffect(() => {
    let current = true;
    setVersions([]);
    setDetailError("");
    if (selected) void client.getCatalogComponent(selected).then(result => {
      if (current) { setVersions(result.versions); setVersion(value => result.versions.some(item => item.version === value) ? value : result.versions[0]?.version ?? ""); }
    }).catch(error => { if (current) setDetailError(message(error)); });
    return () => { current = false; };
  }, [client, selected, detailRetry]);
  useEffect(() => {
    let current = true;
    setDetails(null);
    setDetailError("");
    if (selected && version) void client.getCatalogVersion(selected, version).then(result => {
      if (current) setDetails(result);
    }).catch(error => { if (current) setDetailError(message(error)); });
    return () => { current = false; };
  }, [client, selected, version, detailRetry]);
  useEffect(() => setBaseRevision(revision), [revision]);
  useEffect(() => setPreviewKey(""), [baseRevision, revision]);
  useEffect(() => { ++previewSequence.current; }, [selected, version, renamed, renames, baseRevision, revision]);
  useEffect(() => {
    if (selected && compact && mobileDetails) detailHeading.current?.focus({ preventScroll: true });
  }, [selected, compact, mobileDetails]);
  useEffect(() => {
    if (!preview) return;
    if (detailScroll.current) detailScroll.current.scrollTop = 0;
    previewHeading.current?.focus({ preventScroll: true });
  }, [preview]);

  const clearPreview = () => {
    ++previewSequence.current;
    setPreview(null); setPreviewKey(""); setImportError(""); setStaleSpec(false);
  };
  const select = (item: CatalogComponent) => {
    listPosition.current = resultsList.current?.scrollTop ?? 0;
    if (item.key !== selected) {
      clearPreview(); setVersion(""); setDetails(null); setRenamed(false); setRenames({}); setSelected(item.key);
      if (detailScroll.current) detailScroll.current.scrollTop = 0;
    }
    setMobileDetails(true);
  };
  const back = () => {
    setMobileDetails(false);
    requestAnimationFrame(() => {
      if (!resultsList.current) return;
      resultsList.current.scrollTop = listPosition.current;
      resultsList.current.querySelector<HTMLButtonElement>("[aria-pressed='true']")?.focus({ preventScroll: true });
    });
  };
  const review = async () => {
    if (!ready || pending.current) return;
    pending.current = true;
    const sequence = ++previewSequence.current;
    const key = inputsKey;
    setAction("review"); setImportError(""); setStaleSpec(false); setMobileDetails(true);
    try {
      const result = await client.previewCatalogImport(request(), documentKey);
      if (mounted.current && sequence === previewSequence.current) { setPreview(result); setPreviewKey(key); }
    } catch (error) {
      if (mounted.current) { setImportError(message(error)); setStaleSpec(error instanceof SpecEditorHttpError && error.status === 409); }
    } finally { pending.current = false; if (mounted.current) setAction(null); }
  };
  const save = async () => {
    if (!canImport || pending.current) return;
    pending.current = true;
    setAction("import"); setImportError("");
    try { const result = await client.importCatalogComponent(request(), documentKey); if (mounted.current) await onImported(result.root, result.reused); }
    catch (error) {
      if (mounted.current) { setImportError(message(error)); setPreview(null); setStaleSpec(error instanceof SpecEditorHttpError && error.status === 409); }
    } finally { pending.current = false; if (mounted.current) setAction(null); }
  };
  const refresh = async () => {
    if (pending.current) return;
    pending.current = true; setAction("refresh");
    try { const view = await client.getDocumentView(documentKey); if (mounted.current) { setBaseRevision(view.source_revision_hash); clearPreview(); } }
    catch (error) { if (mounted.current) setImportError(message(error)); }
    finally { pending.current = false; if (mounted.current) setAction(null); }
  };

  return <dialog className="spec-catalog-dialog" ref={dialog} aria-modal="true" aria-labelledby="catalog-title" aria-describedby="catalog-description"
    data-compact-view={mobileDetails ? "details" : "results"} onCancel={event => { if (pending.current) event.preventDefault(); else onClose(); }}
    onKeyDown={event => {
      if (event.key !== "Tab") return;
      const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
        "button:not(:disabled), input:not(:disabled), select:not(:disabled), summary, a[href], [tabindex='0']",
      )).filter(element => element.getClientRects().length > 0);
      const first = controls[0], last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}>
    <header className="spec-catalog-header">
      <div><h2 id="catalog-title">Component library</h2><p id="catalog-description">Choose a Component to import into this Spec.</p></div>
      <button aria-label="Close Component library" className="spec-catalog-close" type="button" disabled={busy} onClick={() => { if (!pending.current) onClose(); }}>×</button>
    </header>
    <div className="spec-catalog-toolbar">
      <div className="spec-catalog-search-row">
        <label className="spec-catalog-search"><span className="visually-hidden">Search Components</span><input autoFocus type="search" placeholder="Search Components…" disabled={busy} value={q} onChange={event => { setQ(event.target.value); setOffset(0); }} /></label>
        <button type="button" disabled={busy} aria-expanded={filtersOpen} aria-controls="catalog-filters" onClick={() => setFiltersOpen(value => !value)}>Filters{filterCount ? ` (${filterCount})` : ""}</button>
      </div>
      {filtersOpen && <div id="catalog-filters" className="spec-catalog-filters">
        <label>Category<select value={category} disabled={busy} onChange={event => { setCategory(event.target.value); setOffset(0); }}><option value="">All categories</option>{categories.map(item => <option key={item}>{item}</option>)}</select></label>
        <label>Implementation<select value={implementation} disabled={busy} onChange={event => { setImplementation(event.target.value); setOffset(0); }}><option value="">All implementations</option><option value="body_sv">SystemVerilog</option><option value="composite">Composite</option></select></label>
        <label>Recorded verification<select value={status} disabled={busy} onChange={event => { setStatus(event.target.value); setOffset(0); }}><option value="">All results</option><option value="reported_pass">Reported pass</option><option value="reported_fail">Reported fail</option><option value="reported_incomplete">Incomplete</option><option value="unreported">Unreported</option></select></label>
        {filterCount > 0 && <button type="button" className="spec-catalog-text-button" disabled={busy} onClick={() => { setCategory(""); setImplementation(""); setStatus(""); setOffset(0); }}>Clear filters</button>}
        {capabilityError && <div className="spec-catalog-error" role="alert"><p>{capabilityError}</p><button type="button" disabled={busy} onClick={() => setCapabilityRetry(value => value + 1)}>Retry categories</button></div>}
      </div>}
    </div>
    <div className="spec-catalog-columns">
      <aside className="spec-catalog-results" aria-label="Catalog results" aria-busy={loading}>
        <p role="status" className="spec-catalog-count">{loading ? "Loading Components…" : `${total} published ${total === 1 ? "Component" : "Components"}`}</p>
        <div className="spec-catalog-results-scroll" ref={resultsList}>
          {resultsError ? <div className="spec-catalog-error" role="alert"><p>{resultsError}</p><button type="button" disabled={busy} onClick={() => setListRetry(value => value + 1)}>Retry catalog request</button></div> : <>
            {items.map(item => <button className="spec-catalog-result" aria-pressed={selected === item.key} title={item.id} key={item.key} type="button" disabled={busy || loading} onClick={() => select(item)}>
              <strong>{item.id}</strong><span className="spec-catalog-result-summary">{item.summary}</span><small>{item.category} <span aria-hidden="true">·</span> {item.version}</small>
            </button>)}
            {!loading && !items.length && <div className="spec-catalog-empty"><strong>No matching Components</strong><p>Try another search or clear the filters.</p></div>}
          </>}
        </div>
        <nav className="spec-catalog-pages" aria-label="Catalog pages">
          <button type="button" disabled={busy || !offset || loading} onClick={() => setOffset(value => Math.max(0, value - 25))}>Previous</button>
          <span>{Math.min(offset + 1, total)}–{Math.min(offset + 25, total)} of {total}</span>
          <button type="button" disabled={busy || offset + 25 >= total || loading} onClick={() => setOffset(value => value + 25)}>Next</button>
        </nav>
      </aside>
      <section className="spec-catalog-selected" aria-label="Selected Component" aria-busy={!!selected && !ready && !detailError}>
        {selected ? <>
          <div className="spec-catalog-detail-header">
            <button className="spec-catalog-back" type="button" disabled={busy} onClick={back}>← Back to results</button>
            <div className="spec-catalog-identity"><div><span className="spec-catalog-eyebrow">COMPONENT</span><h3 ref={detailHeading} tabIndex={-1} title={selectedName}>{selectedName}</h3></div>
              <label>Version<select value={version} disabled={busy || !versions.length} onChange={event => { clearPreview(); setVersion(event.target.value); setRenamed(false); setRenames({}); }}>
                {!versions.length && <option value="">Loading…</option>}{versions.map(item => <option key={item.version}>{item.version}</option>)}
              </select></label>
            </div>
          </div>
          <div className="spec-catalog-detail-scroll" ref={detailScroll}>
            {detailError ? <div className="spec-catalog-error" role="alert"><p>{detailError}</p><button type="button" disabled={busy} onClick={() => setDetailRetry(value => value + 1)}>Retry Component details</button></div> : !ready ? <p className="spec-catalog-muted" role="status">Loading Component details…</p> : <>
              {importError && <div className="spec-catalog-error" role="alert"><p>{importError}</p>{staleSpec && <button type="button" disabled={busy} onClick={() => void refresh()}>Refresh Spec for a new preview</button>}</div>}
              {preview && <section className="spec-catalog-preview" aria-label="Import preview">
                <h4 ref={previewHeading} tabIndex={-1}>Import preview</h4>
                <p role="status">{previewKey !== inputsKey ? "Inputs changed. Review import again before importing." : canImport ? "Ready to import into this Spec." : "Resolve the conflicts, then review import again."}</p>
                {preview.reused && <p>The matching local import is unchanged and will be reused.</p>}
                {preview.definitions.map(row => <div className="spec-catalog-definition" key={row.source_id}><div><strong>{row.name}</strong><small>{row.reused ? "Reuse existing" : "Add definition"}</small></div>
                  {renamed && !row.reused && <label>Local name for {row.source_id}<input disabled={busy} value={renames[row.source_id] ?? row.name} onChange={event => { setPreviewKey(""); setRenames(values => ({ ...values, [row.source_id]: event.target.value })); }} /></label>}
                </div>)}
                {preview.conflicts.map(conflict => <p className="spec-catalog-conflict" key={conflict.source_id}>{conflict.name}: {conflict.reason} Suggested name: <strong>{conflict.suggested_name}</strong>. Select “Import as a renamed copy” and review again.</p>)}
              </section>}
              <p className="spec-catalog-description">{details.summary}</p>
              <div className="spec-catalog-badges"><span>{details.category}</span><span>Recorded verification: {details.functional_status.replaceAll("_", " ")}</span></div>
              <p className="spec-catalog-notice">Imported source requires verification in this Spec. Parameter defaults come from this release.</p>
              <label className="spec-catalog-copy-option"><input type="checkbox" checked={renamed} disabled={busy} onChange={event => { setPreviewKey(""); setRenamed(event.target.checked); setRenames({}); }} /> Import as a renamed copy</label>
              <section className="spec-catalog-section"><h4>Ports <span>{details.ports.length}</span></h4>
                {details.ports.length ? <div className="spec-catalog-table-scroll" tabIndex={0} role="region" aria-label="Component ports"><table><thead><tr><th>ID</th><th>Direction</th><th>Range</th></tr></thead><tbody>{details.ports.map(port => <tr key={port.name}><td><code>{port.name}</code></td><td>{port.direction}</td><td><code>{port.width ?? "Scalar"}</code></td></tr>)}</tbody></table></div> : <p className="spec-catalog-muted">No ports in this release.</p>}
              </section>
              <section className="spec-catalog-section"><h4>Parameters <span>{details.parameters.length}</span></h4>
                {details.parameters.length ? <div className="spec-catalog-table-scroll" tabIndex={0} role="region" aria-label="Component parameters"><table><thead><tr><th>ID</th><th>Type</th><th>Default</th><th>Description</th></tr></thead><tbody>{details.parameters.map(parameter => <tr key={parameter.name}><td><code>{parameter.name}</code></td><td><code>{parameter.rtl_type}</code></td><td><code>{parameter.value}</code></td><td>{parameter.description || "—"}</td></tr>)}</tbody></table></div> : <p className="spec-catalog-muted">No parameters in this release.</p>}
              </section>
              <details className="spec-catalog-disclosure"><summary>Usage</summary><pre>{details.usage_markdown || details.metadata.summary}</pre></details>
              <details className="spec-catalog-disclosure"><summary>Presets and timing</summary><h4>Presets</h4><div className="spec-catalog-table-scroll"><table><thead><tr><th>Preset</th><th>Parameter values</th></tr></thead><tbody>{Object.entries(details.metadata.presets).map(([name, values]) => <tr key={name}><td>{name}</td><td>{Object.entries(values).map(([key, value]) => `${key}=${value}`).join(", ") || "Default parameters"}</td></tr>)}</tbody></table></div><dl>{Object.entries(details.metadata.timing).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl></details>
              <details className="spec-catalog-disclosure"><summary>Release information</summary><p>Component ID: <code>{details.id}</code></p><p>Licence: {details.metadata.licence}</p>{details.metadata.limitations.length ? <ul>{details.metadata.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>No limitations recorded.</p>}</details>
              <details className="spec-catalog-disclosure"><summary>Recorded evidence ({details.evidence.length})</summary><p>These records describe the published release.</p>{details.evidence.map((value, index) => <EvidenceRecord key={index} value={value} />)}</details>
            </>}
          </div>
        </> : <div className="spec-catalog-empty spec-catalog-start"><span aria-hidden="true">＋</span><h3>Choose a Component</h3><p>Select a result to inspect its interface, parameter defaults, and release evidence.</p></div>}
      </section>
    </div>
    <footer className="spec-catalog-footer">
      <p title={selected ? `${selectedName} · ${version}` : undefined}>{selected ? <><strong>{selectedName}</strong><span>{version ? `Version ${version}` : "Loading release…"}</span></> : "Select a Component to continue."}</p>
      <div><button type="button" disabled={busy} onClick={() => { if (!pending.current) onClose(); }}>Cancel</button><button className="spec-catalog-primary" type="button" disabled={busy || !ready || (compact && !mobileDetails)} onClick={() => void (canImport ? save() : review())}>
        {action === "import" ? "Importing…" : action === "review" ? "Reviewing…" : action === "refresh" ? "Refreshing…" : canImport ? "Import into Spec" : "Review import"}
      </button></div>
    </footer>
  </dialog>;
}

function EvidenceRecord({ value }: { value: unknown }) {
  try {
    const record = value as { received_at: string; report: { checks: Array<{ kind: string; preset?: string; status: string; summary: string }>; tools: Record<string, string> } };
    return <section><p>Received: {record.received_at}</p><div className="spec-catalog-table-scroll"><table><thead><tr><th>Check</th><th>Preset</th><th>Result</th><th>Details</th></tr></thead><tbody>{record.report.checks.map((check, index) => <tr key={index}><td>{check.kind}</td><td>{check.preset ?? "All"}</td><td>{check.status}</td><td>{check.summary}</td></tr>)}</tbody></table></div><details><summary>Tool versions</summary><dl>{Object.entries(record.report.tools).map(([name, version]) => <div key={name}><dt>{name}</dt><dd>{version}</dd></div>)}</dl></details></section>;
  } catch { return <p>This evidence record could not be displayed.</p>; }
}

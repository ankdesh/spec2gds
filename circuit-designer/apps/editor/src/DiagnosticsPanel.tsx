import { useEffect, useRef } from "react";
import type { DocumentSnapshot, EntityRef } from "@spec2gds/document-core";
import type { SpecSourceLocation } from "@spec2gds/document-a2ui-react";
import { collectFindings, targetName } from "./diagnostics";

const labels = { passed: "Lint passed", failed: "Lint failed", unverified: "Not verified", stale: "Out of date" };

export function DiagnosticsPanel({ snapshot, selectedTarget, onNavigate }: {
  snapshot: DocumentSnapshot | null;
  selectedTarget: EntityRef | null;
  onNavigate(location: SpecSourceLocation): void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const findings = collectFindings(snapshot);
  useEffect(() => {
    if (!selectedTarget) return;
    const item = Array.from(root.current?.querySelectorAll<HTMLElement>("[data-report-target]") ?? [])
      .find(item => item.dataset.reportTarget === `${selectedTarget.entity_kind}:${selectedTarget.entity_id}`);
    item?.scrollIntoView({ block: "nearest" });
  }, [selectedTarget]);
  if (!snapshot) return <p>Open a Spec to inspect diagnostics.</p>;
  const targets = new Map<string, EntityRef>();
  for (const report of snapshot.verifications ?? []) targets.set(`${report.target.entity_kind}:${report.target.entity_id}`, report.target);
  for (const finding of findings) if (finding.target) targets.set(`${finding.target.entity_kind}:${finding.target.entity_id}`, finding.target);
  return <div className="diagnostics-panel" ref={root}>
    <h2>Verification</h2>
    {!targets.size && <p>No verification reports. Use Verify in a Component or Design Options menu.</p>}
    {[...targets].map(([key, target]) => {
      const report = snapshot.verifications?.find(item => item.target.entity_id === target.entity_id && item.target.entity_kind === target.entity_kind);
      const stale = report && (report.status === "stale" || report.source_revision_hash !== snapshot.source_revision_hash);
      const items = findings.filter(item => item.target?.entity_id === target.entity_id && item.target.entity_kind === target.entity_kind);
      return <section className="diagnostic-target" key={key} data-report-target={key}>
        <h3>{targetName(snapshot, target)}</h3>
        <p>{report ? labels[stale ? "stale" : report.status] : "Section validation"}</p>
        {report && <p className="diagnostic-context">Functional simulation unverified</p>}
        {stale && <p>The saved source changed. Verify again to check this revision.</p>}
        {items.map(item => <article className="diagnostic-finding" key={item.key}>
          <p><strong>{item.diagnostic?.blocking === true ? "Error" : item.diagnostic?.blocking === false ? "Warning" : "Diagnostic"}</strong> · {item.code && <code>{item.code} </code>}{item.message}</p>
          {item.diagnostic?.file_path && <p className="diagnostic-location">{item.diagnostic.source_kind === "generated" ? "Generated RTL" : "SystemVerilog"}: <code>{item.diagnostic.file_path}{item.diagnostic.line ? `:${item.diagnostic.line}${item.diagnostic.column ? `:${item.diagnostic.column}` : ""}` : ""}</code></p>}
          <button type="button" onClick={() => onNavigate({ target, sectionId: item.sectionId,
            line: item.diagnostic?.source_kind === "generated" ? undefined : item.diagnostic?.line,
            column: item.diagnostic?.column, sourceRevisionHash: item.revision })}>Go to source</button>
        </article>)}
        {!items.length && <button type="button" onClick={() => onNavigate({ target })}>Go to source</button>}
        {report && <details><summary>Technical details</summary>
          <p>Checked target: <code>{target.entity_id}</code></p>
          <p>Source revision: <code>{report.source_revision_hash}</code></p>
          <p>{report.tool_version}</p>
          {report.interfaces?.map(item => <div key={item.component}><strong>{item.component}: {item.status}</strong>{item.ports.map(port => <p key={port.name}><code>{port.name}</code> · {port.range || "scalar"} · {port.width ?? "unresolved"} bits</p>)}</div>)}
          <pre>{JSON.stringify(report, null, 2)}</pre>
        </details>}
      </section>;
    })}
    {([ ["source", "Source package"], ["artifacts", "Artifact issues"] ] as const).map(([group, title]) => <details key={group} open={findings.some(item => item.group === group)}>
      <summary>{title}</summary>
      {findings.filter(item => item.group === group).map(item => <p key={item.key}>{item.message}</p>)}
      {!findings.some(item => item.group === group) && <p>No issues reported.</p>}
    </details>)}
    <details><summary>Catalog evidence</summary>
      <p>Published release evidence is separate from verification of the current Spec.</p>
      {!snapshot.catalog_origins?.length && <p>No Catalog evidence.</p>}
      {snapshot.catalog_origins?.map(origin => <section key={origin.package_sha256 + origin.root.entity_id}>
        <h3>{targetName(snapshot, origin.root)}</h3>
        <p>Imported from {origin.source_vlnv}. This is an editable local copy.</p>
        {origin.metadata?.summary && <p>{origin.metadata.summary}</p>}
        {origin.metadata?.licence && <p>Published licence: {origin.metadata.licence}</p>}
        {origin.evidence?.map(evidence => <ul key={evidence.evidence_sha256}>{evidence.report.checks.map((check, index) => <li key={index}>{check.kind}{check.preset ? ` (${check.preset})` : ""}: {check.status} — {check.summary}</li>)}</ul>)}
        <details><summary>Technical details</summary><pre>{JSON.stringify(origin, null, 2)}</pre></details>
      </section>)}
    </details>
  </div>;
}

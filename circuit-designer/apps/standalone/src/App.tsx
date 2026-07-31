import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { HttpCircuitDesignerBackend } from "@spec2gds/circuit-client-http";
import {
  CircuitDraft,
  exportCircuitJson,
  projectDocument,
  uniqueSlug,
  type CircuitDocument,
  type CircuitExport,
  type CircuitOperation,
  type CircuitProposal,
  type CircuitSnapshot,
  type ComponentDefinition,
  type EditLease,
  type NetEndpoint,
  type NetRoute,
  type NodeGeometry,
} from "@spec2gds/circuit-core";
import {
  createLayoutTask,
  layoutCircuitGraph,
  type LayoutResult,
} from "@spec2gds/circuit-layout";
import { CircuitDesignerCanvas, type CircuitCanvasMode } from "@spec2gds/circuit-react";
import {
  circuitDocumentFileContents,
  circuitDocumentFilename,
  parseCircuitDocumentJson,
  summarizeFileDiagnostics,
} from "./circuit-files";
import { standaloneExamples, type StandaloneExampleId } from "./examples";
import { linkedCircuitDocumentId } from "./launch-state";

type Selection = { kind: "node" | "net"; id: string } | null;
const operationId = (prefix: string) => `${prefix}_${crypto.randomUUID()}`;

function endpointFromTerminal(terminalKey: string, lsb: number, width: number): NetEndpoint {
  const slice = width > 0 ? { slice: { lsb, width } } : {};
  if (terminalKey.startsWith("boundary:")) {
    return { kind: "boundary", terminal_id: terminalKey.slice("boundary:".length), ...slice };
  }
  const separator = terminalKey.indexOf(":");
  return {
    kind: "instance",
    instance_id: terminalKey.slice(0, separator),
    terminal_id: terminalKey.slice(separator + 1),
    ...slice,
  };
}

export function App() {
  const [exampleId, setExampleId] = useState<StandaloneExampleId>("subsystem");
  const [linkedDocumentId, setLinkedDocumentId] = useState<string | undefined>(
    () => linkedCircuitDocumentId(window.location.search),
  );
  const initial = useMemo(() => standaloneExamples[exampleId].build(), [exampleId]);
  const backend = useMemo(
    () => new HttpCircuitDesignerBackend({
      baseUrl: import.meta.env.VITE_CIRCUIT_DESIGNER_API_BASE ?? "/api/circuit-designer/v1",
    }),
    [],
  );
  const [snapshot, setSnapshot] = useState<CircuitSnapshot>();
  const [document, setDocument] = useState<CircuitDocument>();
  const [lease, setLease] = useState<EditLease>();
  const [layout, setLayout] = useState<LayoutResult>();
  const [layoutProgress, setLayoutProgress] = useState("");
  const [selection, setSelection] = useState<Selection>(null);
  const [mode, setMode] = useState<CircuitCanvasMode>("select");
  const [message, setMessage] = useState("Ready. Unlock to make a private draft.");
  const [componentName, setComponentName] = useState("");
  const [endpointA, setEndpointA] = useState("");
  const [endpointB, setEndpointB] = useState("");
  const [netName, setNetName] = useState("");
  const [sliceLsb, setSliceLsb] = useState(0);
  const [sliceWidth, setSliceWidth] = useState(0);
  const [proposals, setProposals] = useState<CircuitProposal[]>([]);
  const [sourceDescription, setSourceDescription] = useState(standaloneExamples.subsystem.summary);
  const [openingFile, setOpeningFile] = useState(false);
  const draftRef = useRef<CircuitDraft>();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const priorMode = useRef<CircuitCanvasMode>("select");

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        if (linkedDocumentId) {
          const next = await backend.get(linkedDocumentId);
          if (!active) return;
          setSnapshot(next);
          setDocument(next.document);
          setLayout(undefined);
          setSelection(null);
          setLease(undefined);
          setSourceDescription("Projected from the specification editor through the direct-port adapter.");
          setMessage(`Opened source-owned projection at revision ${next.revision}. Return to the specification editor to change source.`);
          draftRef.current = undefined;
          return;
        }
        const created = await backend.create(initial, operationId("initialize"));
        let next = created.snapshot;
        let joined = false;
        if (created.status === "conflict") {
          next = await backend.get(initial.document_id);
          joined = true;
        }
        if (!next) {
          throw new Error(summarizeFileDiagnostics(created.diagnostics) || "The service rejected the example document.");
        }
        if (!active) return;
        setSnapshot(next);
        setDocument(next.document);
        setLayout(undefined);
        setSelection(null);
        setLease(undefined);
        setSourceDescription(standaloneExamples[exampleId].summary);
        setMessage(joined
          ? `Joined the existing REST session at revision ${next.revision}.`
          : `Created REST session at revision ${next.revision}.`);
        draftRef.current = undefined;
      } catch (reason) {
        if (!active) return;
        setSnapshot(undefined);
        setDocument(undefined);
        setLayout(undefined);
        setMessage(`Circuit Designer service unavailable: ${reason instanceof Error ? reason.message : String(reason)}`);
      }
    })();
    return () => { active = false; };
  }, [backend, exampleId, initial, linkedDocumentId]);

  const graph = useMemo(
    () => document ? projectDocument(document, lease ? "draft" : snapshot?.revision ?? "loading") : undefined,
    [document, lease, snapshot?.revision],
  );

  useEffect(() => {
    if (!graph) return;
    let active = true;
    layoutCircuitGraph(graph).then((result) => {
      if (active) setLayout(result);
    }).catch((reason) => {
      if (active) setMessage(`Layout failed: ${String(reason)}`);
    });
    return () => { active = false; };
  }, [graph]);

  useEffect(() => {
    if (!snapshot || !backend) return;
    void backend.listProposals(snapshot.document.document_id).then(setProposals);
  }, [backend, snapshot]);

  useEffect(() => {
    if (!snapshot) return;
    const documentId = snapshot.document.document_id;
    return backend.subscribe(documentId, (event) => {
      if (event.kind === "proposal.changed") {
        void backend.listProposals(documentId).then(setProposals).catch(() => undefined);
        return;
      }
      if (event.kind !== "document.changed" || lease) return;
      void backend.get(documentId).then((next) => {
        if (next.revision === snapshot.revision) return;
        setSnapshot(next);
        setDocument(next.document);
        setSelection(null);
        setLayout(undefined);
        setMessage(`REST session updated by another client to revision ${next.revision}.`);
      }).catch((reason) => {
        setMessage(`Could not refresh the REST session: ${reason instanceof Error ? reason.message : String(reason)}`);
      });
    });
  }, [backend, lease, snapshot?.document.document_id, snapshot?.revision]);

  useEffect(() => {
    const typing = (target: EventTarget | null) =>
      target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement;
    const down = (event: KeyboardEvent) => {
      if (typing(event.target)) return;
      if (event.key === "Escape") setMode("select");
      if (event.code === "Space" && !event.repeat) {
        event.preventDefault();
        priorMode.current = mode;
        setMode("pan");
      }
    };
    const up = (event: KeyboardEvent) => {
      if (event.code === "Space" && !typing(event.target)) {
        event.preventDefault();
        setMode(priorMode.current);
      }
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [mode]);

  function mutate(operation: CircuitOperation, success: string): boolean {
    const draft = draftRef.current;
    if (!draft) {
      setMessage("Unlock the document before editing.");
      return false;
    }
    const diagnostics = draft.apply(operation);
    const errors = diagnostics.filter((item) => item.severity === "error");
    if (errors.length) {
      setMessage(errors.map((item) => item.message).join(" · "));
      return false;
    }
    setDocument(draft.document);
    setMessage(success);
    return true;
  }

  async function unlock(): Promise<void> {
    if (!snapshot || !backend || lease) return;
    try {
      const nextLease = await backend.acquireLease(snapshot.document.document_id, "standalone-canvas");
      draftRef.current = new CircuitDraft(snapshot.document, snapshot.revision);
      setLease(nextLease);
      setDocument(draftRef.current.document);
      setMessage("Private draft opened. Save commits atomically; Cancel discards it.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function save(): Promise<void> {
    const draft = draftRef.current;
    if (!snapshot || !backend || !lease || !draft) return;
    if (!draft.dirty) {
      await cancel();
      return;
    }
    const result = await backend.commit(
      snapshot.document.document_id,
      draft.toBatch(operationId("draft_save")),
      lease.lease_id,
    );
    if (result.status !== "accepted" || !result.snapshot) {
      setMessage(result.diagnostics.map((item) => item.message).join(" · "));
      return;
    }
    await backend.releaseLease(snapshot.document.document_id, lease.lease_id);
    draftRef.current = undefined;
    setLease(undefined);
    setSnapshot(result.snapshot);
    setDocument(result.snapshot.document);
    downloadCircuitDocument(result.snapshot.document);
    setMessage(`Saved revision ${result.snapshot.revision} and downloaded ${circuitDocumentFilename(result.snapshot.document)}.`);
  }

  async function cancel(): Promise<void> {
    if (!snapshot || !backend || !lease) return;
    await backend.releaseLease(snapshot.document.document_id, lease.lease_id);
    draftRef.current?.cancel();
    draftRef.current = undefined;
    setLease(undefined);
    setDocument(snapshot.document);
    setMessage("Draft cancelled. No changes were persisted.");
  }

  function undoDraft(direction: "undo" | "redo"): void {
    const draft = draftRef.current;
    if (!draft) return;
    setDocument(direction === "undo" ? draft.undo() : draft.redo());
    setMessage(direction === "undo" ? "Draft change undone." : "Draft change redone.");
  }

  function addLocalComponent(): void {
    if (!document || !componentName.trim()) return;
    const componentId = uniqueSlug(componentName, document.components.map((item) => item.id));
    const instanceId = uniqueSlug(componentName, document.design.instances.map((item) => item.id));
    const component: ComponentDefinition = {
      id: componentId,
      label: componentName.trim(),
      origin: "local",
      editable: true,
      terminals: [
        { id: "input", label: "input", direction: "input", width: 1, category: "port" },
        { id: "output", label: "output", direction: "output", width: 1, category: "port" },
      ],
      parameters: [],
      appearance: { renderer_key: "generic", properties: {} },
    };
    if (!mutate({ operation_id: operationId("component"), type: "add_component", component }, "Local component definition created.")) return;
    mutate({
      operation_id: operationId("instance"),
      type: "add_instance",
      instance: { id: instanceId, label: componentName.trim(), component_id: componentId, parameter_values: {} },
    }, "Local component and first instance created.");
    setComponentName("");
  }

  function createNet(source: string, target: string, requestedName = ""): void {
    if (!document || !source || !target || source === target) return;
    const label = requestedName.trim() || `net ${document.design.nets.length + 1}`;
    const id = uniqueSlug(label, document.design.nets.map((item) => item.id));
    mutate({
      operation_id: operationId("net"),
      type: "create_net",
      net: {
        id,
        label,
        endpoints: [
          endpointFromTerminal(source, sliceLsb, sliceWidth),
          endpointFromTerminal(target, sliceLsb, sliceWidth),
        ],
      },
    }, `Created net “${label}”.`);
  }

  function moveNode(instanceId: string, geometry: NodeGeometry): void {
    mutate({
      operation_id: operationId("move"),
      type: "set_instance_geometry",
      instance_id: instanceId,
      geometry,
    }, `Moved ${instanceId}.`);
  }

  function saveRoute(netId: string, route: NetRoute): void {
    mutate({
      operation_id: operationId("route"),
      type: "set_net_route",
      net_id: netId,
      route,
    }, `Updated route ${netId}.`);
  }

  async function autoLayout(): Promise<void> {
    if (!document || !draftRef.current) {
      setMessage("Unlock before applying automatic layout.");
      return;
    }
    setLayoutProgress("Starting layout…");
    const task = createLayoutTask(document, {
      layout: { preserveNodeGeometry: "pinned" },
      onProgress: (phase, progress) => setLayoutProgress(`${phase} · ${Math.round(progress * 100)}%`),
    });
    try {
      const result = await task.result;
      for (const [instanceId, geometry] of Object.entries(result.document.layout.instance_geometry)) {
        mutate({
          operation_id: operationId("layout"),
          type: "set_instance_geometry",
          instance_id: instanceId,
          geometry,
        }, "Applying automatic layout…");
      }
      for (const [terminalKey, placement] of Object.entries(result.document.layout.terminal_placements)) {
        mutate({
          operation_id: operationId("placement"),
          type: "set_terminal_placement",
          terminal_key: terminalKey,
          placement,
        }, "Applying automatic layout…");
      }
      for (const [netId, route] of Object.entries(result.document.layout.net_routes)) saveRoute(netId, route);
      setMessage(`Automatic layout completed in ${result.elapsed_ms} ms.`);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLayoutProgress("");
    }
  }

  function triggerDownload(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.hidden = true;
    window.document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function downloadCircuitDocument(value: CircuitDocument): void {
    triggerDownload(
      new Blob([circuitDocumentFileContents(value)], { type: "application/json" }),
      circuitDocumentFilename(value),
    );
  }

  async function download(format: "json" | "svg" | "png"): Promise<void> {
    if (!snapshot || lease) {
      setMessage("Save or Cancel the private draft before downloading an authoritative file.");
      return;
    }
    if (format === "json") {
      downloadCircuitDocument(snapshot.document);
      setMessage(`Downloaded ${circuitDocumentFilename(snapshot.document)}.`);
      return;
    }
    try {
      const exported: CircuitExport = await backend.export(snapshot.document.document_id, { format });
      const data = typeof exported.data === "string"
        ? exported.data
        : exported.data.slice().buffer;
      triggerDownload(new Blob([data], { type: exported.media_type }), exported.filename);
      setMessage(`Exported ${format.toUpperCase()}.`);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function openCircuitFile(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const input = event.currentTarget;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    if (lease) {
      setMessage("Save or Cancel the private draft before opening another circuit file.");
      return;
    }

    setOpeningFile(true);
    try {
      const parsed = parseCircuitDocumentJson(await file.text());
      if (!parsed.valid) {
        setMessage(`Could not open ${file.name}: ${summarizeFileDiagnostics(parsed.diagnostics)}`);
        return;
      }
      const created = await backend.create(parsed.document, operationId("open_file"));
      let next = created.snapshot;
      let joined = false;
      if (created.status === "conflict") {
        const existing = await backend.get(parsed.document.document_id);
        if (exportCircuitJson(existing.document) !== exportCircuitJson(parsed.document)) {
          setMessage(
            `Could not open ${file.name}: a different REST session already uses document ID “${parsed.document.document_id}”.`,
          );
          return;
        }
        next = existing;
        joined = true;
      }
      if (!next) {
        setMessage(`Could not open ${file.name}: ${summarizeFileDiagnostics(created.diagnostics)}`);
        return;
      }
      draftRef.current = undefined;
      setSnapshot(next);
      setDocument(next.document);
      setLease(undefined);
      setSelection(null);
      setLayout(undefined);
      setProposals(await backend.listProposals(next.document.document_id));
      setLinkedDocumentId(undefined);
      window.history.replaceState({}, "", window.location.pathname);
      setSourceDescription(`Opened from ${file.name}; permanent changes are saved by downloading a new file.`);
      const warnings = parsed.diagnostics.filter((item) => item.severity === "warning");
      setMessage(
        `${joined ? "Joined matching session for" : "Opened"} ${file.name} at revision ${next.revision}`
        + (warnings.length ? ` with ${warnings.length} warning${warnings.length === 1 ? "" : "s"}.` : "."),
      );
    } catch (reason) {
      setMessage(`Could not open ${file.name}: ${reason instanceof Error ? reason.message : String(reason)}`);
    } finally {
      setOpeningFile(false);
    }
  }

  async function openHierarchy(componentId: string): Promise<void> {
    if (!document || !backend || draftRef.current?.dirty) {
      setMessage("Save or Cancel the current draft before navigating into a child design.");
      return;
    }
    try {
      const result = await backend.resolveComponentDesign(document.document_id, componentId);
      setMessage(result.status === "available" ? `Resolved child design ${result.document?.label}.` : result.message ?? "No child design is available.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function decideProposal(proposalId: string, decision: "accept" | "reject"): Promise<void> {
    if (!document || !backend) return;
    const result = await backend.decideProposal(document.document_id, proposalId, decision);
    setProposals(await backend.listProposals(document.document_id));
    if (result?.snapshot) {
      setSnapshot(result.snapshot);
      setDocument(result.snapshot.document);
    }
    setMessage(`Proposal ${decision === "accept" ? "accepted" : "rejected"}.`);
  }

  const selectedInstance = selection?.kind === "node"
    ? document?.design.instances.find((item) => item.id === selection.id)
    : undefined;
  const selectedNet = selection?.kind === "net"
    ? document?.design.nets.find((item) => item.id === selection.id)
    : undefined;
  const terminals = graph?.terminals ?? [];

  return <main className="standalone-shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark">CD</span><div><span>Independent v1</span><h1>Circuit Designer</h1></div></div>
      <label className="example-picker">Document<select value={linkedDocumentId ? "__linked__" : exampleId} onChange={(event) => {
        if (event.target.value === "__linked__") return;
        setSnapshot(undefined);
        setDocument(undefined);
        setLayout(undefined);
        setLinkedDocumentId(undefined);
        window.history.replaceState({}, "", window.location.pathname);
        setExampleId(event.target.value as StandaloneExampleId);
      }} disabled={!snapshot || Boolean(lease) || openingFile}>
        {linkedDocumentId && <option value="__linked__">Editor projection</option>}
        {Object.entries(standaloneExamples).map(([id, example]) => <option key={id} value={id}>{example.title}</option>)}
      </select></label>
      <div className="toolbar">
        {!lease && !linkedDocumentId && <button className="primary" onClick={() => void unlock()}>Unlock</button>}
        {!lease && linkedDocumentId && <button disabled title="This projection is owned by the specification editor.">Source-owned</button>}
        {lease && <><button disabled={!draftRef.current?.canUndo} onClick={() => undoDraft("undo")}>Undo</button><button disabled={!draftRef.current?.canRedo} onClick={() => undoDraft("redo")}>Redo</button><button className="primary" onClick={() => void save()}>Save</button><button onClick={() => void cancel()}>Cancel</button></>}
        <input
          ref={fileInputRef}
          className="file-input"
          type="file"
          accept=".json,application/json"
          aria-label="Circuit file"
          disabled={!snapshot || Boolean(lease) || openingFile}
          onChange={(event) => void openCircuitFile(event)}
        />
        <button disabled={!snapshot || Boolean(lease) || openingFile} onClick={() => fileInputRef.current?.click()}>
          {openingFile ? "Opening…" : "Open file"}
        </button>
        <button disabled={!snapshot || Boolean(lease)} onClick={() => void download("json")}>Download file</button>
        <button disabled={!snapshot || Boolean(lease)} onClick={() => void download("svg")}>SVG</button>
        <button disabled={!snapshot || Boolean(lease)} onClick={() => void download("png")}>PNG</button>
      </div>
    </header>
    <div className="notice"><span className="local-dot" />{linkedDocumentId ? "Editor projection" : "Independent document"} · {lease ? "private draft" : `revision ${snapshot?.revision ?? "…"}`}<span>{layoutProgress || message}</span></div>
    <section className="workspace">
      <aside className="library">
        <p className="eyebrow">Component catalog</p>
        <h2>{document?.label}</h2>
        <p>{sourceDescription}</p>
        <div className="metrics"><div><b>{document?.design.instances.length ?? 0}</b><span>Instances</span></div><div><b>{document?.design.nets.length ?? 0}</b><span>Nets</span></div></div>
        <div className="catalog-list">{document?.components.map((component) => <button key={component.id} onClick={() => setMessage(`${component.label}: ${component.terminals.length} terminals · ${component.origin}`)}><b>{component.label}</b><small>{component.origin} · {component.appearance.renderer_key}</small></button>)}</div>
        <div className="section"><h3>Local definition</h3><label>Name<input value={componentName} onChange={(event) => setComponentName(event.target.value)} placeholder="Arithmetic unit" /></label><button className="primary" disabled={!lease || !componentName.trim()} onClick={addLocalComponent}>Create definition + instance</button></div>
        <div className="section"><h3>Layout</h3><button disabled={!lease} onClick={() => void autoLayout()}>Arrange and route</button></div>
        <div className="section"><h3>Connect / bus slice</h3>
          <label>Net label<input value={netName} onChange={(event) => setNetName(event.target.value)} /></label>
          <label>Endpoint A<select value={endpointA} onChange={(event) => setEndpointA(event.target.value)}><option value="">Choose…</option>{terminals.map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.id}</option>)}</select></label>
          <label>Endpoint B<select value={endpointB} onChange={(event) => setEndpointB(event.target.value)}><option value="">Choose…</option>{terminals.filter((terminal) => terminal.id !== endpointA).map((terminal) => <option key={terminal.id} value={terminal.id}>{terminal.id}</option>)}</select></label>
          <div className="slice-row"><label>LSB<input type="number" min="0" value={sliceLsb} onChange={(event) => setSliceLsb(Number(event.target.value))} /></label><label>Width (0=full)<input type="number" min="0" value={sliceWidth} onChange={(event) => setSliceWidth(Number(event.target.value))} /></label></div>
          <button className="primary" disabled={!lease || !endpointA || !endpointB} onClick={() => { createNet(endpointA, endpointB, netName); setNetName(""); }}>Create net</button>
        </div>
        {proposals.length > 0 && <div className="section"><h3>Pending proposals</h3>{proposals.map((proposal) => <div className="proposal-card" key={proposal.proposal_id}><b>{proposal.title}</b><p>{proposal.summary}</p><small>{proposal.diff.added.length} added · {proposal.diff.changed.length} changed · {proposal.diff.removed.length} removed</small><button onClick={() => void decideProposal(proposal.proposal_id, "accept")}>Accept</button><button onClick={() => void decideProposal(proposal.proposal_id, "reject")}>Reject</button></div>)}</div>}
      </aside>
      <div className="stage">
        <div className="mode-toolbar">{(["select", "connect", "route", "pan"] as CircuitCanvasMode[]).map((item) => <button key={item} className={mode === item ? "active" : ""} onClick={() => setMode(item)}>{item}</button>)}</div>
        {!layout && <div className="loading">Computing flattened canvas projection…</div>}
        {graph && layout && <CircuitDesignerCanvas
          graph={graph}
          layout={layout.layout}
          boundaryGeometry={layout.boundary_geometry}
          editable={Boolean(lease)}
          mode={mode}
          onSelect={setSelection}
          onNodeGeometryChange={moveNode}
          onConnectTerminals={(source, target) => createNet(source, target)}
          onNetRouteChange={saveRoute}
          fitViewOnInit={false}
        />}
        {layout && <div className="layout-time">Grid router · {layout.elapsed_ms} ms</div>}
      </div>
      <aside className="inspector">
        <p className="eyebrow">Inspector</p>
        {!selection && <div className="empty-inspector"><span>⌁</span><p>Select an instance or net. Manual edits remain private until Save.</p></div>}
        {selectedInstance && document && <><span className="kind">instance</span><h2>{selectedInstance.label}</h2><code>{selectedInstance.id}</code>
          <label>Label<input value={selectedInstance.label} onChange={(event) => mutate({ operation_id: operationId("label"), type: "update_instance", instance: { ...selectedInstance, label: event.target.value || selectedInstance.id } }, "Instance label updated.")} disabled={!lease} /></label>
          <button onClick={() => void openHierarchy(selectedInstance.component_id)}>Open child design</button>
          <button className="danger" disabled={!lease} onClick={() => mutate({ operation_id: operationId("remove"), type: "remove_instance", instance_id: selectedInstance.id, cascade: true }, "Instance removed with explicit connectivity cascade.")}>Delete with cascade</button>
          <details><summary>Canonical data</summary><pre>{JSON.stringify(selectedInstance, null, 2)}</pre></details>
        </>}
        {selectedNet && <><span className="kind">net</span><h2>{selectedNet.label || selectedNet.id}</h2><code>{selectedNet.id}</code>
          <p className="draw-hint">{selectedNet.endpoints.map((endpoint) => JSON.stringify(endpoint)).join("\n")}</p>
          <button className="danger" disabled={!lease} onClick={() => mutate({ operation_id: operationId("delete_net"), type: "delete_net", net_id: selectedNet.id }, "Net deleted.")}>Delete net</button>
          <details><summary>Canonical data</summary><pre>{JSON.stringify(selectedNet, null, 2)}</pre></details>
        </>}
      </aside>
    </section>
  </main>;
}

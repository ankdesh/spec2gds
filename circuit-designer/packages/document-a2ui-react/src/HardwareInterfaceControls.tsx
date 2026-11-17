import React, { useEffect, useRef, useState } from "react";
import { SpecEditorHttpError, type EditorTransactionOperation, type EntityRef, type ParameterInput } from "@spec2gds/document-core";
import type { SectionEditState } from "./index";

export function HardwareModal({ title, children, cancel, busy = false }: { title: string; children: React.ReactNode; cancel(): void; busy?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const focus = document.activeElement as HTMLElement | null;
    dialog.current?.showModal();
    return () => { dialog.current?.close(); focus?.focus(); };
  }, []);
  return <dialog ref={dialog} className="spec-hardware-dialog" aria-label={title} onCancel={event => { event.preventDefault(); if (!busy) cancel(); }}><h3>{title}</h3>{children}</dialog>;
}

export function InternalDesignForm({ state }: { state: SectionEditState }) {
  const source = state.controller!.source!;
  const component = state.section.entity_ref!;
  const base = `${state.section.title.slice(0, 175)} internal Design`;
  const names = new Set([...source.components, ...source.designs].map(item => (item.display_name || item.vlnv.split(":")[2]).normalize("NFKC").toLocaleLowerCase()));
  let suggested = base; let suffix = 2;
  while (names.has(suggested.normalize("NFKC").toLocaleLowerCase())) suggested = `${base} ${suffix++}`;
  const [name, setName] = useState(suggested);
  const identity = useRef(`design_${Array.from(crypto.getRandomValues(new Uint32Array(4)), value => value.toString(16)).join("")}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef<EditorTransactionOperation>();
  const [uncertain, setUncertain] = useState(false);
  const pendingChoice = pending.current?.type === "create_internal_design" ? pending.current.sv_disposition : undefined;
  const hasSv = source.entity_sections.some(section => section.parent.entity_id === component.entity_id && section.section_type === "sv");
  const create = async (sv_disposition?: "retain_reference" | "remove") => {
    setBusy(true); setError("");
    const operation = pending.current ?? { type: "create_internal_design" as const, component, design_id: identity.current, name, sv_disposition };
    pending.current = operation;
    try { await state.controller!.applyOperations!([operation]); pending.current = undefined; setUncertain(false); state.cancel(); }
    catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught);
      const rejected = caught instanceof SpecEditorHttpError || message.startsWith("The saved source changed.");
      if (rejected) pending.current = undefined;
      setUncertain(!rejected);
      setError(rejected ? message : `Could not confirm creation. Retry the same choice to confirm its result. ${message}`);
    }
    finally { setBusy(false); }
  };
  return <HardwareModal title="Create internal Design" cancel={state.cancel} busy={busy || uncertain}>
    <form onSubmit={event => { event.preventDefault(); if (!hasSv) void create(); }}>
      <label>Design name<input autoFocus required maxLength={200} value={name} disabled={busy || uncertain} onChange={event => setName(event.target.value)} /></label>
      <p>This creates and assigns an empty internal Design in one save. It uses this Component’s ports and parameters. Begin editing in Circuit Designer before changing its circuit.</p>
      {hasSv && <p>Retain the SV Section as reference text excluded from implementation, or remove it.</p>}
      {error && <p className="spec-edit-error" role="alert">{error}</p>}
      <div className="spec-edit-actions">{hasSv ? <><button disabled={busy || !name.trim() || (uncertain && pendingChoice !== "retain_reference")} type="button" onClick={() => void create("retain_reference")}>Retain SV</button><button disabled={busy || !name.trim() || (uncertain && pendingChoice !== "remove")} type="button" onClick={() => void create("remove")}>Remove SV</button></> : <button disabled={busy} type="submit">Create internal Design</button>}<button disabled={busy || uncertain} type="button" onClick={state.cancel}>Cancel</button></div>
    </form>
  </HardwareModal>;
}

type Port = { originalName?: string; name: string; direction: string; range: string; description: string };
export function DesignInterfaceControls({ state }: { state: SectionEditState }) {
  const source = state.controller!.source!;
  const design = source.designs.find(item => item.ref.entity_id === state.section.entity_ref!.entity_id)!;
  const [ports, setPorts] = useState<Port[]>(() => design.ports?.map(p => ({ originalName: p.name, name: p.name, direction: p.direction, range: p.range || "", description: p.description || "" })) ?? []);
  const [parameters, setParameters] = useState<ParameterInput[]>(design.parameters ?? []);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try { await state.controller!.applyOperations!([{ type: "set_design_interface", design: design.ref, ports: ports.map(({ originalName: _, ...p }) => p), parameters, port_renames: Object.fromEntries(ports.filter(p => p.originalName && p.originalName !== p.name).map(p => [p.originalName!, p.name])) }]); state.cancel(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
    finally { setBusy(false); }
  };
  return <HardwareModal title="Edit Design interface" cancel={state.cancel} busy={busy}><form onSubmit={save}>
    <h4>Ports</h4><p>Ranges use saved Design parameters. Leave Range blank for a scalar port.</p>
    {ports.map((port, index) => <fieldset key={index} disabled={busy}><legend>Port {index + 1}</legend>
      <label>Port ID<input required value={port.name} onChange={e => setPorts(ports.map((p, i) => i === index ? { ...p, name: e.target.value } : p))} /></label>
      <label>Direction<select value={port.direction} onChange={e => setPorts(ports.map((p, i) => i === index ? { ...p, direction: e.target.value } : p))}><option value="in">Input</option><option value="out">Output</option><option value="inout">Bidirectional</option></select></label>
      <label>Range<input value={port.range} placeholder="DATA_WIDTH-1:0" onChange={e => setPorts(ports.map((p, i) => i === index ? { ...p, range: e.target.value } : p))} /></label>
      <label>Description<input value={port.description} onChange={e => setPorts(ports.map((p, i) => i === index ? { ...p, description: e.target.value } : p))} /></label>
      <button type="button" onClick={() => setPorts(ports.filter((_, i) => i !== index))}>Remove port</button>
    </fieldset>)}
    <button disabled={busy} type="button" onClick={() => setPorts([...ports, { name: "", direction: "in", range: "", description: "" }])}>Add port</button>
    <h4>Parameters</h4>
    {parameters.map((parameter, index) => <fieldset key={index} disabled={busy}><legend>Parameter {index + 1}</legend>{([ ["name", "Parameter ID"], ["rtl_type", "RTL type"], ["value", "Default expression"], ["description", "Description"] ] as const).map(([key, label]) => <label key={key}>{label}<input required={key === "name" || key === "value"} value={parameter[key]} onChange={e => setParameters(parameters.map((p, i) => i === index ? { ...p, [key]: e.target.value } : p))} /></label>)}<button type="button" onClick={() => setParameters(parameters.filter((_, i) => i !== index))}>Remove parameter</button></fieldset>)}
    <button disabled={busy} type="button" onClick={() => setParameters([...parameters, { name: "", rtl_type: "int unsigned", value: "1", description: "" }])}>Add parameter</button>
    {error && <p className="spec-edit-error" role="alert">{error}</p>}<div className="spec-edit-actions"><button disabled={busy} type="submit">Save interface to Spec</button><button disabled={busy} type="button" onClick={state.cancel}>Cancel</button></div>
  </form></HardwareModal>;
}

export function InstanceParameterForm({ state, name, cancel }: { state: SectionEditState; name: string; cancel(): void }) {
  const source = state.controller!.source!;
  const instance = source.designs.find(d => d.ref.entity_id === state.section.entity_ref!.entity_id)?.instances?.find(i => i.name === name);
  const definition = source.components.find(c => c.vlnv === instance?.component_vlnv);
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(instance?.parameter_values ?? []));
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  return <HardwareModal title={`Parameters for ${name}`} cancel={cancel} busy={busy}><form onSubmit={async event => { event.preventDefault(); if (!instance) return; setBusy(true); setError(""); try { await state.controller!.applyOperations!([{ type: "upsert_instance", design: state.section.entity_ref as EntityRef, instance: { name, component_vlnv: instance.component_vlnv, parameter_values: Object.fromEntries(Object.entries(values).filter(([, value]) => value.trim())) } }]); cancel(); } catch (caught) { setError(String(caught)); } finally { setBusy(false); } }}>
    <p>Use a Design parameter or a constant expression. Leave blank to use the Component default.</p>
    {definition?.parameters?.map(p => <label key={p.name}>{p.name}<input disabled={busy} placeholder={`Default: ${p.value}`} value={values[p.name] ?? ""} onChange={e => setValues({ ...values, [p.name]: e.target.value })} /></label>)}
    {!definition?.parameters?.length && <p>This Component has no parameters.</p>}
    {error && <p className="spec-edit-error" role="alert">{error}</p>}<div className="spec-edit-actions"><button disabled={busy} type="submit">Save parameters to Spec</button><button disabled={busy} type="button" onClick={cancel}>Cancel</button></div>
  </form></HardwareModal>;
}

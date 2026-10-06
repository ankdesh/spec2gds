/** Product UI layered onto native Harness session/workspace/slot services.
 * Follow configuration editor → reviewed save → pinned new-session selection
 * for authoring, and execution inspector → revision-carrying action for controls.
 * Native chat/tool history remains authoritative; DOM state cannot grant tools,
 * change an owner binding or approve replacement artifact content. */
/* Product-owned browser plugin loaded by the DSH module table. Keep this file plain
 * JavaScript so the distribution does not carry a second frontend toolchain. */
window.__ModuleLoader__.load({ id: "@spec2gds/harness-web", factory: (require) => {
  const module = { exports: {} };
  const React = require("react");
  const h = React.createElement;
  let openNativeSession = () => {};
  document.title = "spec2gds Assistant";

  const style = document.createElement("style");
  style.dataset.plugin = "@spec2gds/harness-assistant";
  style.textContent = `
    .s2g-editor{width:min(920px,100%);max-height:90vh;overflow:auto}.s2g-editor>label{display:grid;gap:4px;margin:8px 0}.s2g-editor textarea{width:100%;box-sizing:border-box;font:12px/1.4 monospace}.s2g-editor fieldset{border:1px solid #9aa5a2;border-radius:7px}.s2g-editor .s2g-inline{display:inline-flex;align-items:center;gap:4px;font-weight:400}.s2g-editor .s2g-inline input{width:auto}.s2g-editor svg{width:100%;max-height:350px}.s2g-editor pre,.s2g-inspector pre{max-height:300px;overflow:auto;white-space:pre-wrap}.s2g-inspector article{padding:8px;border:1px solid #9aa5a2}.s2g-inspector table{width:100%;text-align:left;font-size:11px}
    .s2g-brand{display:flex;align-items:center;gap:8px;font-weight:700;color:var(--text-primary,#171717)}
    .s2g-mark{display:grid;place-items:center;width:28px;height:28px;border-radius:8px;background:#176b5b;color:white;font:700 12px/1 system-ui}
    .s2g-review{margin:6px 0;padding:12px;border:1px solid color-mix(in srgb,#176b5b 28%,transparent);border-radius:10px;background:color-mix(in srgb,#176b5b 5%,transparent);font:13px/1.45 system-ui}
    .s2g-review header{display:flex;justify-content:space-between;gap:12px}.s2g-review h4{margin:0;font-size:14px}.s2g-state{text-transform:uppercase;font-size:10px;letter-spacing:.08em;color:#176b5b}
    .s2g-review details{margin-top:8px}.s2g-review pre{overflow:auto;max-height:260px;padding:8px;border-radius:7px;background:color-mix(in srgb,currentColor 5%,transparent);font-size:11px}
    .s2g-summary{margin:9px 0}.s2g-summary ul{margin:5px 0;padding-left:20px}.s2g-summary code{font-size:11px}
    .s2g-required{display:grid;gap:10px;margin-top:10px}.s2g-required label{display:grid;gap:4px;font-weight:600}.s2g-required label small{font-weight:400;color:var(--text-secondary,#52615e)}
    .s2g-required input{box-sizing:border-box;width:100%;padding:8px 9px;border:1px solid #9aa5a2;border-radius:7px;background:#fff;color:#17211f;caret-color:#17211f;-webkit-text-fill-color:#17211f;font:inherit}
    .s2g-required input:focus{outline:2px solid color-mix(in srgb,#176b5b 45%,transparent);outline-offset:1px}.s2g-required-status{margin:8px 0 0;color:#176b5b}
    .s2g-diff{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.s2g-diff small{display:block;margin-bottom:3px;font-weight:600}
    .s2g-actions{display:flex;gap:8px;margin-top:10px}.s2g-actions button{padding:5px 9px;border:1px solid #176b5b;border-radius:6px;background:transparent;color:inherit;cursor:pointer}.s2g-actions button.primary{background:#176b5b;color:#fff}
    .s2g-circuit{width:100%;height:180px;border-radius:8px;background:color-mix(in srgb,currentColor 3%,transparent)}
    .s2g-error{color:#b42318;margin-top:7px}
    .s2g-mask{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:20px;background:rgba(8,18,16,.48);backdrop-filter:blur(3px)}
    .s2g-dialog{width:min(520px,100%);padding:20px;border:1px solid color-mix(in srgb,#176b5b 35%,transparent);border-radius:14px;background:var(--dsw-surface-primary,#fff);box-shadow:0 18px 55px rgba(0,0,0,.24);color:var(--text-primary,#17211f);font:14px/1.45 system-ui}
    .s2g-dialog h2{margin:0 0 5px;font-size:20px}.s2g-dialog>p{margin:0 0 16px;color:var(--text-secondary,#52615e)}
    .s2g-dialog [hidden]{display:none!important}
    .s2g-form{display:grid;gap:12px}.s2g-form label{display:grid;gap:5px;font-weight:600}.s2g-form input,.s2g-form select{box-sizing:border-box;width:100%;padding:9px 10px;border:1px solid color-mix(in srgb,currentColor 22%,transparent);border-radius:7px;background:var(--dsw-surface-primary,#fff);color:inherit;font:inherit}
    .s2g-form .s2g-pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}.s2g-dialog-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:5px}.s2g-dialog-actions button{padding:8px 12px;border:1px solid #176b5b;border-radius:7px;background:transparent;color:inherit;cursor:pointer}.s2g-dialog-actions button.primary{background:#176b5b;color:#fff}.s2g-dialog-actions button:disabled{opacity:.55;cursor:wait}
    .s2g-choice{display:flex;gap:16px}.s2g-choice label{display:flex;align-items:center;gap:6px;font-weight:600}.s2g-choice input{width:auto}.s2g-hint{margin:0;color:var(--text-secondary,#52615e);font-size:12px}.s2g-empty{padding:10px;border:1px dashed color-mix(in srgb,currentColor 25%,transparent);border-radius:7px;color:var(--text-secondary,#52615e)}
    .s2g-workflow{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:8px;margin:4px 8px;padding:7px 9px;border:1px solid color-mix(in srgb,#176b5b 28%,transparent);border-radius:8px;background:color-mix(in srgb,#176b5b 5%,transparent);font:12px/1.35 system-ui}
    .s2g-workflow strong{font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#176b5b}.s2g-workflow-main{min-width:0}.s2g-workflow-objective{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.s2g-workflow-meta{color:var(--text-secondary,#52615e);font-size:10px}.s2g-workflow-controls{display:flex;align-items:center;gap:5px}.s2g-workflow button{padding:3px 7px;border:1px solid #176b5b;border-radius:5px;background:transparent;color:inherit;cursor:pointer}.s2g-workflow button:disabled{opacity:.5}.s2g-workflow input{min-width:170px;padding:4px 6px;border:1px solid color-mix(in srgb,currentColor 22%,transparent);border-radius:5px;background:var(--dsw-surface-primary,#fff);color:inherit}
  `;
  document.head.appendChild(style);

  async function api(path, body) {
    const response = await fetch(`/spec2gds-api${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || `Request failed (${response.status})`);
    return value;
  }

  const escapeHtml = value => String(value).replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  })[character]);

  const configuredServices = owners => ["spec", "circuit"].flatMap(domain =>
    (Array.isArray(owners?.[domain]) ? owners[domain] : []).map(item => ({ domain, url: item.url, available: item.available })));

  function targetRows(payload) {
    if (payload.domain === "spec" && Array.isArray(payload.documents)) {
      return payload.documents.flatMap(document => targetRows({ ...payload, documents: undefined, document, entities: document.entities }));
    }
    if (payload.domain === "spec" && payload.document) {
      const document = payload.document;
      return [{ domain: "spec", serviceBaseUrl: payload.serviceBaseUrl, documentId: String(document.document_id),
        serviceDocumentKey: document.owner_document_key,
        title: String(document.title || "Spec"), scope: "document" },
      ...(Array.isArray(payload.entities) ? payload.entities : []).map(entity => ({
        domain: "spec", serviceBaseUrl: payload.serviceBaseUrl, documentId: String(document.document_id),
        serviceDocumentKey: document.owner_document_key,
        title: `${entity.title || (entity.entity_kind === "design" ? "Design" : "Component")} · ${entity.entity_kind || "entity"}`,
        scope: "entity", entityKind: String(entity.entity_kind || "entity"), entityId: String(entity.entity_id),
      }))];
    }
    return (Array.isArray(payload.documents) ? payload.documents : []).map(document => ({
      domain: "circuit", serviceBaseUrl: payload.serviceBaseUrl, documentId: String(document.document_id),
      title: String(document.label || document.title || "Circuit"), scope: "document",
      sourceBinding: document.source_binding || null,
    }));
  }

  function belongsToWorkspace(target, workspace) {
    if (!workspace) return true;
    if (workspace.domain === target.domain && workspace.serviceUrl === target.serviceBaseUrl && workspace.documentId === target.documentId) return true;
    const source = target.sourceBinding;
    return target.domain === "circuit" && workspace.domain === "spec" && source
      && String(source.source_service_url || "").replace(/\/$/, "") === workspace.serviceUrl
      && source.source_document_id === workspace.documentId;
  }

  async function discoverTargets(services, workspace) {
    const results = await Promise.allSettled(services.filter(item => item.available !== false).map(async service => {
      const query = new URLSearchParams({ domain: service.domain, service_base_url: service.url });
      return targetRows(await api(`/targets?${query}`));
    }));
    return results.flatMap(result => result.status === "fulfilled" ? result.value : []).filter(target => belongsToWorkspace(target, workspace));
  }

  function trapDialogFocus(mask) {
    mask.addEventListener("keydown", event => {
      if(event.key!=="Tab"||[...document.querySelectorAll(".s2g-mask")].at(-1)!==mask)return;
      const controls=[...mask.querySelectorAll("button,input,select,textarea,a[href]")].filter(control=>!control.disabled&&control.tabIndex!==-1&&control.getClientRects().length);
      const first=controls[0], last=controls.at(-1);
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
    });
  }

  function reserveBindingDialog(workspace) {
    return new Promise(resolve => {
      const mask = document.createElement("div");
      mask.className = "s2g-mask";
      mask.innerHTML = `<section class="s2g-dialog" role="dialog" aria-modal="true" aria-labelledby="s2g-new-title">
        <h2 id="s2g-new-title">${workspace ? `New conversation in ${escapeHtml(workspace.title)}` : "Start a design conversation"}</h2>
        <p>${workspace ? "Choose the Spec or a Circuit derived from this design source." : "Choose an existing design source or create a new one."}</p>
        <form class="s2g-form">
          <div class="s2g-choice" data-mode ${workspace ? "hidden" : ""}><label><input type="radio" name="mode" value="existing" checked> Existing</label><label><input type="radio" name="mode" value="create"> Create new</label></div>
          <label data-service>Design service<select name="service"></select></label>
          <div data-manual hidden class="s2g-pair"><label>Service type<select name="manualDomain"><option value="spec">Spec Editor</option><option value="circuit">Circuit Designer</option></select></label><label>Service URL<input name="manualUrl" spellcheck="false" placeholder="http://127.0.0.1:6010"></label></div>
          <div data-existing><label>Target<select name="target"></select></label><p class="s2g-hint">The list is browse-only. A conversation remains permanently bound to the selected target.</p></div>
          <div data-create hidden class="s2g-form"><label>Name<input name="title" autocomplete="off" maxlength="200" placeholder="My design"></label><p class="s2g-hint">Specs are created under the configured Spec document root. Circuits start as empty documents.</p></div>
          <label>Assistant preset<select name="preset"><option value="focused">Focused · one-shot Q&amp;A and proposals</option><option value="goal">Goal · bounded long-running work</option><option value="orchestrated">Orchestrated · persistent event agents</option></select></label>
          <label data-event-setup hidden>Event template<select aria-label="Event template" name="eventTemplate"></select></label><button type="button" data-edit-template hidden>Configure event template</button>
          <p class="s2g-hint">The preset and agent configuration are fixed for this conversation. Service-specific context, tools, and review rules are added separately.</p>
          <p class="s2g-empty" data-empty hidden>No matching documents are available from the connected services.</p>
          <p class="s2g-error" hidden></p>
          <div class="s2g-dialog-actions"><button type="button" data-cancel>Cancel</button><button class="primary" type="submit">Start conversation</button></div>
        </form>
      </section>`;
      document.body.appendChild(mask); trapDialogFocus(mask);
      const form = mask.querySelector("form"), serviceSelect = form.elements.service, targetSelect = form.elements.target;
      const error = mask.querySelector(".s2g-error"), empty = mask.querySelector("[data-empty]");
      let services = [], targets = [], eventTemplates = [];
      const syncTemplates = () => {
        const service = services[Number(serviceSelect.value)], preset=form.elements.preset.value;
        const visible = eventTemplates.filter(item=>{const doc=JSON.parse(item.text);return doc.domain===service?.domain&&doc.preset===preset;});
        form.elements.eventTemplate.innerHTML=visible.map(item=>`<option value="${escapeHtml(item.key)}">${escapeHtml(item.name)} · revision ${item.revision}</option>`).join("");
        mask.querySelector("[data-event-setup]").hidden=preset==="focused";mask.querySelector("[data-edit-template]").hidden=preset==="focused";
      };
      form.elements.preset.addEventListener("change",syncTemplates);
      mask.querySelector("[data-edit-template]").addEventListener("click",async()=>{
        try {const service=services[Number(serviceSelect.value)];if(!service)throw new Error("Choose a connected service first.");const saved=await editEventTemplate(service.domain,form.elements.preset.value);eventTemplates=(await api("/event-templates")).templates;syncTemplates();if(saved)form.elements.eventTemplate.value=saved.key;}
        catch(caught){error.textContent=caught.message;error.hidden=false;}
      });
      const previousFocus = document.activeElement;
      const close = value => { document.removeEventListener("keydown", escape); mask.remove(); previousFocus?.focus(); resolve(value); };
      const escape = event => { if (event.key === "Escape" && [...document.querySelectorAll(".s2g-mask")].at(-1) === mask) close(null); };
      const setBusy = busy => [...form.querySelectorAll("button,select,input")].forEach(element => { element.disabled = busy; });
      const selectedMode = () => workspace ? "existing" : form.elements.mode.value;
      const renderTargets = () => {
        const selectedService = services[Number(serviceSelect.value)];
        const visible = targets.filter(target => !selectedService || (target.domain === selectedService.domain && target.serviceBaseUrl === selectedService.url));
        targetSelect.innerHTML = visible.map(target => `<option value="${targets.indexOf(target)}">${target.domain === "spec" ? "Spec" : "Circuit"} · ${escapeHtml(target.title)}</option>`).join("");
        empty.hidden = visible.length > 0;
        targetSelect.closest("label").hidden = visible.length === 0;
      };
      const renderServices = () => {
        serviceSelect.innerHTML = services.map((service, index) => `<option value="${index}">${service.domain === "spec" ? "Spec Editor" : "Circuit Designer"} · ${escapeHtml(service.url)}${service.available === false ? " (offline)" : ""}</option>`).join("")
          + (workspace ? "" : `<option value="manual">Connect another service…</option>`);
        renderTargets(); syncTemplates();
      };
      const syncMode = () => {
        const create = selectedMode() === "create";
        mask.querySelector("[data-existing]").hidden = create;
        mask.querySelector("[data-create]").hidden = !create;
        empty.hidden = create || targetSelect.options.length > 0;
      };
      serviceSelect.addEventListener("change", () => {
        const manual = serviceSelect.value === "manual";
        mask.querySelector("[data-manual]").hidden = !manual;
        if (!manual) { renderTargets(); syncTemplates(); }
      });
      for (const input of form.querySelectorAll("input[name=mode]")) input.addEventListener("change", syncMode);
      mask.querySelector("[data-cancel]").addEventListener("click", () => close(null));
      mask.addEventListener("mousedown", event => { if (event.target === mask) close(null); });
      document.addEventListener("keydown", escape);
      form.addEventListener("submit", async event => {
        event.preventDefault();
        setBusy(true); error.hidden = true;
        try {
          let service = services[Number(serviceSelect.value)];
          if (serviceSelect.value === "manual") {
            const manualUrl = form.elements.manualUrl.value.trim();
            const domain = form.elements.manualDomain.value;
            const connected = (await api("/services/connect", { domain, serviceBaseUrl: manualUrl })).service;
            service = { domain, url: connected.url, available: true };
            services.push(service);
            targets.push(...targetRows(await api(`/targets?${new URLSearchParams({ domain, service_base_url: connected.url })}`)));
            renderServices(); serviceSelect.value = String(services.length - 1); renderTargets(); syncMode(); setBusy(false);
            return;
          }
          if (!service) throw new Error("Choose a design service.");
          const preset = form.elements.preset.value;
          const template=eventTemplates.find(item=>item.key===form.elements.eventTemplate.value);
          const templateSelection=preset==="focused"?{}:{eventTemplateKey:template?.key,eventTemplateRevision:template?.revision};
          if (selectedMode() === "create") {
            const title = form.elements.title.value.trim();
            if (!title) throw new Error("Name is required.");
            close(await api("/sources/create", { domain: service.domain, serviceBaseUrl: service.url, title, preset, ...templateSelection }));
          } else {
            const target = targets[Number(targetSelect.value)];
            if (!target) throw new Error("Choose an available target.");
            close(await api("/bindings/reserve", { ...target, preset, ...templateSelection }));
          }
        } catch (caught) {
          error.textContent = caught instanceof Error ? caught.message : String(caught); error.hidden = false;
          setBusy(false);
        }
      });
      queueMicrotask(async () => {
        setBusy(true);
        try {
          const capabilities = await api("/capabilities");
          eventTemplates=(await api("/event-templates")).templates;
          services = configuredServices(capabilities.owners);
          if (workspace) services = services.filter(service => service.available !== false);
          targets = await discoverTargets(services, workspace);
          if (workspace) {
            const used = new Set(targets.map(target => `${target.domain}\0${target.serviceBaseUrl}`));
            services = services.filter(service => used.has(`${service.domain}\0${service.url}`));
          }
          renderServices(); syncMode();
        } catch (caught) {
          error.textContent = caught instanceof Error ? caught.message : String(caught); error.hidden = false;
        } finally { setBusy(false); serviceSelect.focus(); }
      });
    });
  }

  // Workspace paths identify sources. Display names can collide or change and
  // are disambiguated without changing the permanent source/binding identity.
  const workspaceRequests = new WeakMap();
  function ensureWorkspace(ctx, descriptor) {
    let requests = workspaceRequests.get(ctx);
    if (!requests) { requests = new Map(); workspaceRequests.set(ctx, requests); }
    if (requests.has(descriptor.path)) return requests.get(descriptor.path);
    const pending = createWorkspace(ctx, descriptor).finally(() => requests.delete(descriptor.path));
    requests.set(descriptor.path, pending);
    return pending;
  }

  async function createWorkspace(ctx, descriptor) {
    const existing = ctx.workspaces.list.getSnapshot().items.find(item => item.path === descriptor.path);
    const workspace = existing || await ctx.workspaces.create({ path: descriptor.path });
    if (workspace.title !== descriptor.title) {
      try { return await ctx.workspaces.rename(workspace.workspaceId, descriptor.title); }
      catch (error) {
        if (!String(error instanceof Error ? error.message : error).includes("workspace/name-conflict")) throw error;
        for (let number = 2; number < 10000; number++) {
          try { return await ctx.workspaces.rename(workspace.workspaceId, `${descriptor.title} ${number}`); }
          catch (caught) { if (!String(caught.message).includes("workspace/name-conflict")) throw caught; }
        }
        throw new Error("No available workspace name.");
      }
    }
    return workspace;
  }

  // The native session must use the exact host-reserved identity. Activating another
  // ID would detach the displayed chat from its permanent owner/configuration pin.
  async function createBoundSession(ctx, reserved, workspaceContext, options = {}) {
    let reservation = reserved;
    if (!reservation) {
      reservation = await reserveBindingDialog(workspaceContext);
      if (!reservation) return;
    }
    const id = reservation.session.sessionId;
    try {
      const descriptor = reservation.workspace || {
        key: reservation.session.workspaceKey,
        title: reservation.session.workspaceTitle,
        path: reservation.session.workspacePath,
        domain: reservation.session.workspaceDomain,
        serviceUrl: reservation.session.workspaceServiceUrl,
        documentId: reservation.session.workspaceDocumentId,
      };
      const workspace = await ensureWorkspace(ctx, descriptor);
      const known = options.preserveReservation && ctx.sessions.list?.getSnapshot().byId?.[id];
      const createdId = known ? id : await ctx.sessions.create({
        sessionId: id,
        workspaceId: workspace.workspaceId,
        agentPreset: reservation.session.preset || "focused",
      });
      if (createdId !== id) throw new Error(`The Harness created session ${createdId} instead of reserved binding ${id}.`);
      await api(`/bindings/${encodeURIComponent(id)}/activate`, {});
      if (ctx.workspaces.refresh) await ctx.workspaces.refresh();
      else if (ctx.sessions.refresh) await ctx.workspaces.create({ path: descriptor.path });
      await ctx.sessions.refresh?.();
      if (options.open !== false) ctx.sessions.open(createdId);
      return createdId;
    } catch (error) {
      if (!options.preserveReservation) await api(`/bindings/${encodeURIComponent(id)}/abandon`, {}).catch(() => undefined);
      throw error;
    }
  }

  async function continueSourceCreation(ctx, reserved) {
    const sessionId = await createBoundSession(ctx, reserved, undefined, { open: false, preserveReservation: true });
    if (!reserved.continuation.sent) {
      const session = ctx.sessions.binding(sessionId)?.session;
      if (!session) throw new Error("The Spec conversation is not ready. Retry this card to continue in the saved package.");
      const result = await session.prompt([{ type: "text", text: reserved.continuation.message }], "queue", undefined, reserved.continuation.requestId);
      if (!result.ok) throw new Error(result.error?.message || "The initial request could not be submitted. Retry this card.");
      await api(`/source-requests/${encodeURIComponent(reserved.creation_request.requestId)}/continued`, {});
    }
    ctx.sessions.open(sessionId);
  }

  async function createUnboundSession(ctx) {
    const descriptor = (await api("/workspaces")).unbound_workspace;
    const workspace = descriptor ? await ensureWorkspace(ctx, descriptor) : null;
    const sessionId = await ctx.sessions.create({ agentPreset: "focused", ...(workspace ? { workspaceId: workspace.workspaceId } : {}) });
    if (ctx.workspaces.refresh) await ctx.workspaces.refresh();
    else if (workspace && ctx.sessions.refresh) await ctx.workspaces.create({ path: descriptor.path });
    await ctx.sessions.refresh?.();
    ctx.sessions.open(sessionId);
  }

  function resultContentValue(content) {
    if (!Array.isArray(content) || content.length !== 1 || content[0]?.type !== "text") return null;
    try { return JSON.parse(content[0].text); } catch { return null; }
  }

  const roleName = value => String(value || "Assistant").replaceAll("_", " ").replaceAll("-", " ").replace(/(^| )([a-z])/g, (_, prefix, character) => prefix + character.toUpperCase());
  const pretty = value => JSON.stringify(value, null, 2);
  const record = value => value && typeof value === "object" && !Array.isArray(value) ? value : {};

  function SpecDiff({ preview }) {
    const changes = Array.isArray(record(preview).diff) ? record(preview).diff : [];
    if (!changes.length) return h("p", null, "No semantic section changes reported.");
    return h("div", null, changes.map((change, index) => {
      const item = record(change);
      return h("section", { key: index }, h("p", null, `${item.label || "Section"} · ${item.change || "changed"}`),
        h("details", null, h("summary", null, "Technical details"),
        h("code", null, item.path), h("button", { onClick: () => navigator.clipboard.writeText(pretty(item)) }, "Copy details"),
        h("div", { className: "s2g-diff" },
          h("div", null, h("small", null, "Before"), h("pre", null, pretty(item.before))),
          h("div", null, h("small", null, "After"), h("pre", null, pretty(item.after))))));
    }));
  }

  function CircuitGraph({ document, diff, side }) {
    const doc = record(document), design = record(doc.design);
    const instances = Array.isArray(design.instances) ? design.instances.map(record) : [];
    const nets = Array.isArray(design.nets) ? design.nets.map(record) : [];
    const changed = new Set([...(diff.added || []), ...(diff.removed || []), ...(diff.changed || [])].map(item => `${record(item).kind}:${record(item).id}`));
    const width = 420, height = 170, step = Math.max(85, Math.floor(width / Math.max(1, instances.length)));
    const points = new Map(instances.map((item, index) => [String(item.id), { x: 20 + index * step, y: 52 + (index % 2) * 55 }]));
    const lines = [];
    for (const net of nets) {
      const endpoints = Array.isArray(net.endpoints) ? net.endpoints.map(record).filter(item => item.kind === "instance") : [];
      for (let index = 1; index < endpoints.length; index++) {
        const a = points.get(String(endpoints[index - 1].instance_id)), b = points.get(String(endpoints[index].instance_id));
        if (a && b) lines.push(h("line", { key: `${net.id}:${index}`, x1: a.x + 52, y1: a.y + 18, x2: b.x + 52, y2: b.y + 18, stroke: changed.has(`net:${net.id}`) ? "#d97706" : "#87928f", strokeWidth: 2 }));
      }
    }
    return h("div", null, h("small", null, side), h("svg", { className: "s2g-circuit", viewBox: `0 0 ${width} ${height}` }, lines,
      instances.map(item => {
        const point = points.get(String(item.id));
        return h("g", { key: item.id }, h("rect", { x: point.x, y: point.y, width: 104, height: 36, rx: 6, fill: changed.has(`instance:${item.id}`) ? "#fef3c7" : "#e8f2ef", stroke: changed.has(`instance:${item.id}`) ? "#d97706" : "#176b5b" }), h("text", { x: point.x + 52, y: point.y + 22, textAnchor: "middle", fontSize: 11, fill: "#17211f" }, String(item.label || "Instance")));
      })));
  }

  function CircuitDiff({ preview }) {
    const value = record(preview), diff = record(value.diff);
    const base = value.base_document, candidate = value.candidate || record(value.snapshot).document;
    const counts = ["added", "removed", "changed", "connections_changed"].map(key => `${key.replaceAll("_", " ")}: ${Array.isArray(diff[key]) ? diff[key].length : 0}`).join(" · ");
    return h("div", null, h("p", null, counts), base && candidate ? h("div", { className: "s2g-diff" }, h(CircuitGraph, { document: base, diff, side: "Before" }), h(CircuitGraph, { document: candidate, diff, side: "After" })) : null);
  }

  function ReviewCard({ review: initial }) {
    const [review, setReview] = React.useState(initial);
    React.useEffect(() => { setReview(initial); }, [initial.proposalId, initial.state]);
    const [busy, setBusy] = React.useState(false);
    const [error, setError] = React.useState("");
    const artifact = record(review.artifact), operations = artifact.operations || record(artifact.batch).operations;
    const actionable = ["ready", "rejected", "stale", "reconcile"].includes(review.state);
    async function act(action, deliveryId) {
      setBusy(true); setError("");
      try { setReview((await api(`/reviews/${encodeURIComponent(review.proposalId)}/actions`, { action })).review); }
      catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
      finally { setBusy(false); }
    }
    return h("article", { className: "s2g-review" },
      h("header", null, h("h4", null, `${review.reviewNumber ? `Review ${review.reviewNumber} · ` : ""}${artifact.title || "Design proposal"}`), h("span", { className: "s2g-state", role: "status" }, review.state === "applied" && record(review.serviceResult).application_mode === "automatic" ? "Applied automatically" : review.state)),
      review.state === "applied" ? h("small", null, "Changes saved") : null,
      h("section", { className: "s2g-summary" },
        h("p", null, record(review.changeSummary).text || "Proposal summary unavailable."),
        Array.isArray(record(review.changeSummary).changedTargets) && record(review.changeSummary).changedTargets.length
          ? h("ul", null, record(review.changeSummary).changedTargets.map(target => h("li", { key: target }, h("code", null, target))))
          : null),
      review.error ? h("section", { className: "s2g-error" },
        h("strong", null, String(record(review.error).error_code || "PROPOSAL_ERROR")),
        h("p", null, String(record(review.error).details || "The proposal was not accepted.")),
        h("small", null, record(review.error).retryable ? "This may be retried after the underlying condition changes." : "No automatic retry will be attempted.")) : null,
      review.domain === "spec" ? h(SpecDiff, { preview: review.preview }) : h(CircuitDiff, { preview: review.preview }),
      h("details", null, h("summary", null, "Technical details"), h("button", { onClick: () => navigator.clipboard.writeText(pretty(review)) }, "Copy details"), h("pre", null, pretty({ operations, proposal: review.proposalId, saved_revision: record(review.serviceResult).source_revision_hash }))),
      h("details", null, h("summary", null, "Requested change, rationale, assumptions, and service preview"), h("pre", null, pretty({ requested_change: artifact.summary, rationale: artifact.rationale, assumptions: artifact.assumptions, preview: review.preview, diagnostics: review.diagnostics }))),
      actionable ? h("div", { className: "s2g-actions" }, h("button", { disabled: busy, onClick: () => act("discard") }, "Discard"), ["ready", "reconcile"].includes(review.state) ? h("button", { className: "primary", disabled: busy, onClick: () => act(review.domain === "spec" ? "apply" : "send") }, review.state === "reconcile" ? "Reconcile" : review.domain === "spec" ? "Save to Spec" : "Send to Circuit Designer") : null) : null,
      error ? h("p", { className: "s2g-error" }, error) : null);
  }

  function ProposalErrorCard({ error }) {
    const value = record(error);
    const actions = Array.isArray(value.suggested_actions) ? value.suggested_actions : [];
    return h("article", { className: "s2g-review" },
      h("header", null, h("h4", null, "Proposal not created"), h("span", { className: "s2g-state" }, value.error_code || "ERROR")),
      h("p", { className: "s2g-error" }, value.details || "The request could not be represented safely."),
      value.target ? h("details", null, h("summary", null, "Technical details"), h("pre", null, pretty(value))) : null,
      actions.length ? h("ul", null, actions.map(action => h("li", { key: action }, action))) : null,
      h("small", null, value.retryable ? "Retryable after the underlying condition changes." : "No automatic retry will be attempted."));
  }

  function requiredInputMessage(request, values) {
    return JSON.stringify({ kind: "confirmed_proposal_input", input_id: request.input_id, values,
      instruction: request.confirmation_instruction });
  }

  function ProposalInputCard({ request, inputActions }) {
    const value = record(request);
    const fields = (Array.isArray(value.fields) ? value.fields : []).map(record);
    const [values, setValues] = React.useState(() => Object.fromEntries(fields.map(field => [String(field.name), String(field.default_value || "")])));
    const [submitted, setSubmitted] = React.useState(false);
    const [error, setError] = React.useState("");
    async function submit(event) {
      event.preventDefault();
      const missing = fields.find(field => !String(values[field.name] || "").trim());
      if (missing) { setError(`${String(missing.label || missing.name)} is required.`); return; }
      setError("");
      try { await api(`/proposal-inputs/${encodeURIComponent(String(value.input_id))}/confirm`, { values }); }
      catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); return; }
      setSubmitted(true);
      inputActions.setDraft(requiredInputMessage(value, values));
      queueMicrotask(() => inputActions.submit());
    }
    return h("article", { className: "s2g-review", "data-s2g-required-input": submitted ? "submitted" : "pending" },
      h("header", null, h("h4", null, value.title || "Complete the proposal details"), h("span", { className: "s2g-state" }, submitted ? "SUBMITTED" : "INPUT REQUIRED")),
      h("p", null, value.description || "Review the defaults and fill in the required values."),
      submitted ? h("p", { className: "s2g-required-status" }, "Details submitted. The Assistant is continuing the proposal.")
        : h("form", { className: "s2g-required", onSubmit: submit },
          fields.map(field => h("label", { key: field.name }, String(field.label || field.name),
            field.description ? h("small", null, String(field.description)) : null,
            h("input", {
              name: String(field.name), value: String(values[field.name] || ""), required: true,
              onChange: event => setValues(current => ({ ...current, [field.name]: event.target.value })),
            }))),
          error ? h("p", { className: "s2g-error" }, error) : null,
          h("div", { className: "s2g-actions" }, h("button", { className: "primary", type: "submit" }, value.submit_label || "Continue proposal"))));
  }

  function ArchitectureReviewCard({ request, inputActions }) {
    const [value, setValue] = React.useState(request);
    const [feedback, setFeedback] = React.useState("");
    const [busy, setBusy] = React.useState(false);
    const [error, setError] = React.useState("");
    React.useEffect(() => {
      let mounted = true;
      api(`/architecture-reviews/${encodeURIComponent(request.reviewId)}`)
        .then(result => { if (mounted) setValue(result.architecture_review); })
        .catch(caught => { if (mounted) setError(caught.message); });
      return () => { mounted = false; };
    }, [request.reviewId]);
    async function decide(action) {
      if (busy) return;
      setBusy(true); setError("");
      try {
        const result = await api(`/architecture-reviews/${encodeURIComponent(value.reviewId)}/${action}`, { feedback });
        setValue(result.architecture_review);
        if (action !== "cancel") {
          inputActions.setDraft(result.continuation);
          queueMicrotask(() => inputActions.submit());
        }
      } catch (caught) { setError(caught.message); }
      finally { setBusy(false); }
    }
    const plan = record(value.plan);
    return h("article", { className: "s2g-review", "data-s2g-architecture-review": value.status },
      h("header", null, h("h4", null, `${value.reviewNumber ? `Review ${value.reviewNumber} · ` : ""}${plan.title || "Architecture review"}`), h("span", { className: "s2g-state" }, value.status)),
      ["components", "designs", "interfaces", "clocks_resets", "decomposition_rationale", "assumptions", "open_questions", "concrete_configuration"].map(key =>
        h("details", { key, open: true }, h("summary", null, key.replaceAll("_", " ")), h("pre", null, typeof plan[key] === "string" ? plan[key] : pretty(plan[key])))),
      value.status === "pending" ? h("div", null,
        h("label", null, "Revision feedback", h("textarea", { value: feedback, onChange: event => setFeedback(event.target.value) })),
        h("div", { className: "s2g-actions" },
          h("button", { disabled: busy, onClick: () => decide("cancel") }, "Cancel"),
          h("button", { disabled: busy, onClick: () => decide("revise") }, "Revise architecture"),
          h("button", { className: "primary", disabled: busy || Boolean(plan.open_questions?.length), onClick: () => decide("approve") }, "Approve architecture"))) : null,
      error ? h("p", { className: "s2g-error", role: "alert" }, error) : null);
  }

  function SourceCreationCard({ request, onContinue, onOpen }) {
    const [value, setValue] = React.useState(request);
    const [values, setValues] = React.useState(() => ({ documentId: request.documentId, title: request.title, serviceBaseUrl: request.serviceBaseUrl }));
    const [busy, setBusy] = React.useState(true);
    const [error, setError] = React.useState("");
    const [automaticAttempted, setAutomaticAttempted] = React.useState(false);
    React.useEffect(() => {
      let mounted = true;
      api(`/source-requests/${encodeURIComponent(request.requestId)}`).then(result => {
        if (!mounted) return;
        setValue(result.creation_request);
        setValues({ documentId: result.creation_request.documentId, title: result.creation_request.title, serviceBaseUrl: result.creation_request.serviceBaseUrl });
      }).catch(caught => { if (mounted) setError(caught.message); })
        .finally(() => { if (mounted) setBusy(false); });
      return () => { mounted = false; };
    }, [request.requestId]);
    React.useEffect(() => {
      if (busy || automaticAttempted || !value.automatic || value.status !== "reserved" || !value.reservation || !value.continuation) return;
      setAutomaticAttempted(true);
      setBusy(true);
      onContinue({ ...value.reservation, creation_request: value, continuation: value.continuation })
        .then(() => setValue(current => ({ ...current, status: "continued", error: null })))
        .catch(caught => setError(caught instanceof Error ? caught.message : String(caught)))
        .finally(() => setBusy(false));
    }, [busy, automaticAttempted, value.status, value.automatic, value.reservation, value.continuation]);
    const editable = value.status === "pending";
    const services = Array.isArray(value.services) ? value.services : [];
    const unavailable = editable && !services.some(service => service.url === values.serviceBaseUrl && service.available);
    const saved = ["created", "reserved", "continued"].includes(value.status);
    const path = editable ? value.specDocumentRoot : value.destination;
    const update = name => event => setValues(current => ({ ...current, [name]: event.target.value }));
    async function refresh() {
      const result = await api(`/source-requests/${encodeURIComponent(request.requestId)}`);
      setValue(result.creation_request);
      if (result.creation_request.status !== "pending") setValues({ documentId: result.creation_request.documentId, title: result.creation_request.title, serviceBaseUrl: result.creation_request.serviceBaseUrl });
    }
    async function submit(event) {
      event.preventDefault();
      if (busy) return;
      setBusy(true); setError("");
      try {
        const reserved = await api("/sources/create", { domain: "spec", creationRequestId: value.requestId, ...values });
        setValue(reserved.creation_request);
        await onContinue(reserved);
        setValue(current => ({ ...current, status: "continued", error: null }));
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : String(caught));
        await refresh().catch(() => undefined);
      } finally { setBusy(false); }
    }
    async function cancel() {
      if (busy) return;
      setBusy(true); setError("");
      try { setValue((await api(`/source-requests/${encodeURIComponent(value.requestId)}/cancel`, {})).creation_request); }
      catch (caught) { setError(caught.message); }
      finally { setBusy(false); }
    }
    const terminal = ["continued", "cancelled"].includes(value.status)
      || (value.status === "uncertain" && !value.creationReceipts);
    return h("article", { className: "s2g-review", "data-s2g-source-creation": value.status },
      h("header", null, h("h4", null, "Create a specification"), h("span", { className: "s2g-state" }, value.status)),
      h("p", null, value.status === "cancelled" ? "Creation cancelled. No package was created."
        : saved ? "The package is saved. Its contents follow the Spec Editor approval policy."
          : "Review the suggested names. Creating the package opens a new conversation and continues your original request there."),
      value.status !== "cancelled" ? h("p", null, "Save location: ", h("code", null, path)) : null,
      error || value.error ? h("p", { className: "s2g-error", role: "alert" }, error || value.error) : null,
      !terminal ? h("form", { className: "s2g-form", onSubmit: submit },
        h("label", null, "Name", h("input", { name: "title", value: values.title, disabled: busy || !editable, required: true, maxLength: 200, onChange: update("title") })),
        services.length > 1 ? h("label", null, "Spec service", h("select", { value: values.serviceBaseUrl, disabled: busy || !editable, onChange: update("serviceBaseUrl") },
          services.map(service => h("option", { key: service.url, value: service.url }, `${service.url}${service.available ? "" : " (offline)"}`)))) : null,
        unavailable ? h("p", { className: "s2g-error" }, "The selected Spec service is offline or none is configured. Start the service, then refresh availability.") : null,
        h("div", { className: "s2g-actions" },
          editable ? h("button", { type: "button", disabled: busy, onClick: cancel }, "Cancel") : null,
          h("button", { type: "button", disabled: busy, onClick: () => { setBusy(true); refresh().catch(caught => setError(caught.message)).finally(() => setBusy(false)); } }, "Refresh"),
          value.status !== "creating" ? h("button", { className: "primary", type: "submit", disabled: busy || unavailable }, value.status === "uncertain" ? "Recover creation receipt" : saved ? "Continue in Spec conversation" : "Create Spec and continue") : null)) : null,
      value.status === "continued" ? h("div", { className: "s2g-actions" }, h("button", { type: "button", onClick: () => onOpen(value.destinationSessionId) }, "Open Spec conversation")) : null);
  }

  const proposalToolNames = new Set(["prepare_spec_proposal", "prepare_circuit_proposal", "prepare_spec_document_creation", "prepare_architecture_review"]);

  const proposalReviewsDefinition = {
    kind: "spec2gds-proposal-reviews",
    match(event) {
      if (event.type === "turn/start") return { id: String(event.data.turn), role: "start" };
      if (event.type === "tool/call" || event.type === "tool/result" || event.type === "turn/end") return { id: String(event.data.turn), role: "update" };
      return null;
    },
    start(_context, match) {
      if (match.event.type !== "turn/start") throw new Error("proposal review tracking requires turn/start");
      return { turn: match.event.data.turn, calls: new Map(), results: [] };
    },
    update(context, match) {
      if (match.event.type === "turn/end") return { ...context.state,
        blockedSeq: match.event.data.reason?.kind === "blocked" ? match.event.seq : null };
      if (match.event.type === "tool/call") {
        if (!proposalToolNames.has(match.event.data.name)) return context.state;
        const calls = new Map(context.state.calls);
        calls.set(String(match.event.data.callId), match.event.data.name);
        return { ...context.state, calls };
      }
      if (match.event.type !== "tool/result") return context.state;
      const callId = String(match.event.data.message.source.callId);
      if (!context.state.calls.has(callId)) return context.state;
      const block = match.event.data.message.content[0];
      const toolName = context.state.calls.get(callId);
      const creationTool = ["prepare_architecture_review", "prepare_spec_document_creation"].includes(toolName);
      const value = creationTool && block?.isError
        ? { creation_error: (block.content || []).filter(item => item.type === "text").map(item => item.text).join("\n") || "Tool arguments were rejected." }
        : resultContentValue(block?.content);
      if (!value?.review && !value?.error && !value?.required_input && !value?.source_creation && !value?.creation_error && !value?.architecture_review) return context.state;
      const result = { callId, toolName, seq: match.event.seq, review: value.review || null, error: value.error || null, requiredInput: value.required_input || null,
        architectureReview: value.architecture_review || null, sourceCreation: value.source_creation || null, creationError: value.creation_error || null };
      return { ...context.state, results: [...context.state.results.filter(item => item.callId !== callId), result] };
    },
    buildLocationData(context, scope, previous) {
      if (scope !== "turn" || !context.state) return null;
      if (previous?.kind === "turn" && previous.turn === context.state.turn
        && previous.key === "spec2gds-proposal-reviews" && previous.value.results === context.state.results
        && previous.value.blockedSeq === context.state.blockedSeq) return previous;
      return { kind: "turn", turn: context.state.turn, key: "spec2gds-proposal-reviews", value: { results: context.state.results, blockedSeq: context.state.blockedSeq } };
    },
  };

  function selectProposalReview(owner) {
    const data = owner.turn.data.get("spec2gds-proposal-reviews");
    const results = data?.results || [];
    const visible = results.filter(result => result.seq < owner.seq);
    const latest = visible.at(-1);
    if (!latest) return null;
    // Approval controls must survive a later tool error in the same turn.
    const reviews = new Map();
    for (const result of visible) {
      if (result.architectureReview) reviews.set(result.architectureReview.reviewId, result.architectureReview);
    }
    reviews.delete(latest.architectureReview?.reviewId);
    return { ...latest, blocked: data?.blockedSeq != null && data.blockedSeq <= owner.seq,
      earlierArchitectureReviews: [...reviews.values()] };
  }

  function ProposalReviewTail({ matched, inputActions, onContinueCreation, onOpenCreation }) {
    if (matched.earlierArchitectureReviews?.length) return h("div", null,
      matched.earlierArchitectureReviews.map(request => h(ArchitectureReviewCard, { key: request.reviewId, request, inputActions })),
      h(ProposalReviewTail, { matched: { ...matched, earlierArchitectureReviews: [] }, inputActions, onContinueCreation, onOpenCreation }));
    if (matched.architectureReview) return h(ArchitectureReviewCard, { key: matched.architectureReview.reviewId, request: matched.architectureReview, inputActions });
    if (matched.sourceCreation) return h(SourceCreationCard, { key: matched.sourceCreation.requestId, request: matched.sourceCreation, onContinue: onContinueCreation, onOpen: onOpenCreation });
    if (matched.creationError) return h("article", { className: "s2g-review", role: "alert" },
      h("h4", null, matched.toolName === "prepare_architecture_review" ? "Architecture review could not be prepared" : "Spec creation unavailable"),
      h("p", { className: "s2g-error" }, matched.creationError),
      matched.blocked ? h("p", null, "The turn stopped before this request completed. Correct the reported fields before retrying.") : null);
    if (matched.review) return h(ReviewCard, { review: matched.review });
    if (matched.requiredInput) return h(ProposalInputCard, { request: matched.requiredInput, inputActions });
    return h(ProposalErrorCard, { error: matched.error });
  }

  // The visual form and text panel share one canonical configuration document.
  // Saving needs the server-reviewed text/revision; changing fields invalidates
  // that acknowledgement rather than approving edits via local DOM state.
  async function editEventTemplate(domain, preset, sources = []) {
    const catalog = await api("/event-templates");
    const templates = catalog.templates.filter(template => { const doc = JSON.parse(template.text); return doc.domain === domain && doc.preset === preset; });
    let selected = templates[0], draft = JSON.parse(selected.text), preview = null, validationGeneration = 0;
    return new Promise(resolve => {
      const mask = document.createElement("div"); mask.className = "s2g-mask";
      mask.innerHTML = `<section class="s2g-dialog s2g-editor" role="dialog" aria-modal="true" aria-labelledby="s2g-editor-title">
        <h2 id="s2g-editor-title">Event setup · ${escapeHtml(preset)}</h2>
        <p>Edit reactions between agents and events. Saved templates apply to new conversations.</p>
        <label>Template<select data-template></select></label><label>Template name<input data-name></label>
        <div data-topology aria-label="Event topology"></div>
        <details open><summary>Visual configuration</summary><form class="s2g-form" data-visual></form></details>
        <details><summary>Text definition (JSON / YAML subset)</summary><label>Configuration text<textarea data-text rows="18" spellcheck="false"></textarea></label><button data-import>Apply text to visual editor</button></details>
        <p class="s2g-hint">Exact event types select reactions. Payloads must match their contracts. Providers, tools, and native compositions are limited by the deployment. HTTP sources are configured separately in each conversation.</p>
        <p data-error role="alert" class="s2g-error"></p><section data-preview hidden aria-label="Configuration review"></section>
        <div class="s2g-dialog-actions"><button data-cancel>Close</button><button data-validate>Validate and preview</button><button data-save class="primary" disabled>Save reviewed template</button></div>
      </section>`;
      document.body.appendChild(mask); trapDialogFocus(mask);
      for(const label of mask.querySelectorAll("label")){const control=label.querySelector("input,select,textarea");if(control)control.setAttribute("aria-label",[...label.childNodes].filter(node=>node.nodeType===3).map(node=>node.textContent).join("").trim());}
      const field = selector => mask.querySelector(selector);
      const selection = field("[data-template]");
      const base = JSON.parse(templates.find(template => template.builtin).text);
      const previousFocus = document.activeElement;
      const close = value => { document.removeEventListener("keydown", escape); mask.remove(); previousFocus?.focus(); resolve(value); };
      const escape = event => { if (event.key === "Escape" && [...document.querySelectorAll(".s2g-mask")].at(-1) === mask) close(null); };
      // Every definition edit invalidates review. Generations also reject a
      // delayed preview response arriving after another edit or template selection.
      const invalidate = () => { validationGeneration++; preview = null; field("[data-preview]").hidden = true; field("[data-save]").disabled = true; field("[data-error]").textContent = ""; };
      const syncText = () => { field("[data-text]").value = JSON.stringify(draft, null, 2) + "\n"; invalidate(); renderTopology(); };
      function renderTopology() {
        const events = Object.keys(draft.definition.events), agents = draft.definition.agents;
        const height = (Math.max(events.length, agents.length) + sources.length) * 38 + 24;
        const lines = draft.definition.subscriptions.map(edge => {
          const from = events.indexOf(edge.event), to = agents.findIndex(agent => agent.id === edge.target);
          return from < 0 || to < 0 ? "" : `<path d="M 180 ${from * 38 + 27} C 230 ${from * 38 + 27}, 240 ${to * 38 + 27}, 290 ${to * 38 + 27}" stroke="#176b5b" fill="none"><title>${escapeHtml(roleName(edge.event))} → ${escapeHtml(roleName(edge.target))}</title></path>`;
        }).join("");
        const sourceRows=sources.map((source,i)=>`<text x="5" y="${(Math.max(events.length,agents.length)+i)*38+27}" font-size="12" fill="#17211f">Source monitor ${i+1} → source.changed (${source.enabled?"enabled":"disabled"})</text>`).join("");
        field("[data-topology]").innerHTML = `<svg role="img" aria-label="Events react through subscriptions to agents" viewBox="0 0 470 ${height}">${sourceRows}${lines}${events.map((event, i) => `<g><rect x="5" y="${i*38+10}" width="175" height="30" rx="5" fill="#e8f3ef"/><text x="10" y="${i*38+30}" font-size="12" fill="#17211f">${escapeHtml(event)}</text></g>`).join("")}${agents.map((agent,i) => `<g><rect x="290" y="${i*38+10}" width="175" height="30" rx="5" fill="#e8f3ef"/><text x="300" y="${i*38+30}" font-size="12" fill="#17211f">${escapeHtml(roleName(agent.id))}</text></g>`).join("")}</svg>`;
      }
      function render() {
        selection.innerHTML = templates.map(item => `<option value="${escapeHtml(item.key)}">${escapeHtml(item.name)}${item.builtin ? " (built-in)" : ` · revision ${item.revision}`}</option>`).join("");
        selection.value = selected.key; field("[data-name]").value = selected.builtin ? `${selected.name} custom` : selected.name;
        const visual = field("[data-visual]");
        visual.innerHTML = `<h3>Agents and approved capabilities</h3>${draft.definition.agents.map((agent,i) => `<fieldset data-agent="${i}"><legend>${escapeHtml(roleName(agent.id))} · ${agent.id === "primary" ? "proposal author" : "read-only specialist"}</legend>
          <label>Prompt · ${escapeHtml(agent.id)}<textarea aria-label="Prompt · ${escapeHtml(agent.id)}" data-prompt rows="5">${escapeHtml(agent.prompt)}</textarea></label>
          <label>Model route · ${escapeHtml(agent.id)}<select data-route><option value="inherit">Inherit selected native route</option><option value="deployment">${escapeHtml(catalog.route.provider)} / ${escapeHtml(catalog.route.model)}</option></select></label>
          <div>Native composition: ${escapeHtml(agent.agentPreset || "read-only event member")}; skills/MCP come from that composition.</div>
          ${(base.definition.agents.find(item=>item.id===agent.id)?.tools || ["get_bound_context","publish_event","get_event_system","wait_for_event"]).map(tool => `<label class="s2g-inline"><input type="checkbox" data-tool="${escapeHtml(tool)}" ${agent.tools.includes(tool)?"checked":""}> ${escapeHtml(tool)}</label>`).join("")}
          <label>Published events · ${escapeHtml(agent.id)}<input data-publishes value="${escapeHtml(agent.publishes.join(", "))}"></label>
          ${agent.id !== "primary" ? '<button type="button" data-remove-agent>Remove agent</button>' : ""}</fieldset>`).join("")}
          <label>Add approved role<select data-add-role><option value="">Choose role</option>${base.definition.agents.filter(agent=>!draft.definition.agents.some(item=>item.id===agent.id)).map(agent=>`<option>${escapeHtml(agent.id)}</option>`).join("")}</select></label>
          <label>New read-only role name<input data-agent-name placeholder="observer"></label><button type="button" data-add-agent>Add read-only agent</button><h3>Subscriptions</h3>${draft.definition.subscriptions.map((edge,i)=>`<fieldset data-edge="${i}"><legend>Reaction ${i+1}</legend><details><summary>Technical details</summary><label>Subscription ID<input data-edge-id readonly value="${escapeHtml(edge.id)}"></label></details><label>Event type<select data-edge-event>${Object.keys(draft.definition.events).map(event=>`<option ${event===edge.event?"selected":""}>${escapeHtml(event)}</option>`).join("")}</select></label><label>Target agent<select data-edge-target>${draft.definition.agents.map(agent=>`<option value="${escapeHtml(agent.id)}" ${agent.id===edge.target?"selected":""}>${escapeHtml(roleName(agent.id))}</option>`).join("")}</select></label><label>Retry policy<select data-edge-retry><option value="human">Human-controlled recovery</option><option value="safe" ${edge.retry?"selected":""}>Replay-safe: 3 attempts, 1–10 second backoff</option></select></label><button type="button" data-remove-edge>Remove subscription</button></fieldset>`).join("")}
          <button type="button" data-add-edge>Add subscription</button><h3>Payload contracts</h3>${Object.entries(draft.definition.events).map(([event,schema],i)=>`<fieldset data-event="${escapeHtml(event)}"><legend>${escapeHtml(event)}${event in base.definition.events?" · host contract":""}</legend><label>Schema · ${escapeHtml(event)}<textarea aria-label="Schema · ${escapeHtml(event)}" data-schema rows="5" ${event in base.definition.events?"readonly":""}>${escapeHtml(JSON.stringify(schema,null,2))}</textarea></label>${event in base.definition.events?"":'<button type="button" data-remove-event>Remove event type</button>'}</fieldset>`).join("")}
          <label>New event type<input data-event-name placeholder="observation.ready"></label><button type="button" data-add-event>Add event type</button>
          <h3>Aggregate limits (deployment ceilings apply)</h3>${Object.entries(draft.limits).map(([name,value])=>`<label>${escapeHtml(name)}<input type="number" min="1" data-limit="${name}" value="${value}" ${name==="maxOutputTokens"?"readonly":""}></label>`).join("")}`;
        for(const label of visual.querySelectorAll("label")){const control=label.querySelector("input,select,textarea");if(control)control.setAttribute("aria-label",[...label.childNodes].filter(node=>node.nodeType===3).map(node=>node.textContent).join("").trim());}
        visual.onsubmit = event => event.preventDefault();
        for (const node of visual.querySelectorAll("[data-agent]")) {
          const agent = draft.definition.agents[Number(node.dataset.agent)];
          node.querySelector("[data-prompt]").oninput = event => { agent.prompt = event.target.value; syncText(); };
          const route = node.querySelector("[data-route]"); route.value = agent.provider ? "deployment" : "inherit";
          route.onchange = () => { delete agent.provider; delete agent.model; if (route.value === "deployment") Object.assign(agent, catalog.route); syncText(); };
          for (const checkbox of node.querySelectorAll("[data-tool]")) checkbox.onchange = () => { agent.tools = [...node.querySelectorAll("[data-tool]:checked")].map(input=>input.dataset.tool); syncText(); };
          node.querySelector("[data-publishes]").oninput = event => { agent.publishes = event.target.value.split(",").map(item=>item.trim()).filter(Boolean); syncText(); };
          const remove = node.querySelector("[data-remove-agent]"); if(remove) remove.onclick = () => { draft.definition.agents.splice(Number(node.dataset.agent),1); render(); };
        }
        visual.querySelector("[data-add-role]").onchange = event => { const agent = base.definition.agents.find(item=>item.id===event.target.value); if(agent) draft.definition.agents.push(JSON.parse(JSON.stringify(agent))); render(); };
        visual.querySelector("[data-add-agent]").onclick=()=>{const name=visual.querySelector("[data-agent-name]").value.normalize("NFKC").trim();const baseName=name.normalize("NFKD").replace(/[^a-zA-Z0-9]+/g,"_").replace(/^_+|_+$/g,"").toLowerCase().slice(0,40);let id=baseName;for(let number=2;draft.definition.agents.some(agent=>agent.id===id);number++)id=`${baseName}_${number}`;if(draft.preset!=="orchestrated"||!/^[a-z][a-z0-9_-]{0,47}$/.test(id)||draft.definition.agents.some(agent=>agent.id===id)){field("[data-error]").textContent="Choose a readable role name in orchestrated.";return;}draft.definition.agents.push({id,prompt:catalog.default_member_prompt,tools:["get_bound_context","publish_event","get_event_system"],publishes:[]});render();};
        for (const node of visual.querySelectorAll("[data-edge]")) {
          const edge = draft.definition.subscriptions[Number(node.dataset.edge)];
          for (const [selector,key] of [["[data-edge-id]","id"],["[data-edge-event]","event"],["[data-edge-target]","target"]]) node.querySelector(selector).onchange = event => { edge[key] = event.target.value; syncText(); };
          node.querySelector("[data-edge-retry]").onchange = event => { delete edge.retry; if(event.target.value==="safe") edge.retry={replaySafe:true,maxAttempts:3,initialBackoffMillis:1000,maxBackoffMillis:10000}; syncText(); };
          node.querySelector("[data-remove-edge]").onclick = () => { draft.definition.subscriptions.splice(Number(node.dataset.edge),1); render(); };
        }
        visual.querySelector("[data-add-edge]").onclick = () => { let number=1;while(draft.definition.subscriptions.some(edge=>edge.id===`reaction-${number}`))number++;draft.definition.subscriptions.push({id:`reaction-${number}`,event:Object.keys(draft.definition.events)[0],target:"primary"}); render(); };
        for (const node of visual.querySelectorAll("[data-event]")) {
          node.querySelector("[data-schema]").onchange = event => { try { draft.definition.events[node.dataset.event]=JSON.parse(event.target.value); syncText(); } catch(caught) { field("[data-error]").textContent=caught.message; } };
          const remove=node.querySelector("[data-remove-event]"); if(remove) remove.onclick=()=>{delete draft.definition.events[node.dataset.event];render();};
        }
        visual.querySelector("[data-add-event]").onclick = () => { const event=visual.querySelector("[data-event-name]").value.trim(); if (!/^[a-z][a-z0-9_.-]{0,79}$/.test(event) || event in draft.definition.events) {field("[data-error]").textContent="Choose a new event identifier.";return;} draft.definition.events[event]={type:"object",properties:{text:{type:"string"}},required:["text"],additionalProperties:false}; render(); };
        for (const input of visual.querySelectorAll("[data-limit]")) input.onchange=()=>{draft.limits[input.dataset.limit]=Number(input.value);syncText();};
        syncText();
      }
      selection.onchange = () => { selected=templates.find(item=>item.key===selection.value); draft=JSON.parse(selected.text);render(); };
      field("[data-text]").oninput = invalidate;
      field("[data-import]").onclick = async () => { try { const validated=await api(`/event-templates/${encodeURIComponent(selected.key)}/preview`,{revision:selected.revision,text:field("[data-text]").value}); draft=JSON.parse(validated.after);render(); } catch(caught) {field("[data-error]").textContent=caught.message;} };
      field("[data-name]").oninput = () => { /* Naming does not alter the reviewed execution definition. */ };
      field("[data-validate]").onclick = async () => {
        field("[data-save]").disabled=true;field("[data-error]").textContent="";
        const generation=++validationGeneration, text=field("[data-text]").value;
        try {
          const result=await api(`/event-templates/${encodeURIComponent(selected.key)}/preview`,{revision:selected.revision,text});
          // Never enable Save for a result calculated from text the user replaced.
          if(generation!==validationGeneration||text!==field("[data-text]").value)return;
          preview=result;
          const before=preview.before.split("\n"), after=preview.after.split("\n"), lines=[];
          for(let i=0;i<Math.max(before.length,after.length);i++) if(before[i]!==after[i]) { if(before[i]!==undefined)lines.push(`- ${before[i]}`);if(after[i]!==undefined)lines.push(`+ ${after[i]}`); }
          field("[data-preview]").innerHTML=`<h3>Review configuration changes</h3><p>Validation passed. Saving ${selected.builtin?"creates a new template":"updates this template revision"}; existing conversations keep their pinned definition.</p><ul>${preview.warnings.map(warning=>`<li>${escapeHtml(warning)}</li>`).join("")}</ul><pre>${escapeHtml(lines.join("\n") || "No definition changes.")}</pre>`;
          field("[data-preview]").hidden=false;field("[data-save]").disabled=false;
        } catch(caught) { preview=null;field("[data-error]").textContent=caught.message; }
      };
      field("[data-save]").onclick = async () => {
        if(!preview)return;field("[data-save]").disabled=true;
        // Send the server-canonical reviewed text, not unvalidated form state.
        try { const result=await api(`/event-templates/${encodeURIComponent(selected.key)}/save`,{revision:selected.revision,text:preview.after,reviewDigest:preview.reviewDigest,name:field("[data-name]").value}); close(result.template); }
        catch(caught){field("[data-error]").textContent=caught.message;preview=null;}
      };
      field("[data-cancel]").onclick=()=>close(null);document.addEventListener("keydown",escape);render();selection.focus();
    });
  }

  // Inspector rows reflect committed native ledger state. Delivery acceptance,
  // activation completion, retry history and owner receipt remain distinct.
  // Historic request charges lack per-agent attribution, so show aggregate facts.
  function ExecutionInspector({ execution, sources, goal }) {
    const [selected, setSelected] = React.useState("");
    const events = execution.events || [], deliveries = execution.deliveries || [];
    const event = events.find(item=>item.id===selected) || events.at(-1);
    // Follow committed parent event IDs; timestamps/order alone do not establish
    // which input caused a delivery or an owner proposal.
    const lineage = []; let current = event;
    while(current && !lineage.some(item=>item.id===current.id)) { lineage.unshift(current); current=events.find(item=>item.id===current.causation); }
    return h("details", { className:"s2g-inspector" }, h("summary",null,"Technical details"),
      h("h3",null,"Pinned event configuration"), h("p",null,`${execution.definition.id}@${execution.definition.version} · digest ${execution.digest}. Changes apply to new conversations.`),
      h("button",{onClick:()=>void editEventTemplate(execution.definition.id.includes(".circuit.")?"circuit":"spec",execution.mode,sources).catch(error=>window.alert(error.message))},"Configure event templates"),
      h("details",null,h("summary",null,"Pinned prompts, capabilities, payloads, subscriptions, and limits"),h("pre",null,JSON.stringify({definition:execution.definition,limits:execution.limits},null,2))),
      ...execution.members.map(member=>h("button",{key:member.id,disabled:!member.created,onClick:()=>openNativeSession(member.sessionId)},`Native conversation history · ${member.id}`)),
      h("h3",null,"Why did this agent run?"),
      h("label",null,"Inspect event",h("select",{value:event?.id||"",onChange:change=>setSelected(change.target.value)},...events.map(item=>h("option",{key:item.id,value:item.id},`${item.type} · ${item.producer} · ${item.id}`)))),
      event?h("div",{"data-causal-event":event.id},h("p",null,`Causal chain: ${lineage.map(item=>`${item.type} (${item.producer})`).join(" → ")}`),h("p",null,`Correlation ${event.correlation} · cause ${event.causation||"root input"} · depth ${event.depth}`),h("pre",null,JSON.stringify(event.payload,null,2)),
        ...deliveries.filter(item=>item.eventId===event.id).map(delivery=>{
          const subscription=execution.definition.subscriptions.find(item=>item.id===delivery.subscription), member=execution.members.find(item=>item.id===delivery.target);
          const results=events.filter(item=>item.causation===event.id);
          return h("article",{key:delivery.id,"data-delivery":delivery.id},h("h4",null,`${delivery.target} · ${delivery.state}`),h("p",null,`Matched ${subscription?`${subscription.id}: exact ${subscription.event} → ${subscription.target}`:delivery.subscription}. Attempt ${delivery.attempt}; activation ${delivery.activationId}; delivery ${delivery.id}.`),h("p",null,`Retry of ${delivery.retryOf||"none"}${delivery.notBefore?`; eligible ${new Date(delivery.notBefore).toISOString()}`:""}. ${delivery.error||""}`),member?h("button",{disabled:!member.created,onClick:()=>openNativeSession(member.sessionId)},`Native conversation history · ${member.id}`):null,h("p",null,`Causal results: ${results.map(item=>`${item.type} (${item.producer})`).join(", ")||"none recorded"}`));
        })) : h("p",null,"No events recorded yet."),
      goal?h("details",null,h("summary",null,"Native goal state and continuation turns"),h("pre",null,JSON.stringify(goal,null,2))):null,
      h("h3",null,"Where did the budget go?"),h("p",null,"All native primary, specialist, continuation, and retry requests share this allowance. Pending requests show reserved tokens until settled."),
      h("table",null,h("caption",null,"Model request charges"),h("thead",null,h("tr",null,...["Request","Tokens","Active ms","State"].map(label=>h("th",{key:label,scope:"col"},label)))),h("tbody",null,...execution.requests.map(request=>h("tr",{key:request.id},h("td",null,request.id),h("td",null,String(request.tokens)),h("td",null,String(request.activeMillis)),h("td",null,request.settled?"settled":"reserved"))))),
      h("h3",null,"External sources"),...(sources||[]).map(source=>h("pre",{key:source.id},JSON.stringify({id:source.id,definition:source.definition,enabled:source.enabled,sequence:source.sequence,error:source.error},null,2))));
  }

  function MonitorForm({ sessionId, suggestion, onChanged }) {
    const [url, setUrl] = React.useState(suggestion?.url || "");
    const [pointer, setPointer] = React.useState(suggestion?.pointer || "");
    const [condition, setCondition] = React.useState("changed");
    const [expected, setExpected] = React.useState("");
    const [seconds, setSeconds] = React.useState("60");
    const [error, setError] = React.useState("");
    const [busy, setBusy] = React.useState(false);
    return h("details", null, h("summary", null, "Monitor service endpoint"),
      h("form", { className: "s2g-form", onSubmit: async event => {
        event.preventDefault(); setBusy(true); setError("");
        try {
          const definition = { url, pointer, eventType: "source.changed", condition,
            intervalMillis: Number(seconds) * 1000, debounceMillis: 5000, emitInitial: condition === "equals",
            ...(condition === "equals" ? { expectedJson: expected } : {}) };
          const result = await api(`/bindings/${encodeURIComponent(sessionId)}/execution/sources`, { action: "add", definition });
          onChanged(result);
        } catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
        finally { setBusy(false); }
      } },
      h("label", null, "Approved service URL", h("input", { type: "url", value: url, required: true, onChange: event => setUrl(event.target.value) })),
      h("label", null, "JSON pointer", h("input", { value: pointer, placeholder: "/source_revision_hash", onChange: event => setPointer(event.target.value) })),
      h("label", null, "Condition", h("select", { value: condition, onChange: event => setCondition(event.target.value) }, h("option", { value: "changed" }, "Value changes"), h("option", { value: "equals" }, "Value equals JSON"))),
      condition === "equals" ? h("label", null, "Expected JSON value", h("input", { value: expected, required: true, placeholder: '"ready"', onChange: event => setExpected(event.target.value) })) : null,
      h("label", null, "Check interval in seconds", h("input", { type: "number", min: 5, max: 3600, value: seconds, onChange: event => setSeconds(event.target.value) })),
      h("p", null, "Unchanged checks use no model requests. Changed observations use this conversation's remaining budget and service approval rules."),
      h("button", { type: "submit", disabled: busy }, "Start monitoring"), error ? h("p", { className: "s2g-error" }, error) : null));
  }

  // Polling refreshes the displayed execution revision used by control actions.
  // A stale answer/resume/retry must fail at the host instead of waking other work.
  function ExecutionDock({ sessionId }) {
    const [execution, setExecution] = React.useState(null);
    const [busy, setBusy] = React.useState(false);
    const [error, setError] = React.useState("");
    const [sources, setSources] = React.useState([]);
    const [suggestion, setSuggestion] = React.useState(null);
    const [goal, setGoal] = React.useState(null);
    const [legacy, setLegacy] = React.useState(false);
    React.useEffect(() => {
      let disposed = false;
      const load = async () => {
        try {
          const data = await api(`/bindings/${encodeURIComponent(sessionId)}/execution`);
          if (!disposed) { setExecution(data.execution || null); setLegacy(Boolean(data.legacy)); setSources(data.sources || []); setSuggestion(data.monitorSuggestion || null); setGoal(data.goal || null); }
        } catch (caught) { if (!disposed) setError(caught instanceof Error ? caught.message : String(caught)); }
      };
      void load();
      const timer = setInterval(() => void load(), 2000);
      return () => { disposed = true; clearInterval(timer); };
    }, [sessionId]);
    if (legacy) return h("div", { className: "s2g-workflow" }, "This legacy conversation is readable history. Start a new bound conversation to use the updated preset.");
    if (!execution) return null;
    const requests = execution.requests || [];
    const members = execution.members || [];
    const deliveries = execution.deliveries || [];
    const limits = record(execution.limits);
    const tokens = requests.reduce((sum, request) => sum + request.tokens, 0);
    const pending = deliveries.filter(delivery => ["pending", "dispatching", "accepted"].includes(delivery.state));
    const failed = deliveries.filter(delivery => ["failed", "interrupted"].includes(delivery.state));
    async function act(action, deliveryId) {
      setBusy(true); setError("");
      try {
        const data = await api(`/bindings/${encodeURIComponent(sessionId)}/execution/actions`, { action, revision: execution.revision, ...(deliveryId ? { deliveryId, acknowledgeUncertainty: true } : {}) });
        setExecution(data.execution);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : String(caught));
        // Refresh after CAS rejection so another action uses the observed state.
        // Do not replay an answer/retry automatically against a newer revision.
        const data = await api(`/bindings/${encodeURIComponent(sessionId)}/execution`).catch(() => null);
        if (data) setExecution(data.execution);
      } finally { setBusy(false); }
    }
    return h("div", { className: "s2g-workflow", "data-s2g-execution": execution.status },
      h("strong", null, (execution.status === "active" && execution.waits?.some(wait => wait.state === "waiting") ? "waiting" : execution.status === "active" && goal?.phase === "complete" ? "goal complete" : execution.status === "active" && goal?.phase === "blocked" ? "goal blocked" : execution.status).replaceAll("-", " ")),
      h("div", { className: "s2g-workflow-main" },
        h("div", { className: "s2g-workflow-objective" }, execution.reason || `${execution.mode} · ${members.map(member => member.name || member.id.replaceAll("_", " ")).join(", ")}`),
        h("div", { className: "s2g-workflow-meta" }, `turns ${execution.rounds.length}/${limits.maxRounds} · requests ${requests.length}/${limits.maxRequests} · tokens ${tokens}/${limits.maxTokens} · active seconds ${Math.ceil(requests.reduce((sum, request) => sum + request.activeMillis, 0) / 1000)}/${Math.floor(limits.maxActiveMillis / 1000)} · pending ${pending.length} · failures ${failed.length}`),
        h("details", null, h("summary", null, "Technical details"),
          h("ul", null, ...(execution.events || []).slice(-8).map(event => h("li", { key: event.id }, `${event.type} · ${event.producer}`))),
          ...failed.map(delivery => h("div", { key: delivery.id },
            h("p", null, `${delivery.target} · attempt ${delivery.attempt}: ${delivery.error}`),
            execution.status === "active" && !deliveries.some(item => item.retryOf === delivery.id)
              ? h("button", { disabled: busy, onClick: () => {
                if (window.confirm("This attempt may already have produced results. Retry with a new activation using the remaining budget?")) void act("retry", delivery.id);
              } }, "Acknowledge uncertainty and retry") : null))),
        ...(execution.waits || []).filter(wait => wait.state === "waiting").map(wait => h("div", { key: wait.id },
          h("p", null, `${wait.member} waiting for ${wait.kind}: ${wait.reason}`),
          wait.kind === "human" && execution.status === "active" ? h("button", { disabled: busy, onClick: async () => {
            const answer = window.prompt(wait.reason); if (!answer?.trim()) return;
            setBusy(true); setError("");
            try { const result = await api(`/bindings/${encodeURIComponent(sessionId)}/execution/answers`, { waitId: wait.id, revision: execution.revision, answer }); setExecution(result.execution); }
            catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
            finally { setBusy(false); }
          } }, "Answer") : null)),
        ...sources.map(source => h("div", { key: source.id },
          h("p", null, `${source.enabled ? "Monitoring" : "Monitor disabled"} · Source changes · events ${source.sequence}${source.error ? ` · ${source.error}` : ""}`),
          h("button", { disabled: busy, onClick: async () => {
            setBusy(true); setError("");
            try { const result = await api(`/bindings/${encodeURIComponent(sessionId)}/execution/sources`, { action: source.enabled ? "disable" : "enable", sourceId: source.id, revision: source.revision }); setSources(result.sources); }
            catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); const fresh=await api(`/bindings/${encodeURIComponent(sessionId)}/execution`).catch(()=>null); if(fresh){setExecution(fresh.execution);setSources(fresh.sources||[]);} }
            finally { setBusy(false); }
          } }, source.enabled ? "Disable monitor" : "Enable monitor"))),
        h(ExecutionInspector, { key: `inspector:${sessionId}`, execution, sources, goal }),
        suggestion && execution.status !== "stopped" ? h(MonitorForm, { key: `monitor:${sessionId}`, sessionId, suggestion, onChanged: result => { setExecution(result.execution); setSources(result.sources); } }) : null,
        error ? h("span", { className: "s2g-error" }, error) : null),
      h("div", { className: "s2g-workflow-controls" },
        execution.status === "active" ? h("button", { disabled: busy, onClick: () => void act("pause") }, "Pause") : null,
        ["paused", "needs-resume"].includes(execution.status) ? h("button", { disabled: busy, onClick: () => void act("resume") }, "Resume") : null,
        execution.status !== "stopped" ? h("button", { disabled: busy, onClick: () => void act("stop") }, "Stop") : null));
  }

  function SourceNameDock({ sessionId, onSourceNamed }) {
    const [source, setSource] = React.useState(null);
    React.useEffect(() => {
      let disposed = false;
      const refresh = async () => {
        try { const result = await api(`/bindings/${encodeURIComponent(sessionId)}`); if (!disposed) { setSource(result.session); if (onSourceNamed && result.session) await onSourceNamed(result.session); } }
        catch { /* An unbound chat has no source label. */ }
      };
      void refresh(); const timer = setInterval(() => void refresh(), 15000);
      return () => { disposed = true; clearInterval(timer); };
    }, [sessionId]);
    if (!source) return null;
    return h("div", { className: "s2g-source-name" }, h("span", null, `Source: ${source.sourceName || "Selected document"}`),
      h("details", null, h("summary", null, "Technical details"), h("pre", null, pretty({ document: source.documentId, entity: source.entityId, owner: source.serviceDocumentKey })),
        h("button", { onClick: () => void navigator.clipboard.writeText(pretty({ document: source.documentId, entity: source.entityId, owner: source.serviceDocumentKey })) }, "Copy identifiers")));
  }

  function BrandMark() { return h("span", { className: "s2g-mark" }, "S2G"); }
  function BrandName() { return h("span", { className: "s2g-brand" }, "spec2gds AI Assistant"); }

  module.exports.inject = ["slots", "uiConversation", "uiSession", "sessions", "workspaces"];
  module.exports.apply = function apply(ctx) {
    const setProductTitle = () => {
      if (document.title !== "spec2gds Assistant") document.title = "spec2gds Assistant";
    };
    setProductTitle();
    if (typeof MutationObserver === "function") {
      const titleObserver = new MutationObserver(setProductTitle);
      titleObserver.observe(document.head, { childList: true, subtree: true, characterData: true });
    }
    openNativeSession = id => ctx.sessions.open(id);
    ctx.uiSession.registerNewSessionHandler({ id: "spec2gds", priority: -100, async handle(intent) {
      let workspace;
      if (intent?.source === "workspace") {
        const local = ctx.workspaces.list.getSnapshot().items.find(item => item.workspaceId === intent.workspaceId);
        if (!local) throw new Error("The selected design workspace is no longer available.");
        const product = (await api("/workspaces")).workspaces.find(item => item.path === local.path);
        if (!product) throw new Error("This workspace is not connected to a spec2gds design source.");
        workspace = product;
      }
      await createBoundSession(ctx, undefined, workspace);
      return true;
    } });
    ctx.slots.inject("sidebar.brand.mark", () => ctx.slots.register({ name: "sidebar.brand.mark" }, BrandMark));
    ctx.slots.inject("sidebar.brand.name", () => ctx.slots.register({ name: "sidebar.brand.name" }, BrandName));
    ctx.slots.inject("conversation.input.dock", () => ctx.slots.register({ name: "conversation.input.dock", id: "source-name", order: 10 }, props => h(SourceNameDock, { ...props, onSourceNamed: source => ensureWorkspace(ctx, { path: source.workspacePath, title: source.workspaceTitle }) })));
    ctx.slots.inject("conversation.input.dock", () => ctx.slots.register({ name: "conversation.input.dock", id: "execution", order: 11 }, ExecutionDock));
    ctx.uiConversation.events.register(proposalReviewsDefinition);
    ctx.slots.inject("conversation.chat.turnTail", () => ctx.slots.register({ name: "conversation.chat.turnTail", select: selectProposalReview },
      props => h(ProposalReviewTail, { ...props, onContinueCreation: reserved => continueSourceCreation(ctx, reserved), onOpenCreation: id => ctx.sessions.open(id) })));
    queueMicrotask(async () => {
      try {
        const stored = await api("/workspaces");
        for (const descriptor of stored.workspaces || []) await ensureWorkspace(ctx, descriptor);
      } catch (error) { console.warn("spec2gds workspace synchronization failed", error); }
    });
    const params = new URLSearchParams(location.search);
    const launch = new URLSearchParams(location.hash.replace(/^#/, ""));
    if (document.documentElement) document.documentElement.dataset.spec2gdsLaunch = "ready";
    const sessionId = params.get("spec2gds_session") || launch.get("spec2gds_session");
    const unbound = launch.get("spec2gds_unbound") === "1";
    if (sessionId || unbound) {
      if (document.documentElement) document.documentElement.dataset.spec2gdsLaunch = "pending";
      params.delete("spec2gds_session");
      history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}`);
      queueMicrotask(async () => {
        try {
          if (sessionId) await createBoundSession(ctx, await api(`/bindings/${encodeURIComponent(sessionId)}`));
          else await createUnboundSession(ctx);
          if (document.documentElement) document.documentElement.dataset.spec2gdsLaunch = "ready";
        }
        catch (error) {
          if (document.documentElement) { document.documentElement.dataset.spec2gdsLaunch = "error"; document.documentElement.dataset.spec2gdsLaunchError = error instanceof Error ? error.message : String(error); }
          window.alert(error instanceof Error ? error.message : String(error));
        }
      });
    }
  };
  return module.exports;
} });

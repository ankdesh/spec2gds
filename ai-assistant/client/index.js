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
    .s2g-flow-approval{box-sizing:border-box;width:min(var(--dsh-chat-content-width,760px),calc(100% - 32px));margin-inline:auto;padding-inline:var(--dsh-composer-dock-inset,8px)}
    .s2g-flow-approval .s2g-actions{flex-wrap:wrap}
    .s2g-mask{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:20px;background:rgba(8,18,16,.48);backdrop-filter:blur(3px)}
    .s2g-dialog{width:min(520px,100%);padding:20px;border:1px solid color-mix(in srgb,#176b5b 35%,transparent);border-radius:14px;background:var(--dsw-surface-primary,#fff);box-shadow:0 18px 55px rgba(0,0,0,.24);color:var(--text-primary,#17211f);font:14px/1.45 system-ui}
    .s2g-dialog h2{margin:0 0 5px;font-size:20px}.s2g-dialog>p{margin:0 0 16px;color:var(--text-secondary,#52615e)}
    .s2g-dialog [hidden]{display:none!important}
    .s2g-form{display:grid;gap:12px}.s2g-form label{display:grid;gap:5px;font-weight:600}.s2g-form input,.s2g-form select{box-sizing:border-box;width:100%;padding:9px 10px;border:1px solid color-mix(in srgb,currentColor 22%,transparent);border-radius:7px;background:var(--dsw-surface-primary,#fff);color:inherit;font:inherit}
    .s2g-form .s2g-pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}.s2g-dialog-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:5px}.s2g-dialog-actions button{padding:8px 12px;border:1px solid #176b5b;border-radius:7px;background:transparent;color:inherit;cursor:pointer}.s2g-dialog-actions button.primary{background:#176b5b;color:#fff}.s2g-dialog-actions button:disabled{opacity:.55;cursor:wait}
    .s2g-choice{display:flex;gap:16px}.s2g-choice label{display:flex;align-items:center;gap:6px;font-weight:600}.s2g-choice input{width:auto}.s2g-hint{margin:0;color:var(--text-secondary,#52615e);font-size:12px}.s2g-empty{padding:10px;border:1px dashed color-mix(in srgb,currentColor 25%,transparent);border-radius:7px;color:var(--text-secondary,#52615e)}
    .s2g-workflow{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:8px;margin:4px 8px;padding:7px 9px;border:1px solid color-mix(in srgb,#176b5b 28%,transparent);border-radius:8px;background:color-mix(in srgb,#176b5b 5%,transparent);font:12px/1.35 system-ui}
    .s2g-workflow strong{font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#176b5b}.s2g-workflow-main{min-width:0}.s2g-workflow-objective{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.s2g-workflow-meta{color:var(--text-secondary,#52615e);font-size:10px}.s2g-workflow-controls{display:flex;align-items:center;gap:5px}.s2g-workflow button{padding:3px 7px;border:1px solid #176b5b;border-radius:5px;background:transparent;color:inherit;cursor:pointer}.s2g-workflow button:disabled{opacity:.5}.s2g-workflow input{min-width:170px;padding:4px 6px;border:1px solid color-mix(in srgb,currentColor 22%,transparent);border-radius:5px;background:var(--dsw-surface-primary,#fff);color:inherit}
    .s2g-review{color:var(--text-primary,inherit);min-width:0}.s2g-review h5{font-size:13px;margin:14px 0 8px}.s2g-change{margin:10px 0;border-top:1px solid color-mix(in srgb,currentColor 18%,transparent);padding-top:10px}.s2g-change-label{display:flex;gap:8px;align-items:baseline;margin:0 0 7px}.s2g-change-badge{font-size:11px;font-weight:700}.s2g-change-badge--added{color:var(--text-primary,#176b5b)}.s2g-change-badge--removed{color:var(--text-primary,#b42318)}
    .s2g-comparison-scroll{overflow:auto;max-width:100%;max-height:520px;border:1px solid color-mix(in srgb,currentColor 20%,transparent);border-radius:7px}.s2g-comparison{width:100%;min-width:560px;border-collapse:collapse;table-layout:fixed}.s2g-comparison th,.s2g-comparison td{padding:7px 9px;vertical-align:top;text-align:left;border:1px solid color-mix(in srgb,currentColor 12%,transparent);overflow-wrap:anywhere}.s2g-comparison th{background:color-mix(in srgb,currentColor 6%,transparent)}.s2g-comparison .s2g-field{width:22%}
    .s2g-text-comparison td{padding:0}.s2g-text-line{display:flex;gap:9px;min-height:20px;white-space:pre-wrap;padding:2px 7px}.s2g-code-line{font:12px/1.6 ui-monospace,monospace}.s2g-line-number{flex:none;width:34px;text-align:right;user-select:none;opacity:.65}.s2g-line-content{min-width:0;overflow-wrap:anywhere}.s2g-line--before{background:color-mix(in srgb,#cc4747 18%,transparent)}.s2g-line--after{background:color-mix(in srgb,#15976b 18%,transparent)}
    .s2g-value{margin:0}.s2g-value dt{font-weight:600;margin-top:5px}.s2g-value dd{margin:2px 0 7px 10px;white-space:pre-wrap;overflow-wrap:anywhere}.s2g-value-list{margin:0;padding-left:20px}.s2g-content-card{margin:8px 0;padding:10px;border:1px solid color-mix(in srgb,currentColor 20%,transparent);border-radius:7px}.s2g-content-card h6{font-size:13px;margin:0 0 7px}.s2g-progress{font:13px/1.5 system-ui;margin:10px 0}.s2g-progress ol{padding-left:22px}.s2g-progress li{padding:3px 0}.s2g-progress-state{font-size:11px;font-weight:600;margin-right:8px}.s2g-flow-strip{display:flex;flex-wrap:wrap;align-items:center;gap:10px;font:13px/1.5 system-ui;padding:8px 0}.s2g-flow-strip .s2g-actions{margin:0;margin-left:auto}.s2g-source-name{font:13px/1.5 system-ui;padding:5px 0}.s2g-circuit{min-width:260px}.s2g-workflow-objective{white-space:normal}
    html[data-spec2gds-ui] [data-chat-flow-kind="system-prompt"],html[data-spec2gds-ui] [data-chat-flow-kind="context"]{display:none}
    html[data-spec2gds-ui] [data-turn-tail] button[aria-haspopup="dialog"]{display:none}
    html[data-spec2gds-ui] button[aria-label$="of context used"]{display:none}
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
          <label data-event-setup hidden>Event template<select aria-label="Event template" name="eventTemplate"></select></label>
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
        mask.querySelector("[data-event-setup]").hidden=preset==="focused";
      };
      form.elements.preset.addEventListener("change",syncTemplates);
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
            if (service.domain === "spec" && preset === "orchestrated") throw new Error("Spec creation requires Focused or Goal. Orchestrated supports Spec reads and analysis only.");
            if (service.domain === "spec") close({ flowStart: { toolName: "flow_create_empty_spec", inputs: { title, request: "Create an empty Spec named " + title, service_url: service.url }, preset } });
            else close(await api("/sources/create", { domain: service.domain, serviceBaseUrl: service.url, title, preset, ...templateSelection }));
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
    if (reservation.flowStart) {
      const descriptor = (await api("/workspaces")).unbound_workspace;
      const workspace = await ensureWorkspace(ctx, descriptor);
      const id = await ctx.sessions.create({ workspaceId: workspace.workspaceId, agentPreset: reservation.flowStart.preset });
      ctx.sessions.open(id);
      await api("/flow-runs/start", { sessionId: id, toolName: reservation.flowStart.toolName, inputs: reservation.flowStart.inputs, requestId: crypto.randomUUID() });
      return id;
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
  const record = value => value && typeof value === "object" && !Array.isArray(value) ? value : {};

  const label = value => String(value).replaceAll("_", " ").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, letter => letter.toUpperCase());
  const hiddenDisplayKeys = new Set(["id", "operation_id", "entity_id", "document_id", "section_id", "proposal_id", "session_id", "schema_path", "reference_anchor", "entity_ref", "entity_refs", "target", "ref", "source_revision_hash", "owner_document_key", "type_version"]);
  function operationLabel(operation) {
    const type = String(operation.type || "");
    const actions = { create_entity: `Add ${operation.kind === "design" ? "Design" : "Component"}`, add_component_port: "Add port", update_component_port: "Update port", delete_component_port: "Remove port", set_entity_metadata: "Update Component or Design details", upsert_entity_section: "Update Section", delete_entity_section: "Remove Section", upsert_narrative_block: "Update narrative", delete_narrative_block: "Remove narrative", upsert_instance: "Update instance", add_instance: "Add instance", create_net: "Add connection" };
    return `${actions[type] || "Update design content"}${operation.name || operation.port?.name ? ` · ${operation.name || operation.port.name}` : ""}`;
  }
  function readableError(value, fallback = "The request could not finish. Try again when the service is available.") {
    const message = value instanceof Error ? value.message : value;
    if (typeof message !== "string" || !message.trim() || /^\s*[\[{]/.test(message)) return fallback;
    return message.replace(/sha256:[\w.-]+/g, "the saved revision");
  }
  function ValueTree({ value, field = "" }) {
    if (value === undefined) return h("span", null, "Unavailable");
    if (value === null) return h("span", null, "Not present");
    if (typeof value === "boolean") return h("span", null, value ? "Yes" : "No");
    if (Array.isArray(value)) return value.length ? h("ul", { className: "s2g-value-list" }, value.map((item, index) => h("li", { key: index }, h(ValueTree, { value: item })))) : h("span", null, "None");
    if (typeof value === "object") {
      const entries = Object.entries(value).filter(([key]) => !hiddenDisplayKeys.has(key));
      return entries.length ? h("dl", { className: "s2g-value" }, entries.map(([key, item]) => h(React.Fragment, { key }, h("dt", null, label(key)), h("dd", null, h(ValueTree, { value: item, field: key }))))) : h("span", null, "None");
    }
    if (/\b(width|range)\b/i.test(field)) {
      const range = /^\[?(\d+):(\d+)\]?$/.exec(String(value));
      if (range) { const width = Math.abs(Number(range[1]) - Number(range[2])) + 1; return h("span", null, String(value).replace(/^\[|\]$/g, "")); }
      if (typeof value === "number") return h("span", null, `${value} ${value === 1 ? "bit" : "bits"}`);
    }
    if (/\bdirection$/i.test(field) && ["in", "out", "inout"].includes(value)) return h("span", null, ({ in: "Input", out: "Output", inout: "Input/output" })[value]);
    return h("span", { style: { whiteSpace: "pre-wrap" } }, String(value) || "Empty");
  }

  // Bounded look-ahead aligns insertions without quadratic memory on large RTL.
  // Every source line is retained, including when the texts have no anchors.
  function alignedLines(before, after) {
    const old = before === null || before === undefined ? [] : String(before).split("\n");
    const next = after === null || after === undefined ? [] : String(after).split("\n");
    let a = 0, b = 0; const lines = [];
    const append = (left, right, changed) => lines.push({ before: left ? old[a++] : null, after: right ? next[b++] : null,
      beforeNumber: left ? a : null, afterNumber: right ? b : null, changed });
    while (a < old.length || b < next.length) {
      if (a === old.length) { append(false, true, true); continue; }
      if (b === next.length) { append(true, false, true); continue; }
      if (old[a] === next[b]) { append(true, true, false); continue; }
      let removed = -1, added = -1;
      for (let offset = 1; offset <= 100 && (a + offset < old.length || b + offset < next.length); offset++) {
        if (removed < 0 && old[a + offset] === next[b]) removed = offset;
        if (added < 0 && next[b + offset] === old[a]) added = offset;
        if (removed >= 0 || added >= 0) break;
      }
      if (added >= 0 && (removed < 0 || added <= removed)) { for (let i = 0; i < added; i++) append(false, true, true); }
      else if (removed >= 0) { for (let i = 0; i < removed; i++) append(true, false, true); }
      else append(true, true, true);
    }
    return lines;
  }

  function TextComparison({ change }) {
    const lines = alignedLines(change.before, change.after);
    const code = change.kind === "code";
    return h("div", { className: "s2g-comparison-scroll", tabIndex: 0, role: "region", "aria-label": `${change.label} comparison` },
      h("table", { className: "s2g-comparison s2g-text-comparison" },
        h("thead", null, h("tr", null, h("th", { scope: "col" }, "Before"), h("th", { scope: "col" }, "After"))),
        h("tbody", null, lines.length ? lines.map((line, index) => h("tr", { key: index }, ["before", "after"].map(side => h("td", { key: side },
          h("div", { className: `s2g-text-line ${code ? "s2g-code-line" : ""} ${line.changed && line[side] !== null ? `s2g-line--${side}` : ""}` },
            code ? h("span", { className: "s2g-line-number", "aria-hidden": true }, line[`${side}Number`]) : null,
            h("span", { className: "s2g-line-content" }, !change[`${side}Available`] ? index === 0 ? "Unavailable" : "" : change[side] === null && index === 0 ? "Not present" : line[side] ?? "")))))) : h("tr", null, h("td", null, "Not present"), h("td", null, "Not present")))));
  }

  function Comparison({ change }) {
    return h("section", { className: "s2g-change", "data-s2g-change": change.change },
      h("p", { className: "s2g-change-label" }, h("span", { className: `s2g-change-badge s2g-change-badge--${change.change}` }, label(change.change)), h("strong", null, change.label)),
      ["text", "code"].includes(change.kind) ? h(TextComparison, { change }) : h("div", { className: "s2g-comparison-scroll", tabIndex: 0, role: "region", "aria-label": `${change.label} comparison` },
        h("table", { className: "s2g-comparison" }, h("thead", null, h("tr", null, h("th", { className: "s2g-field", scope: "col" }, "Field"), h("th", { scope: "col" }, "Before"), h("th", { scope: "col" }, "After"))),
          h("tbody", null, h("tr", null, h("th", { scope: "row" }, change.label), h("td", null, h(ValueTree, { value: change.beforeAvailable ? change.before : undefined, field: change.label })), h("td", null, h(ValueTree, { value: change.afterAvailable ? change.after : undefined, field: change.label })))))));
  }

  function ProposalComparison({ review, onRetry }) {
    const presentation = record(review.presentation);
    // Historical inline results may predate the display projection. Stored review
    // lookup remains the source of truth; the fallback still avoids JSON blocks.
    const fallback = Array.isArray(review.preview?.diff) ? review.preview.diff.map((item, index) => ({ label: item.label || "Section", changes: [{ ...item, id: String(index), label: item.label || "Section", change: item.change || "changed", kind: typeof item.before === "string" || typeof item.after === "string" ? "text" : "value", beforeAvailable: "before" in item, afterAvailable: "after" in item }] })) : [];
    const groups = presentation.groups || fallback;
    const available = presentation.previewAvailable ?? Boolean(review.preview);
    if (!available) return h("section", { role: "status" }, h("p", null, "The service preview is unavailable. Before values cannot be shown."), onRetry ? h("button", { type: "button", onClick: onRetry }, "Retry preview lookup") : null);
    return h("section", { "aria-label": "Proposed changes" }, groups.length ? groups.map((group, index) => h("section", { key: index },
      h("h5", null, group.label), group.changes.map(change => h(Comparison, { key: change.id, change })))) : h("p", null, "No content changes reported."));
  }

  function CircuitGraph({ document, diff, side }) {
    const doc = record(document), design = record(doc.design);
    const instances = Array.isArray(design.instances) ? design.instances.map(record) : [];
    const nets = Array.isArray(design.nets) ? design.nets.map(record) : [];
    const changed = new Set([...(diff.added || []), ...(diff.removed || []), ...(diff.changed || [])].map(item => `${record(item).kind}:${record(item).id}`));
    const width = Math.max(420, instances.length * 130), height = 170, step = 130;
    const points = new Map(instances.map((item, index) => [String(item.id), { x: 20 + index * step, y: 52 + (index % 2) * 55 }]));
    const lines = [];
    for (const net of nets) {
      const endpoints = Array.isArray(net.endpoints) ? net.endpoints.map(record).filter(item => item.kind === "instance") : [];
      for (let index = 1; index < endpoints.length; index++) {
        const a = points.get(String(endpoints[index - 1].instance_id)), b = points.get(String(endpoints[index].instance_id));
        if (a && b) lines.push(h("line", { key: `${net.id}:${index}`, x1: a.x + 52, y1: a.y + 18, x2: b.x + 52, y2: b.y + 18, stroke: changed.has(`net:${net.id}`) ? "#d97706" : "#87928f", strokeWidth: 2 }));
      }
    }
    return h("div", null, h("small", null, side), h("svg", { className: "s2g-circuit", role: "img", "aria-label": `${side} Circuit topology`, style: { minWidth: width }, viewBox: `0 0 ${width} ${height}` }, lines,
      instances.map(item => {
        const point = points.get(String(item.id));
        return h("g", { key: item.id }, h("rect", { x: point.x, y: point.y, width: 104, height: 36, rx: 6, fill: changed.has(`instance:${item.id}`) ? "#fef3c7" : "#e8f2ef", stroke: changed.has(`instance:${item.id}`) ? "#d97706" : "#176b5b" }), h("text", { x: point.x + 52, y: point.y + 22, textAnchor: "middle", fontSize: 11, fill: "#17211f" }, String(item.label || "Instance")));
      })));
  }

  function CircuitDiff({ preview }) {
    const value = record(preview), diff = record(value.diff);
    const base = value.base_document, candidate = value.candidate || record(value.snapshot).document;
    const counts = ["added", "removed", "changed", "connections_changed"].map(key => `${key.replaceAll("_", " ")}: ${Array.isArray(diff[key]) ? diff[key].length : 0}`).join(" · ");
    return h("div", null, h("p", null, counts), base && candidate ? h("div", { className: "s2g-comparison-scroll", tabIndex: 0, role: "region", "aria-label": "Circuit topology comparison" }, h("div", { className: "s2g-diff", style: { minWidth: 840 } }, h(CircuitGraph, { document: base, diff, side: "Before" }), h(CircuitGraph, { document: candidate, diff, side: "After" }))) : null);
  }

  function StoredReviewCard({ reference, sessionId, callId }) {
    const [review, setReview] = React.useState(null);
    const [error, setError] = React.useState("");
    const [attempt, setAttempt] = React.useState(0);
    React.useEffect(() => {
      let active = true, loading = false, settled = false;
      setReview(null); setError("");
      const load = async () => {
        if (loading || settled) return;
        loading = true;
        try {
        const id = reference?.sessionId || sessionId;
        if (!id) throw new Error("The review conversation is unavailable.");
        const result = reference?.proposalId
          ? await api(`/bindings/${encodeURIComponent(id)}/reviews/${encodeURIComponent(reference.proposalId)}`)
          : await api(`/bindings/${encodeURIComponent(id)}/reviews`);
        const found = result.review || result.reviews?.find(item => item.callId === callId);
        if (!found) throw new Error("No stored review matches this tool call.");
        if (active) { setReview(found); settled = ["applied", "discarded"].includes(found.state); }
        } finally { loading = false; }
      };
      void load().catch(caught => { if (active) setError(caught.message); });
      const timer = setInterval(() => void load().catch(caught => { if (active) setError(readableError(caught)); }), 2000);
      return () => { active = false; clearInterval(timer); };
    }, [reference?.sessionId, reference?.proposalId, sessionId, callId, attempt]);
    if (review) return h(ReviewCard, { review });
    return h("article", { className: "s2g-review", role: error ? "alert" : "status" },
      h("p", null, error || "Loading stored review…"),
      error ? h("button", { onClick: () => setAttempt(value => value + 1) }, "Retry review lookup") : null);
  }

  function ReviewCard({ review: initial }) {
    const [review, setReview] = React.useState(initial);
    React.useEffect(() => { setReview(previous => previous.proposalId !== initial.proposalId || (initial.version || 0) >= (previous.version || 0) ? initial : previous); }, [initial]);
    const [busy, setBusy] = React.useState(false);
    const [error, setError] = React.useState("");
    const artifact = record(review.artifact), presentation = record(review.presentation);
    const actionable = review.domain === "circuit" && ["ready", "rejected", "stale", "reconcile"].includes(review.state);
    async function act(action, deliveryId) {
      setBusy(true); setError("");
      try { setReview((await api(`/reviews/${encodeURIComponent(review.proposalId)}/actions`, { action })).review); }
      catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
      finally { setBusy(false); }
    }
    async function refreshPreview() {
      setBusy(true); setError("");
      try { setReview((await api(`/bindings/${encodeURIComponent(review.sessionId)}/reviews/${encodeURIComponent(review.proposalId)}`)).review); }
      catch (caught) { setError(readableError(caught)); }
      finally { setBusy(false); }
    }
    const stateLabel = review.state === "applied" ? presentation.saved ? "Saved" : "Confirming save" : ({ previewing: "Checking", ready: "Checked", applying: "Saving", sent: "Awaiting review", stale: "Source changed", reconcile: "Needs review" })[review.state] || label(review.state);
    return h("article", { className: "s2g-review" },
      h("header", null, h("h4", null, `${review.reviewNumber ? `Review ${review.reviewNumber} · ` : ""}${artifact.title || "Design proposal"}`), h("span", { className: "s2g-state", role: "status" }, stateLabel)),
      presentation.saved ? h("small", null, record(review.serviceResult).application_mode === "automatic" ? "Changes saved automatically" : "Changes saved") : null,
      h("section", { className: "s2g-summary" },
        h("p", null, presentation.summary || artifact.summary || "Proposal summary unavailable."),
        presentation.rationale || artifact.rationale ? h("p", null, h("strong", null, "Reason: "), presentation.rationale || artifact.rationale) : null,
        (presentation.assumptions || artifact.assumptions || []).length ? h("section", null, h("h5", null, "Assumptions"), h(ValueTree, { value: presentation.assumptions || artifact.assumptions })) : null,
        (presentation.warnings || []).map((warning, index) => h("p", { key: index, role: "status" }, readableError(warning, "The changes need attention.")))),
      review.error ? h("section", { className: "s2g-error" },
        h("strong", null, "Changes need attention"),
        h("p", null, presentation.errorMessage || readableError(record(review.error).details, "The proposal was not accepted.")),
        h("small", null, record(review.error).retryable ? "This may be retried after the underlying condition changes." : "No automatic retry will be attempted.")) : null,
      h(ProposalComparison, { review, onRetry: busy ? undefined : refreshPreview }),
      review.domain === "circuit" ? h(CircuitDiff, { preview: review.preview }) : null,
      actionable ? h("div", { className: "s2g-actions" }, h("button", { disabled: busy, onClick: () => act("discard") }, "Discard"), ["ready", "reconcile"].includes(review.state) ? h("button", { className: "primary", disabled: busy, onClick: () => act(review.domain === "spec" ? "apply" : "send") }, review.state === "reconcile" ? "Reconcile" : review.domain === "spec" ? "Save to Spec" : "Send to Circuit Designer") : null) : null,
      error ? h("p", { className: "s2g-error" }, error) : null);
  }

  function ProposalErrorCard({ error }) {
    const value = record(error);
    const actions = Array.isArray(value.suggested_actions) ? value.suggested_actions : [];
    return h("article", { className: "s2g-review" },
      h("header", null, h("h4", null, "Proposal not created")),
      h("p", { className: "s2g-error" }, readableError(value.details, "The request could not be represented safely.")),
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

  function architectureInformation(plan, elaborations = []) {
    const configuration = record(plan.concrete_configuration);
    const literalWidth = range => {
      if (range === null) return 1;
      const match = /^\[?([+-]?\d+)(?::([+-]?\d+))?\]?$/.exec(String(range).trim());
      return match ? Math.abs(Number(match[1]) - Number(match[2] ?? match[1])) + 1 : undefined;
    };
    const interfaces = (Array.isArray(plan.interfaces) ? plan.interfaces : []).map(group => {
      const evaluated = elaborations.find(item => item.component === group.component && item.status === "resolved");
      return { ...group, ports: (group.ports || []).map(port => {
        const bounds = evaluated?.ports?.find(item => item.name === port.name);
        const width = bounds?.width ?? literalWidth(port.range) ?? port.width;
        const details = { ...record(configuration[port.name]) };
        if (details.width === width) delete details.width;
        if (details.range === port.range || details.range === `[${port.range}]`) delete details.range;
        for (const key of ["name", "direction", "description"]) if (details[key] === port[key]) delete details[key];
        if (!Object.hasOwn(port, "range") && port.width !== undefined) details.width = port.width;
        return { ...port, details, evaluated: bounds, calculatedWidth: width };
      }) };
    });
    const vectors = interfaces.flatMap(group => group.ports).filter(port => port.range !== null && port.calculatedWidth > 1);
    const behavior = Object.fromEntries(Object.entries(configuration).filter(([key, value]) =>
      !(key === "module_name" && (plan.components || []).some(item => item.name === value))
      && !interfaces.some(group => group.ports.some(port => port.name === key))
      && !(key === "width" && vectors.length && vectors.every(port => port.calculatedWidth === value))
      && !(key === "clocks_resets" && JSON.stringify(value) === JSON.stringify(plan.clocks_resets))
      && !(key === "parameters" && interfaces.some(group => JSON.stringify(group.parameters) === JSON.stringify(value)))));
    return { interfaces, behavior, parameters: interfaces.flatMap(group => (group.parameters || []).map(parameter => ({ component: group.component, ...parameter }))) };
  }

  function ArchitectureReviewCard({ request, flow, sessionId, historical = false }) {
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
        const result = await api(`/architecture-reviews/${encodeURIComponent(value.reviewId)}/${action}`, { feedback, sessionId, flowRevision: flow.revision });
        setValue(result.architecture_review);

      } catch (caught) { setError(caught.message); }
      finally { setBusy(false); }
    }
    const plan = record(value.plan);
    const information = architectureInformation(plan, value.elaborations);
    const actionable = !historical && value.status === "pending" && flow.status === "waiting" && flow.pending?.request?.review_id === value.reviewId;
    return h("article", { className: "s2g-review", "data-s2g-architecture-review": historical ? "historical" : value.status, "data-s2g-architecture-review-id": value.reviewId },
      h("header", null, h("h4", null, `${value.reviewNumber ? `Review ${value.reviewNumber} · ` : ""}${plan.title || "Architecture review"}`), h("span", { className: "s2g-state" }, label(value.status))),
      ["components", "designs"].filter(key => plan[key]?.length).map(key => h("section", { key }, h("h5", null, label(key)), (Array.isArray(plan[key]) ? plan[key] : []).map((item, index) =>
        h("article", { key: index, className: "s2g-content-card" }, h("h6", null, item.name || label(key).replace(/s$/, "")), h(ValueTree, { value: Object.fromEntries(Object.entries(item).filter(([field]) => field !== "name")) }))))),
      h("section", null, h("h5", null, "Interfaces"), information.interfaces.map((item, index) => h("article", { key: index, className: "s2g-content-card" },
        h("h6", null, item.component || "Interface"), h("div", { className: "s2g-comparison-scroll", tabIndex: 0, role: "region", "aria-label": "Port interface" },
          h("table", { className: "s2g-comparison" }, h("thead", null, h("tr", null, ["Port ID", "Definition", "Description"].map(column => h("th", { key: column, scope: "col" }, column)))),
            h("tbody", null, item.ports.map((port, portIndex) => h("tr", { key: portIndex }, h("th", { scope: "row" }, port.name),
              h("td", null, port.direction, Object.hasOwn(port, "range") ? (port.range ? ` · ${String(port.range).replace(/^\[|\]$/g, "")}` : "") : " · Range not recorded",
                port.evaluated && port.range && !/^\[?[+-]?\d+(?::[+-]?\d+)?\]?$/.test(port.range) ? h("small", { style: { display: "block" } }, `At defaults: ${port.evaluated.left}:${port.evaluated.right}`) : null),
              h("td", null, port.description || "Description not recorded", Object.keys(port.details).length ? h(ValueTree, { value: port.details }) : null))))))))),
      information.parameters.length ? h("section", null, h("h5", null, "Parameters"), information.parameters.map((parameter, index) => h("article", { key: index, className: "s2g-content-card" },
        h("h6", null, parameter.name), h("p", null, `${parameter.rtl_type || "Untyped"} · Default: ${parameter.value}`), parameter.description ? h("p", null, parameter.description) : null))) : null,
      Object.keys(information.behavior).length ? h("section", null, h("h5", null, "Behavior"), h(ValueTree, { value: information.behavior })) : null,
      information.interfaces.filter(group => group.constant_context?.trim()).map((group, index) => h("section", { key: `constants-${index}` }, h("h5", null, `${group.component} · Interface constants`), h("pre", null, group.constant_context))),
      ["clocks_resets", "decomposition_rationale", "assumptions", "open_questions"].filter(key => plan[key]?.length).map(key =>
        h("section", { key }, h("h5", null, ({ clocks_resets: "Clocks and resets", decomposition_rationale: "Reason for this architecture" })[key] || label(key)), h(ValueTree, { value: plan[key] }))),
      Array.isArray(value.proposed_operations) ? h("section", null, h("h5", null, "Planned changes"), value.proposed_operations.map((operation, index) =>
        h("article", { key: index, className: "s2g-content-card" }, h("h6", null, operationLabel(operation)), h(ValueTree, { value: Object.fromEntries(Object.entries(operation).filter(([key]) => key !== "type")) })))) : null,
      actionable ? h("div", null,
        h("label", null, "Revision feedback", h("textarea", { value: feedback, onChange: event => setFeedback(event.target.value) })),
        h("div", { className: "s2g-actions" },
          h("button", { disabled: busy, onClick: () => decide("cancel") }, "Cancel"),
          h("button", { disabled: busy, onClick: () => decide("revise") }, "Revise architecture"),
          h("button", { className: "primary", disabled: busy || Boolean(plan.open_questions?.length), onClick: () => decide("approve") }, "Approve architecture"))) : null,
      value.feedback ? h("p", null, "Review feedback: ", value.feedback) : null,
      error ? h("p", { className: "s2g-error", role: "alert" }, error) : null);
  }

  const proposalToolNames = new Set(["prepare_circuit_proposal", "prepare_spec_proposal", "submit_spec_change"]);
  const flowToolNames = new Set(["flow_edit_spec", "flow_architecture", "flow_add_component", "flow_component_content", "flow_create_spec_with_component", "flow_create_empty_spec"]);

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
        if (!proposalToolNames.has(match.event.data.name) && !flowToolNames.has(match.event.data.name)) return context.state;
        const calls = new Map(context.state.calls);
        calls.set(String(match.event.data.callId), match.event.data.name);
        return { ...context.state, calls };
      }
      if (match.event.type !== "tool/result") return context.state;
      const callId = String(match.event.data.message.source.callId);
      if (!context.state.calls.has(callId)) return context.state;
      const block = match.event.data.message.content[0];
      const toolName = context.state.calls.get(callId);
      if (flowToolNames.has(toolName)) {
        const value = resultContentValue(block?.content);
        if (typeof value?.execution_id !== "string") return context.state;
        const result = { callId, toolName, seq: match.event.seq, flowExecutionId: value.execution_id };
        return { ...context.state, results: [...context.state.results.filter(item => item.callId !== callId), result] };
      }
      const reference = match.event.data.meta;
      if (reference?.kind === "spec2gds.review" && reference.version === 1
        && typeof reference.sessionId === "string" && typeof reference.proposalId === "string") {
        const result = { callId, toolName, seq: match.event.seq, reviewReference: reference };
        return { ...context.state, results: [...context.state.results.filter(item => item.callId !== callId), result] };
      }
      const value = resultContentValue(block?.content);
      if (!value && !block?.isError) {
        const result = { callId, toolName, seq: match.event.seq, recoverCall: true };
        return { ...context.state, results: [...context.state.results.filter(item => item.callId !== callId), result] };
      }
      if (!value?.review && !value?.error && !value?.required_input) return context.state;
      const result = { callId, toolName, seq: match.event.seq, review: value.review || null, error: value.error || null, requiredInput: value.required_input || null };
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
    return { ...latest, blocked: Boolean(data.blockedSeq) };
  }

  function ProposalReviewTail({ matched, inputActions, sessionId }) {
    if (matched.flowExecutionId) return h(FlowPresentationView, { executionId: matched.flowExecutionId, sessionId, key: `${sessionId}:${matched.flowExecutionId}` });
    if (matched.reviewReference || matched.recoverCall) return h(StoredReviewCard, {
      reference: matched.reviewReference, sessionId, callId: matched.callId });
    if (matched.review && !matched.review.presentation && matched.review.proposalId && (matched.review.sessionId || sessionId)) return h(StoredReviewCard, {
      reference: { proposalId: matched.review.proposalId, sessionId: matched.review.sessionId || sessionId }, sessionId, callId: matched.callId });
    if (matched.review) return h(ReviewCard, { review: matched.review });
    if (matched.requiredInput) return h(ProposalInputCard, { request: matched.requiredInput, inputActions });
    return h(ProposalErrorCard, { error: matched.error });
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
    const deliveries = execution.deliveries || [];
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
        h("div", { className: "s2g-workflow-objective" }, readableError(execution.reason, execution.mode === "goal" ? "Working toward the requested result" : "Preparing and checking changes")),
        h("div", { className: "s2g-workflow-meta" }, pending.length ? "Work is in progress" : failed.length ? "Some work needs attention" : "Ready"),
          ...failed.map(delivery => h("div", { key: delivery.id },
            h("p", null, readableError(delivery.error, "The current work did not finish.")),
            execution.status === "active" && !deliveries.some(item => item.retryOf === delivery.id)
              ? h("button", { disabled: busy, onClick: () => {
                if (window.confirm("This attempt may already have produced results. Retry with a new activation using the remaining budget?")) void act("retry", delivery.id);
              } }, "Acknowledge uncertainty and retry") : null)),
        ...(execution.waits || []).filter(wait => wait.state === "waiting").map(wait => h("div", { key: wait.id },
          h("p", null, readableError(wait.reason, "Awaiting a review decision")),
          wait.kind === "human" && execution.status === "active" ? h("button", { disabled: busy, onClick: async () => {
            const answer = window.prompt(wait.reason); if (!answer?.trim()) return;
            setBusy(true); setError("");
            try { const result = await api(`/bindings/${encodeURIComponent(sessionId)}/execution/answers`, { waitId: wait.id, revision: execution.revision, answer }); setExecution(result.execution); }
            catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
            finally { setBusy(false); }
          } }, "Answer") : null)),
        ...sources.map(source => h("div", { key: source.id },
          h("p", null, `${source.enabled ? "Monitoring source changes" : "Monitor disabled"}${source.error ? " · Source check unavailable" : ""}`),
          h("button", { disabled: busy, onClick: async () => {
            setBusy(true); setError("");
            try { const result = await api(`/bindings/${encodeURIComponent(sessionId)}/execution/sources`, { action: source.enabled ? "disable" : "enable", sourceId: source.id, revision: source.revision }); setSources(result.sources); }
            catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); const fresh=await api(`/bindings/${encodeURIComponent(sessionId)}/execution`).catch(()=>null); if(fresh){setExecution(fresh.execution);setSources(fresh.sources||[]);} }
            finally { setBusy(false); }
          } }, source.enabled ? "Disable monitor" : "Enable monitor"))),
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
        try { const result = await api(`/bindings/${encodeURIComponent(sessionId)}?optional=true`); if (!disposed) { setSource(result.session); if (onSourceNamed && result.session) await onSourceNamed(result.session); } }
        catch { /* Retain the source label while the lookup is unavailable. */ }
      };
      void refresh(); const timer = setInterval(() => void refresh(), 15000);
      return () => { disposed = true; clearInterval(timer); };
    }, [sessionId]);
    if (!source) return null;
    return h("div", { className: "s2g-source-name" }, h("span", null, `Source: ${source.sourceName || "Selected document"}`));
  }

  function FlowPresentationView({ sessionId, executionId, dock = false }) {
    const [view, setView] = React.useState(null);
    const [error, setError] = React.useState("");
    const [feedback, setFeedback] = React.useState("");
    const [busy, setBusy] = React.useState(false);
    const [refresh, setRefresh] = React.useState(0);
    React.useEffect(() => {
      if (!sessionId) return;
      let mounted = true, loading = false;
      const cache = new Map();
      async function load() {
        if (loading) return;
        loading = true;
        try {
          const result = await api(`/flows/${encodeURIComponent(sessionId)}${executionId ? `?execution_id=${encodeURIComponent(executionId)}` : ""}`);
          const current = result.flows.at(-1);
          const history = dock ? [] : result.flows.slice(0, -1);
          const references = dock ? [] : [...new Map(result.flows.flatMap(flow => flow.progress?.reviewReferences || []).map(reference => [reference.proposalId, reference])).values()];
          const reviews = await Promise.all(references.map(async reference => {
            const old = cache.get(reference.proposalId);
            if (old?.version === reference.version) return old;
            const response = await api(`/bindings/${encodeURIComponent(reference.sessionId)}/reviews/${encodeURIComponent(reference.proposalId)}`);
            cache.set(reference.proposalId, response.review);
            return response.review;
          }));
          const architectures = dock ? [] : await Promise.all(result.flows.flatMap(flow => {
            const id = flow.pending?.request?.kind === "architecture" ? flow.pending.request.review_id : flow.architecture_review_id;
            return id ? [api(`/architecture-reviews/${encodeURIComponent(id)}`).then(response => ({ flow, review: response.architecture_review }))] : [];
          }));
          if (!mounted) return;
          setView({ sessionId, executionId, current, reviews, architectures, history }); setError("");
        } catch (caught) { if (mounted) setError(readableError(caught)); }
        finally { loading = false; }
      }
      void load();
      const timer = setInterval(() => void load(), 2000);
      return () => { mounted = false; clearInterval(timer); };
    }, [sessionId, executionId, dock, refresh]);
    const current = view?.sessionId === sessionId && view.executionId === executionId ? view.current : null;
    if (!current) return error ? h("p", { role: "alert" }, error, h("button", { type: "button", onClick: () => setRefresh(value => value + 1) }, "Retry progress lookup")) : null;
    const pending = record(current.pending?.request), creation = current.creation_confirmation;
    const destination = creation?.binding_confirmed ? creation.conversation_id : undefined;
    const progress = record(current.progress);
    const phase = (progress.items || []).findLast(item => ["running", "waiting", "paused"].includes(item.state))?.label;
    const state = ({ running: "Running", waiting: "Awaiting review", succeeded: "Complete", failed: "Failed", cancelled: "Cancelled", paused: "Paused", "needs-resume": "Ready to resume", "needs-reconcile": "Needs review" })[current.status] || "In progress";
    async function control(action) {
      setBusy(true); setError("");
      try { await api(`/flow-runs/${encodeURIComponent(current.id)}/${action}`, { sessionId, revision: current.revision }); }
      catch (caught) { setError(readableError(caught)); }
      finally { setBusy(false); setRefresh(value => value + 1); }
    }
    return h("section", { className: dock ? "s2g-flow-approval" : "s2g-review", id: dock ? undefined : `s2g-flow-${current.id}`,
      "data-s2g-flow-status": dock ? current.status : undefined, "data-s2g-flow-definition": dock ? current.definition_id : undefined,
      "data-s2g-flow-error": dock ? current.error || "" : undefined, "data-s2g-flow-review": dock ? undefined : current.id },
      dock ? h("div", { className: "s2g-flow-strip", "aria-label": "Flow progress" }, h("strong", null, progress.title || "Spec flow"), h("span", { role: "status" }, phase ? `${state} · ${phase}` : state),
        h("div", { className: "s2g-actions" }, (current.allowed_actions || []).map(action => h("button", { type: "button", key: action, disabled: busy, onClick: () => void control(action) }, label(action)))))
        : h("header", null, h("h4", null, progress.title || "Spec flow"), h("span", { className: "s2g-state" }, state)),
      !dock ? h("section", { className: "s2g-progress", "aria-label": "Flow actions" }, h("ol", null, (progress.items || []).map(item => h("li", { key: item.id },
        h("span", { className: "s2g-progress-state" }, ({ complete: "Complete", running: "In progress", waiting: "Awaiting review", proposed: "Proposed", checked: "Checked", saved: "Saved", failed: "Needs attention", paused: "Paused", cancelled: "Cancelled" })[item.state] || "In progress"), item.label)))) : null,
      !dock ? view.architectures.filter(item => item.flow.id === current.id).map(item => h(ArchitectureReviewCard, { key: item.review.reviewId, request: item.review, sessionId, flow: item.flow })) : null,
      !dock ? view.reviews.map(review => h(ReviewCard, { key: review.proposalId, review })) : null,
      !dock && view.history.length ? h("section", { "aria-label": "Earlier flow attempts" }, h("h5", null, "Earlier attempts"), view.history.map(flow => h("section", { key: flow.id },
        h("p", null, flow.progress?.title || "Spec flow", " · ", label(flow.status)),
        h("ul", null, (flow.progress?.items || []).map(item => h("li", { key: item.id }, item.label))),
        view.architectures.filter(item => item.flow.id === flow.id).map(item => h(ArchitectureReviewCard, { key: item.review.reviewId, request: item.review, sessionId, flow, historical: true }))))) : null,
      creation?.content_required && ["failed", "needs-reconcile"].includes(current.status) ? h("p", null, "Document created; content request incomplete. ", h("a", { href: creation.editor_url, target: "_blank", rel: "noopener noreferrer" }, "Open Spec Editor")) : null,
      dock && current.status === "waiting" && pending.kind === "spec-receipt" ? h("p", null,
        "The Spec change is waiting for a content decision. ", h("a", { href: pending.editor_url, target: "_blank", rel: "noopener noreferrer" }, "Review in Spec Editor")) : null,
      !dock && current.status === "failed" && current.architecture_review_id ? h("div", null,
        h("label", null, "Architecture revision feedback", h("textarea", { value: feedback, onChange: event => setFeedback(event.target.value) })),
        h("button", { type: "button", disabled: busy || !feedback.trim(), onClick: async () => {
          setBusy(true);
          try { await api(`/architecture-reviews/${encodeURIComponent(current.architecture_review_id)}/revise`, { sessionId, flowRevision: current.revision, feedback }); setFeedback(""); setError(""); }
          catch (caught) { setError(readableError(caught)); }
          finally { setBusy(false); setRefresh(value => value + 1); }
        } }, "Revise architecture")) : null,
      destination && destination !== sessionId && dock ? h("button", { type: "button", onClick: () => openNativeSession(destination) }, "Open Spec conversation") : null,
      dock && current.status === "failed" ? h("p", { role: "alert" }, "The flow did not finish. Review the changes and the available recovery actions.") : null,
      error ? h("p", { role: "alert" }, error) : null);
  }

  function FlowApprovalDock(props) { return h(FlowPresentationView, { ...props, dock: true, key: props.sessionId }); }

  const toolActions = {
    get_bound_context: ["Reading the source", "Source read"], prepare_circuit_proposal: ["Preparing Circuit changes", "Circuit changes prepared"],
    structured_output: ["Preparing content", "Content prepared"], get_event_system: ["Checking progress", "Progress checked"],
    publish_event: ["Reporting progress", "Progress reported"], get_goal: ["Checking the requested result", "Result checked"],
    update_goal: ["Updating progress", "Progress updated"], get_flow: ["Checking flow progress", "Flow progress checked"],
    prepare_spec_proposal: ["Preparing Spec changes", "Spec changes prepared"], submit_spec_change: ["Checking Spec changes", "Spec changes submitted"],
  };
  function ProductToolRow({ toolName, block }) {
    const settled = block.kind === "tool-result";
    const result = settled ? resultContentValue(block.content) : null;
    const failed = block.isError || result?.success === false || result?.error;
    const actions = flowToolNames.has(toolName) ? ["Starting the Spec flow", "Spec flow started"] : toolActions[toolName] || ["Preparing changes", "Changes prepared"];
    return h("p", { className: "s2g-tool-progress", role: failed ? "alert" : "status" }, failed ? "The current action needs attention." : actions[settled ? 1 : 0]);
  }

  function BrandMark() { return h("span", { className: "s2g-mark" }, "S2G"); }
  function BrandName() { return h("span", { className: "s2g-brand" }, "spec2gds AI Assistant"); }

  module.exports.inject = ["slots", "uiConversation", "uiSession", "sessions", "workspaces"];
  module.exports.apply = function apply(ctx) {
    if (document.documentElement) document.documentElement.dataset.spec2gdsUi = "true";
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
    ctx.slots.inject("conversation.input.dock", () => ctx.slots.register({ name: "conversation.input.dock", id: "source-name", order: 10 }, props => h(SourceNameDock, { ...props, key: props.sessionId, onSourceNamed: source => ensureWorkspace(ctx, { path: source.workspacePath, title: source.workspaceTitle }) })));
    ctx.slots.inject("conversation.input.dock", () => ctx.slots.register({ name: "conversation.input.dock", id: "execution", order: 11 }, props => h(ExecutionDock, { ...props, key: props.sessionId })));
    ctx.slots.inject("conversation.input.dock", () => ctx.slots.register({ name: "conversation.input.dock", id: "flow-approvals", order: 13 }, FlowApprovalDock));
    ctx.slots.inject("conversation.composer.dock", () => ctx.slots.register({ name: "conversation.composer.dock", id: "stats", priority: -100 }, () => null));
    for (const key of ["system-prompt", "context"]) ctx.slots.inject("conversation.chat.node", () => ctx.slots.register({ name: "conversation.chat.node", key, priority: -100 }, () => null));
    for (const key of [...flowToolNames, ...Object.keys(toolActions)]) ctx.slots.inject("tool.call.toolview", () => ctx.slots.register({ name: "tool.call.toolview", key, priority: -100 }, ProductToolRow));
    ctx.uiConversation.events.register(proposalReviewsDefinition);
    ctx.slots.inject("conversation.chat.turnTail", () => ctx.slots.register({ name: "conversation.chat.turnTail", select: selectProposalReview },
      props => h(ProposalReviewTail, props)));
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

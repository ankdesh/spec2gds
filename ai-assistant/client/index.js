/* Product-owned browser plugin loaded by the DSH module table. Keep this file plain
 * JavaScript so the distribution does not carry a second frontend toolchain. */
window.__ModuleLoader__.load({ id: "@spec2gds/harness-web", factory: (require) => {
  const module = { exports: {} };
  const React = require("react");
  const h = React.createElement;
  document.title = "spec2gds Assistant";

  const style = document.createElement("style");
  style.dataset.plugin = "@spec2gds/harness-assistant";
  style.textContent = `
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
    if (payload.domain === "spec" && payload.document) {
      const document = payload.document;
      return [{ domain: "spec", serviceBaseUrl: payload.serviceBaseUrl, documentId: String(document.document_id),
        ownerDocumentKey: document.owner_document_key,
        title: String(document.title || document.document_id), scope: "document" },
      ...(Array.isArray(payload.entities) ? payload.entities : []).map(entity => ({
        domain: "spec", serviceBaseUrl: payload.serviceBaseUrl, documentId: String(document.document_id),
        ownerDocumentKey: document.owner_document_key,
        title: `${entity.title || entity.entity_id} · ${entity.entity_kind || "entity"}`,
        scope: "entity", entityKind: String(entity.entity_kind || "entity"), entityId: String(entity.entity_id),
      }))];
    }
    return (Array.isArray(payload.documents) ? payload.documents : []).map(document => ({
      domain: "circuit", serviceBaseUrl: payload.serviceBaseUrl, documentId: String(document.document_id),
      title: String(document.label || document.title || document.document_id), scope: "document",
      sourceBinding: document.source_binding || null,
    }));
  }

  function belongsToWorkspace(target, workspace) {
    if (!workspace) return true;
    if (workspace.domain === target.domain && workspace.ownerUrl === target.serviceBaseUrl && workspace.documentId === target.documentId) return true;
    const source = target.sourceBinding;
    return target.domain === "circuit" && workspace.domain === "spec" && source
      && String(source.source_service_url || "").replace(/\/$/, "") === workspace.ownerUrl
      && source.source_document_id === workspace.documentId;
  }

  async function discoverTargets(services, workspace) {
    const results = await Promise.allSettled(services.filter(item => item.available !== false).map(async service => {
      const query = new URLSearchParams({ domain: service.domain, service_base_url: service.url });
      return targetRows(await api(`/targets?${query}`));
    }));
    return results.flatMap(result => result.status === "fulfilled" ? result.value : []).filter(target => belongsToWorkspace(target, workspace));
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
          <div data-create hidden class="s2g-form"><div class="s2g-pair"><label>Document ID<input name="documentId" autocomplete="off" spellcheck="false" placeholder="my_design"></label><label>Title<input name="title" autocomplete="off" placeholder="My design"></label></div><p class="s2g-hint">Specs are created under the configured Spec document root. Circuits start as empty documents.</p></div>
          <label>Assistant preset<select name="preset"><option value="focused">Focused · one-shot Q&amp;A and proposals</option><option value="goal">Goal · bounded long-running work</option><option value="orchestrated">Orchestrated · persistent event agents</option></select></label>
          <p class="s2g-hint">The preset and agent configuration are fixed for this conversation. Service-specific context, tools, and review rules are added separately.</p>
          <p class="s2g-empty" data-empty hidden>No matching documents are available from the connected services.</p>
          <p class="s2g-error" hidden></p>
          <div class="s2g-dialog-actions"><button type="button" data-cancel>Cancel</button><button class="primary" type="submit">Start conversation</button></div>
        </form>
      </section>`;
      document.body.appendChild(mask);
      const form = mask.querySelector("form"), serviceSelect = form.elements.service, targetSelect = form.elements.target;
      const error = mask.querySelector(".s2g-error"), empty = mask.querySelector("[data-empty]");
      let services = [], targets = [];
      const close = value => { document.removeEventListener("keydown", escape); mask.remove(); resolve(value); };
      const escape = event => { if (event.key === "Escape") close(null); };
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
        renderTargets();
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
        if (!manual) renderTargets();
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
          if (selectedMode() === "create") {
            const documentId = form.elements.documentId.value.trim(), title = form.elements.title.value.trim();
            if (!documentId || !title) throw new Error("Document ID and title are required.");
            close(await api("/sources/create", { domain: service.domain, serviceBaseUrl: service.url, documentId, title, preset }));
          } else {
            const target = targets[Number(targetSelect.value)];
            if (!target) throw new Error("Choose an available target.");
            close(await api("/bindings/reserve", { ...target, preset }));
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
        } finally { setBusy(false); }
      });
    });
  }

  async function ensureWorkspace(ctx, descriptor) {
    const existing = ctx.workspaces.list.getSnapshot().items.find(item => item.path === descriptor.path);
    const workspace = existing || await ctx.workspaces.create({ path: descriptor.path });
    if (workspace.title !== descriptor.title) {
      try { return await ctx.workspaces.rename(workspace.workspaceId, descriptor.title); }
      catch (error) {
        if (!String(error instanceof Error ? error.message : error).includes("workspace/name-conflict")) throw error;
        let owner = "design source";
        try { owner = new URL(descriptor.ownerUrl).host; } catch { /* Use the stable fallback below. */ }
        const disambiguated = `${descriptor.title} · ${owner} · ${String(descriptor.key).slice(0, 8)}`;
        return ctx.workspaces.rename(workspace.workspaceId, disambiguated);
      }
    }
    return workspace;
  }

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
        ownerUrl: reservation.session.workspaceOwnerUrl,
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
      if (!session) throw new Error("The specification chat is not ready. Retry this card to continue in the saved package.");
      const result = await session.prompt([{ type: "text", text: reserved.continuation.message }], "queue", undefined, reserved.continuation.requestId);
      if (!result.ok) throw new Error(result.error?.message || "The initial request could not be submitted. Retry this card.");
      await api(`/source-requests/${encodeURIComponent(reserved.creation_request.requestId)}/continued`, {});
    }
    ctx.sessions.open(sessionId);
  }

  async function createUnboundSession(ctx) {
    const sessionId = await ctx.sessions.create({ agentPreset: "focused" });
    ctx.sessions.open(sessionId);
  }

  function resultContentValue(content) {
    if (!Array.isArray(content) || content.length !== 1 || content[0]?.type !== "text") return null;
    try { return JSON.parse(content[0].text); } catch { return null; }
  }

  const pretty = value => JSON.stringify(value, null, 2);
  const record = value => value && typeof value === "object" && !Array.isArray(value) ? value : {};

  function SpecDiff({ preview }) {
    const changes = Array.isArray(record(preview).diff) ? record(preview).diff : [];
    if (!changes.length) return h("p", null, "No semantic section changes reported.");
    return h("div", null, changes.map((change, index) => {
      const item = record(change);
      return h("details", { key: index }, h("summary", null, `${item.path || "change"} · ${item.change || "changed"}`),
        h("div", { className: "s2g-diff" },
          h("div", null, h("small", null, "Before"), h("pre", null, pretty(item.before))),
          h("div", null, h("small", null, "After"), h("pre", null, pretty(item.after)))));
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
        return h("g", { key: item.id }, h("rect", { x: point.x, y: point.y, width: 104, height: 36, rx: 6, fill: changed.has(`instance:${item.id}`) ? "#fef3c7" : "#e8f2ef", stroke: changed.has(`instance:${item.id}`) ? "#d97706" : "#176b5b" }), h("text", { x: point.x + 52, y: point.y + 22, textAnchor: "middle", fontSize: 11, fill: "#17211f" }, String(item.label || item.id)));
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
      h("header", null, h("h4", null, artifact.title || "Design proposal"), h("span", { className: "s2g-state", role: "status" }, review.state === "applied" && record(review.ownerResult).application_mode === "automatic" ? "Applied automatically" : review.state)),
      review.state === "applied" ? h("small", null, "Saved revision: ", h("code", null, String(record(review.ownerResult).source_revision_hash || ""))) : null,
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
      h("details", null, h("summary", null, "Exact operations"), h("pre", null, pretty(operations))),
      h("details", null, h("summary", null, "Requested change, rationale, assumptions, and owner preview"), h("pre", null, pretty({ requested_change: artifact.summary, rationale: artifact.rationale, assumptions: artifact.assumptions, preview: review.preview, diagnostics: review.diagnostics }))),
      actionable ? h("div", { className: "s2g-actions" }, h("button", { disabled: busy, onClick: () => act("discard") }, "Discard"), ["ready", "reconcile"].includes(review.state) ? h("button", { className: "primary", disabled: busy, onClick: () => act(review.domain === "spec" ? "apply" : "send") }, review.state === "reconcile" ? "Reconcile" : review.domain === "spec" ? "Approve and apply" : "Send to Circuit Designer") : null) : null,
      error ? h("p", { className: "s2g-error" }, error) : null);
  }

  function ProposalErrorCard({ error }) {
    const value = record(error);
    const actions = Array.isArray(value.suggested_actions) ? value.suggested_actions : [];
    return h("article", { className: "s2g-review" },
      h("header", null, h("h4", null, "Proposal not created"), h("span", { className: "s2g-state" }, value.error_code || "ERROR")),
      h("p", { className: "s2g-error" }, value.details || "The request could not be represented safely."),
      value.target ? h("p", null, "Target: ", h("code", null, String(value.target))) : null,
      actions.length ? h("ul", null, actions.map(action => h("li", { key: action }, action))) : null,
      h("small", null, value.retryable ? "Retryable after the underlying condition changes." : "No automatic retry will be attempted."));
  }

  function requiredInputMessage(request, values) {
    return JSON.stringify({ kind: "confirmed_proposal_input", input_id: request.input_id, values,
      instruction: "Use these confirmed values as authoritative. Pass confirmed_input_id and confirmed_values to the proposal tool." });
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
    const path = editable ? `${value.specDocumentRoot}${value.pathSeparator || "/"}${values.documentId}.spec` : value.destination;
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
          : "Review the suggested names. Creating the package opens a new chat and continues your original request there."),
      value.status !== "cancelled" ? h("p", null, "Save location: ", h("code", null, path)) : null,
      error || value.error ? h("p", { className: "s2g-error", role: "alert" }, error || value.error) : null,
      !terminal ? h("form", { className: "s2g-form", onSubmit: submit },
        h("label", null, "Title", h("input", { name: "title", value: values.title, disabled: busy || !editable, required: true, onChange: update("title") })),
        h("label", null, "Document ID", h("input", { name: "documentId", value: values.documentId, disabled: busy || !editable, required: true, maxLength: 128, pattern: "[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}", onChange: update("documentId") })),
        services.length > 1 ? h("label", null, "Spec service", h("select", { value: values.serviceBaseUrl, disabled: busy || !editable, onChange: update("serviceBaseUrl") },
          services.map(service => h("option", { key: service.url, value: service.url }, `${service.url}${service.available ? "" : " (offline)"}`)))) : null,
        unavailable ? h("p", { className: "s2g-error" }, "The selected Spec service is offline or none is configured. Start the service, then refresh availability.") : null,
        h("div", { className: "s2g-actions" },
          editable ? h("button", { type: "button", disabled: busy, onClick: cancel }, "Cancel") : null,
          h("button", { type: "button", disabled: busy, onClick: () => { setBusy(true); refresh().catch(caught => setError(caught.message)).finally(() => setBusy(false)); } }, "Refresh"),
          value.status !== "creating" ? h("button", { className: "primary", type: "submit", disabled: busy || unavailable }, value.status === "uncertain" ? "Recover creation receipt" : saved ? "Continue in specification chat" : "Create specification and continue") : null)) : null,
      value.status === "continued" ? h("div", { className: "s2g-actions" }, h("button", { type: "button", onClick: () => onOpen(value.destinationSessionId) }, "Open specification chat")) : null);
  }

  const proposalToolNames = new Set(["prepare_spec_proposal", "prepare_circuit_proposal", "prepare_spec_document_creation"]);

  const proposalReviewsDefinition = {
    kind: "spec2gds-proposal-reviews",
    match(event) {
      if (event.type === "turn/start") return { id: String(event.data.turn), role: "start" };
      if (event.type === "tool/call" || event.type === "tool/result") return { id: String(event.data.turn), role: "update" };
      return null;
    },
    start(_context, match) {
      if (match.event.type !== "turn/start") throw new Error("proposal review tracking requires turn/start");
      return { turn: match.event.data.turn, calls: new Map(), results: [] };
    },
    update(context, match) {
      if (match.event.type === "tool/call") {
        if (!proposalToolNames.has(match.event.data.name)) return context.state;
        const calls = new Map(context.state.calls);
        calls.set(String(match.event.data.callId), match.event.data.name);
        return { ...context.state, calls };
      }
      if (match.event.type !== "tool/result") return context.state;
      const callId = String(match.event.data.message.source.callId);
      if (!context.state.calls.has(callId)) return context.state;
      const value = resultContentValue(match.event.data.message.content[0]?.content);
      if (!value?.review && !value?.error && !value?.required_input && !value?.source_creation && !value?.creation_error) return context.state;
      const result = { callId, seq: match.event.seq, review: value.review || null, error: value.error || null, requiredInput: value.required_input || null,
        sourceCreation: value.source_creation || null, creationError: value.creation_error || null };
      return { ...context.state, results: [...context.state.results.filter(item => item.callId !== callId), result] };
    },
    buildLocationData(context, scope, previous) {
      if (scope !== "turn" || !context.state) return null;
      if (previous?.kind === "turn" && previous.turn === context.state.turn
        && previous.key === "spec2gds-proposal-reviews" && previous.value.results === context.state.results) return previous;
      return { kind: "turn", turn: context.state.turn, key: "spec2gds-proposal-reviews", value: { results: context.state.results } };
    },
  };

  function selectProposalReview(owner) {
    const results = owner.turn.data.get("spec2gds-proposal-reviews")?.results || [];
    return results.filter(result => result.seq < owner.seq).at(-1) || null;
  }

  function ProposalReviewTail({ matched, inputActions, onContinueCreation, onOpenCreation }) {
    if (matched.sourceCreation) return h(SourceCreationCard, { key: matched.sourceCreation.requestId, request: matched.sourceCreation, onContinue: onContinueCreation, onOpen: onOpenCreation });
    if (matched.creationError) return h("article", { className: "s2g-review" }, h("h4", null, "Specification creation unavailable"), h("p", { className: "s2g-error" }, matched.creationError));
    if (matched.review) return h(ReviewCard, { review: matched.review });
    if (matched.requiredInput) return h(ProposalInputCard, { request: matched.requiredInput, inputActions });
    return h(ProposalErrorCard, { error: matched.error });
  }

  function ExecutionDock({ sessionId }) {
    const [execution, setExecution] = React.useState(null);
    const [busy, setBusy] = React.useState(false);
    const [error, setError] = React.useState("");
    const [legacy, setLegacy] = React.useState(false);
    React.useEffect(() => {
      let disposed = false;
      const load = async () => {
        try {
          const data = await api(`/bindings/${encodeURIComponent(sessionId)}/execution`);
          if (!disposed) { setExecution(data.execution || null); setLegacy(Boolean(data.legacy)); }
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
    async function act(action) {
      setBusy(true); setError("");
      try {
        const data = await api(`/bindings/${encodeURIComponent(sessionId)}/execution/actions`, { action, revision: execution.revision, ...(deliveryId ? { deliveryId, acknowledgeUncertainty: true } : {}) });
        setExecution(data.execution);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : String(caught));
        const data = await api(`/bindings/${encodeURIComponent(sessionId)}/execution`).catch(() => null);
        if (data) setExecution(data.execution);
      } finally { setBusy(false); }
    }
    return h("div", { className: "s2g-workflow", "data-s2g-execution": execution.status },
      h("strong", null, execution.status.replaceAll("-", " ")),
      h("div", { className: "s2g-workflow-main" },
        h("div", { className: "s2g-workflow-objective" }, execution.reason || `${execution.mode} · ${members.map(member => member.id).join(", ")}`),
        h("div", { className: "s2g-workflow-meta" }, `rounds ${execution.rounds.length}/${limits.maxRounds} · requests ${requests.length}/${limits.maxRequests} · tokens ${tokens}/${limits.maxTokens} · active seconds ${Math.ceil(requests.reduce((sum, request) => sum + request.activeMillis, 0) / 1000)}/${Math.floor(limits.maxActiveMillis / 1000)} · pending ${pending.length} · failures ${failed.length}`),
        h("details", null, h("summary", null, "Recent events and deliveries"),
          h("ul", null, ...(execution.events || []).slice(-8).map(event => h("li", { key: event.id }, `${event.type} · ${event.producer}`))),
          ...failed.map(delivery => h("div", { key: delivery.id },
            h("p", null, `${delivery.target} · attempt ${delivery.attempt}: ${delivery.error}`),
            execution.status === "active" && !deliveries.some(item => item.retryOf === delivery.id)
              ? h("button", { disabled: busy, onClick: () => {
                if (window.confirm("This attempt may already have produced results. Retry with a new activation using the remaining budget?")) void act("retry", delivery.id);
              } }, "Acknowledge uncertainty and retry") : null))),
        error ? h("span", { className: "s2g-error" }, error) : null),
      h("div", { className: "s2g-workflow-controls" },
        execution.status === "active" ? h("button", { disabled: busy, onClick: () => void act("pause") }, "Pause") : null,
        ["paused", "needs-resume"].includes(execution.status) ? h("button", { disabled: busy, onClick: () => void act("resume") }, "Resume") : null,
        execution.status !== "stopped" ? h("button", { disabled: busy, onClick: () => void act("stop") }, "Stop") : null));
  }

  function BrandMark() { return h("span", { className: "s2g-mark" }, "S2G"); }
  function BrandName() { return h("span", { className: "s2g-brand" }, "spec2gds assistant"); }

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
    const sessionId = params.get("spec2gds_session") || launch.get("spec2gds_session");
    const unbound = launch.get("spec2gds_unbound") === "1";
    if (sessionId || unbound) {
      params.delete("spec2gds_session");
      history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}`);
      queueMicrotask(async () => {
        try {
          if (sessionId) await createBoundSession(ctx, await api(`/bindings/${encodeURIComponent(sessionId)}`));
          else await createUnboundSession(ctx);
        }
        catch (error) { window.alert(error instanceof Error ? error.message : String(error)); }
      });
    }
  };
  return module.exports;
} });

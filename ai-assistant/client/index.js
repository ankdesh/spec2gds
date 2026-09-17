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
    .s2g-diff{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.s2g-diff small{display:block;margin-bottom:3px;font-weight:600}
    .s2g-actions{display:flex;gap:8px;margin-top:10px}.s2g-actions button{padding:5px 9px;border:1px solid #176b5b;border-radius:6px;background:transparent;color:inherit;cursor:pointer}.s2g-actions button.primary{background:#176b5b;color:#fff}
    .s2g-circuit{width:100%;height:180px;border-radius:8px;background:color-mix(in srgb,currentColor 3%,transparent)}
    .s2g-error{color:#b42318;margin-top:7px}
    .s2g-mask{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:20px;background:rgba(8,18,16,.48);backdrop-filter:blur(3px)}
    .s2g-dialog{width:min(520px,100%);padding:20px;border:1px solid color-mix(in srgb,#176b5b 35%,transparent);border-radius:14px;background:var(--dsw-surface-primary,#fff);box-shadow:0 18px 55px rgba(0,0,0,.24);color:var(--text-primary,#17211f);font:14px/1.45 system-ui}
    .s2g-dialog h2{margin:0 0 5px;font-size:20px}.s2g-dialog>p{margin:0 0 16px;color:var(--text-secondary,#52615e)}
    .s2g-form{display:grid;gap:12px}.s2g-form label{display:grid;gap:5px;font-weight:600}.s2g-form input,.s2g-form select{box-sizing:border-box;width:100%;padding:9px 10px;border:1px solid color-mix(in srgb,currentColor 22%,transparent);border-radius:7px;background:transparent;color:inherit;font:inherit}
    .s2g-form .s2g-pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}.s2g-dialog-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:5px}.s2g-dialog-actions button{padding:8px 12px;border:1px solid #176b5b;border-radius:7px;background:transparent;color:inherit;cursor:pointer}.s2g-dialog-actions button.primary{background:#176b5b;color:#fff}.s2g-dialog-actions button:disabled{opacity:.55;cursor:wait}
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

  function reserveBindingDialog() {
    return new Promise(resolve => {
      const mask = document.createElement("div");
      mask.className = "s2g-mask";
      mask.innerHTML = `<section class="s2g-dialog" role="dialog" aria-modal="true" aria-labelledby="s2g-new-title">
        <h2 id="s2g-new-title">Connect an existing design</h2>
        <p>Each conversation stays bound to this owner and document.</p>
        <form class="s2g-form">
          <label>Owner<select name="domain"><option value="spec">Spec Editor</option><option value="circuit">Circuit Designer</option></select></label>
          <label>Owner service URL<input name="serviceBaseUrl" required value="http://127.0.0.1:6010" spellcheck="false"></label>
          <label>Document ID<input name="documentId" required autocomplete="off" spellcheck="false"></label>
          <label data-spec>Scope<select name="scope"><option value="document">Complete specification</option><option value="entity">One entity</option></select></label>
          <div class="s2g-pair" data-entity hidden><label>Entity kind<input name="entityKind" value="component" spellcheck="false"></label><label>Entity ID<input name="entityId" spellcheck="false"></label></div>
          <p class="s2g-error" hidden></p>
          <div class="s2g-dialog-actions"><button type="button" data-cancel>Cancel</button><button class="primary" type="submit">Connect</button></div>
        </form>
      </section>`;
      document.body.appendChild(mask);
      const form = mask.querySelector("form"), domain = form.elements.domain, scope = form.elements.scope;
      const entity = mask.querySelector("[data-entity]"), error = mask.querySelector(".s2g-error");
      const close = value => { document.removeEventListener("keydown", escape); mask.remove(); resolve(value); };
      const escape = event => { if (event.key === "Escape") close(null); };
      const sync = () => {
        const circuit = domain.value === "circuit";
        mask.querySelector("[data-spec]").hidden = circuit;
        entity.hidden = circuit || scope.value !== "entity";
      };
      const syncDomain = () => {
        const circuit = domain.value === "circuit";
        form.elements.serviceBaseUrl.value = circuit ? "http://127.0.0.1:6011/api/circuit-designer/v1" : "http://127.0.0.1:6010";
        sync();
      };
      domain.addEventListener("change", syncDomain);
      scope.addEventListener("change", sync);
      mask.querySelector("[data-cancel]").addEventListener("click", () => close(null));
      mask.addEventListener("mousedown", event => { if (event.target === mask) close(null); });
      document.addEventListener("keydown", escape);
      form.addEventListener("submit", async event => {
        event.preventDefault();
        const circuit = domain.value === "circuit", entityScope = !circuit && scope.value === "entity";
        if (entityScope && (!form.elements.entityKind.value.trim() || !form.elements.entityId.value.trim())) {
          error.textContent = "Entity kind and ID are required for entity scope."; error.hidden = false; return;
        }
        const buttons = [...form.querySelectorAll("button")]; buttons.forEach(button => { button.disabled = true; });
        error.hidden = true;
        try {
          close(await api("/bindings/reserve", {
            domain: domain.value,
            serviceBaseUrl: form.elements.serviceBaseUrl.value.trim(),
            documentId: form.elements.documentId.value.trim(),
            scope: circuit ? "document" : scope.value,
            ...(entityScope ? { entityKind: form.elements.entityKind.value.trim(), entityId: form.elements.entityId.value.trim() } : {}),
          }));
        } catch (caught) {
          error.textContent = caught instanceof Error ? caught.message : String(caught); error.hidden = false;
          buttons.forEach(button => { button.disabled = false; });
        }
      });
      queueMicrotask(() => form.elements.documentId.focus());
    });
  }

  async function createBoundSession(ctx, reserved) {
    let reservation = reserved;
    if (!reservation) {
      reservation = await reserveBindingDialog();
      if (!reservation) return;
    }
    const id = reservation.session.sessionId;
    try {
      await ctx.sessions.create({ sessionId: id, cwd: reservation.cwd });
      await api(`/bindings/${encodeURIComponent(id)}/activate`, {});
      ctx.sessions.open(id);
    } catch (error) {
      await api(`/bindings/${encodeURIComponent(id)}/abandon`, {}).catch(() => undefined);
      throw error;
    }
  }

  function resultValue(block) {
    if (!block || block.kind !== "tool-result" || !Array.isArray(block.content) || block.content.length !== 1 || block.content[0]?.type !== "text") return null;
    try { return JSON.parse(block.content[0].text); } catch { return null; }
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
    async function act(action) {
      setBusy(true); setError("");
      try { setReview((await api(`/reviews/${encodeURIComponent(review.proposalId)}/actions`, { action })).review); }
      catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
      finally { setBusy(false); }
    }
    return h("article", { className: "s2g-review" },
      h("header", null, h("h4", null, artifact.title || "Design proposal"), h("span", { className: "s2g-state" }, review.state)),
      h("p", null, artifact.summary || ""),
      review.domain === "spec" ? h(SpecDiff, { preview: review.preview }) : h(CircuitDiff, { preview: review.preview }),
      h("details", null, h("summary", null, "Exact operations"), h("pre", null, pretty(operations))),
      h("details", null, h("summary", null, "Rationale, assumptions, and owner preview"), h("pre", null, pretty({ rationale: artifact.rationale, assumptions: artifact.assumptions, preview: review.preview, diagnostics: review.diagnostics }))),
      actionable ? h("div", { className: "s2g-actions" }, h("button", { disabled: busy, onClick: () => act("discard") }, "Discard"), ["ready", "reconcile"].includes(review.state) ? h("button", { className: "primary", disabled: busy, onClick: () => act(review.domain === "spec" ? "apply" : "send") }, review.state === "reconcile" ? "Reconcile" : review.domain === "spec" ? "Approve and apply" : "Send to Circuit Designer") : null) : null,
      error ? h("p", { className: "s2g-error" }, error) : null);
  }

  function ProposalToolView({ block, toolName }) {
    const value = resultValue(block);
    if (!value?.review) return h("div", { className: "s2g-review" }, block?.kind === "tool-result" ? "Proposal result unavailable." : `${toolName.replaceAll("_", " ")}…`);
    return h(ReviewCard, { review: value.review });
  }

  function BrandMark() { return h("span", { className: "s2g-mark" }, "S2G"); }
  function BrandName() { return h("span", { className: "s2g-brand" }, "spec2gds assistant"); }

  module.exports.inject = ["slots", "uiSession", "sessions"];
  module.exports.apply = function apply(ctx) {
    ctx.uiSession.registerNewSessionHandler({ id: "spec2gds", priority: -100, async handle() { await createBoundSession(ctx); return true; } });
    ctx.slots.inject("sidebar.brand.mark", () => ctx.slots.register({ name: "sidebar.brand.mark" }, BrandMark));
    ctx.slots.inject("sidebar.brand.name", () => ctx.slots.register({ name: "sidebar.brand.name" }, BrandName));
    for (const key of ["prepare_spec_proposal", "prepare_circuit_proposal"]) ctx.slots.inject("tool.call.toolview", () => ctx.slots.register({ name: "tool.call.toolview", key }, ProposalToolView));
    const params = new URLSearchParams(location.search), sessionId = params.get("spec2gds_session"), cwd = params.get("spec2gds_cwd");
    if (sessionId && cwd) {
      params.delete("spec2gds_session"); params.delete("spec2gds_cwd");
      history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}${location.hash}`);
      queueMicrotask(() => createBoundSession(ctx, { session: { sessionId }, cwd }).catch(error => window.alert(error instanceof Error ? error.message : String(error))));
    }
  };
  return module.exports;
} });

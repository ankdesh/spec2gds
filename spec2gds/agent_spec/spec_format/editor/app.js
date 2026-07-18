/** Browser client for the V1 API.
 *
 * The client intentionally owns presentation state only. Every edit is sent
 * back as a typed transaction carrying the last observed source revision.
 */

const state = {
  snapshot: null,
  path: "",
  view: "overview",
  executions: [],
  artifacts: [],
  proposals: [],
};

const $ = (selector) => document.querySelector(selector);
const workspace = $("#workspace");
const notice = $("#notice");

/** Escape all dynamic source or activity text before inserting HTML. */
function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

/** Call the local V1 API and normalize JSON/text failures to Error objects. */
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = payload?.detail ?? payload;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

/** Publish a persistent, accessible status message above the workspace. */
function setNotice(message, tone = "neutral") {
  notice.textContent = message;
  notice.dataset.tone = tone;
}

/** Derive the concise display name from a validated SpecIR entity. */
function entityLabel(entity) {
  return entity.vlnv?.split(":").at(-2) || entity.ref?.entity_id || "Unnamed entity";
}

/** Encode the public compact entity-reference syntax used by transactions. */
function entityRef(kind, entityId) {
  return `${kind}:${entityId}`;
}

/** Return explicit entry design ids for fast rendering membership checks. */
function entryDesignIds() {
  return new Set((state.snapshot?.entry_designs || []).map((item) => item.ref.entity_id));
}

/** Count the complete typed narrative tree, including nested list content. */
function narrativeCount(blocks) {
  return blocks.reduce((count, block) => count + 1 + narrativeCount(block.children || []), 0);
}

/** Synchronize persistent navigation chrome with the latest snapshot/activity. */
function updateChrome() {
  const snapshot = state.snapshot;
  const sourceDiagnostics = snapshot?.diagnostics?.source || [];
  const artifactDiagnostics = snapshot?.diagnostics?.artifacts || [];
  $("#document-title").textContent = snapshot?.document_id || "Choose a sample";
  $("#document-summary").textContent = snapshot
    ? `${snapshot.components.length} components · ${snapshot.designs.length} designs · ${snapshot.entry_designs.length} entry points`
    : "Open a deterministic V1 package to explore its SpecIR.";
  $("#revision-label").textContent = snapshot
    ? snapshot.source_revision_hash.replace("sha256:", "rev ").slice(0, 16)
    : "No source loaded";
  $("#connection-light").classList.toggle("online", Boolean(snapshot));
  $("#count-overview").textContent = snapshot ? snapshot.components.length + snapshot.designs.length : "—";
  $("#count-components").textContent = snapshot?.components.length || 0;
  $("#count-designs").textContent = snapshot?.designs.length || 0;
  $("#count-narrative").textContent = narrativeCount(snapshot?.narrative?.blocks || []);
  $("#count-activity").textContent = state.executions.length + state.proposals.length;
  $("#count-diagnostics").textContent = sourceDiagnostics.length + artifactDiagnostics.length;
}

/** Populate the source picker from packages advertised by the Python service. */
async function loadSamples() {
  try {
    const data = await api("/samples");
    const select = $("#sample-select");
    for (const sample of data.samples) {
      const option = document.createElement("option");
      option.value = sample.path;
      option.textContent = sample.name;
      select.append(option);
    }
  } catch (error) {
    setNotice(`Could not list samples: ${error.message}`, "error");
  }
}

/** Refresh activity independently because it does not alter source revision. */
async function refreshActivity() {
  if (!state.snapshot) return;
  const [executions, artifacts, proposals] = await Promise.all([
    api("/executions"),
    api("/artifacts"),
    api("/proposals"),
  ]);
  state.executions = executions.executions;
  state.artifacts = artifacts.artifacts;
  state.proposals = proposals.proposals;
}

/** Validate a package server-side and adopt its immutable editor snapshot. */
async function openPackage(path) {
  if (!path.trim()) {
    setNotice("Choose a checked-in sample or enter an absolute .spec path.", "warning");
    return;
  }
  setNotice("Validating package and constructing SpecIR…");
  try {
    state.snapshot = await api("/documents/open", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path }),
    });
    state.path = path;
    await refreshActivity();
    updateChrome();
    render();
    setNotice("Package loaded. Views below are derived from the validated source revision.", "success");
  } catch (error) {
    setNotice(`Open failed: ${error.message}`, "error");
  }
}

/** Render one compact architecture metric card. */
function metric(label, value, detail) {
  return `<article class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(detail)}</small></article>`;
}

/** Render the source hierarchy and explicit integration entry points. */
function renderOverview() {
  const snapshot = state.snapshot;
  const entries = entryDesignIds();
  const compositionByComponent = new Map(
    snapshot.component_compositions.map((mapping) => [mapping.component.entity_id, mapping.internal_design.entity_id]),
  );
  workspace.innerHTML = `
    <div class="page-heading"><div><p class="eyebrow">Validated source graph</p><h2>Architecture overview</h2></div><span class="hash">${escapeHtml(snapshot.source_revision_hash.slice(0, 24))}…</span></div>
    <div class="metrics">
      ${metric("Components", snapshot.components.length, `${compositionByComponent.size} composite`)}
      ${metric("Designs", snapshot.designs.length, `${entries.size} explicit entry`)}
      ${metric("Narrative nodes", narrativeCount(snapshot.narrative.blocks), `${snapshot.assets.length} source asset`)}
      ${metric("Action executions", state.executions.length, `${state.artifacts.length} artifact`)}
    </div>
    <div class="overview-grid">
      <section class="panel">
        <div class="panel-heading"><div><p class="eyebrow">Hierarchy</p><h3>Composition map</h3></div></div>
        <div class="hierarchy-list">
          ${snapshot.components.map((component) => {
            const internalId = compositionByComponent.get(component.ref.entity_id);
            const design = snapshot.designs.find((item) => item.ref.entity_id === internalId);
            return `<button class="hierarchy-row" data-jump="components">
              <span class="entity-icon component">C</span><span><strong>${escapeHtml(entityLabel(component))}</strong><small>${escapeHtml(component.vlnv)}</small></span>
              <span class="hierarchy-arrow">${design ? `owns → ${escapeHtml(entityLabel(design))}` : "leaf"}</span>
            </button>`;
          }).join("")}
        </div>
      </section>
      <section class="panel">
        <div class="panel-heading"><div><p class="eyebrow">Entry points</p><h3>Integration designs</h3></div></div>
        <div class="entry-grid">
          ${snapshot.designs.filter((design) => entries.has(design.ref.entity_id)).map((design) => `
            <button class="entry-card" data-jump="designs">
              <span class="entry-badge">ENTRY</span><strong>${escapeHtml(entityLabel(design))}</strong>
              <small>${design.instances.length} instances · ${design.connections.length} connections</small>
            </button>`).join("") || "<p class='empty-copy'>No entry designs selected.</p>"}
        </div>
      </section>
    </div>`;
}

/** Build the entity-targeted action launcher shared by source cards. */
function actionButton(kind, entity) {
  return `<button class="secondary entity-actions" data-kind="${kind}" data-id="${escapeHtml(entity.ref.entity_id)}" data-label="${escapeHtml(entityLabel(entity))}">Run action</button>`;
}

/** Render reusable components directly from ComponentIR projections. */
function renderComponents() {
  const compositions = new Map(state.snapshot.component_compositions.map((item) => [item.component.entity_id, item.internal_design.entity_id]));
  workspace.innerHTML = `
    <div class="page-heading"><div><p class="eyebrow">IP-XACT components</p><h2>Reusable hardware blocks</h2></div><p>${state.snapshot.components.length} validated definitions</p></div>
    <div class="card-grid">${state.snapshot.components.map((component) => `
      <article class="entity-card">
        <div class="entity-card-heading"><span class="entity-icon component">C</span><div><h3>${escapeHtml(entityLabel(component))}</h3><code>${escapeHtml(component.vlnv)}</code></div></div>
        <div class="entity-meta"><span>${component.ports.length} ports</span><span>${component.interfaces.length} interfaces</span>${compositions.has(component.ref.entity_id) ? "<span class='accent-pill'>composite</span>" : "<span>leaf</span>"}</div>
        <div class="mini-section"><strong>Ports</strong><div class="chip-row">${component.ports.map((port) => `<span class="chip"><i class="direction ${port.direction}">${escapeHtml(port.direction || "—")}</i>${escapeHtml(port.name)}</span>`).join("") || "<small>No external ports</small>"}</div></div>
        <div class="mini-section"><strong>Interfaces</strong>${component.interfaces.map((item) => `<div class="interface-row"><span>${escapeHtml(item.name)}</span><small>${escapeHtml(item.role)} · ${escapeHtml(item.bus_vlnv.split(":").at(-2))}</small></div>`).join("") || "<small>No bus interfaces</small>"}</div>
        <footer>${actionButton("component", component)}</footer>
      </article>`).join("")}</div>`;
}

/** Render a read-only topology; this view is never persisted as source. */
function topology(design) {
  const edges = design.connections.map((connection) => {
    const endpoints = connection.kind === "interface" ? connection.interface_endpoints : connection.port_endpoints;
    return `<div class="edge-row"><span>${escapeHtml(connection.name)}</span><strong>${endpoints.map((item) => escapeHtml(item.instance_name)).join(" → ") || "external boundary"}</strong><small>${escapeHtml(connection.kind)}</small></div>`;
  }).join("");
  return `<div class="topology"><div class="topology-nodes">${design.instances.map((instance) => `<div class="topology-node"><span>${escapeHtml(instance.name)}</span><small>${escapeHtml(instance.component_vlnv.split(":").at(-2))}</small></div>`).join("") || "<p class='empty-copy'>No instances</p>"}</div><div class="edge-list">${edges || "<p class='empty-copy'>No connections</p>"}</div></div>`;
}

/** Render each design with its derived instances and connections. */
function renderDesigns() {
  const entries = entryDesignIds();
  workspace.innerHTML = `
    <div class="page-heading"><div><p class="eyebrow">Derived topology</p><h2>Design hierarchy</h2></div><p>Read-only graph from current SpecIR</p></div>
    <div class="design-stack">${state.snapshot.designs.map((design) => `
      <article class="design-card">
        <div class="panel-heading"><div><span class="entity-icon design">D</span><div><h3>${escapeHtml(entityLabel(design))}</h3><code>${escapeHtml(design.vlnv)}</code></div></div><div class="design-actions">${entries.has(design.ref.entity_id) ? "<span class='entry-badge'>ENTRY</span>" : ""}${actionButton("design", design)}</div></div>
        ${topology(design)}
      </article>`).join("")}</div>`;
}

/** Recursively render the supported V1 narrative AST vocabulary. */
function renderNarrativeBlock(block, depth = 0) {
  const children = (block.children || []).map((child) => renderNarrativeBlock(child, depth + 1)).join("");
  if (block.type === "section") return `<section class="narrative-section depth-${depth}"><h${Math.min(depth + 2, 6)}>${escapeHtml(block.text)}</h${Math.min(depth + 2, 6)}>${children}</section>`;
  if (block.type === "paragraph") return `<p>${escapeHtml(block.text)}</p>${children}`;
  if (block.type === "list") return `<${block.ordered ? "ol" : "ul"}>${(block.children || []).map((child) => `<li>${escapeHtml(child.text)}</li>`).join("")}</${block.ordered ? "ol" : "ul"}>`;
  if (block.type === "table") return `<div class="table-wrap"><table>${block.rows.map((row, index) => `<tr>${row.map((cell) => index === 0 ? `<th>${escapeHtml(cell)}</th>` : `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</table></div>`;
  if (block.type === "image") return `<figure><img src="/assets/${encodeURIComponent(block.asset_id)}/content" alt="${escapeHtml(block.alt_text)}" /><figcaption>${escapeHtml(block.caption || block.alt_text)}</figcaption></figure>`;
  if (block.type === "entity_link") return `<div class="entity-link"><span>↗</span><strong>${escapeHtml(block.text)}</strong><code>${escapeHtml((block.entity_refs || []).map((item) => entityRef(item.entity_kind, item.entity_id)).join(", "))}</code></div>`;
  if (block.type === "live_view") {
    const ref = block.entity_refs?.[0];
    const design = state.snapshot.designs.find((item) => item.ref.entity_id === ref?.entity_id);
    return `<div class="live-view"><div class="live-label">LIVE · ${escapeHtml(block.renderer_id)}</div>${design ? topology(design) : "<p>Referenced entity is unavailable.</p>"}</div>`;
  }
  return `<p>${escapeHtml(block.text)}</p>${children}`;
}

/** Render narrative source beside a revision-guarded note composer. */
function renderNarrative() {
  workspace.innerHTML = `
    <div class="page-heading"><div><p class="eyebrow">Project narrative</p><h2>Architecture story</h2></div><p>Typed AST with live source views</p></div>
    <div class="narrative-layout"><article class="narrative-document">${state.snapshot.narrative.blocks.map((block) => renderNarrativeBlock(block)).join("") || "<p class='empty-copy'>No narrative blocks.</p>"}</article>
    <aside class="panel note-composer"><p class="eyebrow">Validated edit</p><h3>Add architect note</h3><p>Creates a paragraph block through an atomic revision-guarded transaction.</p><textarea id="note-text" placeholder="Capture a design decision…"></textarea><button id="add-note" class="primary">Commit note</button></aside></div>`;
}

/** Render immutable executions, artifact provenance, and proposal review. */
function renderActivity() {
  workspace.innerHTML = `
    <div class="page-heading"><div><p class="eyebrow">Immutable provenance</p><h2>Actions, artifacts & proposals</h2></div><button id="refresh-activity" class="secondary">Refresh</button></div>
    <div class="activity-columns">
      <section class="panel"><div class="panel-heading"><h3>Action executions</h3><span>${state.executions.length}</span></div>${state.executions.slice().reverse().map((item) => `<article class="activity-item"><span class="status ${item.status}">${escapeHtml(item.status)}</span><strong>${escapeHtml(item.action_id)}</strong><small>${escapeHtml(item.execution_id)}</small><p>${escapeHtml(item.report?.summary || item.diagnostics?.[0] || "No report summary")}</p></article>`).join("") || "<p class='empty-copy'>Run an action from a component or design.</p>"}</section>
      <section class="panel"><div class="panel-heading"><h3>Artifacts</h3><span>${state.artifacts.length}</span></div>${state.artifacts.slice().reverse().map((item) => `<article class="activity-item"><span class="artifact-kind">${escapeHtml(item.kind)}</span><strong>${escapeHtml(item.role)}</strong><small>${item.size} bytes · ${escapeHtml(item.sha256.slice(0, 18))}…</small><a href="/artifacts/${encodeURIComponent(item.artifact_id)}/content" target="_blank">Open verified content ↗</a></article>`).join("") || "<p class='empty-copy'>No generated artifacts.</p>"}</section>
      <section class="panel"><div class="panel-heading"><h3>Change proposals</h3><span>${state.proposals.length}</span></div>${state.proposals.slice().reverse().map((item) => `<article class="activity-item"><span class="status ${item.review_status}">${escapeHtml(item.review_status)}</span><strong>${escapeHtml(item.rationale)}</strong><small>${item.operations.length} proposed operation</small>${item.review_status === "pending" ? `<div class="button-row"><button class="accept-proposal primary" data-id="${escapeHtml(item.proposal_id)}">Accept</button><button class="reject-proposal secondary" data-id="${escapeHtml(item.proposal_id)}">Reject</button></div>` : ""}</article>`).join("") || "<p class='empty-copy'>No proposals awaiting review.</p>"}</section>
    </div>`;
}

/** Render source and sidecar validation health without hiding either domain. */
function renderDiagnostics() {
  const source = state.snapshot.diagnostics.source;
  const artifacts = state.snapshot.diagnostics.artifacts;
  const all = [...source.map((message) => ["Source", message]), ...artifacts.map((message) => ["Artifact", message])];
  workspace.innerHTML = `<div class="page-heading"><div><p class="eyebrow">Validation health</p><h2>Diagnostics</h2></div><span class="health-badge ${all.length ? "warning" : "healthy"}">${all.length ? `${all.length} issue(s)` : "All checks pass"}</span></div><section class="panel diagnostics-panel">${all.map(([kind, message]) => `<article><span>${kind}</span><p>${escapeHtml(message)}</p></article>`).join("") || "<div class='healthy-empty'><strong>✓</strong><h3>Source graph is internally consistent</h3><p>Package, profile, references, hierarchy, narrative, and known artifact content all validate.</p></div>"}</section>`;
}

/** Select the active view and bind events after replacing workspace markup. */
function render() {
  if (!state.snapshot) {
    workspace.className = "workspace empty";
    workspace.innerHTML = `<div class="empty-hero"><span class="hero-orbit">◫</span><p class="eyebrow">V1 architecture workbench</p><h2>Source truth you can inspect.</h2><p>Open the bundled demo to see components, reusable designs, live narrative views, action provenance, and revision-guarded editing.</p><button id="open-first-sample" class="primary">Open visual demo</button></div>`;
    bindEvents();
    return;
  }
  workspace.className = `workspace view-${state.view}`;
  ({ overview: renderOverview, components: renderComponents, designs: renderDesigns, narrative: renderNarrative, activity: renderActivity, diagnostics: renderDiagnostics }[state.view] || renderOverview)();
  bindEvents();
}

/** Fetch target-compatible actions and present their declared outputs. */
async function showActions(kind, entityId, label) {
  const dialog = $("#action-dialog");
  $("#action-title").textContent = label;
  $("#action-list").innerHTML = "<p>Checking action preconditions…</p>";
  dialog.showModal();
  try {
    const data = await api(`/entities/${kind}/${entityId}/actions`);
    $("#action-list").innerHTML = data.actions.map((action) => `<article class="action-option"><div><strong>${escapeHtml(action.title)}</strong><small>${escapeHtml(action.action_id)} · v${escapeHtml(action.version)}</small></div><p>Produces: ${escapeHtml((action.produced_artifact_roles || []).join(", ") || "review proposal")}</p><button class="execute-action primary" data-kind="${kind}" data-id="${escapeHtml(entityId)}" data-action="${escapeHtml(action.action_id)}">Execute</button></article>`).join("") || "<p>No actions target this entity kind.</p>";
    bindEvents();
  } catch (error) {
    $("#action-list").innerHTML = `<p class="error-copy">${escapeHtml(error.message)}</p>`;
  }
}

/** Execute a trusted action and move focus to its durable activity record. */
async function executeAction(button) {
  button.disabled = true;
  button.textContent = "Executing…";
  try {
    const execution = await api(`/entities/${button.dataset.kind}/${button.dataset.id}/actions/${button.dataset.action}/executions`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ inputs: {}, input_artifact_ids: [] }),
    });
    $("#action-dialog").close();
    await refreshActivity();
    updateChrome();
    state.view = "activity";
    syncNavigation();
    render();
    setNotice(`Action execution ${execution.status}: ${execution.action_id}`, execution.status === "succeeded" ? "success" : "error");
  } catch (error) {
    setNotice(`Action failed: ${error.message}`, "error");
    button.disabled = false;
    button.textContent = "Execute";
  }
}

/** Commit one paragraph through the atomic transaction endpoint. */
async function addNote() {
  const text = $("#note-text").value.trim();
  if (!text) return setNotice("Write a note before committing it.", "warning");
  const blockId = `architect_note_${Date.now()}`;
  try {
    const result = await api("/transactions", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ expected_source_revision_hash: state.snapshot.source_revision_hash, operations: [{ type: "upsert_narrative_block", block: { block_id: blockId, type: "paragraph", text } }] }),
    });
    state.snapshot = result.snapshot;
    updateChrome(); render();
    setNotice("Architect note committed as a validated narrative block.", "success");
  } catch (error) { setNotice(`Edit rejected: ${error.message}`, "error"); }
}

/** Accept or reject a proposal through its explicit review endpoint. */
async function reviewProposal(proposalId, decision) {
  try {
    const options = decision === "accept"
      ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ expected_source_revision_hash: state.snapshot.source_revision_hash }) }
      : { method: "POST" };
    const result = await api(`/proposals/${proposalId}/${decision}`, options);
    if (result.snapshot) state.snapshot = result.snapshot;
    await refreshActivity(); updateChrome(); render();
    setNotice(`Proposal ${decision}ed.`, "success");
  } catch (error) { setNotice(`Proposal review failed: ${error.message}`, "error"); }
}

/** Keep top-level navigation state visible after programmatic view changes. */
function syncNavigation() {
  document.querySelectorAll("#view-nav button").forEach((button) => button.classList.toggle("active", button.dataset.view === state.view));
}

/** Bind listeners to the current rendered subtree after each view refresh. */
function bindEvents() {
  document.querySelectorAll(".entity-actions").forEach((button) => button.onclick = () => showActions(button.dataset.kind, button.dataset.id, button.dataset.label));
  document.querySelectorAll(".execute-action").forEach((button) => button.onclick = () => executeAction(button));
  document.querySelectorAll("[data-jump]").forEach((button) => button.onclick = () => { state.view = button.dataset.jump; syncNavigation(); render(); });
  document.querySelectorAll(".accept-proposal").forEach((button) => button.onclick = () => reviewProposal(button.dataset.id, "accept"));
  document.querySelectorAll(".reject-proposal").forEach((button) => button.onclick = () => reviewProposal(button.dataset.id, "reject"));
  if ($("#add-note")) $("#add-note").onclick = addNote;
  if ($("#refresh-activity")) $("#refresh-activity").onclick = async () => { await refreshActivity(); updateChrome(); render(); };
  if ($("#open-first-sample")) $("#open-first-sample").onclick = () => { const path = $("#sample-select").options[1]?.value; if (path) { $("#package-path").value = path; openPackage(path); } };
}

$("#sample-select").addEventListener("change", (event) => { $("#package-path").value = event.target.value; });
$("#open-package").addEventListener("click", () => openPackage($("#package-path").value));
$("#package-path").addEventListener("keydown", (event) => { if (event.key === "Enter") openPackage(event.target.value); });
$("#view-nav").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-view]");
  if (!button) return;
  state.view = button.dataset.view; syncNavigation(); render();
});

await loadSamples();
render();

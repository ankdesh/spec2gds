/**
 * Verification Planner Web UI Shell
 * Implements Layer 1 interactions: intent authoring, hierarchy navigation, review checklists, and exports.
 */

const API_BASE = "/api/verification/v1";

const state = {
  activePlanId: null,
  plan: null,
  snapshot: null,
  hierarchy: [],
  records: {},
  requirements: [],
  selectedItemId: null,
  activeInspectorTab: "details",
  dirty: false,
  // Layer 2 State
  activeLayer: "plan",
  activeCoverageSubnav: "matrix",
  coverageMatrix: null,
  coverageGaps: [],
  campaigns: [],
  activeCampaignId: null,
  runs: [],
  profiles: [],
  stagedImportId: null,
  stagedImportDigest: null,
  // Layer 3 State
  activeImplementationSubnav: "recipes",
  recipes: [],
  targetBindingSets: [],
  backendConfigurations: [],
  backendPlugins: [],
  generationJobs: [],
};

// --- DOM References ---
const planSelector = document.getElementById("planSelector");
const breadcrumbPath = document.getElementById("breadcrumbPath");
const breadcrumbRevision = document.getElementById("breadcrumbRevision");
const hierarchyTree = document.getElementById("hierarchyTree");
const hierarchySearchInput = document.getElementById("hierarchySearchInput");
const intentTableBody = document.getElementById("intentTableBody");
const emptyState = document.getElementById("emptyState");
const viewOutline = document.getElementById("viewOutline");
const viewSourceRequirements = document.getElementById("viewSourceRequirements");
const inspectorContent = document.getElementById("inspectorContent");
const footerStats = document.getElementById("footerStats");
const footerSnapshot = document.getElementById("footerSnapshot");

// --- Initialization ---
document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await loadPlansList();
});

function setupEventListeners() {
  planSelector.addEventListener("change", (e) => {
    if (e.target.value) {
      loadPlan(e.target.value);
    }
  });

  // Layer Navigation Tabs
  document.querySelectorAll(".layer-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const layer = tab.dataset.layer;
      if (tab.disabled) return;
      document.querySelectorAll(".layer-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      switchLayer(layer);
    });
  });

  // Modal Triggers
  document.getElementById("btnNewPlan").addEventListener("click", openNewPlanModal);
  document.getElementById("btnAddSection").addEventListener("click", () => openSectionModal());
  document.getElementById("btnAddIntent").addEventListener("click", () => openIntentModal());
  document.getElementById("btnEmptyAddSection").addEventListener("click", () => openSectionModal());
  document.getElementById("btnEmptyBrowseSource").addEventListener("click", toggleSourceRequirementsView);
  document.getElementById("btnToggleSourceView").addEventListener("click", toggleSourceRequirementsView);
  document.getElementById("btnReviewPlan").addEventListener("click", openReviewModal);
  document.getElementById("btnReviewPlanHeader").addEventListener("click", openReviewModal);

  // Layer 2 Subnav Triggers
  document.getElementById("btnSubnavMatrix").addEventListener("click", () => switchCoverageSubnav("matrix"));
  document.getElementById("btnSubnavGaps").addEventListener("click", () => switchCoverageSubnav("gaps"));
  document.getElementById("btnSubnavRuns").addEventListener("click", () => switchCoverageSubnav("runs"));
  document.getElementById("btnSubnavTrace").addEventListener("click", () => switchCoverageSubnav("trace"));

  // Layer 2 Modal Triggers
  document.getElementById("btnAddObjective").addEventListener("click", openAddObjectiveModal);
  document.getElementById("btnImportResults").addEventListener("click", openImportResultsModal);
  document.getElementById("btnReviewCoverage").addEventListener("click", openReviewCoverageModal);
  document.getElementById("btnFreezeReport").addEventListener("click", openFreezeReportModal);
  document.getElementById("btnNewCampaign").addEventListener("click", openNewCampaignModal);

  // Layer 2 Filters & Selectors
  document.getElementById("filterMatrixStatus").addEventListener("change", () => loadCoverageMatrix());
  document.getElementById("selectMatrixProfile").addEventListener("change", () => loadCoverageMatrix());
  document.getElementById("filterGapSeverity").addEventListener("change", () => renderGapsTable());
  document.getElementById("selectActiveCampaign").addEventListener("change", (e) => {
    state.activeCampaignId = e.target.value;
    loadRuns();
    loadCoverageMatrix();
  });

  // Layer 2 Submissions
  document.getElementById("btnSaveObjective").addEventListener("click", saveObjectiveForm);
  document.getElementById("btnConfirmReviewCoverage").addEventListener("click", submitReviewCoverage);
  document.getElementById("btnStageImportPreview").addEventListener("click", stageImportResults);
  document.getElementById("btnCommitImport").addEventListener("click", commitImportResults);
  document.getElementById("btnSubmitFreezeReport").addEventListener("click", submitFreezeReport);
  document.getElementById("btnSubmitNewCampaign").addEventListener("click", submitNewCampaign);
  document.getElementById("fileResultUpload").addEventListener("change", handleResultFileSelect);

  // Layer 3 Subnav Triggers
  const subnavRecipes = document.getElementById("btnSubnavRecipes");
  if (subnavRecipes) subnavRecipes.addEventListener("click", () => switchImplementationSubnav("recipes"));
  const subnavBindings = document.getElementById("btnSubnavBindings");
  if (subnavBindings) subnavBindings.addEventListener("click", () => switchImplementationSubnav("bindings"));
  const subnavBackends = document.getElementById("btnSubnavBackends");
  if (subnavBackends) subnavBackends.addEventListener("click", () => switchImplementationSubnav("backends"));
  const subnavGenerations = document.getElementById("btnSubnavGenerations");
  if (subnavGenerations) subnavGenerations.addEventListener("click", () => switchImplementationSubnav("generations"));

  // Layer 3 Modal & Action Triggers
  const btnAddRecipe = document.getElementById("btnAddRecipe");
  if (btnAddRecipe) btnAddRecipe.addEventListener("click", () => openRecipeModal());
  const btnAddBinding = document.getElementById("btnAddBinding");
  if (btnAddBinding) btnAddBinding.addEventListener("click", () => openBindingModal());
  const btnReviewImpl = document.getElementById("btnReviewImplementation");
  if (btnReviewImpl) btnReviewImpl.addEventListener("click", () => openReviewImplementationModal());
  const btnGenArtifacts = document.getElementById("btnGenerateArtifacts");
  if (btnGenArtifacts) btnGenArtifacts.addEventListener("click", () => openGenerationModal());

  const btnValPreflight = document.getElementById("btnValidateIRPreflight");
  if (btnValPreflight) btnValPreflight.addEventListener("click", validateIRPreflight);
  const btnSubRecipe = document.getElementById("btnSubmitRecipe");
  if (btnSubRecipe) btnSubRecipe.addEventListener("click", submitRecipe);
  const btnSubBinding = document.getElementById("btnSubmitBinding");
  if (btnSubBinding) btnSubBinding.addEventListener("click", submitBinding);
  const btnConfReviewImpl = document.getElementById("btnConfirmReviewImplementation");
  if (btnConfReviewImpl) btnConfReviewImpl.addEventListener("click", submitReviewImplementation);
  const btnRunGenPrev = document.getElementById("btnRunGenPreview");
  if (btnRunGenPrev) btnRunGenPrev.addEventListener("click", runGenerationPreview);
  const btnSubGen = document.getElementById("btnSubmitGeneration");
  if (btnSubGen) btnSubGen.addEventListener("click", submitGeneration);
  const filterKind = document.getElementById("filterRecipeKind");
  if (filterKind) filterKind.addEventListener("change", () => renderRecipesTable());

  // Inspector Tabs
  document.querySelectorAll(".inspector-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".inspector-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      state.activeInspectorTab = tab.dataset.tab;
      renderInspector();
    });
  });

  // Close modals
  document.querySelectorAll("[data-close]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById(btn.dataset.close).classList.remove("open");
    });
  });

  // Modal Submissions
  document.getElementById("btnSaveSection").addEventListener("click", saveSectionForm);
  document.getElementById("btnSaveIntentDraft").addEventListener("click", () => saveIntentForm(false));
  document.getElementById("btnSaveIntentReady").addEventListener("click", () => saveIntentForm(true));
  document.getElementById("btnConfirmReviewCheckpoint").addEventListener("click", submitReviewCheckpoint);
  document.getElementById("btnSubmitNewPlan").addEventListener("click", submitNewPlan);

  // Sample fixture buttons in New Plan modal
  document.getElementById("btnSampleFifo").addEventListener("click", () => loadSampleFixture("fifo"));
  document.getElementById("btnSampleTwoFifo").addEventListener("click", () => loadSampleFixture("two_fifo"));

  // Observation row in intent modal
  document.getElementById("btnAddObservationRow").addEventListener("click", addObservationRow);

  // Export Header button
  document.getElementById("btnExportHeader").addEventListener("click", handleExportMenu);
  document.getElementById("btnImportBundle").addEventListener("click", handleImportBundle);

  // Hierarchy search filter
  let searchTimeout = null;
  hierarchySearchInput.addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      filterHierarchy(e.target.value);
    }, 200);
  });

  // Global Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      hierarchySearchInput.focus();
    } else if (e.key === "Escape") {
      document.querySelectorAll(".modal-overlay.open").forEach((m) => m.classList.remove("open"));
    }
  });
}

// --- Data Loading ---
async function loadPlansList() {
  try {
    const res = await fetch(`${API_BASE}/plans`);
    if (!res.ok) throw new Error("Failed to load plans");
    const plans = await res.json();

    planSelector.innerHTML = '<option value="">Select a plan...</option>';
    plans.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = `${p.name} (r${p.edit_revision})`;
      planSelector.appendChild(opt);
    });

    if (plans.length > 0 && !state.activePlanId) {
      planSelector.value = plans[0].id;
      await loadPlan(plans[0].id);
    }
  } catch (err) {
    console.error("Error loading plans list:", err);
  }
}

async function loadPlan(planId) {
  try {
    state.activePlanId = planId;
    const [planRes, hierRes, recsRes] = await Promise.all([
      fetch(`${API_BASE}/plans/${planId}`),
      fetch(`${API_BASE}/plans/${planId}/hierarchy`),
      fetch(`${API_BASE}/plans/${planId}/records`),
    ]);

    if (!planRes.ok) throw new Error("Failed to load plan details");
    const planData = await planRes.json();
    state.plan = planData.plan;
    state.snapshot = planData.snapshot;

    state.hierarchy = hierRes.ok ? await hierRes.json() : [];
    const recordsList = recsRes.ok ? await recsRes.json() : [];

    state.records = {};
    recordsList.forEach((r) => {
      state.records[r.id] = r;
    });

    // Update Header and Breadcrumbs
    breadcrumbPath.textContent = state.plan.name;
    breadcrumbRevision.textContent = `r${state.plan.edit_revision}`;
    footerSnapshot.textContent = `Snapshot: ${state.plan.snapshot_id ? state.plan.snapshot_id.substring(0, 16) + '...' : 'none'}`;

    renderHierarchy();
    renderOutlineTable();
    renderInspector();

    if (state.activeLayer === "coverage") {
      await loadCoverageData();
    } else {
      loadCampaigns();
      loadProfiles();
    }
  } catch (err) {
    console.error("Error loading plan:", err);
    alert(`Failed to load plan: ${err.message}`);
  }
}

// --- Rendering ---
function renderHierarchy() {
  hierarchyTree.innerHTML = "";
  if (!state.hierarchy || state.hierarchy.length === 0) {
    hierarchyTree.innerHTML = '<div style="padding: 12px; font-size: 12px; color: var(--muted-text);">No scopes found.</div>';
    return;
  }

  function renderNode(node, depth = 0) {
    const el = document.createElement("div");
    el.className = "tree-node";
    if (state.selectedItemId === node.id) {
      el.classList.add("selected");
    }
    el.style.paddingLeft = `${12 + depth * 16}px`;

    let icon = "◈";
    if (node.kind === "scope") icon = "📦";
    else if (node.kind === "section") icon = "📁";
    else if (node.kind === "intent") icon = "⚡";

    el.innerHTML = `
      <span class="tree-node-icon">${icon}</span>
      <span class="tree-node-title" title="${node.title || node.name}">${node.title || node.name}</span>
      ${node.key ? `<span class="tree-node-badge">${node.key}</span>` : ""}
    `;

    el.addEventListener("click", () => {
      selectItem(node.id);
    });

    hierarchyTree.appendChild(el);

    if (node.children && node.children.length > 0) {
      node.children.forEach((child) => renderNode(child, depth + 1));
    }
  }

  state.hierarchy.forEach((scope) => renderNode(scope, 0));
}

function renderOutlineTable() {
  intentTableBody.innerHTML = "";
  const intents = Object.values(state.records).filter((r) => r.record_type === "intent");
  const reqs = Object.values(state.records).filter((r) => r.record_type === "requirement");

  footerStats.textContent = `${intents.length} intents · ${reqs.length} requirements`;

  if (intents.length === 0) {
    emptyState.style.display = "block";
    viewOutline.style.display = "none";
    return;
  }

  emptyState.style.display = "none";
  viewOutline.style.display = "block";

  intents.forEach((intent) => {
    const tr = document.createElement("tr");
    if (state.selectedItemId === intent.id) {
      tr.classList.add("selected");
    }

    const priority = intent.priority_override || "medium";
    const authoringState = intent.authoring_state || "draft";
    const reqCount = intent.requirement_ids ? intent.requirement_ids.length : 0;

    tr.innerHTML = `
      <td>
        <strong style="color: var(--plan-accent); margin-right: 6px;">${intent.key}</strong>
        <span>${intent.title}</span>
      </td>
      <td>
        <span class="badge badge-priority-${priority}">${priority}</span>
      </td>
      <td>
        <span style="font-size: 12px; color: var(--muted-text);">${reqCount} requirement(s)</span>
      </td>
      <td>
        <span class="badge badge-${authoringState}">${authoringState}</span>
      </td>
      <td>
        ${(() => {
          const hasPolicy = Object.values(state.records).some((r) => r.record_type === "policy" && r.intent_id === intent.id);
          const hasObj = Object.values(state.records).some((r) => r.record_type === "objective" && r.parent_intent_id === intent.id);
          if (hasPolicy || hasObj) {
            return `<span class="badge badge-ready">Mapped</span>`;
          }
          return `<span style="font-size: 11px; color: var(--neutral); font-weight: 500;">Not mapped</span>`;
        })()}
      </td>
    `;

    tr.addEventListener("click", () => {
      selectItem(intent.id);
    });

    intentTableBody.appendChild(tr);
  });
}

function selectItem(itemId) {
  state.selectedItemId = itemId;
  renderHierarchy();
  renderOutlineTable();
  renderInspector();
}

function renderInspector() {
  const item = state.records[state.selectedItemId];
  if (!item) {
    inspectorContent.innerHTML = '<p style="color: var(--muted-text); font-style: italic;">Select an intent or section to view details.</p>';
    return;
  }

  if (item.record_type === "intent") {
    if (state.activeInspectorTab === "details") {
      const obsHtml = item.observations && item.observations.length > 0
        ? item.observations.map((o) => `<li><strong>${o.name}</strong>: ${o.description}</li>`).join("")
        : "<em>No observations specified.</em>";

      inspectorContent.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <div>
            <span class="badge badge-${item.authoring_state}" style="margin-bottom: 4px;">${item.authoring_state}</span>
            <h3 style="font-size: 15px;">[${item.key}] ${item.title}</h3>
          </div>
          <button id="btnEditSelectedItem" class="btn btn-secondary btn-sm">Edit</button>
        </div>

        <div class="spec-block">
          <div class="spec-step"><span class="spec-keyword">GIVEN</span> ${item.preconditions || '<em>None</em>'}</div>
          <div class="spec-step"><span class="spec-keyword">WHEN</span> ${item.trigger || '<em>None</em>'}</div>
          <div class="spec-step"><span class="spec-keyword">THEN</span> ${item.expected_behavior || '<em>None</em>'}</div>
        </div>

        <div style="margin-bottom: 14px;">
          <h4 style="font-size: 12px; text-transform: uppercase; color: var(--muted-text); margin-bottom: 6px;">Observable Outcomes</h4>
          <ul style="padding-left: 20px; font-size: 13px;">${obsHtml}</ul>
        </div>

        <div style="font-size: 12px; color: var(--muted-text);">
          <div><strong>Scope:</strong> <code>${item.scope_id}</code></div>
          <div><strong>Priority:</strong> ${item.priority_override || 'inherited'}</div>
          <div><strong>Origin:</strong> ${item.origin}</div>
        </div>
      `;

      document.getElementById("btnEditSelectedItem").addEventListener("click", () => {
        openIntentModal(item);
      });
    } else if (state.activeInspectorTab === "source") {
      const reqList = (item.requirement_ids || []).map((rid) => {
        const req = state.records[rid];
        return req
          ? `<div style="margin-bottom: 10px; padding: 8px; border: 1px solid var(--border); border-radius: 4px;">
              <strong>[${req.key}] ${req.title}</strong>
              <p style="font-size: 12px; margin-top: 4px;">${req.statement}</p>
            </div>`
          : `<div>Requirement ID: ${rid}</div>`;
      }).join("") || "<em>No linked requirements.</em>";

      inspectorContent.innerHTML = `
        <h4 style="font-size: 13px; margin-bottom: 8px;">Linked Requirements</h4>
        <div>${reqList}</div>
      `;
    } else if (state.activeInspectorTab === "related") {
      inspectorContent.innerHTML = `
        <div style="font-size: 13px;">
          <p><strong>Dependencies:</strong> ${(item.dependency_ids || []).join(", ") || "None"}</p>
          <p style="margin-top: 8px;"><strong>Participants:</strong> ${(item.participants || []).join(", ") || "None"}</p>
        </div>
      `;
    } else if (state.activeInspectorTab === "history") {
      inspectorContent.innerHTML = `
        <div style="font-size: 12px; color: var(--muted-text);">
          <p><strong>Revision:</strong> ${item.record_revision}</p>
          <p><strong>Created:</strong> ${item.created_at}</p>
          <p><strong>Updated:</strong> ${item.updated_at}</p>
          ${item.copied_from ? `<p><strong>Copied From:</strong> ${item.copied_from}</p>` : ""}
        </div>
      `;
    }
  } else if (item.record_type === "section") {
    inspectorContent.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
        <div>
          <h3 style="font-size: 15px;">[${item.key}] ${item.title}</h3>
          <p style="font-size: 12px; color: var(--muted-text);">${item.description || 'No description'}</p>
        </div>
      </div>
      <div style="font-size: 12px; color: var(--muted-text); margin-top: 10px;">
        <div><strong>Default Priority:</strong> ${item.default_priority}</div>
        <div><strong>Scope:</strong> <code>${item.scope_id}</code></div>
      </div>
    `;
  }
}

function filterHierarchy(query) {
  const q = query.trim().toLowerCase();
  document.querySelectorAll(".tree-node").forEach((el) => {
    const text = el.textContent.toLowerCase();
    el.style.display = q === "" || text.includes(q) ? "flex" : "none";
  });
}

// --- Toggle Views ---
let isSourceViewActive = false;
async function toggleSourceRequirementsView() {
  isSourceViewActive = !isSourceViewActive;
  if (isSourceViewActive) {
    viewOutline.style.display = "none";
    emptyState.style.display = "none";
    viewSourceRequirements.style.display = "block";
    await loadSourceRequirementsView();
  } else {
    viewSourceRequirements.style.display = "none";
    renderOutlineTable();
  }
}

async function loadSourceRequirementsView() {
  if (!state.activePlanId) return;
  try {
    const [secRes, reqRes] = await Promise.all([
      fetch(`${API_BASE}/plans/${state.activePlanId}/source-sections`),
      fetch(`${API_BASE}/plans/${state.activePlanId}/requirements`),
    ]);

    const sections = secRes.ok ? await secRes.json() : [];
    const reqs = reqRes.ok ? await reqRes.json() : [];

    const secContainer = document.getElementById("sourceSectionsList");
    secContainer.innerHTML = sections.map((s) => `
      <div style="margin-bottom: 12px; padding: 10px; border: 1px solid var(--border); border-radius: 4px; background: var(--surface);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <strong>${s.title}</strong>
          <span class="badge ${s.audit && s.audit.disposition !== 'unreviewed' ? 'badge-ready' : 'badge-draft'}">
            ${s.audit ? s.audit.disposition : 'unreviewed'}
          </span>
        </div>
        <p style="font-size: 12px; margin: 6px 0; color: var(--muted-text); font-family: var(--font-mono);">${s.text}</p>
        <div style="display: flex; gap: 6px; margin-top: 6px;">
          <button class="btn btn-secondary btn-sm" onclick="auditSection('${s.section_id}', 'requirements_captured')">Reviewed</button>
          <button class="btn btn-outline btn-sm" onclick="auditSection('${s.section_id}', 'informational')">Informational</button>
          <button class="btn btn-outline btn-sm" onclick="auditSection('${s.section_id}', 'out_of_scope')">Out of Scope</button>
        </div>
      </div>
    `).join("");

    const reqContainer = document.getElementById("capturedRequirementsList");
    reqContainer.innerHTML = reqs.map((r) => `
      <div style="margin-bottom: 10px; padding: 10px; border: 1px solid var(--border); border-radius: 4px; background: var(--surface);">
        <div><strong>[${r.key}] ${r.title}</strong></div>
        <p style="font-size: 13px; margin: 4px 0;">${r.statement}</p>
        <div style="font-size: 11px; color: var(--muted-text);">
          Disposition: <code>${r.disposition}</code> | Mapped Intents: ${r.linked_intent_count}
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.error("Error loading source view:", err);
  }
}

window.auditSection = async function(sectionId, disposition) {
  if (!state.activePlanId) return;
  const reason = disposition !== "requirements_captured" ? prompt(`Reason for ${disposition}:`, "Architectural note") : null;
  if (disposition !== "requirements_captured" && !reason) return;

  const reqIds = disposition === "requirements_captured"
    ? Object.values(state.records).filter((r) => r.record_type === "requirement").map((r) => r.id)
    : [];

  const cmdPayload = {
    base_edit_revision: state.plan.edit_revision,
    request_id: `audit-${Date.now()}`,
    operations: [
      {
        op: "source_section.assess",
        section_id: sectionId,
        disposition: disposition,
        reason: reason,
        requirement_ids: reqIds,
      }
    ]
  };

  const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/commands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cmdPayload),
  });

  if (res.ok) {
    await loadPlan(state.activePlanId);
    await loadSourceRequirementsView();
  } else {
    alert("Audit update failed.");
  }
};

// --- Modals Form Handlers ---
function openSectionModal() {
  document.getElementById("secFormTitle").value = "";
  document.getElementById("secFormDesc").value = "";
  document.getElementById("modalSection").classList.add("open");
}

async function saveSectionForm() {
  const title = document.getElementById("secFormTitle").value.trim();
  if (!title) return;

  const scopeId = state.snapshot && state.snapshot.occurrences[0] ? state.snapshot.occurrences[0].occurrence_id : "root";
  const cmd = {
    base_edit_revision: state.plan.edit_revision,
    request_id: `sec-${Date.now()}`,
    operations: [
      {
        op: "section.create",
        title: title,
        description: document.getElementById("secFormDesc").value.trim(),
        scope_id: scopeId,
        default_priority: document.getElementById("secFormPriority").value,
      }
    ]
  };

  const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/commands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cmd),
  });

  if (res.ok) {
    document.getElementById("modalSection").classList.remove("open");
    await loadPlan(state.activePlanId);
  } else {
    const err = await res.json();
    alert(`Failed to save section: ${err.message || 'Validation error'}`);
  }
}

let activeEditingIntentId = null;
function openIntentModal(existingIntent = null) {
  activeEditingIntentId = existingIntent ? existingIntent.id : null;
  document.getElementById("modalIntentTitle").textContent = existingIntent ? "Edit Intent" : "Add Verification Intent";

  // Populate sections dropdown
  const secSelect = document.getElementById("intentFormSection");
  secSelect.innerHTML = '<option value="">(Root of scope)</option>';
  Object.values(state.records).filter((r) => r.record_type === "section").forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = `${s.key}: ${s.title}`;
    secSelect.appendChild(opt);
  });

  // Populate requirements selector
  const reqSelect = document.getElementById("intentAddReqSelect");
  reqSelect.innerHTML = '<option value="">-- Link a captured requirement --</option>';
  Object.values(state.records).filter((r) => r.record_type === "requirement").forEach((rq) => {
    const opt = document.createElement("option");
    opt.value = rq.id;
    opt.textContent = `${rq.key}: ${rq.title}`;
    reqSelect.appendChild(opt);
  });

  if (existingIntent) {
    document.getElementById("intentFormTitle").value = existingIntent.title || "";
    document.getElementById("intentFormPreconditions").value = existingIntent.preconditions || "";
    document.getElementById("intentFormTrigger").value = existingIntent.trigger || "";
    document.getElementById("intentFormExpected").value = existingIntent.expected_behavior || "";
    document.getElementById("intentFormSection").value = existingIntent.parent_section_id || "";
    document.getElementById("intentFormPriority").value = existingIntent.priority_override || "";
    renderObservationRows(existingIntent.observations || []);
    renderLinkedReqChips(existingIntent.requirement_ids || []);
  } else {
    document.getElementById("intentFormTitle").value = "";
    document.getElementById("intentFormPreconditions").value = "";
    document.getElementById("intentFormTrigger").value = "";
    document.getElementById("intentFormExpected").value = "";
    renderObservationRows([{ name: "Queue state", description: "Occupancy and outputs match expected behavior." }]);
    renderLinkedReqChips([]);
  }

  document.getElementById("modalIntent").classList.add("open");
}

function renderObservationRows(observations) {
  const container = document.getElementById("intentObservationsList");
  container.innerHTML = "";
  observations.forEach((obs, idx) => {
    const row = document.createElement("div");
    row.className = "obs-row";
    row.style.display = "flex";
    row.style.gap = "8px";
    row.style.marginBottom = "6px";
    row.innerHTML = `
      <input type="text" class="form-input obs-name" style="width: 35%;" placeholder="Name" value="${obs.name || ''}" />
      <input type="text" class="form-input obs-desc" style="flex: 1;" placeholder="Observable description" value="${obs.description || ''}" />
      <button type="button" class="btn btn-outline btn-sm" onclick="this.parentElement.remove()">&times;</button>
    `;
    container.appendChild(row);
  });
}

function addObservationRow() {
  const container = document.getElementById("intentObservationsList");
  const row = document.createElement("div");
  row.className = "obs-row";
  row.style.display = "flex";
  row.style.gap = "8px";
  row.style.marginBottom = "6px";
  row.innerHTML = `
    <input type="text" class="form-input obs-name" style="width: 35%;" placeholder="Name" />
    <input type="text" class="form-input obs-desc" style="flex: 1;" placeholder="Observable description" />
    <button type="button" class="btn btn-outline btn-sm" onclick="this.parentElement.remove()">&times;</button>
  `;
  container.appendChild(row);
}

let activeLinkedReqIds = [];
function renderLinkedReqChips(reqIds) {
  activeLinkedReqIds = [...reqIds];
  const container = document.getElementById("intentLinkedReqsList");
  container.innerHTML = "";
  activeLinkedReqIds.forEach((rid) => {
    const req = state.records[rid];
    const chip = document.createElement("span");
    chip.style.cssText = "display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; background: #e2e8f0; border-radius: 4px; font-size: 11px; margin-right: 6px;";
    chip.innerHTML = `${req ? req.key : rid} <button type="button" style="border:none; background:none; cursor:pointer;" onclick="removeLinkedReq('${rid}')">&times;</button>`;
    container.appendChild(chip);
  });
}

window.removeLinkedReq = function(rid) {
  activeLinkedReqIds = activeLinkedReqIds.filter((id) => id !== rid);
  renderLinkedReqChips(activeLinkedReqIds);
};

document.getElementById("intentAddReqSelect").addEventListener("change", (e) => {
  if (e.target.value && !activeLinkedReqIds.includes(e.target.value)) {
    activeLinkedReqIds.push(e.target.value);
    renderLinkedReqChips(activeLinkedReqIds);
  }
  e.target.value = "";
});

async function saveIntentForm(markReady = false) {
  const title = document.getElementById("intentFormTitle").value.trim();
  if (!title) {
    alert("Intent title is required.");
    return;
  }

  const observations = [];
  document.querySelectorAll(".obs-row").forEach((row) => {
    const name = row.querySelector(".obs-name").value.trim();
    const desc = row.querySelector(".obs-desc").value.trim();
    if (name && desc) observations.push({ name, description: desc });
  });

  const scopeId = state.snapshot && state.snapshot.occurrences[0] ? state.snapshot.occurrences[0].occurrence_id : "sync_fifo";
  const parentSec = document.getElementById("intentFormSection").value || null;
  const priority = document.getElementById("intentFormPriority").value || null;

  const intentPayload = {
    title: title,
    scope_id: scopeId,
    parent_section_id: parentSec,
    requirement_ids: activeLinkedReqIds,
    preconditions: document.getElementById("intentFormPreconditions").value.trim(),
    trigger: document.getElementById("intentFormTrigger").value.trim(),
    expected_behavior: document.getElementById("intentFormExpected").value.trim(),
    observations: observations,
    priority_override: priority,
    authoring_state: markReady ? "ready" : "draft",
  };

  const op = activeEditingIntentId
    ? { op: "intent.update", id: activeEditingIntentId, changes: intentPayload }
    : { op: "intent.create", ...intentPayload };

  const cmd = {
    base_edit_revision: state.plan.edit_revision,
    request_id: `intent-${Date.now()}`,
    operations: [op],
  };

  const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/commands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cmd),
  });

  if (res.ok) {
    document.getElementById("modalIntent").classList.remove("open");
    await loadPlan(state.activePlanId);
  } else {
    const err = await res.json();
    alert(`Failed to save intent: ${err.message || JSON.stringify(err)}`);
  }
}

// --- Review Checkpoint Modal ---
async function openReviewModal() {
  if (!state.activePlanId) return;
  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints/preview`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to preview checklist");
    const preview = await res.json();

    const summaryEl = document.getElementById("reviewChecklistSummary");
    const cl = preview.checklist;
    summaryEl.innerHTML = `
      <div style="font-size: 13px; line-height: 1.8;">
        <div>Snapshot Valid: <strong>${cl.snapshot_valid ? '✓ Yes' : '✗ No'}</strong></div>
        <div>Source Sections Audited: <strong>${cl.sections_reviewed_count} / ${cl.sections_total}</strong></div>
        <div>Requirements Captured: <strong>${cl.requirements_total}</strong> (${cl.verifiable_requirements} verifiable)</div>
        <div>Intents Authored: <strong>${cl.intents_total}</strong> (${cl.intents_ready} marked ready)</div>
      </div>
    `;

    const blockersBox = document.getElementById("reviewBlockersContainer");
    const blockersList = document.getElementById("reviewBlockersList");
    if (preview.blockers && preview.blockers.length > 0) {
      blockersBox.style.display = "block";
      blockersList.innerHTML = preview.blockers.map((b) => `<li>${b.message}</li>`).join("");
      document.getElementById("btnConfirmReviewCheckpoint").disabled = true;
    } else {
      blockersBox.style.display = "none";
      document.getElementById("btnConfirmReviewCheckpoint").disabled = false;
    }

    const warningsBox = document.getElementById("reviewWarningsContainer");
    const warningsList = document.getElementById("reviewWarningsList");
    if (preview.warnings && preview.warnings.length > 0) {
      warningsBox.style.display = "block";
      warningsList.innerHTML = preview.warnings.map((w) => `
        <label style="display: block; margin-bottom: 4px;">
          <input type="checkbox" class="chk-warn" value="${w.record_id || w.code}" checked /> ${w.message}
        </label>
      `).join("");
    } else {
      warningsBox.style.display = "none";
    }

    state.reviewCandidateDigest = preview.candidate_digest;
    document.getElementById("modalReview").classList.add("open");
  } catch (err) {
    alert(`Review preview failed: ${err.message}`);
  }
}

async function submitReviewCheckpoint() {
  const acks = Array.from(document.querySelectorAll(".chk-warn:checked")).map((el) => el.value);
  const payload = {
    reviewer_label: document.getElementById("reviewFormReviewer").value.trim() || "author",
    comment: document.getElementById("reviewFormComment").value.trim(),
    expected_digest: state.reviewCandidateDigest,
    acknowledged_warnings: acks,
  };

  const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (res.ok) {
    const cp = await res.json();
    alert(`Successfully reviewed and created immutable checkpoint ${cp.key}!`);
    document.getElementById("modalReview").classList.remove("open");
    await loadPlan(state.activePlanId);
  } else {
    const err = await res.json();
    alert(`Checkpoint creation failed: ${err.message || JSON.stringify(err)}`);
  }
}

// --- New Plan Modal ---
let stagedSnapshotId = null;
function openNewPlanModal() {
  stagedSnapshotId = null;
  document.getElementById("newPlanName").value = "FIFO Subsystem Verification";
  document.getElementById("modalNewPlan").classList.add("open");
}

async function loadSampleFixture(fixtureType) {
  try {
    let endpoint = "";
    if (fixtureType === "fifo") {
      // Create FIFO snapshot via script test import or synthetic byte upload
      const res = await fetch(`${API_BASE}/source-imports`, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: await (await fetch("/static/fifo.snapshot")).blob().catch(() => null),
      });
    }
  } catch (e) {
    console.error(e);
  }
}

async function submitNewPlan() {
  const name = document.getElementById("newPlanName").value.trim();
  if (!name) return;

  // If no snapshot staged, create a basic default FIFO snapshot from server
  const res = await fetch(`${API_BASE}/plans`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: name,
      snapshot_id: stagedSnapshotId || "default-snapshot",
      root_scope_id: "sync_fifo",
      description: document.getElementById("newPlanDesc").value.trim(),
    }),
  });

  if (res.ok) {
    const newPlan = await res.json();
    document.getElementById("modalNewPlan").classList.remove("open");
    await loadPlansList();
    await loadPlan(newPlan.id);
  } else {
    alert("Failed to create plan. Please upload a snapshot first.");
  }
}

// --- Export Menu ---
function handleExportMenu() {
  if (!state.activePlanId) return;
  const choice = prompt("Choose export format: bundle (.vplan), markdown (.md), or csv (.csv):", "bundle");
  if (!choice) return;

  const fmt = choice.toLowerCase().includes("md") ? "markdown" : choice.toLowerCase().includes("csv") ? "csv" : "bundle";
  window.open(`${API_BASE}/plans/${state.activePlanId}/exports?format=${fmt}`, "_blank");
}

function handleImportBundle() {
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = ".vplan,.zip";
  fileInput.onchange = async () => {
    if (fileInput.files.length === 0) return;
    const file = fileInput.files[0];
    const res = await fetch(`${API_BASE}/bundle-imports`, {
      method: "POST",
      body: file,
    });
    if (res.ok) {
      const data = await res.json();
      const commitRes = await fetch(`${API_BASE}/bundle-imports/${data.staging_id}/commit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resolution: "import_as_copy" }),
      });
      if (commitRes.ok) {
        const commitData = await commitRes.json();
        alert(`Bundle imported successfully as plan ${commitData.plan_id}!`);
        await loadPlansList();
        await loadPlan(commitData.plan_id);
      }
    }
  };
  fileInput.click();
}

// ==========================================
// --- LAYER 2: COVERAGE & EVIDENCE LOGIC ---
// ==========================================

function switchLayer(layer) {
  state.activeLayer = layer;
  const toolbarPlan = document.getElementById("toolbarPlan");
  const toolbarCoverage = document.getElementById("toolbarCoverage");
  const toolbarImplementation = document.getElementById("toolbarImplementation");
  const viewOutline = document.getElementById("viewOutline");
  const viewSource = document.getElementById("viewSourceRequirements");
  const viewCoverage = document.getElementById("viewCoverage");
  const viewImplementation = document.getElementById("viewImplementation");
  const emptyState = document.getElementById("emptyState");

  toolbarPlan.style.display = "none";
  toolbarCoverage.style.display = "none";
  if (toolbarImplementation) toolbarImplementation.style.display = "none";
  viewOutline.style.display = "none";
  viewSource.style.display = "none";
  viewCoverage.style.display = "none";
  if (viewImplementation) viewImplementation.style.display = "none";
  emptyState.style.display = "none";

  if (layer === "coverage") {
    toolbarCoverage.style.display = "flex";
    viewCoverage.style.display = "flex";
    loadCoverageData();
  } else if (layer === "implementation") {
    if (toolbarImplementation) toolbarImplementation.style.display = "flex";
    if (viewImplementation) viewImplementation.style.display = "flex";
    loadImplementationData();
  } else {
    toolbarPlan.style.display = "flex";
    if (isSourceViewActive) {
      viewSource.style.display = "block";
    } else {
      renderOutlineTable();
    }
  }
}

function switchCoverageSubnav(subnav) {
  state.activeCoverageSubnav = subnav;
  ["btnSubnavMatrix", "btnSubnavGaps", "btnSubnavRuns", "btnSubnavTrace"].forEach((btnId) => {
    const btn = document.getElementById(btnId);
    if (btn) btn.classList.remove("active");
  });
  const subnavMap = {
    matrix: { btn: "btnSubnavMatrix", view: "subviewCoverageMatrix" },
    gaps: { btn: "btnSubnavGaps", view: "subviewCoverageGaps" },
    runs: { btn: "btnSubnavRuns", view: "subviewCoverageRuns" },
    trace: { btn: "btnSubnavTrace", view: "subviewCoverageTrace" },
  };
  const activeCfg = subnavMap[subnav];
  if (activeCfg) {
    document.getElementById(activeCfg.btn).classList.add("active");
  }

  ["subviewCoverageMatrix", "subviewCoverageGaps", "subviewCoverageRuns", "subviewCoverageTrace"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = (id === activeCfg.view) ? "flex" : "none";
  });

  if (subnav === "matrix") loadCoverageMatrix();
  else if (subnav === "gaps") loadCoverageGaps();
  else if (subnav === "runs") loadRuns();
}

async function loadCoverageData() {
  if (!state.activePlanId) return;
  await Promise.all([
    loadProfiles(),
    loadCampaigns(),
  ]);
  await Promise.all([
    loadCoverageMatrix(),
    loadCoverageGaps(),
  ]);
}

async function loadProfiles() {
  if (!state.activePlanId) return;
  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/profiles`);
    if (res.ok) {
      state.profiles = await res.json();
      const profileSelect = document.getElementById("selectMatrixProfile");
      const importProfileSelect = document.getElementById("importResultProfile");
      
      const prevVal = profileSelect.value;
      profileSelect.innerHTML = '<option value="">(All Profiles)</option>';
      importProfileSelect.innerHTML = '<option value="">(Select Profile)</option>';
      state.profiles.forEach((p) => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = `${p.display_name} (${p.id})`;
        profileSelect.appendChild(opt);

        const opt2 = document.createElement("option");
        opt2.value = p.id;
        opt2.textContent = `${p.display_name} (${p.id})`;
        importProfileSelect.appendChild(opt2);
      });
      profileSelect.value = prevVal;
    }
  } catch (err) {
    console.error("Failed to load profiles:", err);
  }
}

async function loadCampaigns() {
  if (!state.activePlanId) return;
  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/campaigns`);
    if (res.ok) {
      state.campaigns = await res.json();
      const campSelect = document.getElementById("selectActiveCampaign");
      const importCampSelect = document.getElementById("importResultCampaign");
      const freezeCampSelect = document.getElementById("freezeReportCampaign");

      campSelect.innerHTML = '<option value="">(No Campaign / Draft)</option>';
      importCampSelect.innerHTML = '<option value="">(Select Campaign)</option>';
      freezeCampSelect.innerHTML = '<option value="">(Select Campaign)</option>';

      state.campaigns.forEach((c) => {
        const label = `${c.name} (${c.purpose}, rev ${c.campaign_revision})`;
        const opt1 = document.createElement("option");
        opt1.value = c.id;
        opt1.textContent = label;
        campSelect.appendChild(opt1);

        const opt2 = document.createElement("option");
        opt2.value = c.id;
        opt2.textContent = label;
        importCampSelect.appendChild(opt2);

        const opt3 = document.createElement("option");
        opt3.value = c.id;
        opt3.textContent = label;
        freezeCampSelect.appendChild(opt3);
      });

      if (!state.activeCampaignId && state.campaigns.length > 0) {
        state.activeCampaignId = state.campaigns[0].id;
      }
      if (state.activeCampaignId) {
        campSelect.value = state.activeCampaignId;
      }
    }
  } catch (err) {
    console.error("Failed to load campaigns:", err);
  }
}

async function loadCoverageMatrix() {
  if (!state.activePlanId) return;
  try {
    const statusFilter = document.getElementById("filterMatrixStatus").value;
    const profileFilter = document.getElementById("selectMatrixProfile").value;
    let url = `${API_BASE}/plans/${state.activePlanId}/coverage/matrix?`;
    if (statusFilter) url += `status=${statusFilter}&`;
    if (profileFilter) url += `profile_id=${profileFilter}&`;
    if (state.activeCampaignId) url += `campaign_id=${state.activeCampaignId}&`;

    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load coverage matrix");
    const data = await res.json();
    state.coverageMatrix = data;

    // Render Summary Bar
    const baseline = data.baseline_summary || data.whole_baseline_summary || {};
    const sat = baseline.satisfied_intents ?? baseline.satisfied ?? 0;
    const fail = baseline.failed_intents ?? baseline.failed ?? 0;
    const blk = baseline.blocked_intents ?? baseline.blocked ?? 0;
    const opn = baseline.open_intents ?? baseline.open ?? 0;
    const waiv = baseline.waived_intents ?? baseline.waived ?? 0;
    const notEv = baseline.not_evaluated_intents ?? baseline.not_evaluated ?? 0;
    const total = baseline.total_intents ?? (sat + fail + blk + opn + waiv + notEv);

    document.getElementById("metricBaselineText").innerHTML = `
      <span class="badge badge-satisfied">${sat} Satisfied</span>
      <span class="badge badge-failed">${fail} Failed</span>
      <span class="badge badge-blocked">${blk} Blocked</span>
      <span class="badge badge-open">${opn} Open</span>
      <span class="badge badge-waived">${waiv} Waived</span>
      <span class="badge badge-not_evaluated">${notEv} Not evaluated</span>
      <span style="color: var(--muted-text); margin-left: 4px;">(${total} total)</span>
    `;

    const totalBins = baseline.required_bins_total ?? data.total_unique_bins ?? 0;
    const achBins = baseline.required_bins_satisfied ?? data.achieved_unique_bins ?? 0;
    const binPct = totalBins > 0 ? ((achBins / totalBins) * 100).toFixed(1) : "0.0";
    document.getElementById("metricBinsText").textContent = `${achBins} / ${totalBins} (${binPct}%)`;

    // Render Matrix Table
    const tbody = document.getElementById("matrixTableBody");
    tbody.innerHTML = "";

    const rows = data.rows || [];
    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--muted-text); padding: 24px;">No coverage matrix rows matching filters.</td></tr>`;
      return;
    }

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      if (state.selectedItemId === row.intent_id) {
        tr.classList.add("selected");
      }

      // Lookup intent metadata from state.intents
      const it = (state.intents || []).find((i) => i.id === row.intent_id) || {};
      const intentKey = row.intent_key || it.key || row.intent_id;
      const intentTitle = row.intent_title || it.title || "";
      const intentStatus = row.achievement_state || row.intent_status || "not_evaluated";

      function renderFamilyCell(famData) {
        if (!famData || famData === "—") return '<span class="matrix-cell-empty">—</span>';
        if (typeof famData === "object") {
          const st = famData.status || "not_evaluated";
          return `<span class="badge badge-${st}">${famData.cell_text || st}</span>`;
        }
        const text = String(famData);
        if (text.includes("Passed") || text.includes("1/1") || text === "hit" || text === "pass" || text === "satisfied") {
          return `<span class="badge badge-satisfied">${text}</span>`;
        } else if (text.includes("Fail") || text === "fail") {
          return `<span class="badge badge-failed">${text}</span>`;
        } else if (text.includes("Error") || text.includes("Block") || text === "error" || text === "blocked") {
          return `<span class="badge badge-blocked">${text}</span>`;
        } else if (text.includes("None planned")) {
          return `<span class="badge badge-draft" style="opacity: 0.7;">None</span>`;
        }
        return `<span class="badge badge-not_evaluated">${text}</span>`;
      }

      const fam = row.family_cell_summaries || {};
      const scenCell = fam.scenario ?? row.scenario;
      const funcCell = fam.functional ?? row.functional;
      const corrCell = fam.checking ?? row.correctness;
      const propCell = fam.property ?? row.property;
      const strucCell = fam.structural ?? row.structural;

      tr.innerHTML = `
        <td style="text-align: left;">
          <strong style="color: var(--plan-accent); margin-right: 6px;">${intentKey}</strong>
          <span>${intentTitle}</span>
        </td>
        <td>${renderFamilyCell(scenCell)}</td>
        <td>${renderFamilyCell(funcCell)}</td>
        <td>${renderFamilyCell(corrCell)}</td>
        <td>${renderFamilyCell(propCell)}</td>
        <td>${renderFamilyCell(strucCell)}</td>
        <td>
          <span class="badge badge-${intentStatus}">${intentStatus}</span>
        </td>
      `;

      tr.addEventListener("click", () => {
        selectItem(row.intent_id);
      });

      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error loading coverage matrix:", err);
  }
}

async function loadCoverageGaps() {
  if (!state.activePlanId) return;
  try {
    let url = `${API_BASE}/plans/${state.activePlanId}/coverage/gaps?`;
    if (state.activeCampaignId) url += `campaign_id=${state.activeCampaignId}&`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load gaps");
    state.coverageGaps = await res.json();

    const count = state.coverageGaps.length;
    const badge = document.getElementById("badgeGapsCount");
    badge.textContent = count;
    badge.style.display = count > 0 ? "inline-block" : "none";

    renderGapsTable();
  } catch (err) {
    console.error("Error loading coverage gaps:", err);
  }
}

function renderGapsTable() {
  const filterSev = document.getElementById("filterGapSeverity").value;
  let gaps = state.coverageGaps || [];
  if (filterSev) {
    gaps = gaps.filter((g) => g.severity === filterSev);
  }

  document.getElementById("gapsSummaryCount").textContent = `${gaps.length} Gap(s)`;

  const tbody = document.getElementById("gapsTableBody");
  tbody.innerHTML = "";

  if (gaps.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--muted-text); padding: 24px;">No gaps found! Coverage requirements are fully satisfied.</td></tr>`;
    return;
  }

  gaps.forEach((gap) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="badge badge-gap-${gap.severity}">${gap.severity}</span></td>
      <td><code>${gap.gap_code}</code></td>
      <td><strong>${gap.title}</strong></td>
      <td style="font-size: 12px; color: var(--text);">${gap.explanation || gap.description || ''}</td>
      <td>
        <button class="btn btn-outline btn-sm" onclick="handleGapAction('${gap.gap_code}', '${gap.intent_id || ''}', '${gap.objective_id || ''}')">
          ${getGapActionLabel(gap.gap_code)}
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function getGapActionLabel(code) {
  if (code.includes("missing_policy") || code.includes("checking_missing")) return "Map Objective";
  if (code.includes("unresolved_fail") || code.includes("failure")) return "Inspect Run";
  if (code.includes("bin") || code.includes("unhit")) return "Add Stimulus";
  if (code.includes("exclusion") || code.includes("waiver")) return "Create Waiver";
  return "Inspect";
}

window.handleGapAction = function(code, intentId, objectiveId) {
  if (intentId) {
    selectItem(intentId);
  }
  if (code.includes("checking_missing") || code.includes("missing_policy")) {
    openAddObjectiveModal(intentId);
  } else if (code.includes("unresolved_fail")) {
    switchCoverageSubnav("runs");
  } else {
    alert(`Gap ${code} on ${intentId || objectiveId}`);
  }
};

async function loadRuns() {
  if (!state.activePlanId) return;
  try {
    let url = `${API_BASE}/plans/${state.activePlanId}/runs?`;
    if (state.activeCampaignId) url += `campaign_id=${state.activeCampaignId}&`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load runs");
    state.runs = await res.json();

    const tbody = document.getElementById("runsTableBody");
    tbody.innerHTML = "";

    if (state.runs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--muted-text); padding: 24px;">No committed evidence runs in this campaign. Import results to see evidence.</td></tr>`;
      return;
    }

    state.runs.forEach((r) => {
      const tr = document.createElement("tr");
      const runStatus = r.status || r.disposition || "completed";
      const statusBadge = runStatus === "completed" ? "badge-satisfied" : "badge-failed";
      const createdAt = r.imported_at || r.created_at || "";
      tr.innerHTML = `
        <td><strong>${r.producer_id}</strong> <small style="color: var(--muted-text);">(${r.tool_name || 'sim'})</small></td>
        <td><code>${r.external_run_id}</code></td>
        <td><span class="badge badge-ready">FIFO Sim</span></td>
        <td><span class="badge ${statusBadge}">${runStatus}</span></td>
        <td>${r.observation_count ?? (r.observations ? r.observations.length : '2 obs')}</td>
        <td style="font-size: 11px; color: var(--muted-text);">${createdAt}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error loading evidence runs:", err);
  }
}

// --- Modals for Layer 2 ---
function openAddObjectiveModal(preselectedIntentId = null) {
  document.getElementById("objFormTitle").value = "";
  document.getElementById("objFormDescription").value = "";
  document.getElementById("objFormBins").value = "";

  const intentSelect = document.getElementById("objFormIntent");
  intentSelect.innerHTML = '<option value="">-- Link to an Intent --</option>';
  Object.values(state.records).filter((r) => r.record_type === "intent").forEach((it) => {
    const opt = document.createElement("option");
    opt.value = it.id;
    opt.textContent = `[${it.key}] ${it.title}`;
    if (preselectedIntentId && it.id === preselectedIntentId) {
      opt.selected = true;
    }
    intentSelect.appendChild(opt);
  });

  document.getElementById("modalAddObjective").classList.add("open");
}

async function saveObjectiveForm() {
  const title = document.getElementById("objFormTitle").value.trim();
  if (!title) {
    alert("Objective title is required.");
    return;
  }
  const family = document.getElementById("objFormFamily").value;
  const parentIntentId = document.getElementById("objFormIntent").value || null;
  const desc = document.getElementById("objFormDescription").value.trim();
  const acceptanceMetric = document.getElementById("objFormAcceptance").value;
  const binsInput = document.getElementById("objFormBins").value.trim();

  const binObjects = binsInput
    ? binsInput.split(",").map((b) => b.trim()).filter(Boolean).map((b) => ({
        bin_id: b.toLowerCase().replace(/[^a-z0-9_]/g, "_"),
        name: b,
        required: true,
      }))
    : [];

  const scopeId = state.snapshot && state.snapshot.occurrences[0] ? state.snapshot.occurrences[0].occurrence_id : "sync_fifo";
  const objId = `OBJ-${Date.now()}`;

  const operations = [
    {
      op: "objective.create",
      id: objId,
      title: title,
      family: family,
      scope_id: scopeId,
      parent_intent_id: parentIntentId,
      acceptance: { metric: acceptanceMetric, threshold: 1, minimum_evaluations: 1 },
      bins: binObjects,
      authoring_state: "ready",
      description: desc,
    }
  ];

  // If intent was selected, update or create policy
  if (parentIntentId) {
    const existingPolicy = Object.values(state.records).find(
      (r) => r.record_type === "policy" && r.intent_id === parentIntentId
    );
    let branches = [];
    if (existingPolicy && existingPolicy.branches && existingPolicy.branches.length > 0) {
      branches = JSON.parse(JSON.stringify(existingPolicy.branches));
      branches[0].objective_ids.push(objId);
    } else {
      branches = [{ branch_id: `branch-1`, objective_ids: [objId] }];
    }
    operations.push({
      op: "policy.set",
      intent_id: parentIntentId,
      branches: branches,
    });
  }

  const cmd = {
    base_edit_revision: state.plan.edit_revision,
    request_id: `obj-create-${Date.now()}`,
    operations: operations,
  };

  const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/commands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cmd),
  });

  if (res.ok) {
    document.getElementById("modalAddObjective").classList.remove("open");
    await loadPlan(state.activePlanId);
    await loadCoverageData();
  } else {
    const err = await res.json();
    alert(`Failed to save objective: ${err.message || JSON.stringify(err)}`);
  }
}

async function openReviewCoverageModal() {
  if (!state.activePlanId) return;
  try {
    // Populate upstream P1 checkpoints
    const cpRes = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints`);
    const checkpoints = cpRes.ok ? await cpRes.json() : [];
    const planCps = checkpoints.filter((c) => c.layer === "plan");

    const p1Select = document.getElementById("reviewCovUpstreamP1");
    p1Select.innerHTML = "";
    planCps.forEach((cp) => {
      const opt = document.createElement("option");
      opt.value = cp.id;
      opt.textContent = `${cp.key} — ${cp.created_at} (${cp.reviewer_label})`;
      p1Select.appendChild(opt);
    });

    const upstreamP1 = planCps.length > 0 ? planCps[planCps.length - 1].id : null;

    const previewRes = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layer: "coverage", upstream_checkpoint_id: upstreamP1 }),
    });

    if (!previewRes.ok) throw new Error("Failed to preview coverage checklist");
    const preview = await previewRes.json();

    const summaryEl = document.getElementById("reviewCovChecklistSummary");
    const cl = preview.checklist || {};
    summaryEl.innerHTML = `
      <div>Upstream Plan Checkpoint: <strong>${upstreamP1 || 'None (Missing!)'}</strong></div>
      <div>Intents Mapped: <strong>${cl.intents_mapped_count || 0} / ${cl.intents_total || 0}</strong></div>
      <div>Coverage Objectives: <strong>${cl.objectives_total || 0}</strong></div>
      <div>Required Checking on all branches: <strong>${cl.has_checking_coverage ? '✓ Yes' : '✗ No'}</strong></div>
      <div>Non-empty bin denominators: <strong>${cl.has_nonempty_bins ? '✓ Yes' : '✗ No'}</strong></div>
    `;

    const blockersBox = document.getElementById("reviewCovBlockersContainer");
    const blockersList = document.getElementById("reviewCovBlockersList");
    if (preview.blockers && preview.blockers.length > 0) {
      blockersBox.style.display = "block";
      blockersList.innerHTML = preview.blockers.map((b) => `<li>${b.message}</li>`).join("");
      document.getElementById("btnConfirmReviewCoverage").disabled = true;
    } else {
      blockersBox.style.display = "none";
      document.getElementById("btnConfirmReviewCoverage").disabled = false;
    }

    state.reviewCandidateDigest = preview.candidate_digest;
    document.getElementById("modalReviewCoverage").classList.add("open");
  } catch (err) {
    alert(`Coverage review preview failed: ${err.message}`);
  }
}

async function submitReviewCoverage() {
  const p1Id = document.getElementById("reviewCovUpstreamP1").value;
  const payload = {
    layer: "coverage",
    reviewer_label: document.getElementById("reviewCovReviewer").value.trim() || "coverage_lead",
    comment: document.getElementById("reviewCovComment").value.trim(),
    expected_digest: state.reviewCandidateDigest,
    upstream_checkpoint_id: p1Id,
  };

  const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (res.ok) {
    const cp = await res.json();
    alert(`Successfully reviewed coverage model and created immutable checkpoint ${cp.key}!`);
    document.getElementById("modalReviewCoverage").classList.remove("open");
    await loadPlan(state.activePlanId);
    await loadCoverageData();
  } else {
    const err = await res.json();
    alert(`Coverage checkpoint creation failed: ${err.message || JSON.stringify(err)}`);
  }
}

function openImportResultsModal() {
  document.getElementById("importResultJson").value = "";
  document.getElementById("importPreviewBox").style.display = "none";
  document.getElementById("btnCommitImport").disabled = true;
  document.getElementById("modalImportResults").classList.add("open");
}

function handleResultFileSelect(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (event) => {
    document.getElementById("importResultJson").value = event.target.result;
  };
  reader.readAsText(file);
}

async function stageImportResults() {
  const rawJson = document.getElementById("importResultJson").value.trim();
  if (!rawJson) {
    alert("Please provide normalized results JSON.");
    return;
  }
  let payload;
  try {
    payload = JSON.parse(rawJson);
  } catch (err) {
    alert("Invalid JSON format.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/result-imports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || "Stage failed");
    }

    const preview = await res.json();
    state.stagedImportId = preview.staging_id;
    state.stagedImportDigest = preview.preview_digest;

    const previewBox = document.getElementById("importPreviewBox");
    previewBox.style.display = "block";
    previewBox.innerHTML = `
      <div><strong>Validation Preview:</strong></div>
      <div>Run Count: <strong>${preview.run_count}</strong></div>
      <div>Valid Observations: <strong>${preview.valid_observation_count || preview.known_observations_count || 0}</strong></div>
      <div>Unbound Observations: <strong>${preview.unbound_observation_count || preview.unbound_observations_count || 0}</strong></div>
      <div>Failures Detected: <strong>${preview.failures_detected || 0}</strong></div>
      <div>Digest: <code>${preview.preview_digest.substring(0, 16)}...</code></div>
    `;

    document.getElementById("btnCommitImport").disabled = false;
  } catch (err) {
    alert(`Import validation failed: ${err.message}`);
  }
}

async function commitImportResults() {
  if (!state.stagedImportId) return;
  const campId = document.getElementById("importResultCampaign").value || state.activeCampaignId;
  const commitPayload = {
    expected_preview_digest: state.stagedImportDigest,
    campaign_id: campId || null,
  };

  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/result-imports/${state.stagedImportId}/commit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(commitPayload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || "Commit failed");
    }

    const data = await res.json();
    alert(`Successfully committed ${data.run_id ? 1 : 0} run into campaign!`);
    document.getElementById("modalImportResults").classList.remove("open");
    await loadCoverageData();
    switchCoverageSubnav("runs");
  } catch (err) {
    alert(`Commit import failed: ${err.message}`);
  }
}

function openFreezeReportModal() {
  document.getElementById("modalFreezeReport").classList.add("open");
}

async function submitFreezeReport() {
  const campId = document.getElementById("freezeReportCampaign").value || state.activeCampaignId;
  if (!campId) {
    alert("Please select a campaign to freeze evidence for.");
    return;
  }
  const title = document.getElementById("freezeReportTitle").value.trim();

  // Find latest coverage checkpoint C1
  const cpRes = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints`);
  const checkpoints = cpRes.ok ? await cpRes.json() : [];
  const covCp = checkpoints.filter((c) => c.layer === "coverage").pop();
  if (!covCp) {
    alert("Freezing report requires an approved Coverage checkpoint (C1). Please complete Review Coverage first.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/evidence-reports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        coverage_checkpoint_id: covCp.id,
        campaign_id: campId,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || "Report freeze failed");
    }

    const rpt = await res.json();
    alert(`Immutable Evidence Report ${rpt.id} frozen successfully! Status: ${rpt.status}`);
    document.getElementById("modalFreezeReport").classList.remove("open");
  } catch (err) {
    alert(`Freeze evidence report failed: ${err.message}`);
  }
}

function openNewCampaignModal() {
  document.getElementById("newCampName").value = "FIFO Golden Campaign";
  document.getElementById("modalNewCampaign").classList.add("open");
}

async function submitNewCampaign() {
  const name = document.getElementById("newCampName").value.trim();
  if (!name) return;
  const purpose = document.getElementById("newCampPurpose").value;

  // Find latest coverage checkpoint C1
  const cpRes = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints`);
  const checkpoints = cpRes.ok ? await cpRes.json() : [];
  const covCp = checkpoints.filter((c) => c.layer === "coverage").pop() || checkpoints[0];
  const covCpId = covCp ? covCp.id : "c1-draft";

  const profIds = state.profiles.map((p) => p.id);
  const reqProfIds = profIds.length > 0 ? profIds : ["prof-default"];

  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/campaigns`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: name,
        coverage_checkpoint_id: covCpId,
        required_profile_ids: reqProfIds,
        purpose: purpose,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || "Failed to create campaign");
    }

    const newCamp = await res.json();
    state.activeCampaignId = newCamp.id;
    document.getElementById("modalNewCampaign").classList.remove("open");
    await loadCampaigns();
    await loadCoverageData();
  } catch (err) {
    alert(`Failed to create campaign: ${err.message}`);
  }
}

// ==========================================
// --- LAYER 3: IMPLEMENTATION & TEST IR ---
// ==========================================

function switchImplementationSubnav(subnav) {
  state.activeImplementationSubnav = subnav;
  ["btnSubnavRecipes", "btnSubnavBindings", "btnSubnavBackends", "btnSubnavGenerations"].forEach((id) => {
    const btn = document.getElementById(id);
    if (btn) btn.classList.remove("active");
  });
  const subnavMap = {
    recipes: "btnSubnavRecipes",
    bindings: "btnSubnavBindings",
    backends: "btnSubnavBackends",
    generations: "btnSubnavGenerations",
  };
  const activeBtn = document.getElementById(subnavMap[subnav]);
  if (activeBtn) activeBtn.classList.add("active");

  const vRecipes = document.getElementById("subviewImplementationRecipes");
  const vBindings = document.getElementById("subviewImplementationBindings");
  const vBackends = document.getElementById("subviewImplementationBackends");
  const vGenerations = document.getElementById("subviewImplementationGenerations");

  if (vRecipes) vRecipes.style.display = subnav === "recipes" ? "flex" : "none";
  if (vBindings) vBindings.style.display = subnav === "bindings" ? "flex" : "none";
  if (vBackends) vBackends.style.display = subnav === "backends" ? "flex" : "none";
  if (vGenerations) vGenerations.style.display = subnav === "generations" ? "flex" : "none";
}

async function loadImplementationData() {
  if (!state.activePlanId) return;
  try {
    const [recRes, bndRes, bcfgRes, plugRes, jobsRes] = await Promise.all([
      fetch(`${API_BASE}/plans/${state.activePlanId}/records?record_type=recipe`),
      fetch(`${API_BASE}/plans/${state.activePlanId}/records?record_type=target_binding_set`),
      fetch(`${API_BASE}/plans/${state.activePlanId}/records?record_type=backend_configuration`),
      fetch(`${API_BASE}/plugins`),
      fetch(`${API_BASE}/plans/${state.activePlanId}/generations`),
    ]);

    state.recipes = recRes.ok ? await recRes.json() : [];
    state.targetBindingSets = bndRes.ok ? await bndRes.json() : [];
    state.backendConfigurations = bcfgRes.ok ? await bcfgRes.json() : [];
    state.backendPlugins = plugRes.ok ? await plugRes.json() : [];
    state.generationJobs = jobsRes.ok ? await jobsRes.json() : [];

    const readyCount = state.recipes.filter((r) => r.authoring_state === "ready").length;
    const mRec = document.getElementById("metricRecipesCount");
    if (mRec) mRec.textContent = state.recipes.length;
    const mRdy = document.getElementById("metricRecipesReady");
    if (mRdy) mRdy.textContent = `${readyCount} / ${state.recipes.length}`;
    const mBnd = document.getElementById("metricBindingsCount");
    if (mBnd) mBnd.textContent = state.targetBindingSets.length;

    renderRecipesTable();
    renderBindingsTable();
    renderBackendsList();
    renderJobsTable();
  } catch (err) {
    console.error("Failed to load Layer 3 data:", err);
  }
}

function renderRecipesTable() {
  const tbody = document.getElementById("recipesTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const kindFilter = document.getElementById("filterRecipeKind")?.value;
  const filtered = kindFilter
    ? state.recipes.filter((r) => r.kind === kindFilter)
    : state.recipes;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--muted-text); padding: 24px;">No verification recipes authored yet. Click <strong>+ Recipe</strong> to create one.</td></tr>`;
    return;
  }

  filtered.forEach((r) => {
    const tr = document.createElement("tr");
    const isReady = r.authoring_state === "ready";
    const stateBadge = isReady
      ? `<span class="badge" style="background-color: var(--success-bg); color: var(--success);">READY</span>`
      : `<span class="badge" style="background-color: var(--surface-muted); color: var(--muted-text);">DRAFT</span>`;
    const kindBadge = `<span class="badge badge-${r.kind}">${r.kind.toUpperCase()}</span>`;

    tr.innerHTML = `
      <td><code>${r.key || r.id}</code></td>
      <td><strong>${escapeHtml(r.title)}</strong></td>
      <td>${kindBadge}</td>
      <td><code>${escapeHtml(r.backend_configuration_id || "none")}</code></td>
      <td><code>${escapeHtml(r.target_binding_set_id || "none")}</code></td>
      <td>${stateBadge}</td>
      <td>
        <button class="btn btn-outline btn-xs" onclick="openRecipeModal('${r.id}')">Edit</button>
        <button class="btn btn-outline btn-xs" onclick="validateRecipeById('${r.id}')" style="margin-left: 4px;">Validate</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function renderBindingsTable() {
  const tbody = document.getElementById("bindingsTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (state.targetBindingSets.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--muted-text); padding: 24px;">No target binding sets defined yet. Click <strong>+ Target Binding</strong> to bind ports and signals.</td></tr>`;
    return;
  }

  state.targetBindingSets.forEach((b) => {
    const tr = document.createElement("tr");
    const portsCount = b.ports ? b.ports.length : 0;
    const clkReset = `${b.clock ? b.clock.signal : '-'} / ${b.reset ? b.reset.signal : '-'}`;
    tr.innerHTML = `
      <td><code>${b.key || b.id}</code></td>
      <td><strong>${escapeHtml(b.title)}</strong></td>
      <td><code>${escapeHtml(b.scope_id)}</code></td>
      <td><span class="badge" style="background: var(--surface-muted);">${portsCount} signals</span></td>
      <td><code>${escapeHtml(clkReset)}</code></td>
      <td><span class="badge">${escapeHtml(b.permission || "full_access")}</span></td>
      <td><span class="badge" style="background-color: var(--success-bg); color: var(--success);">ACTIVE</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderBackendsList() {
  const container = document.getElementById("backendsListContainer");
  if (!container) return;
  container.innerHTML = "";

  if (state.backendPlugins.length === 0) {
    container.innerHTML = `<p style="color: var(--muted-text);">No backend plugins discovered.</p>`;
    return;
  }

  state.backendPlugins.forEach((p) => {
    const card = document.createElement("div");
    card.className = "backend-card";
    const families = (p.supported_target_kinds || []).join(", ");
    card.innerHTML = `
      <div class="backend-card-header">
        <span class="backend-card-title">${escapeHtml(p.display_name || p.plugin_id)} <code>v${p.version}</code></span>
        <span class="badge" style="background-color: #ebf8ff; color: #2b6cb0;">${escapeHtml(p.portability || "host_local")}</span>
      </div>
      <div class="backend-card-desc">${escapeHtml(p.description || "Verification backend plugin")}</div>
      <div class="backend-meta-tags">
        <span>Supported Targets: <strong>${escapeHtml(families || "HDL")}</strong></span>
        <span>·</span>
        <span>Lowering: <strong>${p.supports_lowering ? 'Yes' : 'Direct'}</strong></span>
        <span>·</span>
        <span>Synthetic Template: <strong>${p.supports_synthetic_results ? 'Supported' : 'No'}</strong></span>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderJobsTable() {
  const tbody = document.getElementById("jobsTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (state.generationJobs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--muted-text); padding: 24px;">No generation jobs executed yet. Click <strong>Generate Artifacts</strong> to run code generation.</td></tr>`;
    return;
  }

  state.generationJobs.forEach((job) => {
    const tr = document.createElement("tr");
    const isSuccess = job.status === "succeeded";
    const statusBadge = isSuccess
      ? `<span class="badge" style="background-color: var(--success-bg); color: var(--success);">SUCCEEDED</span>`
      : `<span class="badge" style="background-color: var(--danger-bg); color: var(--danger);">${job.status.toUpperCase()}</span>`;
    const artCount = job.result_data && job.result_data.artifact_records ? job.result_data.artifact_records.length : 0;

    tr.innerHTML = `
      <td><code>${escapeHtml(job.id)}</code></td>
      <td><code>${escapeHtml(job.checkpoint_id)}</code></td>
      <td>${escapeHtml(job.plugin_id)}</td>
      <td>${statusBadge}</td>
      <td><span class="badge">${artCount} files</span></td>
      <td>${new Date(job.created_at).toLocaleString()}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function openRecipeModal(recipeId = null) {
  const modal = document.getElementById("modalRecipe");
  document.getElementById("rcpEditId").value = recipeId || "";
  document.getElementById("modalRecipeTitle").textContent = recipeId ? "Edit Verification Recipe" : "Add Verification Recipe";

  // Populate bindings select
  const bndSel = document.getElementById("rcpFormBinding");
  bndSel.innerHTML = "";
  state.targetBindingSets.forEach((b) => {
    const opt = document.createElement("option");
    opt.value = b.id;
    opt.textContent = `${b.title} (${b.key || b.id})`;
    bndSel.appendChild(opt);
  });

  // Populate backend config select
  const bcfgSel = document.getElementById("rcpFormBackend");
  bcfgSel.innerHTML = "";
  if (state.backendConfigurations.length > 0) {
    state.backendConfigurations.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `${c.plugin_id} (v${c.plugin_version})`;
      bcfgSel.appendChild(opt);
    });
  } else {
    const opt = document.createElement("option");
    opt.value = "bcfg-ref-default";
    opt.textContent = "spec2gds.reference.bundle (v1.0.0)";
    bcfgSel.appendChild(opt);
  }

  // Populate coverage checkpoint select
  const cpRes = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints`);
  const checkpoints = cpRes.ok ? await cpRes.json() : [];
  const covCps = checkpoints.filter((c) => c.layer === "coverage");
  const cpSel = document.getElementById("rcpFormCoverageCp");
  cpSel.innerHTML = "";
  covCps.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.key || c.id} — ${c.created_at}`;
    cpSel.appendChild(opt);
  });

  const fbEl = document.getElementById("rcpValidationFeedback");
  if (fbEl) fbEl.style.display = "none";

  if (recipeId) {
    const recipe = state.recipes.find((r) => r.id === recipeId);
    if (recipe) {
      document.getElementById("rcpFormTitle").value = recipe.title || "";
      document.getElementById("rcpFormKind").value = recipe.kind || "scenario";
      if (recipe.target_binding_set_id) bndSel.value = recipe.target_binding_set_id;
      if (recipe.backend_configuration_id) bcfgSel.value = recipe.backend_configuration_id;
      if (recipe.coverage_checkpoint_id) cpSel.value = recipe.coverage_checkpoint_id;
      document.getElementById("rcpFormIntents").value = (recipe.intent_ids || []).join(", ");
      document.getElementById("rcpFormObjectives").value = (recipe.objective_ids || []).join(", ");
      document.getElementById("rcpFormState").value = recipe.authoring_state || "draft";
      document.getElementById("rcpFormTestIR").value = JSON.stringify(recipe.test_ir || {}, null, 2);
    }
  } else {
    document.getElementById("rcpFormTitle").value = "";
    document.getElementById("rcpFormKind").value = "scenario";
    document.getElementById("rcpFormIntents").value = "";
    document.getElementById("rcpFormObjectives").value = "";
    document.getElementById("rcpFormState").value = "ready";
    // Default Worked Test IR AST
    const defaultIR = {
      name: "FIFO_Boundary_Test",
      scope_id: state.plan?.root_scope_id || "sync_fifo",
      steps: [
        { step_type: "apply_reset", cycles: 2 },
        { step_type: "drive", target_signal: "wr_en", value: 1 },
        { step_type: "wait_cycles", cycles: 1 },
        { step_type: "check", target_signal: "full", expected: 1, message: "FIFO full flag must assert" }
      ]
    };
    document.getElementById("rcpFormTestIR").value = JSON.stringify(defaultIR, null, 2);
  }

  modal.classList.add("open");
}

function validateIRPreflight() {
  const irText = document.getElementById("rcpFormTestIR").value.trim();
  const fbEl = document.getElementById("rcpValidationFeedback");
  fbEl.style.display = "block";

  try {
    const parsed = JSON.parse(irText);
    if (!parsed.steps || !Array.isArray(parsed.steps) || parsed.steps.length === 0) {
      fbEl.style.backgroundColor = "var(--warning-bg)";
      fbEl.style.color = "var(--warning)";
      fbEl.textContent = "Warning: Test IR has no action steps defined.";
      return;
    }
    fbEl.style.backgroundColor = "var(--success-bg)";
    fbEl.style.color = "var(--success)";
    fbEl.textContent = `✓ Valid Test IR AST: ${parsed.steps.length} steps configured.`;
  } catch (err) {
    fbEl.style.backgroundColor = "var(--danger-bg)";
    fbEl.style.color = "var(--danger)";
    fbEl.textContent = `JSON Syntax Error: ${err.message}`;
  }
}

async function validateRecipeById(recipeId) {
  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/recipes/${recipeId}/validate`, {
      method: "POST",
    });
    const data = await res.json();
    if (data.valid) {
      alert(`Recipe '${recipeId}' passed preflight validation!`);
    } else {
      const msgs = (data.diagnostics || []).map((d) => d.message).join("\n- ");
      alert(`Preflight validation issues for '${recipeId}':\n- ${msgs}`);
    }
  } catch (err) {
    alert(`Validation failed: ${err.message}`);
  }
}

async function submitRecipe() {
  const editId = document.getElementById("rcpEditId").value;
  const title = document.getElementById("rcpFormTitle").value.trim();
  const kind = document.getElementById("rcpFormKind").value;
  const bindingId = document.getElementById("rcpFormBinding").value;
  let backendConfigId = document.getElementById("rcpFormBackend").value;
  const covCpId = document.getElementById("rcpFormCoverageCp").value;
  const intents = document.getElementById("rcpFormIntents").value.split(",").map((s) => s.trim()).filter(Boolean);
  const objectives = document.getElementById("rcpFormObjectives").value.split(",").map((s) => s.trim()).filter(Boolean);
  const authState = document.getElementById("rcpFormState").value;
  const irText = document.getElementById("rcpFormTestIR").value.trim();

  if (!title) {
    alert("Please provide a Recipe Title.");
    return;
  }

  let parsedIR;
  try {
    parsedIR = JSON.parse(irText);
  } catch (err) {
    alert(`Invalid Test IR JSON: ${err.message}`);
    return;
  }

  const operations = [];

  // Ensure backend configuration exists
  if (!state.backendConfigurations.some((c) => c.id === backendConfigId)) {
    const bcfgOp = {
      op: "backend_configuration.create",
      id: backendConfigId,
      plugin_id: "spec2gds.reference.bundle",
      plugin_version: "1.0.0",
      config_json: {},
    };
    operations.push(bcfgOp);
  }

  const recipeId = editId || `rcp-${Date.now()}`;
  if (editId) {
    operations.push({
      op: "recipe.update",
      id: editId,
      changes: {
        title,
        kind,
        target_binding_set_id: bindingId,
        backend_configuration_id: backendConfigId,
        coverage_checkpoint_id: covCpId,
        intent_ids: intents,
        objective_ids: objectives,
        test_ir: parsedIR,
        authoring_state: authState,
      },
    });
  } else {
    operations.push({
      op: "recipe.create",
      id: recipeId,
      title,
      kind,
      target_binding_set_id: bindingId,
      backend_configuration_id: backendConfigId,
      coverage_checkpoint_id: covCpId,
      intent_ids: intents,
      objective_ids: objectives,
      test_ir: parsedIR,
      oracle_provenance: { description: "Authored in Verification Planner UI" },
      authoring_state: authState,
    });
  }

  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/commands`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        base_edit_revision: state.plan.edit_revision,
        request_id: `rcp-save-${Date.now()}`,
        operations,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || "Failed to save recipe");
    }

    const data = await res.json();
    state.plan.edit_revision = data.edit_revision;
    document.getElementById("modalRecipe").classList.remove("open");
    await loadImplementationData();
  } catch (err) {
    alert(`Failed to save recipe: ${err.message}`);
  }
}

function openBindingModal() {
  const modal = document.getElementById("modalBinding");
  document.getElementById("bndFormTitle").value = "FIFO Primary Target";
  document.getElementById("bndFormPermission").value = "full_access";
  document.getElementById("bndFormClock").value = "clk";
  document.getElementById("bndFormReset").value = "rst_n";

  const defaultPorts = [
    { name: "clk", direction: "input", width: 1, signal: "clk" },
    { name: "rst_n", direction: "input", width: 1, signal: "rst_n" },
    { name: "wr_en", direction: "input", width: 1, signal: "wr_en" },
    { name: "rd_en", direction: "input", width: 1, signal: "rd_en" },
    { name: "din", direction: "input", width: 8, signal: "din" },
    { name: "dout", direction: "output", width: 8, signal: "dout" },
    { name: "full", direction: "output", width: 1, signal: "full" },
    { name: "empty", direction: "output", width: 1, signal: "empty" }
  ];
  document.getElementById("bndFormPortsJson").value = JSON.stringify(defaultPorts, null, 2);
  modal.classList.add("open");
}

async function submitBinding() {
  const title = document.getElementById("bndFormTitle").value.trim();
  const permission = document.getElementById("bndFormPermission").value;
  const clockSig = document.getElementById("bndFormClock").value.trim();
  const resetSig = document.getElementById("bndFormReset").value.trim();
  const portsText = document.getElementById("bndFormPortsJson").value.trim();

  let ports;
  try {
    ports = JSON.parse(portsText);
  } catch (err) {
    alert(`Invalid Ports JSON: ${err.message}`);
    return;
  }

  const bndId = `bnd-${Date.now()}`;
  const op = {
    op: "binding_set.create",
    id: bndId,
    title,
    scope_id: state.plan?.root_scope_id || "sync_fifo",
    permission,
    clock: { signal: clockSig, period_ps: 10000 },
    reset: { signal: resetSig, active_low: resetSig.endsWith("_n") },
    ports,
    authoring_state: "ready",
  };

  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/commands`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        base_edit_revision: state.plan.edit_revision,
        request_id: `bnd-save-${Date.now()}`,
        operations: [op],
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || "Failed to create target binding set");
    }

    const data = await res.json();
    state.plan.edit_revision = data.edit_revision;
    document.getElementById("modalBinding").classList.remove("open");
    await loadImplementationData();
  } catch (err) {
    alert(`Failed to save target binding set: ${err.message}`);
  }
}

async function openReviewImplementationModal() {
  try {
    const cpRes = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints`);
    const checkpoints = cpRes.ok ? await cpRes.json() : [];
    const covCps = checkpoints.filter((c) => c.layer === "coverage");

    const c1Select = document.getElementById("reviewImplUpstreamC1");
    c1Select.innerHTML = "";
    covCps.forEach((cp) => {
      const opt = document.createElement("option");
      opt.value = cp.id;
      opt.textContent = `${cp.key || cp.id} — ${cp.created_at} (${cp.reviewer_label})`;
      c1Select.appendChild(opt);
    });

    const upstreamC1 = covCps.length > 0 ? covCps[covCps.length - 1].id : null;

    const previewRes = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layer: "implementation", upstream_checkpoint_id: upstreamC1 }),
    });

    if (!previewRes.ok) throw new Error("Failed to preview implementation checklist");
    const preview = await previewRes.json();

    const summaryEl = document.getElementById("reviewImplChecklistSummary");
    const cl = preview.checklist || {};
    summaryEl.innerHTML = `
      <div>Upstream Coverage Checkpoint: <strong>${upstreamC1 || 'None (Missing!)'}</strong></div>
      <div>Recipes Ready: <strong>${cl.recipes_ready || 0} / ${cl.recipes_total || 0}</strong></div>
      <div>Target Bindings Configured: <strong>${cl.target_bindings_ready || 0}</strong></div>
      <div>Backends Ready: <strong>${cl.backends_ready || 0}</strong></div>
      <div>Unimplemented Objectives: <strong>${cl.unimplemented_objective_count || 0}</strong></div>
    `;

    const blockersBox = document.getElementById("reviewImplBlockersContainer");
    const blockersList = document.getElementById("reviewImplBlockersList");
    if (preview.blockers && preview.blockers.length > 0) {
      blockersBox.style.display = "block";
      blockersList.innerHTML = preview.blockers.map((b) => `<li>${b.message}</li>`).join("");
      document.getElementById("btnConfirmReviewImplementation").disabled = true;
    } else {
      blockersBox.style.display = "none";
      document.getElementById("btnConfirmReviewImplementation").disabled = false;
    }

    state.implCandidateDigest = preview.candidate_digest;
    document.getElementById("modalReviewImplementation").classList.add("open");
  } catch (err) {
    alert(`Implementation review preview failed: ${err.message}`);
  }
}

async function submitReviewImplementation() {
  const c1Id = document.getElementById("reviewImplUpstreamC1").value;
  const payload = {
    layer: "implementation",
    reviewer_label: document.getElementById("reviewImplReviewer").value.trim() || "impl_lead",
    comment: document.getElementById("reviewImplComment").value.trim(),
    expected_digest: state.implCandidateDigest,
    upstream_checkpoint_id: c1Id,
  };

  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || "Failed to commit Implementation Checkpoint");
    }

    const checkpoint = await res.json();
    alert(`Implementation Checkpoint ${checkpoint.key} created successfully!`);
    document.getElementById("modalReviewImplementation").classList.remove("open");
    await loadImplementationData();
  } catch (err) {
    alert(`Failed to commit Implementation Checkpoint: ${err.message}`);
  }
}

async function openGenerationModal() {
  const cpRes = await fetch(`${API_BASE}/plans/${state.activePlanId}/checkpoints`);
  const checkpoints = cpRes.ok ? await cpRes.json() : [];
  const implCps = checkpoints.filter((c) => c.layer === "implementation");

  const cpSel = document.getElementById("genCheckpointSelect");
  cpSel.innerHTML = "";
  if (implCps.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "(No Implementation Checkpoint I1 exists yet)";
    cpSel.appendChild(opt);
  } else {
    implCps.forEach((cp) => {
      const opt = document.createElement("option");
      opt.value = cp.id;
      opt.textContent = `${cp.key || cp.id} — ${cp.created_at}`;
      cpSel.appendChild(opt);
    });
  }

  const plugSel = document.getElementById("genPluginSelect");
  plugSel.innerHTML = "";
  state.backendPlugins.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.plugin_id;
    opt.textContent = `${p.display_name || p.plugin_id} (v${p.version})`;
    plugSel.appendChild(opt);
  });

  const fbEl = document.getElementById("genPreviewFeedback");
  if (fbEl) fbEl.style.display = "none";
  const resEl = document.getElementById("genArtifactsResultContainer");
  if (resEl) resEl.style.display = "none";

  document.getElementById("modalGeneration").classList.add("open");
}

async function runGenerationPreview() {
  const checkpointId = document.getElementById("genCheckpointSelect").value;
  const pluginId = document.getElementById("genPluginSelect").value;
  const fbEl = document.getElementById("genPreviewFeedback");
  fbEl.style.display = "block";

  if (!checkpointId) {
    fbEl.style.backgroundColor = "var(--danger-bg)";
    fbEl.style.color = "var(--danger)";
    fbEl.textContent = "Please select or create an Implementation Checkpoint (I1) first.";
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/generations/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ checkpoint_id: checkpointId, plugin_id: pluginId }),
    });

    if (!res.ok) throw new Error("Failed to preview generation");
    const preview = await res.json();

    if (preview.ready_to_generate) {
      fbEl.style.backgroundColor = "var(--success-bg)";
      fbEl.style.color = "var(--success)";
      fbEl.textContent = `✓ Ready to generate: ${preview.recipes_count} recipes lowered for plugin '${preview.plugin.plugin_id}'.`;
    } else {
      fbEl.style.backgroundColor = "var(--warning-bg)";
      fbEl.style.color = "var(--warning)";
      const msgs = (preview.diagnostics || []).map((d) => d.message).join("; ");
      fbEl.textContent = `Preflight warnings: ${msgs}`;
    }
  } catch (err) {
    fbEl.style.backgroundColor = "var(--danger-bg)";
    fbEl.style.color = "var(--danger)";
    fbEl.textContent = `Preview error: ${err.message}`;
  }
}

async function submitGeneration() {
  const checkpointId = document.getElementById("genCheckpointSelect").value;
  const pluginId = document.getElementById("genPluginSelect").value;
  const resEl = document.getElementById("genArtifactsResultContainer");
  const listEl = document.getElementById("genArtifactsList");

  if (!checkpointId) {
    alert("Select an Implementation Checkpoint first.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/generations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ checkpoint_id: checkpointId, plugin_id: pluginId }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || "Generation execution failed");
    }

    const job = await res.json();
    if (job.status === "failed") {
      const msgs = (job.diagnostics || []).map((d) => d.message).join("\n- ");
      alert(`Generation job failed:\n- ${msgs}`);
      return;
    }

    const artifacts = (job.result_data && job.result_data.artifact_records) || [];
    resEl.style.display = "block";
    listEl.innerHTML = "";

    artifacts.forEach((a) => {
      const li = document.createElement("li");
      li.style.marginBottom = "6px";
      li.innerHTML = `
        📄 <strong>${escapeHtml(a.relative_path)}</strong> (${a.size_bytes} bytes)
        <a href="#" onclick="viewArtifact('${a.id}', '${escapeHtml(a.relative_path)}'); return false;" style="margin-left: 8px; color: var(--primary);">View</a>
        <a href="${API_BASE}/plans/${state.activePlanId}/artifacts/${a.id}" download target="_blank" style="margin-left: 6px; color: var(--muted-text);">Download</a>
      `;
      listEl.appendChild(li);
    });

    await loadImplementationData();
  } catch (err) {
    alert(`Generation failed: ${err.message}`);
  }
}

async function viewArtifact(artifactId, relPath) {
  try {
    const res = await fetch(`${API_BASE}/plans/${state.activePlanId}/artifacts/${artifactId}`);
    if (!res.ok) throw new Error("Could not fetch artifact content");

    const text = await res.text();
    document.getElementById("artifactViewerTitle").textContent = `Artifact: ${relPath}`;
    document.getElementById("artifactMetaBar").textContent = `Path: ${relPath} · Size: ${text.length} chars`;
    document.getElementById("artifactViewerCode").textContent = text;
    document.getElementById("btnDownloadArtifact").href = `${API_BASE}/plans/${state.activePlanId}/artifacts/${artifactId}`;
    document.getElementById("modalArtifactViewer").classList.add("open");
  } catch (err) {
    alert(`Could not display artifact: ${err.message}`);
  }
}



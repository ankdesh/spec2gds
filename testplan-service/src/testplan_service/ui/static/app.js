// spec2gds Testplan Manager - Client Application
(function () {
  "use strict";

  const API_BASE = "/api/v1";
  let activePlanId = null;
  let activePlanDoc = null;
  let selectedNodeId = null;
  let collapsedNodes = new Set();
  let currentPreviewProposal = null;

  // DOM Elements
  const planSelector = document.getElementById("planSelector");
  const btnNewPlan = document.getElementById("btnNewPlan");
  const btnImportPlan = document.getElementById("btnImportPlan");
  const btnExportMarkdown = document.getElementById("btnExportMarkdown");
  const btnExportJson = document.getElementById("btnExportJson");
  const btnAiProposals = document.getElementById("btnAiProposals");
  const btnAddRootNode = document.getElementById("btnAddRootNode");
  const btnExpandAll = document.getElementById("btnExpandAll");
  const btnCollapseAll = document.getElementById("btnCollapseAll");
  const searchInput = document.getElementById("searchInput");
  const kindFilter = document.getElementById("kindFilter");
  const treeContainer = document.getElementById("treeContainer");

  // Metadata & Summary elements
  const metaPlanId = document.getElementById("metaPlanId");
  const metaTargetDesign = document.getElementById("metaTargetDesign");
  const metaVersion = document.getElementById("metaVersion");
  const metaRevision = document.getElementById("metaRevision");
  const summaryPassRate = document.getElementById("summaryPassRate");
  const progressBarFill = document.getElementById("progressBarFill");
  const summaryTotalNodes = document.getElementById("summaryTotalNodes");
  const summaryCoverageBins = document.getElementById("summaryCoverageBins");
  const categoryPills = document.getElementById("categoryPills");
  const stagePills = document.getElementById("stagePills");

  // Inspector elements
  const inspectorEmpty = document.getElementById("inspectorEmpty");
  const inspectorForm = document.getElementById("inspectorForm");
  const formNodeId = document.getElementById("formNodeId");
  const formParentId = document.getElementById("formParentId");
  const formTitle = document.getElementById("formTitle");
  const formKind = document.getElementById("formKind");
  const formCategory = document.getElementById("formCategory");
  const formStatus = document.getElementById("formStatus");
  const formPriority = document.getElementById("formPriority");
  const formStage = document.getElementById("formStage");
  const formMethodology = document.getElementById("formMethodology");
  const formDescription = document.getElementById("formDescription");
  const formStimulus = document.getElementById("formStimulus");
  const formExpected = document.getElementById("formExpected");
  const formCoverageBins = document.getElementById("formCoverageBins");
  const formTags = document.getElementById("formTags");
  const btnDeselectNode = document.getElementById("btnDeselectNode");
  const btnDeleteSelectedNode = document.getElementById("btnDeleteSelectedNode");

  // Modals
  const modalNewPlan = document.getElementById("modalNewPlan");
  const formNewPlan = document.getElementById("formNewPlan");
  const modalProposals = document.getElementById("modalProposals");
  const modalImport = document.getElementById("modalImport");
  const formImport = document.getElementById("formImport");
  const proposalJsonInput = document.getElementById("proposalJsonInput");
  const btnLoadSampleProposal = document.getElementById("btnLoadSampleProposal");
  const btnPreviewProposal = document.getElementById("btnPreviewProposal");
  const btnApplyProposal = document.getElementById("btnApplyProposal");
  const proposalPreviewBox = document.getElementById("proposalPreviewBox");
  const proposalDiffText = document.getElementById("proposalDiffText");

  // API Client Helpers
  async function apiFetch(endpoint, options = {}) {
    const headers = { Accept: "application/json", ...options.headers };
    if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.body);
    }
    const response = await fetch(endpoint, { ...options, headers });
    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      try {
        const err = await response.json();
        detail = err.message || err.error || JSON.stringify(err);
      } catch (_) {}
      throw new Error(detail);
    }
    if (response.status === 204) return null;
    return response.json();
  }

  // Initialization
  async function init() {
    setupEventHandlers();
    await loadPlanList();
  }

  function setupEventHandlers() {
    planSelector.addEventListener("change", (e) => {
      if (e.target.value) loadPlan(e.target.value);
    });

    btnNewPlan.addEventListener("click", () => openModal(modalNewPlan));
    btnImportPlan.addEventListener("click", () => openModal(modalImport));
    btnAiProposals.addEventListener("click", () => {
      openModal(modalProposals);
      if (activePlanDoc && !proposalJsonInput.value.trim()) {
        loadSampleProposal();
      }
    });

    document.querySelectorAll(".modal-close").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const overlay = e.target.closest(".modal-overlay");
        if (overlay) closeModal(overlay);
      });
    });

    formNewPlan.addEventListener("submit", handleCreatePlan);
    formImport.addEventListener("submit", handleImportPlan);

    btnExportMarkdown.addEventListener("click", () => {
      if (!activePlanId) return;
      window.open(`${API_BASE}/testplans/${encodeURIComponent(activePlanId)}/export/markdown`, "_blank");
    });

    btnExportJson.addEventListener("click", () => {
      if (!activePlanId) return;
      window.open(`${API_BASE}/testplans/${encodeURIComponent(activePlanId)}/export/json`, "_blank");
    });

    btnAddRootNode.addEventListener("click", () => handleAddNode(null));
    btnExpandAll.addEventListener("click", () => {
      collapsedNodes.clear();
      renderTree();
    });
    btnCollapseAll.addEventListener("click", () => {
      if (!activePlanDoc) return;
      Object.keys(activePlanDoc.nodes).forEach((id) => collapsedNodes.add(id));
      renderTree();
    });

    searchInput.addEventListener("input", renderTree);
    kindFilter.addEventListener("change", renderTree);

    btnDeselectNode.addEventListener("click", deselectNode);
    inspectorForm.addEventListener("submit", handleSaveNode);
    btnDeleteSelectedNode.addEventListener("click", handleDeleteSelectedNode);

    btnLoadSampleProposal.addEventListener("click", loadSampleProposal);
    btnPreviewProposal.addEventListener("click", handlePreviewProposal);
    btnApplyProposal.addEventListener("click", handleApplyProposal);
  }

  function openModal(modal) {
    modal.classList.add("active");
  }
  function closeModal(modal) {
    modal.classList.remove("active");
  }

  // Load List of Plans
  async function loadPlanList() {
    try {
      const plans = await apiFetch(`${API_BASE}/testplans`);
      planSelector.innerHTML = "";
      if (plans.length === 0) {
        // Auto-create a sample plan if none exist
        await createSamplePlan();
        return;
      }
      plans.forEach((p) => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = `${p.name} (${p.target_design || "No Target"})`;
        planSelector.appendChild(opt);
      });
      if (!activePlanId || !plans.some((p) => p.id === activePlanId)) {
        activePlanId = plans[0].id;
      }
      planSelector.value = activePlanId;
      await loadPlan(activePlanId);
    } catch (err) {
      alert(`Error loading testplans: ${err.message}`);
    }
  }

  // Create a default initial sample plan if repo is empty
  async function createSamplePlan() {
    try {
      const sample = {
        id: "alu_verification_plan",
        name: "ALU Subsystem Verification Plan",
        target_design: "alu_core",
        description: "Comprehensive hierarchical test plan verifying arithmetic, logical, and reset operations.",
        version: "1.0.0",
        tags: ["alu", "arithmetic", "spec2gds"],
      };
      await apiFetch(`${API_BASE}/testplans`, { method: "POST", body: sample });

      // Add baseline nodes
      const groupNode = {
        id: "grp_functional",
        parent_id: null,
        title: "Functional Logic Verification",
        kind: "group",
        category: "functional_mode",
        description: "Coverage for standard arithmetic and bitwise logic operations.",
        methodology: "directed",
        stage: "V1",
        status: "planned",
        order: 0,
      };
      await apiFetch(`${API_BASE}/testplans/alu_verification_plan/nodes`, {
        method: "POST",
        body: groupNode,
      });

      const tc1 = {
        id: "tc_add_overflow",
        parent_id: "grp_functional",
        title: "Addition Overflow Corner Case",
        kind: "testcase",
        category: "port_boundary",
        description: "Stimulate maximum 32-bit addition to verify carry-out and overflow flags.",
        methodology: "constrained_random",
        stage: "V2",
        priority: "high",
        status: "passed",
        stimulus: "op_a = 0xFFFFFFFF, op_b = 0x00000001, opcode = ADD",
        expected_outcome: "sum = 0x00000000, carry_out = 1, overflow = 1",
        coverage_bins: ["boundary:op_a:max", "functional_mode:add:overflow"],
        tags: ["add", "overflow", "boundary"],
        order: 0,
      };
      await apiFetch(`${API_BASE}/testplans/alu_verification_plan/nodes`, {
        method: "POST",
        body: tc1,
      });

      const tc2 = {
        id: "tc_reset_recovery",
        parent_id: "grp_functional",
        title: "Active-Low Reset Output Cleared",
        kind: "testcase",
        category: "reset_behavior",
        description: "Assert rst_n and verify all internal accumulator registers clear synchronously.",
        methodology: "formal",
        stage: "V0",
        priority: "critical",
        status: "passed",
        stimulus: "rst_n = 0, valid_in = 1",
        expected_outcome: "data_out = 0, valid_out = 0",
        coverage_bins: ["reset_behavior:rst_n:cleared"],
        tags: ["reset", "safety"],
        order: 1,
      };
      await apiFetch(`${API_BASE}/testplans/alu_verification_plan/nodes`, {
        method: "POST",
        body: tc2,
      });

      await loadPlanList();
    } catch (e) {
      console.error("Failed to seed initial sample plan", e);
    }
  }

  // Load one plan
  async function loadPlan(planId) {
    try {
      activePlanId = planId;
      activePlanDoc = await apiFetch(`${API_BASE}/testplans/${encodeURIComponent(planId)}`);
      updateSidebarMeta();
      await updateSummaryMetrics();
      renderTree();
      if (selectedNodeId && activePlanDoc.nodes[selectedNodeId]) {
        selectNode(selectedNodeId);
      } else {
        deselectNode();
      }
    } catch (err) {
      alert(`Failed to load plan: ${err.message}`);
    }
  }

  function updateSidebarMeta() {
    metaPlanId.textContent = activePlanDoc.id;
    metaTargetDesign.textContent = activePlanDoc.target_design || "(unspecified)";
    metaVersion.textContent = activePlanDoc.version;
    metaRevision.textContent = `r${activePlanDoc.revision}`;
  }

  async function updateSummaryMetrics() {
    try {
      const summary = await apiFetch(`${API_BASE}/testplans/${encodeURIComponent(activePlanId)}/summary`);
      summaryPassRate.textContent = `${summary.pass_rate_percent}%`;
      progressBarFill.style.width = `${summary.pass_rate_percent}%`;
      summaryTotalNodes.textContent = summary.total_nodes;
      summaryCoverageBins.textContent = summary.total_coverage_bins;

      categoryPills.innerHTML = "";
      Object.entries(summary.nodes_by_category).forEach(([cat, count]) => {
        const p = document.createElement("span");
        p.className = "pill";
        p.textContent = `${cat}: ${count}`;
        categoryPills.appendChild(p);
      });

      stagePills.innerHTML = "";
      Object.entries(summary.nodes_by_stage).forEach(([st, count]) => {
        const p = document.createElement("span");
        p.className = "pill";
        p.textContent = `${st}: ${count}`;
        stagePills.appendChild(p);
      });
    } catch (err) {
      console.error("Failed to load summary", err);
    }
  }

  // Render Tree
  function renderTree() {
    if (!activePlanDoc) return;
    treeContainer.innerHTML = "";

    const query = searchInput.value.toLowerCase().trim();
    const kindVal = kindFilter.value;

    const roots = buildTreeNodes(activePlanDoc.nodes);
    if (roots.length === 0) {
      treeContainer.innerHTML = `
        <div style="text-align: center; color: var(--text-muted); margin-top: 40px;">
          No nodes in this testplan. Click <strong>+ Add Item</strong> above to start building the hierarchy.
        </div>`;
      return;
    }

    roots.forEach((root) => {
      const el = renderNodeElement(root, 0, query, kindVal);
      if (el) treeContainer.appendChild(el);
    });
  }

  function buildTreeNodes(nodesDict) {
    const clones = {};
    Object.values(nodesDict).forEach((n) => {
      clones[n.id] = { ...n, children: [] };
    });
    const roots = [];
    Object.values(clones).forEach((n) => {
      if (n.parent_id && clones[n.parent_id]) {
        clones[n.parent_id].children.push(n);
      } else {
        roots.push(n);
      }
    });
    const sortFn = (a, b) => (a.order - b.order) || a.title.localeCompare(b.title);
    roots.sort(sortFn);
    Object.values(clones).forEach((n) => n.children.sort(sortFn));
    return roots;
  }

  function renderNodeElement(node, depth, query, kindVal) {
    const matchesQuery = !query ||
      node.title.toLowerCase().includes(query) ||
      node.id.toLowerCase().includes(query) ||
      node.category.toLowerCase().includes(query) ||
      (node.tags && node.tags.some((t) => t.toLowerCase().includes(query)));

    const matchesKind = !kindVal || node.kind === kindVal;

    // Process children first
    const renderedChildren = [];
    node.children.forEach((child) => {
      const cEl = renderNodeElement(child, depth + 1, query, kindVal);
      if (cEl) renderedChildren.push(cEl);
    });

    const isVisible = (matchesQuery && matchesKind) || renderedChildren.length > 0;
    if (!isVisible) return null;

    const wrapper = document.createElement("div");
    wrapper.className = "tree-node-wrapper";

    const row = document.createElement("div");
    row.className = `tree-node tree-node-kind-${node.kind} tree-node-status-${node.status} ${node.id === selectedNodeId ? "selected" : ""}`;
    row.style.paddingLeft = `${12 + depth * 20}px`;

    // Collapse / Expand arrow
    const hasChildren = node.children.length > 0;
    const isCollapsed = collapsedNodes.has(node.id);
    const arrow = document.createElement("span");
    arrow.className = "toggle-arrow";
    arrow.textContent = hasChildren ? (isCollapsed ? "▶" : "▼") : "•";
    if (hasChildren) {
      arrow.addEventListener("click", (e) => {
        e.stopPropagation();
        if (collapsedNodes.has(node.id)) {
          collapsedNodes.delete(node.id);
        } else {
          collapsedNodes.add(node.id);
        }
        renderTree();
      });
    }
    row.appendChild(arrow);

    // Kind Badge
    const kindBadge = document.createElement("span");
    kindBadge.className = `badge badge-kind-${node.kind}`;
    kindBadge.textContent = node.kind;
    row.appendChild(kindBadge);

    // Status Badge
    const statusBadge = document.createElement("span");
    statusBadge.className = `badge badge-status-${node.status}`;
    statusBadge.textContent = node.status;
    row.appendChild(statusBadge);

    // Category Badge
    if (node.category && node.category !== "general") {
      const catBadge = document.createElement("span");
      catBadge.className = "badge badge-cat";
      catBadge.textContent = node.category.replace("_", " ");
      row.appendChild(catBadge);
    }

    // Title
    const titleSpan = document.createElement("span");
    titleSpan.className = "node-title";
    titleSpan.textContent = node.title;
    row.appendChild(titleSpan);

    // Action buttons on hover
    const actions = document.createElement("div");
    actions.className = "node-actions";

    const btnAddChild = document.createElement("button");
    btnAddChild.className = "icon-btn";
    btnAddChild.title = "Add child node";
    btnAddChild.textContent = "+";
    btnAddChild.addEventListener("click", (e) => {
      e.stopPropagation();
      handleAddNode(node.id);
    });
    actions.appendChild(btnAddChild);

    const btnDel = document.createElement("button");
    btnDel.className = "icon-btn";
    btnDel.title = "Delete node";
    btnDel.textContent = "🗑";
    btnDel.addEventListener("click", (e) => {
      e.stopPropagation();
      handleDeleteNode(node.id);
    });
    actions.appendChild(btnDel);

    row.appendChild(actions);

    row.addEventListener("click", () => selectNode(node.id));
    wrapper.appendChild(row);

    // Append child container if not collapsed
    if (hasChildren && !isCollapsed) {
      const childrenContainer = document.createElement("div");
      renderedChildren.forEach((c) => childrenContainer.appendChild(c));
      wrapper.appendChild(childrenContainer);
    }

    return wrapper;
  }

  // Node Selection & Inspector
  function selectNode(nodeId) {
    selectedNodeId = nodeId;
    const node = activePlanDoc.nodes[nodeId];
    if (!node) {
      deselectNode();
      return;
    }

    inspectorEmpty.style.display = "none";
    inspectorForm.style.display = "flex";

    formNodeId.value = node.id;
    formParentId.value = node.parent_id || "";
    formTitle.value = node.title || "";
    formKind.value = node.kind || "testcase";
    formCategory.value = node.category || "general";
    formStatus.value = node.status || "planned";
    formPriority.value = node.priority || "medium";
    formStage.value = node.stage || "V1";
    formMethodology.value = node.methodology || "directed";
    formDescription.value = node.description || "";
    formStimulus.value = node.stimulus || "";
    formExpected.value = node.expected_outcome || "";
    formCoverageBins.value = (node.coverage_bins || []).join(", ");
    formTags.value = (node.tags || []).join(", ");

    // Update selection styling in tree
    document.querySelectorAll(".tree-node").forEach((el) => el.classList.remove("selected"));
    const selectedEl = document.querySelector(`.tree-node[style*="padding-left"]`);
    renderTree();
  }

  function deselectNode() {
    selectedNodeId = null;
    inspectorEmpty.style.display = "block";
    inspectorForm.style.display = "none";
    document.querySelectorAll(".tree-node").forEach((el) => el.classList.remove("selected"));
  }

  // Node CRUD operations
  async function handleAddNode(parentId) {
    if (!activePlanId) return;
    const title = prompt(parentId ? "Enter child node title:" : "Enter root item title:");
    if (!title || !title.trim()) return;

    const defaultKind = parentId ? "testcase" : "group";
    const newNode = {
      id: `node_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 6)}`,
      parent_id: parentId,
      title: title.trim(),
      kind: defaultKind,
      category: "general",
      status: "planned",
      priority: "medium",
      stage: "V1",
      methodology: "directed",
      order: 0,
    };

    try {
      await apiFetch(`${API_BASE}/testplans/${encodeURIComponent(activePlanId)}/nodes`, {
        method: "POST",
        body: newNode,
      });
      await loadPlan(activePlanId);
      selectNode(newNode.id);
    } catch (err) {
      alert(`Failed to add node: ${err.message}`);
    }
  }

  async function handleSaveNode(e) {
    e.preventDefault();
    if (!activePlanId || !selectedNodeId) return;

    const updates = {
      title: formTitle.value.trim(),
      kind: formKind.value,
      category: formCategory.value,
      status: formStatus.value,
      priority: formPriority.value,
      stage: formStage.value,
      methodology: formMethodology.value,
      description: formDescription.value.trim(),
      stimulus: formStimulus.value.trim(),
      expected_outcome: formExpected.value.trim(),
      coverage_bins: formCoverageBins.value
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      tags: formTags.value
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };

    try {
      await apiFetch(
        `${API_BASE}/testplans/${encodeURIComponent(activePlanId)}/nodes/${encodeURIComponent(selectedNodeId)}`,
        { method: "PUT", body: updates }
      );
      await loadPlan(activePlanId);
    } catch (err) {
      alert(`Failed to save node: ${err.message}`);
    }
  }

  async function handleDeleteNode(nodeId) {
    if (!confirm(`Are you sure you want to delete node '${nodeId}' and all its children?`)) {
      return;
    }
    try {
      await apiFetch(
        `${API_BASE}/testplans/${encodeURIComponent(activePlanId)}/nodes/${encodeURIComponent(nodeId)}?cascade=true`,
        { method: "DELETE" }
      );
      if (selectedNodeId === nodeId) deselectNode();
      await loadPlan(activePlanId);
    } catch (err) {
      alert(`Failed to delete node: ${err.message}`);
    }
  }

  async function handleDeleteSelectedNode() {
    if (selectedNodeId) handleDeleteNode(selectedNodeId);
  }

  // Plan CRUD
  async function handleCreatePlan(e) {
    e.preventDefault();
    const id = document.getElementById("newPlanId").value.trim();
    const name = document.getElementById("newPlanName").value.trim();
    const target = document.getElementById("newPlanTarget").value.trim();
    const desc = document.getElementById("newPlanDesc").value.trim();

    try {
      await apiFetch(`${API_BASE}/testplans`, {
        method: "POST",
        body: { id, name, target_design: target, description: desc },
      });
      closeModal(modalNewPlan);
      formNewPlan.reset();
      activePlanId = id;
      await loadPlanList();
    } catch (err) {
      alert(`Failed to create testplan: ${err.message}`);
    }
  }

  async function handleImportPlan(e) {
    e.preventDefault();
    const text = document.getElementById("importJsonInput").value.trim();
    try {
      const payload = JSON.parse(text);
      const imported = await apiFetch(`${API_BASE}/testplans/import`, {
        method: "POST",
        body: payload,
      });
      closeModal(modalImport);
      formImport.reset();
      activePlanId = imported.id;
      await loadPlanList();
    } catch (err) {
      alert(`Import failed: ${err.message}`);
    }
  }

  // AI Proposals Integration
  function loadSampleProposal() {
    if (!activePlanDoc) return;
    const sample = {
      proposal_id: `prop_${Date.now().toString(36)}`,
      document_id: activePlanDoc.id,
      base_revision: activePlanDoc.revision,
      title: "Add Timing and Error Injection Testpoints",
      summary: "LLM-assisted coverage expansion targeting backpressure stalls and invalid handshake inputs.",
      rationale: "Analysis identified coverage gaps in timing and error injection categories.",
      operations: [
        {
          action: "add_node",
          parent_id: null,
          node_data: {
            id: `grp_robustness_${Date.now().toString(36).slice(-4)}`,
            title: "Protocol Robustness & Error Handling",
            kind: "group",
            category: "protocol_compliance",
            description: "Stress tests for valid/ready backpressure and out-of-range stimulus.",
            methodology: "constrained_random",
            stage: "V2",
            status: "planned",
            order: 2,
          },
        },
        {
          action: "add_node",
          parent_id: `grp_robustness_${Date.now().toString(36).slice(-4)}`,
          node_data: {
            id: `tc_stall_${Date.now().toString(36).slice(-4)}`,
            title: "Consecutive 4-Cycle Ready Deassertion",
            kind: "testcase",
            category: "timing_sequencing",
            description: "Hold ready low for 4 cycles while valid is high to test FIFO fullness.",
            methodology: "directed",
            stage: "V2",
            status: "planned",
            stimulus: "valid_in = 1, ready_in = 0 for 4 clock cycles",
            expected_outcome: "DUT asserts backpressure, drops 0 packets, pipeline freezes",
            coverage_bins: ["timing_sequencing:ready:backpressure_stall"],
            order: 0,
          },
        },
      ],
    };
    proposalJsonInput.value = JSON.stringify(sample, null, 2);
    btnApplyProposal.disabled = true;
    proposalPreviewBox.style.display = "none";
  }

  async function handlePreviewProposal() {
    const raw = proposalJsonInput.value.trim();
    if (!raw) return;
    try {
      const proposal = JSON.parse(raw);
      currentPreviewProposal = proposal;
      const res = await apiFetch("/assistant/proposals/preview", {
        method: "POST",
        body: proposal,
      });

      proposalPreviewBox.style.display = "block";
      const diffLines = (res.summary_diff || []).map((line) => {
        if (line.startsWith("+")) return `<span class="diff-add">${escapeHtml(line)}</span>`;
        if (line.startsWith("~")) return `<span class="diff-mod">${escapeHtml(line)}</span>`;
        if (line.startsWith("-")) return `<span class="diff-del">${escapeHtml(line)}</span>`;
        return escapeHtml(line);
      });

      const diagLines = (res.diagnostics || []).map(
        (d) => `<span style="color: var(--status-in-progress, #7e5a0d);">[Warning] ${escapeHtml(d)}</span>`
      );

      proposalDiffText.innerHTML = [
        `Valid: ${res.valid ? "YES" : "NO"} | Added: ${res.nodes_added} | Modified: ${res.nodes_modified} | Deleted: ${res.nodes_deleted}`,
        "",
        ...diagLines,
        ...diffLines,
      ].join("\n");

      btnApplyProposal.disabled = !res.valid;
    } catch (err) {
      alert(`Preview failed: ${err.message}`);
    }
  }

  async function handleApplyProposal() {
    if (!currentPreviewProposal) return;
    try {
      const res = await apiFetch("/assistant/proposals/apply", {
        method: "POST",
        body: currentPreviewProposal,
      });
      alert(`Proposal Applied Successfully!\nNew revision: r${res.new_revision}`);
      closeModal(modalProposals);
      await loadPlan(res.document_id);
    } catch (err) {
      alert(`Apply failed: ${err.message}`);
    }
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // Start app
  window.addEventListener("DOMContentLoaded", init);
})();

/**
 * Spec2GDS Component Library static frontend application.
 */

(function () {
  "use strict";

  // Elements
  const elStatus = document.getElementById("service-status");
  const elAlertDisconnected = document.getElementById("alert-disconnected");
  const elSearch = document.getElementById("input-search");
  const elCategory = document.getElementById("select-category");
  const elFunctionalStatus = document.getElementById("select-status");
  const elGrid = document.getElementById("components-grid");
  const elLoading = document.getElementById("state-loading");
  const elEmpty = document.getElementById("state-empty");
  const elPrevPage = document.getElementById("btn-prev-page");
  const elNextPage = document.getElementById("btn-next-page");
  const elPaginationInfo = document.getElementById("pagination-info");

  const modalDetails = document.getElementById("modal-details");
  const modalDetailsBody = document.getElementById("modal-details-body");
  const btnCloseDetails = document.getElementById("btn-close-details");

  const modalUpload = document.getElementById("modal-upload");
  const btnUpload = document.getElementById("btn-upload");
  const btnCloseUpload = document.getElementById("btn-close-upload");
  const btnCancelUpload = document.getElementById("btn-cancel-upload");
  const formUpload = document.getElementById("form-upload");
  const inputFile = document.getElementById("input-file");
  const uploadFeedback = document.getElementById("upload-feedback");

  // State
  let limit = 25;
  let offset = 0;
  let total = 0;
  let searchTimeout = null;

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  async function checkHealth() {
    try {
      const res = await fetch("/api/spec-library/v1/health");
      if (res.ok) {
        const data = await res.json();
        elStatus.textContent = data.status === "ready" ? "Service Ready" : "Degraded";
        elStatus.className = "status-indicator " + (data.status === "ready" ? "status-ready" : "status-error");
        elAlertDisconnected.classList.add("hidden");
      } else {
        throw new Error("HTTP " + res.status);
      }
    } catch (err) {
      elStatus.textContent = "Disconnected";
      elStatus.className = "status-indicator status-error";
      elAlertDisconnected.classList.remove("hidden");
    }
  }

  async function loadCapabilities() {
    try {
      const res = await fetch("/api/spec-library/v1/capabilities");
      if (res.ok) {
        const caps = await res.json();
        elCategory.innerHTML = '<option value="">All Categories</option>';
        (caps.categories || []).forEach(cat => {
          const opt = document.createElement("option");
          opt.value = cat;
          opt.textContent = cat.charAt(0).toUpperCase() + cat.slice(1);
          elCategory.appendChild(opt);
        });
      }
    } catch (err) {
      console.warn("Could not load capabilities:", err);
    }
  }

  async function loadComponents() {
    elLoading.classList.remove("hidden");
    elEmpty.classList.add("hidden");
    elGrid.innerHTML = "";

    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString()
    });
    if (elSearch.value.trim()) params.set("q", elSearch.value.trim());
    if (elCategory.value) params.set("category", elCategory.value);
    if (elFunctionalStatus.value) params.set("functional_status", elFunctionalStatus.value);

    try {
      const res = await fetch("/api/spec-library/v1/components?" + params.toString());
      if (!res.ok) throw new Error("Failed to load components");
      const data = await res.json();
      total = data.total;
      renderGrid(data.items);
      renderPagination();
    } catch (err) {
      console.error(err);
      elEmpty.classList.remove("hidden");
    } finally {
      elLoading.classList.add("hidden");
    }
  }

  function renderGrid(items) {
    if (!items || items.length === 0) {
      elEmpty.classList.remove("hidden");
      return;
    }

    items.forEach(item => {
      const card = document.createElement("article");
      card.className = "card";
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.setAttribute("aria-label", `Component ${item.id} version ${item.version}`);

      const tagsHtml = (item.tags || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join("");
      const statusBadge = getStatusBadge(item.functional_status);

      card.innerHTML = `
        <div>
          <div class="card-header">
            <h3 class="card-title">${escapeHtml(item.id)}</h3>
            <span class="card-version">${escapeHtml(item.version)}</span>
          </div>
          <p class="card-summary">${escapeHtml(item.summary || "No description provided.")}</p>
          <div class="card-tags">${tagsHtml}</div>
        </div>
        <div class="card-footer">
          <span>Category: <strong>${escapeHtml(item.category)}</strong></span>
          ${statusBadge}
        </div>
      `;

      card.addEventListener("click", () => openDetails(item.key, item.version));
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openDetails(item.key, item.version);
        }
      });

      elGrid.appendChild(card);
    });
  }

  function getStatusBadge(status) {
    if (status === "reported_pass") return '<span class="badge badge-pass">Pass</span>';
    if (status === "reported_fail") return '<span class="badge badge-fail">Fail</span>';
    if (status === "reported_incomplete") return '<span class="badge badge-incomplete">Incomplete</span>';
    return '<span class="badge badge-unreported">Unreported</span>';
  }

  function renderPagination() {
    const start = total === 0 ? 0 : offset + 1;
    const end = Math.min(offset + limit, total);
    elPaginationInfo.textContent = `Showing ${start} - ${end} of ${total}`;
    elPrevPage.disabled = offset <= 0;
    elNextPage.disabled = offset + limit >= total;
  }

  async function openDetails(key, version) {
    modalDetailsBody.innerHTML = '<div class="spinner" aria-hidden="true"></div>';
    modalDetails.showModal();

    try {
      const [compRes, verRes] = await Promise.all([
        fetch(`/api/spec-library/v1/components/${key}`),
        fetch(`/api/spec-library/v1/components/${key}/versions/${version}`)
      ]);

      if (!compRes.ok || !verRes.ok) throw new Error("Could not fetch details");
      const compData = await compRes.json();
      const verData = await verRes.json();

      renderModalDetails(compData, verData);
    } catch (err) {
      modalDetailsBody.innerHTML = `<div class="banner banner-error">Failed to load component details: ${escapeHtml(err.message)}</div>`;
    }
  }

  function renderModalDetails(comp, ver) {
    const meta = ver.metadata || {};
    const validationBox = `
      <div class="section-box">
        <div class="section-title">Package Validation</div>
        <p>Archive Package: <strong>${escapeHtml(ver.validation.package)}</strong></p>
        <p>Implementation (SV): <strong>${escapeHtml(ver.validation.implementation)}</strong></p>
        <p>Diagnostics: ${ver.validation.diagnostics.length === 0 ? "Clean (0 errors)" : escapeHtml(ver.validation.diagnostics.join(", "))}</p>
      </div>
    `;

    const functionalBox = `
      <div class="section-box">
        <div class="section-title">Supplied Functional Evidence</div>
        <p>Status: ${getStatusBadge(ver.functional_status)}</p>
        <p>Records Attached: <strong>${ver.evidence_count}</strong></p>
        <p style="font-size:0.75rem; color:#64748b; margin-top:0.25rem;">
          Note: This reflects supplied pipeline verification records, separate from online service execution.
        </p>
      </div>
    `;

    const versionList = (comp.versions || []).map(v => `
      <tr>
        <td>${escapeHtml(v.version)}</td>
        <td>${escapeHtml(v.package_sha256.substring(0, 16))}...</td>
        <td>${getStatusBadge(v.functional_status)}</td>
        <td><a href="${escapeHtml(v.download_url)}" class="btn btn-secondary" style="padding:0.2rem 0.5rem; font-size:0.75rem;" download>Download</a></td>
      </tr>
    `).join("");

    modalDetailsBody.innerHTML = `
      <table class="detail-meta-table">
        <tr><th>ID</th><td>${escapeHtml(ver.id)}</td></tr>
        <tr><th>VLNV</th><td>${escapeHtml(ver.vlnv)}</td></tr>
        <tr><th>Identity Key</th><td>${escapeHtml(ver.key)}</td></tr>
        <tr><th>Category</th><td>${escapeHtml(ver.category)}</td></tr>
        <tr><th>Package SHA-256</th><td>${escapeHtml(ver.package_sha256)}</td></tr>
        <tr><th>Package Size</th><td>${ver.package_size_bytes} bytes</td></tr>
        <tr><th>Summary</th><td>${escapeHtml(ver.summary)}</td></tr>
      </table>

      ${validationBox}
      ${functionalBox}

      <div class="section-box">
        <div class="section-title">All Versions</div>
        <table class="detail-meta-table" style="font-size:0.8rem;">
          <thead>
            <tr><th>Version</th><th>SHA-256</th><th>Evidence</th><th>Action</th></tr>
          </thead>
          <tbody>
            ${versionList}
          </tbody>
        </table>
      </div>

      <div class="modal-actions">
        <a href="${escapeHtml(ver.download_url)}" class="btn btn-primary" download>Download .spec Package</a>
      </div>
    `;
  }

  // Event Listeners
  elSearch.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      offset = 0;
      loadComponents();
    }, 300);
  });

  elCategory.addEventListener("change", () => {
    offset = 0;
    loadComponents();
  });

  elFunctionalStatus.addEventListener("change", () => {
    offset = 0;
    loadComponents();
  });

  elPrevPage.addEventListener("click", () => {
    if (offset >= limit) {
      offset -= limit;
      loadComponents();
    }
  });

  elNextPage.addEventListener("click", () => {
    if (offset + limit < total) {
      offset += limit;
      loadComponents();
    }
  });

  btnCloseDetails.addEventListener("click", () => modalDetails.close());

  btnUpload.addEventListener("click", () => {
    uploadFeedback.className = "feedback-box hidden";
    inputFile.value = "";
    modalUpload.showModal();
  });

  btnCloseUpload.addEventListener("click", () => modalUpload.close());
  btnCancelUpload.addEventListener("click", () => modalUpload.close());

  formUpload.addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = inputFile.files[0];
    if (!file) return;

    uploadFeedback.className = "feedback-box";
    uploadFeedback.textContent = "Uploading and validating package...";

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/spec-library/v1/uploads", {
        method: "POST",
        body: formData
      });

      const data = await res.json();
      if (res.status === 201) {
        uploadFeedback.className = "feedback-box success";
        uploadFeedback.textContent = `Successfully published ${data.version.id} version ${data.version.version}!`;
        setTimeout(() => {
          modalUpload.close();
          loadComponents();
        }, 1200);
      } else if (res.status === 200) {
        uploadFeedback.className = "feedback-box success";
        uploadFeedback.textContent = `Identical package already exists: ${data.version.id} version ${data.version.version}.`;
        setTimeout(() => {
          modalUpload.close();
          loadComponents();
        }, 1200);
      } else {
        const err = data.error || {};
        uploadFeedback.className = "feedback-box error";
        uploadFeedback.textContent = `Upload failed (${err.code || res.status}): ${err.message || "Unknown error"}`;
      }
    } catch (err) {
      uploadFeedback.className = "feedback-box error";
      uploadFeedback.textContent = `Upload error: ${err.message}`;
    }
  });

  // Global ESC handler
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (modalDetails.open) modalDetails.close();
      if (modalUpload.open) modalUpload.close();
    }
  });

  // Initialization
  checkHealth();
  loadCapabilities();
  loadComponents();
  setInterval(checkHealth, 15000);
})();

/* Py2ONTO Visual Editor - Frontend */

// ========================================================================
// Default sample data
// ========================================================================

const DEFAULT_DATA = {
  classes: [
    { parent_class: "Thing",  id: "Disease",  label: "Disease",  iri: "", comment: "A pathological condition of a living organism", definition: "" },
    { parent_class: "Thing",  id: "Drug",     label: "Drug",     iri: "", comment: "A pharmaceutical or therapeutic agent", definition: "" },
    { parent_class: "Drug",   id: "Aspirin",  label: "Aspirin",  iri: "", comment: "Acetylsalicylic acid — an analgesic, antipyretic, and anti-inflammatory drug", definition: "" },
  ],
  aps: [
    { id: "definition",    label: "definition",     comment: "The authoritative definition of an ontology term", domain: "Thing", range: "Thing", definition: "" },
    { id: "hasDbXref",    label: "has dbxref",     comment: "Database cross-reference to an external resource (e.g., SNOMED CT, MeSH, NCIT)", domain: "Thing", range: "Thing", definition: "" },
  ],
  ops: [
    { id: "treats",  label: "treats",  comment: "Relates a drug to the disease it is therapeutically indicated for", FunctionalProperty: "", InverseFunctionalProperty: "", TransitiveProperty: "", SymmetricProperty: "", AsymmetricProperty: "", ReflexiveProperty: "", IrreflexiveProperty: "", equivalent_to: "", subproperty_of: "", inverse_of: "", domain: "Drug", range: "Disease", disjoint_with: "", definition: "" },
  ],
  individuals: [
    { types: "Aspirin",  relation: "has_individual", id: "aspirin_01",  label: "Aspirin (instance)",  comment: "A specific formulation of acetylsalicylic acid 100 mg tablet", definition: "" },
  ],
};

// ========================================================================
// Column definitions per table
// ========================================================================

const TABLE_COLS = {
  classes:     ["parent_class", "id", "label", "iri", "comment", "definition"],
  aps:         ["id", "label", "comment", "domain", "range", "definition"],
  ops:         ["id", "label", "comment", "FunctionalProperty", "InverseFunctionalProperty", "TransitiveProperty", "SymmetricProperty", "AsymmetricProperty", "ReflexiveProperty", "IrreflexiveProperty", "equivalent_to", "subproperty_of", "inverse_of", "domain", "range", "disjoint_with", "definition"],
  individuals: ["types", "relation", "id", "label", "comment", "definition"],
};

// ========================================================================
// Extra columns tracking (for user-added columns)
// ========================================================================

const extraColumns = { classes: [], aps: [], ops: [], individuals: [] };

// Source tracking for classes (not a visible column but preserved in data)
let classSources = {};

// AI-extracted data cache (populated on successful extraction, nulled otherwise)
let aiExtractedData = null;

// Current system prompt cache (loaded from backend)
let currentSystemPrompt = "";

// Current task prompt cache (loaded from backend on page load)
let currentTaskPrompt = "";

// Provider → available models mapping
const PROVIDER_MODELS = {
  deepseek: [
    { value: "deepseek-chat", label: "DeepSeek-V3" },
    { value: "deepseek-reasoner", label: "DeepSeek-R1" },
  ],
  chatglm: [
    { value: "glm-4-flash", label: "GLM-4 Flash" },
    { value: "glm-4", label: "GLM-4" },
    { value: "glm-4-plus", label: "GLM-4 Plus (most capable)" },
  ],
  gemini: [
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash (recommended)" },
    { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro (complex ontologies)" },
  ],
};

// ========================================================================
// Class source badge refresh
// ========================================================================

function refreshClassBadges() {
  document.querySelectorAll("#tbody-classes tr").forEach(tr => {
    const source = tr.dataset.source || "local";
    // Remove existing badge (both ols and bioportal)
    const existing = tr.querySelector(".ols-badge, .bioportal-badge");
    if (existing) existing.remove();
    // Add badge for non-local sources
    if (source && source !== "local") {
      const labelCell = tr.querySelector("td:nth-child(4)");  // label is 4th td (sel, parent, id, label)
      if (labelCell) {
        const badge = document.createElement("span");
        badge.className = source === "BioPortal" ? "bioportal-badge" : "ols-badge";
        badge.textContent = source;
        labelCell.appendChild(badge);
      }
    }
  });
}

// ========================================================================
let toastTimer = null;

// ========================================================================
// Tab switching
// ========================================================================

document.getElementById("tabNav").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab");
  if (!btn) return;
  const tab = btn.dataset.tab;
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  btn.classList.add("active");
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  document.getElementById("panel-" + tab).classList.add("active");
});

// ========================================================================
// Table rendering
// ========================================================================

function renderTable(tableId, rows, cols) {
  const tbody = document.getElementById("tbody-" + tableId);
  const allCols = cols.concat(extraColumns[tableId]);
  tbody.innerHTML = rows.map((r, idx) => {
    // Determine source early so we can lock id/label for external classes
    let rowSource = "local";
    if (tableId === "classes") {
      rowSource = r.source || classSources[r.id] || "local";
      classSources[r.id || idx] = rowSource;
    }
    let cells = `<td class="csel"><input type="checkbox" class="row-sel"></td>`;
    allCols.forEach(c => {
      let extraAttrs = "";
      if ((tableId === "classes" && c === "parent_class") ||
          (tableId === "individuals" && c === "types") ||
          ((tableId === "aps" || tableId === "ops") && (c === "domain" || c === "range"))) {
        extraAttrs = ` list="class-suggestions" autocomplete="off"`;
      }
      // IRI is auto-managed — never manually editable
      if (tableId === "classes" && c === "iri") {
        extraAttrs += ' readonly';
      }
      // External classes (OLS, BioPortal, etc.) — id and label are locked
      if (tableId === "classes" && (c === "id" || c === "label") && rowSource !== "local" && rowSource !== "") {
        extraAttrs += ' readonly';
      }
      // Relation is fixed — always "has_individual", readonly
      if (tableId === "individuals" && c === "relation") {
        extraAttrs += ' readonly';
      }
      cells += `<td><input type="text" value="${esc(r[c] || "")}" data-col="${c}"${extraAttrs}></td>`;
    });
    // For classes, store source as data attribute and show badge on label
    let trAttrs = "";
    if (tableId === "classes") {
      trAttrs = ` data-source="${esc(rowSource)}"`;
      // Add source badge inside the label cell if source is not local
      if (rowSource !== "local" && rowSource !== "") {
        const badgeClass = rowSource === "BioPortal" ? "bioportal-badge" : "ols-badge";
        cells = cells.replace(
          /(<td><input type="text" value="[^"]*" data-col="label"[^>]*>)(<\/td>)/,
          `$1<span class="${badgeClass}">${esc(rowSource)}</span>$2`
        );
      }
    }
    return `<tr${trAttrs}>${cells}</tr>`;
  }).join("");
  // For classes, attach IRI auto-gen listeners after rendering
  if (tableId === "classes") {
    attachIRIListeners();
  }
}

function getTableData(tableId) {
  const rows = [];
  document.querySelectorAll("#tbody-" + tableId + " tr").forEach(tr => {
    const inputs = tr.querySelectorAll("td input[data-col]");
    const row = {};
    inputs.forEach(inp => { row[inp.dataset.col] = inp.value.trim(); });
    // Force relation to always be "has_individual" for individuals
    if (tableId === "individuals") {
      row.relation = "has_individual";
    }
    // Read source from tr data attribute (classes only)
    if (tableId === "classes") {
      row.source = tr.dataset.source || "local";
    }
    if (row.id || row.label) rows.push(row);
  });
  return rows;
}

function addRow(tableId) {
  const tbody = document.getElementById("tbody-" + tableId);
  const cols = TABLE_COLS[tableId].concat(extraColumns[tableId]);
  let cells = `<td class="csel"><input type="checkbox" class="row-sel"></td>`;
  cols.forEach(c => {
    let extraAttrs = "";
    let cellValue = "";
    if ((tableId === "classes" && c === "parent_class") ||
        (tableId === "individuals" && c === "types") ||
        ((tableId === "aps" || tableId === "ops") && (c === "domain" || c === "range"))) {
      extraAttrs = ` list="class-suggestions" autocomplete="off"`;
    }
    if (tableId === "classes" && c === "iri") {
      extraAttrs += ' readonly';
    }
    // Relation is fixed — always "has_individual", readonly
    if (tableId === "individuals" && c === "relation") {
      cellValue = "has_individual";
      extraAttrs += ' readonly';
    }
    cells += `<td><input type="text" value="${esc(cellValue)}" data-col="${c}"${extraAttrs}></td>`;
  });
  const tr = document.createElement("tr");
  tr.innerHTML = cells;
  // For classes, mark source on tr
  if (tableId === "classes") {
    tr.dataset.source = "local";
  }
  // Insert after the last checked row, or append at end if none checked
  const checkedBoxes = tbody.querySelectorAll(".row-sel:checked");
  if (checkedBoxes.length > 0) {
    const lastChecked = checkedBoxes[checkedBoxes.length - 1].closest("tr");
    lastChecked.insertAdjacentElement("afterend", tr);
  } else {
    tbody.appendChild(tr);
  }
  const firstInput = tr.querySelector("input[data-col]");
  if (firstInput) firstInput.focus();
  if (tableId === "classes") {
    attachIRIListeners();
  }
}

function deleteRow(tableId) {
  document.querySelectorAll("#tbody-" + tableId + " .row-sel:checked").forEach(cb => {
    cb.closest("tr").remove();
  });
}

function toggleAll(cb, tableId) {
  document.querySelectorAll("#tbody-" + tableId + " .row-sel").forEach(c => c.checked = cb.checked);
}

function addColumn(tableId) {
  const name = prompt("Column name. Prefix * for annotation property, $ for object property\n(Examples: *hasSynonym  |  $treats — fill cells with target class name):");
  if (!name || !name.trim()) return;
  const col = name.trim();
  if (TABLE_COLS[tableId].includes(col) || extraColumns[tableId].includes(col)) {
    showToast("Column '" + col + "' already exists in this table", "error");
    return;
  }

  // Add to tracking
  extraColumns[tableId].push(col);

  // Add <th> in thead (before the + cell)
  const th = document.createElement("th");
  th.className = "cadd-col";
  th.textContent = col;
  const headerRow = document.querySelector("#table-" + tableId + " thead tr");
  const addTh = headerRow.querySelector(".cadd");
  headerRow.insertBefore(th, addTh);

  // Add <td> to each existing row
  document.querySelectorAll("#tbody-" + tableId + " tr").forEach(tr => {
    const td = document.createElement("td");
    td.className = "cadd-col";
    td.innerHTML = `<input type="text" value="" data-col="${esc(col)}">`;
    const addTd = tr.querySelector(".cadd-col:last-child");
    tr.insertBefore(td, addTd ? addTd.nextSibling : null);
  });

  showToast("Column '" + col + "' added");
}

function deleteColumns(tableId) {
  const extras = extraColumns[tableId];
  if (extras.length === 0) { showToast("No custom columns to delete", "error"); return; }

  const colName = prompt(
    "Delete which custom column?\n\n  " + extras.join(", ") + "\n\nType the exact column name:"
  );
  if (!colName || !colName.trim()) return;

  const col = extras.find(c => c === colName.trim());
  if (!col) { showToast("Column '" + colName + "' not found. Available: " + extras.join(", "), "error"); return; }

  // Remove from tracking
  const idx = extras.indexOf(col);
  if (idx !== -1) extras.splice(idx, 1);
  // Remove <th>
  const ths = document.querySelectorAll("#table-" + tableId + " thead tr th");
  ths.forEach(th => { if (th.textContent === col) th.remove(); });
  // Remove <td> with data-col matching
  document.querySelectorAll("#tbody-" + tableId + " tr").forEach(tr => {
    tr.querySelectorAll("td input[data-col='" + esc(col) + "']").forEach(inp => inp.closest("td").remove());
  });

  showToast("Column '" + col + "' deleted");
}

// ========================================================================
// Class-name suggestions (autocomplete for parent_class / domain / range / types)
// ========================================================================

function updateClassSuggestions() {
  const datalist = document.getElementById("class-suggestions");
  if (!datalist) return;
  const classData = getTableData("classes");
  const ids = new Set();
  ids.add("Thing");  // owl:Thing is always a valid parent class
  classData.forEach(row => {
    if (row.id) ids.add(row.id);
  });
  datalist.innerHTML = "";
  ids.forEach(id => {
    const opt = document.createElement("option");
    opt.value = id;
    datalist.appendChild(opt);
  });
}

// ========================================================================
// IRI auto-generation for classes
// ========================================================================

function syncAllLocalClassIRIs() {
  /** Sync every local class's IRI to baseIRI + ID. External classes are never touched. */
  const tbody = document.getElementById("tbody-classes");
  if (!tbody) return;
  const baseIRI = document.getElementById("iriInput").value.trim();
  if (!baseIRI) return;
  tbody.querySelectorAll("tr").forEach(tr => {
    const source = tr.dataset.source || "local";
    if (source !== "local") return;
    const idInput = tr.querySelector("input[data-col='id']");
    const iriInput = tr.querySelector("input[data-col='iri']");
    if (!idInput || !iriInput) return;
    const id = idInput.value.trim();
    if (id) {
      iriInput.value = baseIRI + id;
    }
  });
}

function attachIRIListeners() {
  /** When a local class ID changes, auto-update its IRI to baseIRI + ID. */
  const tbody = document.getElementById("tbody-classes");
  if (!tbody) return;
  tbody.querySelectorAll("input[data-col='id']").forEach(input => {
    if (input.dataset.iriListenerAttached) return;
    input.dataset.iriListenerAttached = "true";
    input.addEventListener("input", () => {
      const tr = input.closest("tr");
      const source = tr.dataset.source || "local";
      if (source !== "local") return;
      const iriInput = tr.querySelector("input[data-col='iri']");
      if (!iriInput) return;
      const id = input.value.trim();
      const baseIRI = document.getElementById("iriInput").value.trim();
      if (id && baseIRI) {
        iriInput.value = baseIRI + id;
      }
    });
  });
}

// ========================================================================
// Ontology Class Search (OLS + BioPortal)
// ========================================================================

let searchResults = [];           // current displayed results (union of both sources)
let olsSearchResults = [];       // OLS-only results
let bioportalSearchResults = []; // BioPortal-only results
let currentSearchSource = "ols"; // "ols" or "bioportal"
let currentSearchPage = 1;
let totalSearchPages = 1;
let lastSearchQuery = "";

function onSearchSourceChange() {
  const source = document.querySelector("input[name='searchSource']:checked").value;
  currentSearchSource = source;
  // Show/hide ontology filter per source
  document.getElementById("bioportalOntologyFilter").style.display = source === "bioportal" ? "" : "none";
  document.getElementById("olsOntologyFilter").style.display = source === "ols" ? "" : "none";
  // Update placeholder text
  const input = document.getElementById("olsSearchInput");
  if (source === "bioportal") {
    input.placeholder = "Search BioPortal terms (e.g. diabetes, melanoma)...";
  } else {
    input.placeholder = "Search ontology terms (e.g. lung cancer, diabetes)...";
  }
  // Clear previous results
  olsSearchResults = [];
  bioportalSearchResults = [];
  searchResults = [];
  document.getElementById("tbody-ols-results").innerHTML = "";
  document.getElementById("table-ols-results").style.display = "none";
  document.getElementById("olsResultCount").textContent = "";
  document.getElementById("olsInsertBtn").style.display = "none";
  // Reset pagination
  currentSearchPage = 1;
  totalSearchPages = 1;
  document.getElementById("searchPagination").style.display = "none";
  // Update empty state text
  updateSearchEmptyText();
}

function updateSearchEmptyText() {
  const empty = document.getElementById("olsEmpty");
  if (currentSearchSource === "bioportal") {
    empty.textContent = "Search for standard ontology terms from BioPortal. Requires a valid API key in config.json.";
  } else {
    empty.textContent = "Search for standard ontology terms from OLS (Ontology Lookup Service).";
  }
}

function performSearch() {
  if (currentSearchSource === "bioportal") {
    performBioPortalSearch();
  } else {
    performOLSSearch();
  }
}

async function performOLSSearch(page) {
  if (page === undefined) page = 1;
  currentSearchPage = page;

  const q = document.getElementById("olsSearchInput").value.trim();
  if (!q || q.length < 2) { showToast("Enter at least 2 characters to search", "error"); return; }

  const btn = document.getElementById("olsSearchBtn");
  const table = document.getElementById("table-ols-results");
  const empty = document.getElementById("olsEmpty");
  const countLabel = document.getElementById("olsResultCount");
  const insertBtn = document.getElementById("olsInsertBtn");
  const pagination = document.getElementById("searchPagination");

  btn.disabled = true; btn.textContent = "Searching…";
  olsSearchResults = [];
  searchResults = [];
  document.getElementById("tbody-ols-results").innerHTML = "";

  // Build query URL with optional ontology filter (single ontology only) and page
  let olsUrl = "/api/ols-search?q=" + encodeURIComponent(q) + "&page=" + page;
  const olsOntology = document.getElementById("olsOntologyInput").value.trim();
  if (olsOntology) {
    olsUrl += "&ontologies=" + encodeURIComponent(olsOntology);
  }

  try {
    const resp = await fetch(olsUrl);
    const result = await resp.json();

    if (result.success) {
      if (result.results && result.results.length > 0) {
        olsSearchResults = result.results;
        searchResults = result.results;
        totalSearchPages = result.pageCount || 1;
        const total = result.numFound || result.results.length;
        const from = (currentSearchPage - 1) * 100 + 1;
        const to = Math.min(currentSearchPage * 100, total);
        countLabel.textContent = from + "–" + to + " of " + total + " results (OLS)";
        countLabel.style.color = "";
        table.style.display = "";
        empty.style.display = "none";
        insertBtn.style.display = "";
        renderSearchResultsTable(searchResults);
        updateSearchPaginationUI();
      } else {
        olsSearchResults = [];
        searchResults = [];
        totalSearchPages = 1;
        pagination.style.display = "none";
        countLabel.textContent = "0 results (OLS)";
        countLabel.style.color = "";
        table.style.display = "none";
        empty.style.display = "";
        empty.innerHTML = `<div class="ols-empty-msg">No results found for <strong>"${esc(q)}"</strong> in OLS.</div>`;
        insertBtn.style.display = "none";
      }
    } else {
      olsSearchResults = [];
      searchResults = [];
      totalSearchPages = 1;
      pagination.style.display = "none";
      countLabel.textContent = "";
      table.style.display = "none";
      empty.style.display = "";
      const errMsg = result.error || "Unknown error from OLS search";
      empty.innerHTML = `<div class="ols-error-msg">${esc(errMsg)}</div>`;
      insertBtn.style.display = "none";
      showToast(errMsg, "error");
    }
  } catch (err) {
    olsSearchResults = [];
    searchResults = [];
    totalSearchPages = 1;
    pagination.style.display = "none";
    countLabel.textContent = "";
    table.style.display = "none";
    empty.style.display = "";
    empty.innerHTML = `<div class="ols-error-msg">Cannot reach the Py2ONTO server. Is the backend running?</div>`;
    insertBtn.style.display = "none";
    showToast("Cannot connect to server — is the backend running?", "error");
  } finally {
    btn.disabled = false; btn.textContent = "Search";
  }
  lastSearchQuery = q;
}

async function performBioPortalSearch(page) {
  if (page === undefined) page = 1;
  currentSearchPage = page;

  const q = document.getElementById("olsSearchInput").value.trim();
  if (!q || q.length < 2) { showToast("Enter at least 2 characters to search", "error"); return; }

  const btn = document.getElementById("olsSearchBtn");
  const table = document.getElementById("table-ols-results");
  const empty = document.getElementById("olsEmpty");
  const countLabel = document.getElementById("olsResultCount");
  const insertBtn = document.getElementById("olsInsertBtn");
  const pagination = document.getElementById("searchPagination");

  btn.disabled = true; btn.textContent = "Searching…";
  bioportalSearchResults = [];
  searchResults = [];
  document.getElementById("tbody-ols-results").innerHTML = "";

  // Build query URL with pagination and optional ontology filter
  let url = "/api/bioportal-search?q=" + encodeURIComponent(q) + "&page=" + page;
  const ontologies = document.getElementById("bioportalOntologyInput").value.trim();
  if (ontologies) {
    url += "&ontologies=" + encodeURIComponent(ontologies);
  }

  try {
    const resp = await fetch(url);
    const result = await resp.json();

    if (result.success) {
      if (result.results && result.results.length > 0) {
        bioportalSearchResults = result.results;
        searchResults = result.results;
        totalSearchPages = result.pageCount || 1;
        currentSearchPage = result.page || page;
        const total = result.numFound || result.results.length;
        const from = (currentSearchPage - 1) * 100 + 1;
        const to = Math.min(currentSearchPage * 100, total);
        countLabel.textContent = from + "–" + to + " of " + total + " results (BioPortal)";
        countLabel.style.color = "";
        table.style.display = "";
        empty.style.display = "none";
        insertBtn.style.display = "";

        renderSearchResultsTable(searchResults);
        updateSearchPaginationUI();
      } else {
        bioportalSearchResults = [];
        searchResults = [];
        totalSearchPages = 1;
        pagination.style.display = "none";
        countLabel.textContent = "0 results (BioPortal)";
        countLabel.style.color = "";
        table.style.display = "none";
        empty.style.display = "";
        empty.innerHTML = `<div class="ols-empty-msg">No results found for <strong>"${esc(q)}"</strong> in BioPortal.</div>`;
        insertBtn.style.display = "none";
      }
    } else {
      bioportalSearchResults = [];
      searchResults = [];
      totalSearchPages = 1;
      pagination.style.display = "none";
      countLabel.textContent = "";
      table.style.display = "none";
      empty.style.display = "";
      const errMsg = result.error || "Unknown error from BioPortal search";
      empty.innerHTML = `<div class="ols-error-msg">${esc(errMsg)}</div>`;
      insertBtn.style.display = "none";
      showToast(errMsg, "error");
    }
  } catch (err) {
    bioportalSearchResults = [];
    searchResults = [];
    totalSearchPages = 1;
    pagination.style.display = "none";
    countLabel.textContent = "";
    table.style.display = "none";
    empty.style.display = "";
    empty.innerHTML = `<div class="ols-error-msg">Cannot reach the Py2ONTO server. Is the backend running?</div>`;
    insertBtn.style.display = "none";
    showToast("Cannot connect to server — is the backend running?", "error");
  } finally {
    btn.disabled = false; btn.textContent = "Search";
  }
  lastSearchQuery = q;
}

function renderSearchResultsTable(results) {
  const tbody = document.getElementById("tbody-ols-results");
  tbody.innerHTML = results.map((r, i) => `<tr>
    <td class="result-radio-cell"><input type="radio" name="search-select" value="${i}" onclick="document.getElementById('olsInsertBtn').style.display=''"></td>
    <td>${esc(r.id)}</td>
    <td>${esc(r.label)}</td>
    <td><span style="font-family:monospace;font-size:12px;">${esc(r.iri)}</span></td>
    <td>${esc(r.ontology)}</td>
  </tr>`).join("");
}

function searchPrevPage() {
  if (currentSearchPage > 1) {
    if (currentSearchSource === "bioportal") {
      performBioPortalSearch(currentSearchPage - 1);
    } else {
      performOLSSearch(currentSearchPage - 1);
    }
  }
}

function searchNextPage() {
  if (currentSearchPage < totalSearchPages) {
    if (currentSearchSource === "bioportal") {
      performBioPortalSearch(currentSearchPage + 1);
    } else {
      performOLSSearch(currentSearchPage + 1);
    }
  }
}

function updateSearchPaginationUI() {
  const pagination = document.getElementById("searchPagination");
  const prevBtn = document.getElementById("searchPrevBtn");
  const nextBtn = document.getElementById("searchNextBtn");
  const pageLabel = document.getElementById("searchPageLabel");
  if (totalSearchPages <= 1) {
    pagination.style.display = "none";
  } else {
    pagination.style.display = "";
    prevBtn.disabled = currentSearchPage <= 1;
    nextBtn.disabled = currentSearchPage >= totalSearchPages;
    pageLabel.textContent = "Page " + currentSearchPage + " / " + totalSearchPages;
  }
}

function insertSelectedSearchClass() {
  const selected = document.querySelector("input[name='search-select']:checked");
  if (!selected) { showToast("Please select a class first", "error"); return; }

  const r = searchResults[parseInt(selected.value)];
  if (!r) return;

  // Duplicate check — only block when the same (id, parent_class) or
  // (iri, parent_class) pair already exists.  Same ID/IRI with a
  // different parent_class represents multiple inheritance and is
  // intentionally allowed (the backend appends another is_a parent).
  const existing = getTableData("classes");
  const dupID = existing.find(row => row.id === r.id && (row.parent_class || "") === "");
  const dupIRI = existing.find(row => r.iri && row.iri === r.iri && (row.parent_class || "") === "");
  if (dupID || dupIRI) {
    showToast(
      "Class '" + r.id + "' already added with the same parent_class. " +
      "Set a different parent_class if you need multiple inheritance.",
      "error"
    );
    return;
  }

  const newRow = {
    parent_class: "",
    id: r.id,
    label: r.label,
    iri: r.iri,
    comment: "",
    definition: "",
  };
  // Track source
  const sourceLabel = currentSearchSource === "bioportal" ? "BioPortal" : "OLS";
  classSources[r.id] = sourceLabel;

  // Add row to table
  const tbody = document.getElementById("tbody-classes");
  const cols = TABLE_COLS.classes.concat(extraColumns.classes);
  let cells = `<td class="csel"><input type="checkbox" class="row-sel"></td>`;
  cols.forEach(c => {
    let extraAttrs = "";
    if (c === "parent_class") extraAttrs = ` list="class-suggestions" autocomplete="off"`;
    if (c === "iri") extraAttrs += ' readonly';
    // Lock id and label for externally-sourced classes
    if (c === "id" || c === "label") extraAttrs += ' readonly';
    cells += `<td><input type="text" value="${esc(newRow[c] || "")}" data-col="${c}"${extraAttrs}></td>`;
  });
  // Add source badge inside label cell
  const badgeClass = sourceLabel === "BioPortal" ? "bioportal-badge" : "ols-badge";
  cells = cells.replace(
    /(<td><input type="text" value="[^"]*" data-col="label"[^>]*>)(<\/td>)/,
    `$1<span class="${badgeClass}">${esc(sourceLabel)}</span>$2`
  );
  const tr = document.createElement("tr");
  tr.innerHTML = cells;
  tr.dataset.source = sourceLabel;
  tbody.appendChild(tr);
  attachIRIListeners();
  updateClassSuggestions();
  showToast("Inserted: " + r.id + " (" + r.label + ")");
}

function clearSearch() {
  document.getElementById("olsSearchInput").value = "";
  olsSearchResults = [];
  bioportalSearchResults = [];
  searchResults = [];
  currentSearchPage = 1;
  totalSearchPages = 1;
  lastSearchQuery = "";
  // Reset source radio to OLS
  document.querySelector("input[name='searchSource'][value='ols']").checked = true;
  currentSearchSource = "ols";
  document.getElementById("bioportalOntologyFilter").style.display = "none";
  document.getElementById("bioportalOntologyInput").value = "";
  document.getElementById("olsOntologyFilter").style.display = "";
  document.getElementById("olsOntologyInput").value = "";
  document.getElementById("olsSearchInput").placeholder = "Search ontology terms (e.g. lung cancer, diabetes)...";
  document.getElementById("tbody-ols-results").innerHTML = "";
  document.getElementById("table-ols-results").style.display = "none";
  document.getElementById("olsEmpty").style.display = "";
  updateSearchEmptyText();
  document.getElementById("olsResultCount").textContent = "";
  document.getElementById("olsInsertBtn").style.display = "none";
  document.getElementById("searchPagination").style.display = "none";
}

// CSV header → internal column name mapping for each table
const CSV_HEADER_MAP = {
  classes:      { "Parent_Class": "parent_class", "ID": "id", "label": "label", "IRI": "iri", "comment": "comment", "*definition": "definition" },
  aps:          { "ID": "id", "label": "label", "comment": "comment", "domain": "domain", "range": "range", "*definition": "definition" },
  ops:          { "ID": "id", "label": "label", "comment": "comment", "FunctionalProperty": "FunctionalProperty", "InverseFunctionalProperty": "InverseFunctionalProperty", "TransitiveProperty": "TransitiveProperty", "SymmetricProperty": "SymmetricProperty", "AsymmetricProperty": "AsymmetricProperty", "ReflexiveProperty": "ReflexiveProperty", "IrreflexiveProperty": "IrreflexiveProperty", "equivalent_to": "equivalent_to", "subproperty_of": "subproperty_of", "inverse_of": "inverse_of", "domain": "domain", "range": "range", "disjoint_with": "disjoint_with", "*definition": "definition" },
  individuals:  { "Types": "types", "relation": "relation", "ID": "id", "label": "label", "comment": "comment", "*definition": "definition" },
};

function uploadCSV(tableId) {
  document.getElementById("file-" + tableId).click();
}

function handleUpload(tableId, input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    const text = e.target.result;
    const lines = text.split(/\r?\n/).filter(line => line.trim());
    if (lines.length < 2) { showToast("CSV must have a header row and at least one data row", "error"); return; }

    // Parse CSV (simple: split on commas, handle quoted fields)
    function parseCSVLine(line) {
      const result = [];
      let cur = "";
      let inQuotes = false;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') { inQuotes = !inQuotes; }
        else if (ch === ',' && !inQuotes) { result.push(cur.trim()); cur = ""; }
        else { cur += ch; }
      }
      result.push(cur.trim());
      return result;
    }

    const headers = parseCSVLine(lines[0]);
    const dataLines = lines.slice(1).map(parseCSVLine);

    // Map CSV headers to internal column names
    const map = CSV_HEADER_MAP[tableId];
    const colIndices = {}; // internal col name → csv column index
    const extraCols = [];  // csv headers that don't map to known columns
    headers.forEach((h, i) => {
      const mapped = map[h];
      if (mapped) {
        colIndices[mapped] = i;
      } else if (h) {
        extraCols.push({ header: h, index: i });
      }
    });

    // Build rows
    const rows = [];
    const baseCols = TABLE_COLS[tableId];
    dataLines.forEach(tokens => {
      const row = {};
      baseCols.forEach(c => {
        const idx = colIndices[c];
        row[c] = idx !== undefined && idx < tokens.length ? tokens[idx] : "";
      });
      extraCols.forEach(ec => {
        row[ec.header] = ec.index < tokens.length ? tokens[ec.index] : "";
      });
      if (row.id || row.label || row.parent_class) rows.push(row);
    });

    // Add extra columns not in TABLE_COLS
    const headerRow = document.querySelector("#table-" + tableId + " thead tr");
    const addTh = headerRow.querySelector(".cadd");
    extraCols.forEach(ec => {
      if (!extraColumns[tableId].includes(ec.header)) {
        extraColumns[tableId].push(ec.header);
        // Add <th> before the + cell
        const th = document.createElement("th");
        th.className = "cadd-col";
        th.textContent = ec.header;
        headerRow.insertBefore(th, addTh);
      }
    });

    // Clear existing data and re-render
    renderTable(tableId, rows, TABLE_COLS[tableId]);

    // Track sources for classes
    if (tableId === "classes") {
      rows.forEach(r => {
        if (r.source && r.source !== "local" && r.id) {
          classSources[r.id] = r.source;
        }
      });
    }

    showToast("Uploaded " + rows.length + " rows from " + file.name);
    input.value = "";
  };
  reader.readAsText(file);
}

function downloadCSV(tableId) {
  const rows = getTableData(tableId);

  // Build reverse map: internal col name → CSV header
  const reverseMap = {};
  for (const [csvHeader, internal] of Object.entries(CSV_HEADER_MAP[tableId])) {
    reverseMap[internal] = csvHeader;
  }

  // Build ordered CSV headers from TABLE_COLS + extra columns
  const csvHeaders = TABLE_COLS[tableId].map(c => reverseMap[c] || c);
  extraColumns[tableId].forEach(c => { if (!csvHeaders.includes(c)) csvHeaders.push(c); });

  // Build CSV lines
  function toCSVLine(vals) {
    return vals.map(v => {
      const s = String(v);
      if (s.includes(",") || s.includes('"') || s.includes("\n")) {
        return '"' + s.replace(/"/g, '""') + '"';
      }
      return s;
    }).join(",");
  }

  const lines = [toCSVLine(csvHeaders)];
  if (rows.length > 0) {
    rows.forEach(row => {
      const vals = csvHeaders.map(h => {
        // Find internal col name for this header
        return row[CSV_HEADER_MAP[tableId][h] || h] || "";
      });
      lines.push(toCSVLine(vals));
    });
  }

  // Trigger download
  const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = tableId + "_template.csv";
  a.click();
  URL.revokeObjectURL(a.href);
  const suffix = rows.length === 0 ? " (empty template)" : "";
  showToast("Downloaded " + tableId + "_template.csv" + suffix);
}

// ========================================================================
// Tree rendering
// ========================================================================

function renderTree(treeData) {
  const root = document.getElementById("treeRoot");
  const placeholder = document.getElementById("treePlaceholder");

  if (!treeData || !treeData.class_tree || !treeData.class_tree.children || treeData.class_tree.children.length === 0) {
    root.style.display = "none";
    placeholder.style.display = "flex";
    document.getElementById("statsLabel").textContent = "—";
    return;
  }

  root.style.display = "block";
  placeholder.style.display = "none";

  // Render class tree
  let html = buildTreeHTML(treeData.class_tree);
  // Object properties
  if (treeData.object_properties && treeData.object_properties.length > 0) {
    html += `<div class="props-section"><h3>Object Properties</h3><ul class="prop-list">`;
    treeData.object_properties.forEach(op => {
      const detail = op.domain.join(", ") + " → " + op.range.join(", ");
      html += `<li class="prop-op" data-type="op" data-id="${esc(op.id || op.label)}">↦ ${op.label || op.id} <span class="op-detail">(${detail})</span></li>`;
    });
    html += `</ul></div>`;
  }
  // Annotation properties
  if (treeData.annotation_properties && treeData.annotation_properties.length > 0) {
    html += `<div class="props-section"><h3>Annotation Properties</h3><ul class="prop-list">`;
    treeData.annotation_properties.forEach(ap => {
      html += `<li class="prop-ap" data-type="ap" data-id="${esc(ap.id || ap.label)}">@ ${ap.label || ap.id}</li>`;
    });
    html += `</ul></div>`;
  }

  root.innerHTML = html;

  // Stats
  const nodeCounts = countNodes(treeData.class_tree);
  const opCount = treeData.object_properties ? treeData.object_properties.length : 0;
  const apCount = treeData.annotation_properties ? treeData.annotation_properties.length : 0;
  let statsStr = `${nodeCounts.classes} Classes`;
  if (nodeCounts.individuals > 0) statsStr += `, ${nodeCounts.individuals} Individuals`;
  statsStr += ` · ${opCount} Object Properties · ${apCount} Annotation Properties`;
  document.getElementById("statsLabel").textContent = statsStr;

  // Auto-expand root
  const rootToggle = root.querySelector(".tree-toggle");
  if (rootToggle) toggleTreeNode(rootToggle);

  // Attach click handlers: toggle + focus
  root.querySelectorAll(".tree-toggle").forEach(el => {
    el.addEventListener("click", (e) => {
      toggleTreeNode(el);
      focusEntity(el, "tree");
    });
  });
  root.querySelectorAll(".prop-op, .prop-ap").forEach(el => {
    el.addEventListener("click", () => focusEntity(el, "prop"));
  });
}

function focusEntity(el, kind) {
  let type, id;
  if (kind === "tree") {
    const span = el.querySelector(".node-class, .node-class-root, .node-individual");
    if (!span) return;
    type = span.classList.contains("node-individual") ? "individual" : "class";
    id = el.dataset.id;
  } else {
    type = el.dataset.type === "op" ? "ops" : "aps";
    id = el.dataset.id;
  }

  // Thing is the built-in root — don't try to find it in the tables
  if (id === "Thing") return;

  const tabId = type === "class" ? "classes" : type === "individual" ? "individuals" : type;
  const tableId = tabId;

  // Switch tab
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  document.querySelector(`.tab[data-tab="${tabId}"]`).classList.add("active");
  document.getElementById("panel-" + tabId).classList.add("active");

  // Find matching row and scroll
  const tbody = document.getElementById("tbody-" + tableId);
  let found = false;
  tbody.querySelectorAll("tr").forEach(tr => {
    const inputs = tr.querySelectorAll("input[data-col]");
    let rowId = "";
    inputs.forEach(inp => {
      if (inp.dataset.col === "id") rowId = inp.value.trim();
    });
    if (rowId === id) {
      tr.style.background = "var(--primary-subtle)";
      tr.scrollIntoView({ block: "center", behavior: "smooth" });
      setTimeout(() => { tr.style.background = ""; }, 2000);
      found = true;
    }
  });
  if (!found) showToast(`"${id}" not found in ${tabId} table`, "error");
}

function buildTreeHTML(node) {
  const hasChildren = node.children && node.children.length > 0;
  const nodeClass = node.type === "class_root" ? "node-class-root"
    : node.type === "individual" ? "node-individual"
    : "node-class";
  const src = node.source || "";
  const badgeInlineClass = src === "BioPortal" ? "bioportal-badge-inline" : "ols-badge-inline";
  const sourceBadge = (src && src !== "local")
    ? `<span class="${badgeInlineClass}">[${esc(src)}]</span>` : "";
  const arrow = hasChildren ? `<span class="arrow">▶</span>` : `<span class="arrow" style="visibility:hidden">▶</span>`;
  let html = `<ul class="tree-ul"><li class="tree-li">`;
  html += `<span class="tree-toggle" data-id="${esc(node.id)}">${arrow}<span class="${nodeClass}">${esc(node.label || node.id)}${sourceBadge}</span></span>`;
  if (hasChildren) {
    html += `<ul class="tree-ul" style="display:none;">`;
    node.children.forEach(c => { html += `<li class="tree-li">${buildTreeHTML(c)}</li>`; });
    html += `</ul>`;
  }
  html += `</li></ul>`;
  return html;
}

function toggleTreeNode(el) {
  const sub = el.parentElement.querySelector(":scope > .tree-ul");
  const arrow = el.querySelector(".arrow");
  if (sub) {
    if (sub.style.display === "none") {
      sub.style.display = "";
      if (arrow) arrow.classList.add("expanded");
    } else {
      sub.style.display = "none";
      if (arrow) arrow.classList.remove("expanded");
    }
  }
}

function countNodes(node) {
  let classCount = 0;
  let indCount = 0;

  function walk(n) {
    if (n.type === "class" || n.type === "class_root") classCount++;
    else if (n.type === "individual") indCount++;
    if (n.children) n.children.forEach(walk);
  }

  walk(node);
  return { classes: classCount, individuals: indCount };
}

// ========================================================================
// API calls
// ========================================================================

function getFullData() {
  return {
    iri: document.getElementById("iriInput").value.trim() || "http://example.com/onto.owl#",
    classes: getTableData("classes"),
    aps: getTableData("aps"),
    ops: getTableData("ops"),
    individuals: getTableData("individuals"),
  };
}

function validateClassesNoDuplicates() {
  /* Return true if no duplicate (id, parent_class) pairs exist in the classes table. */
  const rows = document.querySelectorAll("#tbody-classes tr");
  const seen = new Map();  // "id::parent_class" -> row index (1-based)
  for (let i = 0; i < rows.length; i++) {
    const tr = rows[i];
    const idInput = tr.querySelector("input[data-col='id']");
    const pcInput = tr.querySelector("input[data-col='parent_class']");
    const idVal = idInput ? idInput.value.trim() : "";
    const pcVal = pcInput ? pcInput.value.trim() : "";
    if (!idVal) continue;
    const key = idVal + "::" + pcVal;
    if (seen.has(key)) {
      showToast(
        "Duplicate class '" + idVal + "' with same parent_class at rows " +
        (seen.get(key) + 1) + " and " + (i + 1) + ". Please remove or change one.",
        "error"
      );
      return false;
    }
    seen.set(key, i);
  }
  return true;
}

async function buildPreview() {
  if (!validateClassesNoDuplicates()) return;
  const btn = document.getElementById("buildBtn");
  const placeholder = document.getElementById("treePlaceholder");
  btn.disabled = true; btn.textContent = "Building…";
  // Clear previous tree immediately so stale data is never shown
  const root = document.getElementById("treeRoot");
  root.innerHTML = "";
  root.style.display = "none";
  placeholder.style.display = "flex";
  placeholder.querySelector("p").innerHTML = "<em>Building ontology…</em>";
  document.getElementById("statsLabel").textContent = "Building…";

  const t0 = performance.now();
  try {
    const resp = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(getFullData()),
    });
    const result = await resp.json();
    if (result.success) {
      renderTree(result.tree);
      const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
      // Build a compact stats summary for the toast
      const t = result.tree;
      const nc = countNodes(t.class_tree);
      const nop = (t.object_properties || []).length;
      const nap = (t.annotation_properties || []).length;
      const parts = [nc.classes + " Classes"];
      if (nc.individuals > 0) parts.push(nc.individuals + " Individuals");
      if (nop > 0) parts.push(nop + " object properties");
      if (nap > 0) parts.push(nap + " annotation properties");
      showToast("Built " + parts.join(", ") + " in " + elapsed + "s", "success");
    } else {
      // style the placeholder as an error hint
      placeholder.querySelector("p").innerHTML =
        "<span style=\"color:var(--danger);\">Build failed</span><br><small>" +
        esc(result.error || "Unknown error") + "</small>";
      showToast(result.error || "Build failed — check table data for errors", "error");
    }
  } catch (err) {
    placeholder.querySelector("p").innerHTML =
      "<span style=\"color:var(--danger);\">Cannot reach server</span><br><small>" +
      esc(err.message) + "</small>";
    showToast("Cannot connect to server — is the backend running?", "error");
  } finally {
    btn.disabled = false; btn.textContent = "Build";
  }
}

async function generateOwl() {
  if (!validateClassesNoDuplicates()) return;
  const data = getFullData();

  // Ask for the output filename
  const filename = prompt("Ontology file name:", "new_onto.owl");
  if (!filename || !filename.trim()) return;
  const savePath = filename.trim();
  if (!savePath.endsWith(".owl")) showToast("Tip: filename should end with .owl", "info");

  const btn = document.getElementById("generateBtn");
  const placeholder = document.getElementById("treePlaceholder");
  btn.disabled = true;

  // Clear previous tree immediately so stale data is never shown
  const root = document.getElementById("treeRoot");
  root.innerHTML = "";
  root.style.display = "none";
  placeholder.style.display = "flex";
  placeholder.querySelector("p").innerHTML = "<em>Generating OWL file…</em>";
  document.getElementById("statsLabel").textContent = "Generating…";

  // Elapsed-time counter
  const t0 = performance.now();
  const timerId = setInterval(() => {
    const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
    btn.textContent = "Generating… " + elapsed + "s";
    document.getElementById("statsLabel").textContent = "Generating… " + elapsed + "s";
  }, 100);

  try {
    const payload = getFullData();
    payload.save_path = savePath;
    const resp = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await resp.json();
    clearInterval(timerId);

    if (result.success) {
      if (result.tree) renderTree(result.tree);

      const downloads = [];

      // Trigger browser download with the OWL content
      if (result.owl_content) {
        const blob = new Blob([result.owl_content], { type: "application/rdf+xml" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = result.filename || "ontology.owl";
        a.click();
        URL.revokeObjectURL(a.href);
        downloads.push("<strong>" + esc(result.filename || "ontology.owl") + "</strong>");
      }

      // Trigger browser download with the metadata report
      if (result.metadata_content) {
        const metaBlob = new Blob([result.metadata_content], { type: "text/plain;charset=utf-8" });
        const metaA = document.createElement("a");
        metaA.href = URL.createObjectURL(metaBlob);
        metaA.download = result.metadata_filename || "ontology.txt";
        metaA.click();
        URL.revokeObjectURL(metaA.href);
        downloads.push("<strong>" + esc(result.metadata_filename || "ontology.txt") + "</strong>");
      }

      const elapsed = ((performance.now() - t0) / 1000).toFixed(1);

      // Build stats summary
      let statsMsg = "";
      if (result.tree) {
        const t = result.tree;
        const nc = countNodes(t.class_tree);
        const nop = (t.object_properties || []).length;
        const nap = (t.annotation_properties || []).length;
        const parts = [nc.classes + " Classes"];
        if (nc.individuals > 0) parts.push(nc.individuals + " Individuals");
        if (nop > 0) parts.push(nop + " object properties");
        if (nap > 0) parts.push(nap + " annotation properties");
        statsMsg = parts.join(", ") + " · ";
      }

      const dlMsg = downloads.length > 0
        ? " Downloaded " + downloads.join(" + ")
        : "";

      showToast(statsMsg + "Saved in " + elapsed + "s" + dlMsg, "success");
    } else {
      placeholder.querySelector("p").innerHTML =
        "<span style=\"color:var(--danger);\">Generation failed</span><br><small>" +
        esc(result.error || "Unknown error") + "</small>";
      showToast(result.error || "Generation failed — check table data", "error");
    }
  } catch (err) {
    clearInterval(timerId);
    placeholder.querySelector("p").innerHTML =
      "<span style=\"color:var(--danger);\">Cannot reach server</span><br><small>" +
      esc(err.message) + "</small>";
    showToast("Cannot connect to server — is the backend running?", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate OWL";
  }
}

// ========================================================================
// Clear all
// ========================================================================

async function clearAll() {
  // Reset backend cache
  try { await fetch("/api/clear", { method: "POST" }); } catch (_) {}

  // Clear all table bodies
  ["classes", "aps", "ops", "individuals"].forEach(tid => {
    document.getElementById("tbody-" + tid).innerHTML = "";
    extraColumns[tid] = [];
    // Remove extra <th> elements (keep the + add-column cell)
    const theadRow = document.querySelector("#table-" + tid + " thead tr");
    if (theadRow) {
      theadRow.querySelectorAll(".cadd-col").forEach(th => th.remove());
    }
  });

  // Clear class sources
  classSources = {};

  // Reset tree view
  const root = document.getElementById("treeRoot");
  root.innerHTML = "";
  root.style.display = "none";
  const placeholder = document.getElementById("treePlaceholder");
  placeholder.style.display = "flex";
  placeholder.querySelector("p").innerHTML = "Edit tables and click <strong>Build</strong> to preview.";
  document.getElementById("statsLabel").textContent = "—";

  // Reset suggestion datalist
  updateClassSuggestions();

  showToast("All data cleared");
}

// ========================================================================
// Toast
// ========================================================================

function showToast(msg, type) {
  // type: "success" (default), "error", "info"
  const el = document.getElementById("toast");
  el.innerHTML = msg;  // allow inline HTML for bold filenames etc.
  el.className = "toast";
  if (type === "error") el.classList.add("toast-error");
  else if (type === "info") el.classList.add("toast-info");
  else el.classList.add("toast-success");
  el.classList.add("show");
  clearTimeout(toastTimer);
  const duration = type === "error" ? 5000 : 3500;
  toastTimer = setTimeout(() => el.classList.remove("show"), duration);
}

// ========================================================================
// Helpers
// ========================================================================

function esc(s) {
  if (!s) return "";
  return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;")
    .replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ========================================================================
// Cell edit overlay — double-click any input to edit in a large textarea
// ========================================================================

let _editOverlayTarget = null;

function _isDollarCol(input) {
  const col = input.dataset.col || "";
  return col.startsWith("$");
}

function _populateEditOverlayPicker(currentVal) {
  const selected = new Set(
    currentVal ? currentVal.split("&").map(s => s.trim()).filter(Boolean) : []
  );
  const classData = getTableData("classes");
  const uniqueIds = [...new Set(classData.map(r => r.id).filter(Boolean))].sort();
  const list = document.getElementById("editOverlayPickerList");
  list.innerHTML = uniqueIds.map(id => {
    const isChecked = selected.has(id);
    return `<label class="class-picker-item${isChecked ? " checked" : ""}">
      <input type="checkbox" value="${esc(id)}"${isChecked ? " checked" : ""}>
      ${esc(id)}
    </label>`;
  }).join("");
  list.querySelectorAll(".class-picker-item").forEach(label => {
    label.addEventListener("click", (e) => {
      if (e.target.tagName === "INPUT") return;
      const cb = label.querySelector("input[type='checkbox']");
      cb.checked = !cb.checked;
      label.classList.toggle("checked", cb.checked);
      _syncTextareaFromPicker();
    });
    const cb = label.querySelector("input[type='checkbox']");
    cb.addEventListener("change", () => {
      label.classList.toggle("checked", cb.checked);
      _syncTextareaFromPicker();
    });
  });
}

function _syncTextareaFromPicker() {
  const checked = document.querySelectorAll("#editOverlayPickerList input[type='checkbox']:checked");
  const names = Array.from(checked).map(cb => cb.value);
  document.getElementById("editOverlayTextarea").value = names.join("&");
}

function _syncPickerFromTextarea() {
  const val = document.getElementById("editOverlayTextarea").value.trim();
  const selected = new Set(val ? val.split("&").map(s => s.trim()).filter(Boolean) : []);
  document.querySelectorAll("#editOverlayPickerList input[type='checkbox']").forEach(cb => {
    cb.checked = selected.has(cb.value);
    cb.closest(".class-picker-item").classList.toggle("checked", cb.checked);
  });
}

function openEditOverlay(input) {
  _editOverlayTarget = input;
  const col = input.dataset.col || "";
  const isDollar = _isDollarCol(input);

  // Build title: "Edit · $hasSymptom (CrohnsDisease)"
  let title = "Edit · " + col;
  const tr = input.closest("tr");
  if (tr) {
    const idInput = tr.querySelector("input[data-col='id']");
    if (idInput && idInput.value.trim()) {
      title += " (" + idInput.value.trim() + ")";
    }
  }
  document.getElementById("editOverlayTitle").textContent = title;
  const ta = document.getElementById("editOverlayTextarea");
  ta.value = input.value;
  ta.readOnly = input.hasAttribute("readonly");
  document.getElementById("editOverlayApplyBtn").style.display = ta.readOnly ? "none" : "";

  const picker = document.getElementById("editOverlayPicker");
  if (isDollar && !ta.readOnly) {
    picker.style.display = "";
    _populateEditOverlayPicker(input.value.trim());
  } else {
    picker.style.display = "none";
  }

  document.getElementById("editOverlay").style.display = "flex";
  setTimeout(() => { ta.focus(); ta.select(); }, 50);
}

function closeEditOverlay() {
  document.getElementById("editOverlay").style.display = "none";
  document.getElementById("editOverlayPicker").style.display = "none";
  _editOverlayTarget = null;
}

function applyEditOverlay() {
  if (!_editOverlayTarget) return;
  if (!_editOverlayTarget.hasAttribute("readonly")) {
    _editOverlayTarget.value = document.getElementById("editOverlayTextarea").value;
    _editOverlayTarget.dispatchEvent(new Event("input", { bubbles: true }));
  }
  closeEditOverlay();
}

document.getElementById("editOverlayTextarea").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    applyEditOverlay();
  } else if (e.key === "Escape") {
    closeEditOverlay();
  }
});

// When editing a $ column, sync checkboxes as user types in the textarea
document.getElementById("editOverlayTextarea").addEventListener("input", () => {
  if (_editOverlayTarget && _isDollarCol(_editOverlayTarget)) {
    _syncPickerFromTextarea();
  }
});

function toggleEditOverlayPicker(checked) {
  document.querySelectorAll("#editOverlayPickerList input[type='checkbox']").forEach(cb => {
    cb.checked = checked;
    cb.closest(".class-picker-item").classList.toggle("checked", checked);
  });
  _syncTextareaFromPicker();
}

document.getElementById("editOverlayApplyBtn").addEventListener("click", applyEditOverlay);

// Dblclick delegation — fire on any td input in the left panel
document.querySelector(".panel-left").addEventListener("dblclick", (e) => {
  const input = e.target.closest("td input[data-col]");
  if (!input) return;
  openEditOverlay(input);
});


// ========================================================================
// Init
// ========================================================================

renderTable("classes", DEFAULT_DATA.classes, TABLE_COLS.classes);
renderTable("aps", DEFAULT_DATA.aps, TABLE_COLS.aps);
renderTable("ops", DEFAULT_DATA.ops, TABLE_COLS.ops);
renderTable("individuals", DEFAULT_DATA.individuals, TABLE_COLS.individuals);

// Auto-generate IRI values for default local classes
syncAllLocalClassIRIs();

// When the user changes the base ontology IRI, re-sync all local class IRIs
document.getElementById("iriInput").addEventListener("input", syncAllLocalClassIRIs);

// Populate class-name suggestions from initial data
updateClassSuggestions();

// Refresh suggestions whenever a class ID is edited
document.getElementById("tbody-classes").addEventListener("input", (e) => {
  if (e.target.dataset.col === "id") updateClassSuggestions();
});

// Check for duplicate (id, parent_class) pairs when user finishes editing
document.getElementById("tbody-classes").addEventListener("focusout", (e) => {
  const col = e.target.dataset.col;
  if (col !== "id" && col !== "parent_class") return;
  const rows = document.querySelectorAll("#tbody-classes tr");
  const seen = new Map();  // "id::parent_class" -> row index (1-based)
  let dupFound = false;
  rows.forEach((tr, i) => {
    const idInput = tr.querySelector("input[data-col='id']");
    const pcInput = tr.querySelector("input[data-col='parent_class']");
    const idVal = idInput ? idInput.value.trim() : "";
    const pcVal = pcInput ? pcInput.value.trim() : "";
    if (!idVal) return;
    const key = idVal + "::" + pcVal;
    if (seen.has(key)) {
      if (!dupFound) {
        showToast("Duplicate class: " + idVal + " (same parent_class) at rows " + (seen.get(key) + 1) + " and " + (i + 1), "error");
        dupFound = true;
      }
    } else {
      seen.set(key, i);
    }
  });
});

// Refresh suggestions after row operations on the classes table
const origAddRow = addRow;
addRow = function(tableId) {
  origAddRow(tableId);
  if (tableId === "classes") updateClassSuggestions();
};

const origDeleteRow = deleteRow;
deleteRow = function(tableId) {
  origDeleteRow(tableId);
  if (tableId === "classes") updateClassSuggestions();
};

// Refresh suggestions after CSV upload for classes
const origHandleUpload = handleUpload;
handleUpload = function(tableId, input) {
  origHandleUpload(tableId, input);
  if (tableId === "classes") {
    // CSV upload is async via FileReader; update after a short delay
    const checkDone = setInterval(() => {
      updateClassSuggestions();
      clearInterval(checkDone);
    }, 200);
  }
};

// ========================================================================
// AI Extraction
// ========================================================================

function renderTableRows(tableId, rows, cols) {
  /* Append rows to an existing table body (used by Merge mode). */
  const tbody = document.getElementById("tbody-" + tableId);
  const allCols = cols.concat(extraColumns[tableId]);
  const html = rows.map(r => {
    // Determine source early so we can lock id/label for external classes
    let rowSource = "local";
    if (tableId === "classes") {
      rowSource = r.source || "local";
    }
    let cells = `<td class="csel"><input type="checkbox" class="row-sel"></td>`;
    allCols.forEach(c => {
      let extraAttrs = "";
      if ((tableId === "classes" && c === "parent_class") ||
          (tableId === "individuals" && c === "types") ||
          ((tableId === "aps" || tableId === "ops") && (c === "domain" || c === "range"))) {
        extraAttrs = ` list="class-suggestions" autocomplete="off"`;
      }
      if (tableId === "classes" && c === "iri") {
        extraAttrs += ' readonly';
      }
      // External classes (OLS, BioPortal, etc.) — id and label are locked
      if (tableId === "classes" && (c === "id" || c === "label") && rowSource !== "local" && rowSource !== "") {
        extraAttrs += ' readonly';
      }
      // Relation is fixed — always "has_individual", readonly
      if (tableId === "individuals" && c === "relation") {
        extraAttrs += ' readonly';
      }
      cells += `<td><input type="text" value="${esc(r[c] || "")}" data-col="${c}"${extraAttrs}></td>`;
    });
    let trAttrs = "";
    if (tableId === "classes") {
      trAttrs = ` data-source="${esc(rowSource)}"`;
      if (rowSource !== "local" && rowSource !== "") {
        const badgeClass = rowSource === "BioPortal" ? "bioportal-badge" : "ols-badge";
        cells = cells.replace(
          /(<td><input type="text" value="[^"]*" data-col="label"[^>]*>)(<\/td>)/,
          `$1<span class="${badgeClass}">${esc(rowSource)}</span>$2`
        );
      }
    }
    return `<tr${trAttrs}>${cells}</tr>`;
  }).join("");
  tbody.insertAdjacentHTML("beforeend", html);
  if (tableId === "classes") attachIRIListeners();
}

async function onProviderChange() {
  const provider = document.getElementById("aiProviderSelect").value;
  const modelSelect = document.getElementById("aiModelSelect");

  if (provider === "ollama") {
    modelSelect.innerHTML = '<option value="">Loading models...</option>';
    try {
      const resp = await fetch("/api/ollama-models");
      const data = await resp.json();
      if (data.success && data.models.length > 0) {
        modelSelect.innerHTML = data.models.map(m =>
          `<option value="${m}">${m}</option>`
        ).join("");
      } else {
        modelSelect.innerHTML = `<option value="">${data.error || "No models found. Run: ollama pull &lt;model&gt;"}</option>`;
      }
    } catch (e) {
      modelSelect.innerHTML = '<option value="">Cannot connect to Ollama (is it running?)</option>';
    }
  } else {
    const models = PROVIDER_MODELS[provider] || [];
    modelSelect.innerHTML = models.map(m =>
      `<option value="${m.value}">${m.label}</option>`
    ).join("");
  }
}

async function runAiExtraction() {
  const text = document.getElementById("aiInputText").value.trim();
  if (!text) { showToast("Please enter a domain description first", "error"); return; }

  const provider = document.getElementById("aiProviderSelect").value;
  const model = document.getElementById("aiModelSelect").value;
  const btn = document.getElementById("aiExtractBtn");
  const spinner = document.getElementById("aiSpinner");
  const warningsDiv = document.getElementById("aiWarnings");
  const resultDiv = document.getElementById("aiResult");

  btn.disabled = true;
  spinner.style.display = "inline";
  warningsDiv.style.display = "none";
  resultDiv.style.display = "none";
  const alignBtn = document.getElementById("alignTermsBtn");
  if (alignBtn) alignBtn.style.display = "none";
  aiExtractedData = null;

  try {
    const payload = { text: text, provider: provider, model: model };
    // Include task prompt (per-extraction instructions, appended to system prompt)
    if (currentTaskPrompt) {
      payload.task_prompt = currentTaskPrompt;
    }
    // Use system prompt from modal editor if customised
    const editorText = document.getElementById("systemPromptEditorText").value;
    if (editorText && editorText.trim()) {
      payload.system_prompt = editorText.trim();
    }
    const resp = await fetch("/api/ai-extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await resp.json();
    if (result.success) {
      aiExtractedData = result.data;
      // Build summary
      const nClasses = (result.data.classes || []).length;
      const nAps = (result.data.aps || []).length;
      const nOps = (result.data.ops || []).length;
      const nInds = (result.data.individuals || []).length;
      const parts = [];
      if (nClasses > 0) parts.push(nClasses + " Classes");
      if (nAps > 0) parts.push(nAps + " annotation properties");
      if (nOps > 0) parts.push(nOps + " object properties");
      if (nInds > 0) parts.push(nInds + " Individuals");
      const summaryText = parts.length > 0
        ? "Extracted: " + parts.join(", ") + ". Review and click Populate Tables."
        : "No ontology elements extracted. Try a more detailed description.";
      document.getElementById("aiResultSummary").textContent = summaryText;
      resultDiv.style.display = "block";

      if (result.warnings && result.warnings.length > 0) {
        warningsDiv.innerHTML = "<strong>⚠ Warnings:</strong><ul style=\"margin:4px 0 0 16px; padding:0;\">"
          + result.warnings.map(w => "<li>" + esc(w) + "</li>").join("")
          + "</ul>";
        warningsDiv.style.display = "block";
      }
      if (parts.length > 0) {
        showToast("Extraction complete — click Populate Tables or Map to Ontology Terms");
        // Show mapping button
        const alignBtn = document.getElementById("alignTermsBtn");
        if (alignBtn) alignBtn.style.display = "";
      } else {
        showToast("No ontology elements extracted", "error");
      }
    } else {
      showToast(result.error || "AI extraction failed", "error");
    }
  } catch (err) {
    showToast("Network error: " + err.message, "error");
  } finally {
    btn.disabled = false;
    spinner.style.display = "none";
  }
}

function populateTables() {
  if (!aiExtractedData) { showToast("No extracted data to populate. Run extraction first.", "error"); return; }

  const mode = document.querySelector("input[name='aiMode']:checked")?.value || "merge";
  const d = aiExtractedData;

  function pop(tableId, rows, baseCols) {
    if (!rows || rows.length === 0) return 0;
    if (mode === "replace") {
      document.getElementById("tbody-" + tableId).innerHTML = "";
      extraColumns[tableId] = [];
      const theadRow = document.querySelector("#table-" + tableId + " thead tr");
      if (theadRow) {
        theadRow.querySelectorAll(".cadd-col").forEach(th => th.remove());
      }
    }

    // ---- deduplicate: collect existing (id, parent_class) keys ----
    // For classes, two rows with the same ID but different parent_class
    // represent multiple inheritance and are NOT duplicates.
    let existingKeys = new Set();
    if (mode === "merge") {
      const tbody = document.getElementById("tbody-" + tableId);
      const isClassTable = tableId === "classes";
      tbody.querySelectorAll("tr").forEach(tr => {
        const idInput = tr.querySelector("input[data-col='id']");
        if (idInput) {
          const val = idInput.value.trim();
          if (val) {
            if (isClassTable) {
              const pcInput = tr.querySelector("input[data-col='parent_class']");
              existingKeys.add(val + "::" + (pcInput ? pcInput.value.trim() : ""));
            } else {
              existingKeys.add(val);
            }
          }
        }
      });
    }

    const seen = new Set();
    const isClassTable = tableId === "classes";
    const filteredRows = [];
    let skipped = 0;
    rows.forEach(row => {
      const rid = (row.id || "").trim();
      if (!rid) {
        // Rows without an ID cannot be deduplicated — keep them
        filteredRows.push(row);
        return;
      }
      const key = isClassTable ? rid + "::" + ((row.parent_class || "").trim()) : rid;
      if (existingKeys.has(key) || seen.has(key)) {
        skipped++;
        return;
      }
      seen.add(key);
      filteredRows.push(row);
    });

    if (skipped > 0) {
      showToast("Skipped " + skipped + " duplicate(s) in " + tableId + " (same ID and parent_class)");
    }

    // Detect extra columns from the extracted data that are not in baseCols.
    // Skip "source" — it is tracked via data-source on <tr>, not a visible column.
    const existingCols = new Set(baseCols);
    existingCols.add("source");
    const newExtraCols = [];
    filteredRows.forEach(row => {
      Object.keys(row).forEach(k => {
        if (!existingCols.has(k) && !newExtraCols.includes(k)) {
          newExtraCols.push(k);
        }
      });
    });
    // Add headers for new extra columns
    newExtraCols.forEach(col => {
      if (!extraColumns[tableId].includes(col)) {
        extraColumns[tableId].push(col);
        const headerRow = document.querySelector("#table-" + tableId + " thead tr");
        const addTh = headerRow.querySelector(".cadd");
        if (addTh) {
          const th = document.createElement("th");
          th.className = "cadd-col";
          th.textContent = col;
          headerRow.insertBefore(th, addTh);
        }
      }
    });
    if (mode === "merge") {
      renderTableRows(tableId, filteredRows, baseCols);
    } else {
      renderTable(tableId, filteredRows, baseCols);
    }
    return filteredRows.length;
  }

  const cCount = pop("classes", d.classes, TABLE_COLS.classes);
  const aCount = pop("aps", d.aps, TABLE_COLS.aps);
  const oCount = pop("ops", d.ops, TABLE_COLS.ops);
  const iCount = pop("individuals", d.individuals, TABLE_COLS.individuals);

  // Sync OP domain/range → $ columns on Classes table (so relationships are
  // visible in the editor, not just in the generated OWL file).
  if (d.ops && d.ops.length > 0) {
    syncOpsToClassColumns(d.ops);
  }

  // Update source tracking for newly inserted classes
  if (d.classes) {
    d.classes.forEach(cls => {
      if (cls.id && cls.source && cls.source !== "local") {
        classSources[cls.id] = cls.source;
      }
    });
  }
  // Refresh badges after population
  refreshClassBadges();
  syncAllLocalClassIRIs();  // sync IRI to toolbar baseIRI for all local classes
  attachIRIListeners();
  updateClassSuggestions();

  const parts = [];
  if (cCount > 0) parts.push(cCount + " Classes");
  if (aCount > 0) parts.push(aCount + " annotation properties");
  if (oCount > 0) parts.push(oCount + " object properties");
  if (iCount > 0) parts.push(iCount + " Individuals");
  showToast("Populated: " + (parts.join(", ") || "nothing"));

  // Auto-switch to Classes tab so the user sees the result immediately
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  const classesTab = document.querySelector(".tab[data-tab='classes']");
  if (classesTab) classesTab.classList.add("active");
  const classesPanel = document.getElementById("panel-classes");
  if (classesPanel) classesPanel.classList.add("active");
}

// ========================================================================
// Sync OP domain/range to Classes table as $ columns
// ========================================================================

function syncOpsToClassColumns(ops) {
  /* For every object property that has both domain and range defined,
     add a "$<opId>" extra column to the Classes table and fill the
     range value on rows whose class ID matches the domain.  This makes
     the OP→class relationship visible and editable in the editor, not
     just in the generated OWL file. */
  if (!ops || ops.length === 0) return;

  ops.forEach(op => {
    const opId = (op.id || "").trim();
    const domainRaw = (op.domain || "").trim();
    const rangeRaw = (op.range || "").trim();

    // Need at least an OP id, a domain, and a range to create the column
    if (!opId || !domainRaw || !rangeRaw) return;

    const colName = "$" + opId;

    // Skip if this $ column already exists on the classes table
    if (extraColumns.classes.includes(colName)) return;

    // Split comma-separated domains / ranges
    const domains = domainRaw.split(",").map(s => s.trim()).filter(Boolean);
    if (domains.length === 0) return;

    // ---- Add column header ----
    extraColumns.classes.push(colName);
    const headerRow = document.querySelector("#table-classes thead tr");
    const addTh = headerRow ? headerRow.querySelector(".cadd") : null;
    if (addTh) {
      const th = document.createElement("th");
      th.className = "cadd-col";
      th.textContent = colName;
      headerRow.insertBefore(th, addTh);
    }

    // ---- Add cell to every class row ----
    document.querySelectorAll("#tbody-classes tr").forEach(tr => {
      const td = document.createElement("td");
      td.className = "cadd-col";

      const idInput = tr.querySelector("input[data-col='id']");
      const classId = idInput ? idInput.value.trim() : "";

      // Fill the range value only when this class is in the domain list.
      // Thing is the universal root — it never gets OP values filled.
      const cellValue = (classId !== "Thing" && domains.includes(classId))
        ? rangeRaw
        : "";

      td.innerHTML = `<input type="text" value="${esc(cellValue)}" data-col="${esc(colName)}">`;

      // Insert before the trailing "+" column cell
      const addTd = tr.querySelector(".cadd-col:last-child");
      tr.insertBefore(td, addTd ? addTd.nextSibling : null);
    });
  });
}

// ========================================================================
// Ontology Term Mapping
// ========================================================================

function showAlignmentModal(extractedData) {
  const modal = document.getElementById("alignModal");
  const classListEl = document.getElementById("alignClassList");
  const rightHeader = document.getElementById("alignRightHeader");
  const rightTable = document.getElementById("alignRightTable");
  const insertBtn = document.getElementById("alignInsertBtn");
  const statusEl = document.getElementById("alignStatus");
  const beginBtn = document.getElementById("alignBeginBtn");

  // Initialize source state — defaults to OLS
  window._alignSource = "ols";
  window._alignSearchDone = false;
  window._alignPageInfo = {};  // { [i]: { ols: {page,totalPages,query,ontology}, bioportal: {...} } }
  const olsRadio = document.querySelector("input[name='alignSource'][value='ols']");
  if (olsRadio) olsRadio.checked = true;
  // Reset ontology filter inputs and show OLS filter by default
  document.getElementById("alignOlsOntologyFilter").style.display = "";
  document.getElementById("alignOlsOntologyInput").value = "";
  document.getElementById("alignBioportalOntologyFilter").style.display = "none";
  document.getElementById("alignBioportalOntologyInput").value = "";

  modal.style.display = "flex";
  classListEl.innerHTML = `<div style="text-align:center;color:var(--text-muted);padding:40px 12px;font-size:12px;">Select a source and click <strong>Begin Search</strong></div>`;
  rightHeader.textContent = "Select a class from the left";
  rightTable.innerHTML = `<div class="align-right-placeholder">← Pick a source above and click <strong>Begin Search</strong>, then select a class on the left to view candidates.</div>`;
  if (beginBtn) { beginBtn.style.display = ""; beginBtn.disabled = false; beginBtn.textContent = "Begin Search"; }
  insertBtn.disabled = true;
  statusEl.textContent = "";

  const classes = extractedData.classes || [];
  if (classes.length === 0) {
    classListEl.innerHTML = `<div style="text-align:center;color:var(--text-muted);padding:40px 12px;font-size:12px;">No classes to align.</div>`;
    insertBtn.disabled = false;
    if (beginBtn) beginBtn.style.display = "none";
    statusEl.textContent = "";
    return;
  }

  // Build left class list (no search yet — just show class labels with pending badges)
  classListEl.innerHTML = classes.map((cls, i) => {
    const label = esc(cls.label || cls.id);
    return `<div class="align-class-item" data-index="${i}" onclick="selectAlignClass(${i})">
      <span class="aci-label">${label}</span>
      <span class="aci-badge pending">pending</span>
    </div>`;
  }).join("");

  // Initialize empty align data (results will be filled by beginAlignmentSearch)
  const alignData = classes.map(cls => ({
    extracted: cls,
    olsResults: null,
    bioportalResults: null,
  }));

  // Track selections — one per class (source-agnostic in "all" mode, per-source otherwise)
  window._alignSelections = {};
  alignData.forEach((_, i) => {
    window._alignSelections[i] = "local";
  });

  window._alignData = alignData;
  window._alignCurrentIndex = -1;
}

async function beginAlignmentSearch() {
  const sourceEl = document.querySelector("input[name='alignSource']:checked");
  if (!sourceEl) return;
  const source = sourceEl.value;
  window._alignSource = source;

  const alignData = window._alignData;
  if (!alignData || alignData.length === 0) return;

  const beginBtn = document.getElementById("alignBeginBtn");
  const classListEl = document.getElementById("alignClassList");
  const statusEl = document.getElementById("alignStatus");
  const insertBtn = document.getElementById("alignInsertBtn");

  if (beginBtn) { beginBtn.disabled = true; beginBtn.textContent = "Searching…"; }
  statusEl.textContent = "Searching " + (source === "all" ? "OLS + BioPortal" : source === "ols" ? "OLS" : "BioPortal") + "…";

  // Determine which sources to search
  const searchOls = (source === "ols" || source === "all");
  const searchBio = (source === "bioportal" || source === "all");

  // Read ontology filters
  const olsOntology = document.getElementById("alignOlsOntologyInput").value.trim();
  const bioOntology = document.getElementById("alignBioportalOntologyInput").value.trim();

  // Search all classes against the selected source(s)
  const searchPromises = alignData.map(async (item, i) => {
    const label = item.extracted.label || item.extracted.id;

    if (searchOls) {
      try {
        let olsUrl = "/api/ols-search?q=" + encodeURIComponent(label) + "&page=1";
        if (olsOntology) olsUrl += "&ontologies=" + encodeURIComponent(olsOntology);
        const resp = await fetch(olsUrl);
        const result = await resp.json();
        item.olsResults = result.success ? (result.results || []) : [];
        // Store pagination info for this class + source
        if (!window._alignPageInfo[i]) window._alignPageInfo[i] = {};
        window._alignPageInfo[i].ols = {
          page: result.page || 1,
          totalPages: result.pageCount || 1,
          query: label,
          ontology: olsOntology,
        };
      } catch (_) { item.olsResults = []; }
    }

    if (searchBio) {
      try {
        let bioUrl = "/api/bioportal-search?q=" + encodeURIComponent(label) + "&page=1";
        if (bioOntology) bioUrl += "&ontologies=" + encodeURIComponent(bioOntology);
        const resp = await fetch(bioUrl);
        const result = await resp.json();
        item.bioportalResults = result.success ? (result.results || []) : [];
        // Store pagination info for this class + source
        if (!window._alignPageInfo[i]) window._alignPageInfo[i] = {};
        window._alignPageInfo[i].bioportal = {
          page: result.page || 1,
          totalPages: result.pageCount || 1,
          query: label,
          ontology: bioOntology,
        };
      } catch (_) { item.bioportalResults = []; }
    }
  });
  await Promise.all(searchPromises);

  window._alignSearchDone = true;

  // Build right-panel candidate tables
  const baseIRI = document.getElementById("iriInput").value.trim();
  const rightTable = document.getElementById("alignRightTable");

  function buildCandidateTable(item, i, sourceKey, sourceDisplay) {
    const cls = item.extracted;
    const results = sourceKey === "ols" ? item.olsResults : item.bioportalResults;
    const localIRI = cls.iri || (baseIRI + (cls.id || ""));
    const tableId = "alignTable-" + sourceKey + "-" + i;

    let html = `<div class="align-right-table-wrap" id="${tableId}" style="display:none;">
      <table class="data-table">
        <thead>
          <tr>
            <th class="result-radio-cell">Select</th>
            <th class="cid">ID</th>
            <th class="clabel">Label</th>
            <th class="ciri">IRI</th>
            <th style="width:90px;">Ontology</th>
          </tr>
        </thead>
        <tbody>`;

    // Keep Local Class row
    html += `<tr class="align-keep-row">
      <td class="result-radio-cell"><input type="radio" name="align-${i}" value="local" checked onchange="onAlignChoice(${i},'local','${sourceKey}')"></td>
      <td style="font-family:monospace;font-size:12px;font-weight:500;color:var(--primary);">${esc(cls.id)}</td>
      <td style="font-weight:500;color:var(--primary);">${esc(cls.label)} <span style="font-size:10px;color:var(--text-muted);">(Keep Local)</span></td>
      <td style="font-family:monospace;font-size:11px;color:var(--text-muted);">${esc(localIRI)}</td>
      <td style="font-size:11px;">Local</td>
    </tr>`;

    if (results === null) {
      html += `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:12px;">Not searched — switch source and click Begin Search</td></tr>`;
    } else if (results.length === 0) {
      html += `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:12px;">No ${sourceDisplay} matches found</td></tr>`;
    } else {
      results.forEach((r, j) => {
        html += `<tr>
          <td class="result-radio-cell"><input type="radio" name="align-${i}" value="${j}" onchange="onAlignChoice(${i},'${j}','${sourceKey}')"></td>
          <td style="font-family:monospace;font-size:12px;">${esc(r.id)}</td>
          <td>${esc(r.label)}</td>
          <td style="font-family:monospace;font-size:11px;color:var(--text-muted);">${esc(r.iri)}</td>
          <td style="font-size:11px;color:var(--accent-orange);font-weight:500;">${esc(r.ontology)}</td>
        </tr>`;
      });
    }

    html += `</tbody></table>
      <div class="align-pagination" id="alignPagination-${sourceKey}-${i}" style="display:none; padding:8px 0; text-align:center; border-top:1px solid var(--border);">
        <button class="btn btn-sm" id="alignPrevBtn-${sourceKey}-${i}" onclick="changeAlignPage(${i},'${sourceKey}',-1)" disabled>← Prev</button>
        <span id="alignPageLabel-${sourceKey}-${i}" style="font-size:12px; color:var(--text-muted); margin:0 8px;"></span>
        <button class="btn btn-sm" id="alignNextBtn-${sourceKey}-${i}" onclick="changeAlignPage(${i},'${sourceKey}',1)" disabled>Next →</button>
      </div>
    </div>`;
    return html;
  }

  // Build tables for all needed sources
  let tablesHTML = "";
  const searchedSources = [];
  if (searchOls) searchedSources.push({ key: "ols", label: "OLS" });
  if (searchBio) searchedSources.push({ key: "bioportal", label: "BioPortal" });

  // Per-source tables
  alignData.forEach((item, i) => {
    searchedSources.forEach(s => {
      tablesHTML += buildCandidateTable(item, i, s.key, s.label);
    });
  });

  // For "all" mode, also build combined tables
  if (source === "all") {
    alignData.forEach((item, i) => {
      const cls = item.extracted;
      const localIRI = cls.iri || (baseIRI + (cls.id || ""));
      let html = `<div class="align-right-table-wrap" id="alignTable-all-${i}" style="display:none;">
        <table class="data-table">
          <thead>
            <tr>
              <th class="result-radio-cell">Select</th>
              <th class="cid">ID</th>
              <th class="clabel">Label</th>
              <th class="ciri">IRI</th>
              <th style="width:90px;">Ontology</th>
              <th style="width:70px;">Source</th>
            </tr>
          </thead>
          <tbody>`;

      // Keep Local row
      html += `<tr class="align-keep-row">
        <td class="result-radio-cell"><input type="radio" name="align-${i}" value="local" checked onchange="onAlignChoice(${i},'local','ols')"></td>
        <td style="font-family:monospace;font-size:12px;font-weight:500;color:var(--primary);">${esc(cls.id)}</td>
        <td style="font-weight:500;color:var(--primary);">${esc(cls.label)} <span style="font-size:10px;color:var(--text-muted);">(Keep Local)</span></td>
        <td style="font-family:monospace;font-size:11px;color:var(--text-muted);">${esc(localIRI)}</td>
        <td style="font-size:11px;">Local</td>
        <td style="font-size:11px;">—</td>
      </tr>`;

      // OLS results with source badge
      const seenIds = new Set();
      (item.olsResults || []).forEach((r, j) => {
        seenIds.add(r.id);
        html += `<tr>
          <td class="result-radio-cell"><input type="radio" name="align-${i}" value="${j}" onchange="onAlignChoice(${i},'${j}','ols')"></td>
          <td style="font-family:monospace;font-size:12px;">${esc(r.id)}</td>
          <td>${esc(r.label)}</td>
          <td style="font-family:monospace;font-size:11px;color:var(--text-muted);">${esc(r.iri)}</td>
          <td style="font-size:11px;color:var(--accent-orange);font-weight:500;">${esc(r.ontology)}</td>
          <td style="font-size:11px;"><span style="background:var(--accent-orange);color:#fff;padding:1px 6px;border-radius:3px;font-size:10px;">OLS</span></td>
        </tr>`;
      });

      // BioPortal results (skip duplicates already shown from OLS)
      (item.bioportalResults || []).forEach((r, j) => {
        if (seenIds.has(r.id)) return;
        html += `<tr>
          <td class="result-radio-cell"><input type="radio" name="align-${i}" value="${j}" onchange="onAlignChoice(${i},'${j}','bioportal')"></td>
          <td style="font-family:monospace;font-size:12px;">${esc(r.id)}</td>
          <td>${esc(r.label)}</td>
          <td style="font-family:monospace;font-size:11px;color:var(--text-muted);">${esc(r.iri)}</td>
          <td style="font-size:11px;color:var(--accent-green);font-weight:500;">${esc(r.ontology)}</td>
          <td style="font-size:11px;"><span style="background:var(--accent-green);color:#fff;padding:1px 6px;border-radius:3px;font-size:10px;">BioPortal</span></td>
        </tr>`;
      });

      const totalCandidates = (item.olsResults || []).length + (item.bioportalResults || []).length;
      if (totalCandidates === 0) {
        html += `<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:12px;">No matches found in either source</td></tr>`;
      }

      html += `</tbody></table></div>`;
      tablesHTML += html;
    });
  }

  rightTable.innerHTML = tablesHTML + `<div class="align-right-placeholder" id="alignPlaceholder">← Click a class on the left to view candidates and make your selection.</div>`;

  // Status
  const olsCount = alignData.reduce((s, a) => s + (a.olsResults || []).length, 0);
  const bioCount = alignData.reduce((s, a) => s + (a.bioportalResults || []).length, 0);
  if (source === "all") {
    statusEl.textContent = olsCount + " OLS + " + bioCount + " BioPortal candidates found.";
  } else if (source === "ols") {
    statusEl.textContent = olsCount + " OLS candidates found.";
  } else {
    statusEl.textContent = bioCount + " BioPortal candidates found.";
  }

  insertBtn.disabled = false;
  if (beginBtn) { beginBtn.textContent = "Search Again"; beginBtn.disabled = false; }

  // Rebuild left class list (preserve badges)
  classListEl.innerHTML = alignData.map((item, i) => {
    const cls = item.extracted;
    const label = esc(cls.label || cls.id);
    return `<div class="align-class-item" data-index="${i}" onclick="selectAlignClass(${i})">
      <span class="aci-label">${label}</span>
      <span class="aci-badge pending">pending</span>
    </div>`;
  }).join("");

  // Auto-select first class
  if (alignData.length > 0) selectAlignClass(0);
}

// Switch alignment source (OLS ↔ BioPortal ↔ All) — only matters after search is done
function onAlignSourceChange() {
  const sourceEl = document.querySelector("input[name='alignSource']:checked");
  if (!sourceEl) return;
  const source = sourceEl.value;
  window._alignSource = source;

  // Show/hide ontology filter per source
  document.getElementById("alignOlsOntologyFilter").style.display = (source === "ols" || source === "all") ? "" : "none";
  document.getElementById("alignBioportalOntologyFilter").style.display = (source === "bioportal" || source === "all") ? "" : "none";

  const alignData = window._alignData;
  if (!alignData || !window._alignSearchDone) return;

  // Show the current source's table for the selected class
  const curIdx = window._alignCurrentIndex;
  if (curIdx >= 0) {
    document.querySelectorAll("[id^='alignTable-ols-'], [id^='alignTable-bioportal-'], [id^='alignTable-all-']").forEach(el => el.style.display = "none");
    const table = document.getElementById("alignTable-" + source + "-" + curIdx);
    if (table) table.style.display = "";
    // Update right header
    const item = alignData[curIdx];
    if (item) {
      const srcLabel = source === "ols" ? "OLS" : source === "bioportal" ? "BioPortal" : "All Sources";
      document.getElementById("alignRightHeader").textContent = (item.extracted.label || item.extracted.id) + " — " + srcLabel + " candidates";
    }
    // Refresh all left-panel badges for current source
    alignData.forEach((_, idx) => updateAlignBadge(idx));
    // Update pagination for the current class
    if (source !== "all") {
      updateAlignPaginationUI(curIdx, source);
    }
  }
}

// Update the left-panel badge for class i to reflect current selection
function updateAlignBadge(i) {
  const source = window._alignSource || "ols";
  const selections = window._alignSelections;
  // In "all" mode, the selection value encodes the source ("ols:0", "bioportal:1", "local")
  const raw = selections && selections[i] !== undefined ? selections[i] : "local";
  let displaySource, isLocal;
  if (raw === "local") {
    isLocal = true;
    displaySource = source === "all" ? "ols" : source; // badge style falls back to ols style
  } else if (raw.startsWith("ols:") || raw.startsWith("bioportal:")) {
    isLocal = false;
    displaySource = raw.split(":")[0];
  } else {
    isLocal = (raw === "local");
    displaySource = source;
  }

  const item = document.querySelector(`.align-class-item[data-index="${i}"]`);
  if (item) {
    const badge = item.querySelector(".aci-badge");
    if (badge) {
      if (isLocal) {
        badge.textContent = "local";
        badge.className = "aci-badge local";
      } else {
        badge.textContent = displaySource === "ols" ? "OLS" : "BioPortal";
        badge.className = displaySource === "ols" ? "aci-badge ols" : "aci-badge bioportal";
      }
    }
  }
}

function selectAlignClass(i) {
  // Update left panel active state
  document.querySelectorAll(".align-class-item").forEach(el => el.classList.remove("active"));
  const item = document.querySelector(`.align-class-item[data-index="${i}"]`);
  if (item) item.classList.add("active");

  // Hide all tables, show current source's table for this class
  const source = window._alignSource || "ols";
  document.querySelectorAll("[id^='alignTable-ols-'], [id^='alignTable-bioportal-'], [id^='alignTable-all-']").forEach(el => el.style.display = "none");
  // Hide all pagination rows
  document.querySelectorAll("[id^='alignPagination-']").forEach(el => el.style.display = "none");
  const table = document.getElementById("alignTable-" + source + "-" + i);
  if (table) table.style.display = "";

  // Hide placeholder
  const placeholder = document.getElementById("alignPlaceholder");
  if (placeholder) placeholder.style.display = "none";

  // Update header
  const alignData = window._alignData;
  if (alignData && alignData[i]) {
    const cls = alignData[i].extracted;
    const srcLabel = source === "ols" ? "OLS" : source === "bioportal" ? "BioPortal" : "All Sources";
    document.getElementById("alignRightHeader").textContent = (cls.label || cls.id) + " — " + srcLabel + " candidates";
  }

  window._alignCurrentIndex = i;
  // Update pagination controls for the newly selected class
  if (source !== "all") {
    updateAlignPaginationUI(i, source);
  }
}

function onAlignChoice(i, value, sourceKey) {
  // sourceKey is "ols" or "bioportal" — used to encode the selection in "all" mode
  const source = window._alignSource || "ols";
  if (window._alignSelections) {
    if (source === "all") {
      // Encode which source the choice came from
      window._alignSelections[i] = (value === "local") ? "local" : (sourceKey + ":" + value);
    } else {
      window._alignSelections[i] = value;
    }
  }
  updateAlignBadge(i);
}

// Update pagination UI for a given class + source
function updateAlignPaginationUI(i, sourceKey) {
  const pageInfo = window._alignPageInfo && window._alignPageInfo[i] ? window._alignPageInfo[i][sourceKey] : null;
  const pagination = document.getElementById("alignPagination-" + sourceKey + "-" + i);
  const prevBtn = document.getElementById("alignPrevBtn-" + sourceKey + "-" + i);
  const nextBtn = document.getElementById("alignNextBtn-" + sourceKey + "-" + i);
  const pageLabel = document.getElementById("alignPageLabel-" + sourceKey + "-" + i);
  if (!pagination || !pageInfo || pageInfo.totalPages <= 1) {
    if (pagination) pagination.style.display = "none";
    return;
  }
  pagination.style.display = "";
  prevBtn.disabled = pageInfo.page <= 1;
  nextBtn.disabled = pageInfo.page >= pageInfo.totalPages;
  pageLabel.textContent = "Page " + pageInfo.page + " / " + pageInfo.totalPages;
}

// Navigate alignment results page for a given class + source
async function changeAlignPage(i, sourceKey, direction) {
  const pageInfo = window._alignPageInfo && window._alignPageInfo[i] ? window._alignPageInfo[i][sourceKey] : null;
  if (!pageInfo) return;

  const newPage = pageInfo.page + direction;
  if (newPage < 1 || newPage > pageInfo.totalPages) return;

  const item = window._alignData[i];
  const statusEl = document.getElementById("alignStatus");
  statusEl.textContent = "Loading page " + newPage + "…";

  // Build the correct API URL
  let url;
  if (sourceKey === "ols") {
    url = "/api/ols-search?q=" + encodeURIComponent(pageInfo.query) + "&page=" + newPage;
    if (pageInfo.ontology) url += "&ontologies=" + encodeURIComponent(pageInfo.ontology);
  } else {
    url = "/api/bioportal-search?q=" + encodeURIComponent(pageInfo.query) + "&page=" + newPage;
    if (pageInfo.ontology) url += "&ontologies=" + encodeURIComponent(pageInfo.ontology);
  }

  try {
    const resp = await fetch(url);
    const result = await resp.json();
    if (result.success) {
      // Update stored results and page info
      if (sourceKey === "ols") {
        item.olsResults = result.results || [];
        pageInfo.page = result.page || newPage;
        pageInfo.totalPages = result.pageCount || 1;
      } else {
        item.bioportalResults = result.results || [];
        pageInfo.page = result.page || newPage;
        pageInfo.totalPages = result.pageCount || 1;
      }
      // Rebuild the table for this class + source
      rebuildAlignTable(i, sourceKey, item);
      updateAlignPaginationUI(i, sourceKey);
      statusEl.textContent = "";
    } else {
      statusEl.textContent = "Error loading page";
    }
  } catch (_) {
    statusEl.textContent = "Error loading page";
  }
}

// Rebuild a single alignment candidate table in-place
function rebuildAlignTable(i, sourceKey, item) {
  const sourceDisplay = sourceKey === "ols" ? "OLS" : "BioPortal";
  const results = sourceKey === "ols" ? item.olsResults : item.bioportalResults;
  const baseIRI = document.getElementById("iriInput").value.trim();
  const cls = item.extracted;
  const localIRI = cls.iri || (baseIRI + (cls.id || ""));
  const tableId = "alignTable-" + sourceKey + "-" + i;

  let html = `<table class="data-table">
    <thead>
      <tr>
        <th class="result-radio-cell">Select</th>
        <th class="cid">ID</th>
        <th class="clabel">Label</th>
        <th class="ciri">IRI</th>
        <th style="width:90px;">Ontology</th>
      </tr>
    </thead>
    <tbody>`;

  // Keep Local Class row
  html += `<tr class="align-keep-row">
    <td class="result-radio-cell"><input type="radio" name="align-${i}" value="local" checked onchange="onAlignChoice(${i},'local','${sourceKey}')"></td>
    <td style="font-family:monospace;font-size:12px;font-weight:500;color:var(--primary);">${esc(cls.id)}</td>
    <td style="font-weight:500;color:var(--primary);">${esc(cls.label)} <span style="font-size:10px;color:var(--text-muted);">(Keep Local)</span></td>
    <td style="font-family:monospace;font-size:11px;color:var(--text-muted);">${esc(localIRI)}</td>
    <td style="font-size:11px;">Local</td>
  </tr>`;

  if (results && results.length > 0) {
    results.forEach((r, j) => {
      html += `<tr>
        <td class="result-radio-cell"><input type="radio" name="align-${i}" value="${j}" onchange="onAlignChoice(${i},'${j}','${sourceKey}')"></td>
        <td style="font-family:monospace;font-size:12px;">${esc(r.id)}</td>
        <td>${esc(r.label)}</td>
        <td style="font-family:monospace;font-size:11px;color:var(--text-muted);">${esc(r.iri)}</td>
        <td style="font-size:11px;color:var(--accent-orange);font-weight:500;">${esc(r.ontology)}</td>
      </tr>`;
    });
  } else {
    html += `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:12px;">No ${sourceDisplay} matches found</td></tr>`;
  }

  html += `</tbody></table>`;

  const wrap = document.getElementById(tableId);
  if (wrap) {
    // Preserve the pagination div (last child), replace the table
    const paginationEl = wrap.querySelector(".align-pagination");
    wrap.innerHTML = html;
    if (paginationEl) wrap.appendChild(paginationEl);
  }
}

function closeAlignmentModal() {
  document.getElementById("alignModal").style.display = "none";
  // Clear ontology filter inputs
  document.getElementById("alignOlsOntologyInput").value = "";
  document.getElementById("alignBioportalOntologyInput").value = "";
  window._alignData = null;
  window._alignSelections = null;
  window._alignSource = null;
  window._alignSearchDone = false;
  window._alignCurrentIndex = -1;
  window._alignPageInfo = null;
}

function insertAlignedClasses() {
  const alignData = window._alignData;
  if (!alignData || alignData.length === 0) { showToast("No mapped terms", "error"); return; }
  if (!window._alignSearchDone) { showToast("Please click Begin Search first", "error"); return; }

  const mode = document.querySelector("input[name='aiMode']:checked")?.value || "merge";
  if (mode === "replace") {
    document.getElementById("tbody-classes").innerHTML = "";
    extraColumns.classes = [];
    classSources = {};
    const theadRow = document.querySelector("#table-classes thead tr");
    if (theadRow) theadRow.querySelectorAll(".cadd-col").forEach(th => th.remove());
  }

  const existing = mode === "merge" ? getTableData("classes") : [];
  const existingKeys = new Set(
    existing.map(r => r.id + "::" + (r.parent_class || ""))
  );
  let inserted = 0;

  // ---- Pass 1: build all rows and the AI-id → new-id mapping ----
  const newRows = [];
  const idRemap = {};
  const skipped = new Set();

  const source = window._alignSource || "ols";
  alignData.forEach((item, i) => {
    const rawSelection = window._alignSelections && window._alignSelections[i] !== undefined
      ? window._alignSelections[i] : "local";
    const cls = item.extracted;

    let newRow;
    if (rawSelection === "local") {
      const baseIRI = document.getElementById("iriInput").value.trim();
      newRow = {
        parent_class: cls.parent_class || "",
        id: cls.id,
        label: cls.label,
        iri: cls.iri || (baseIRI + (cls.id || "")),
        comment: cls.comment || "",
        definition: cls.definition || "",
        source: "local",
      };
    } else {
      // Parse encoded selection: "ols:3" or "bioportal:5" (or bare index for single-source mode)
      let resultSource, resultIndex;
      if (rawSelection.includes(":")) {
        const parts = rawSelection.split(":");
        resultSource = parts[0];
        resultIndex = parseInt(parts[1]);
      } else {
        resultSource = source;
        resultIndex = parseInt(rawSelection);
      }
      const resultsArray = resultSource === "ols" ? item.olsResults : (item.bioportalResults || []);
      const r = resultsArray[resultIndex];
      if (!r) {
        skipped.add(i);
        return;
      }
      newRow = {
        parent_class: cls.parent_class || "",
        id: r.id,
        label: r.label,
        iri: r.iri,
        comment: cls.comment || "",
        definition: cls.definition || "",
        source: resultSource === "ols" ? "OLS" : "BioPortal",
      };
    }

    // Duplicate check — only skip if same ID AND same parent_class
    const rowKey = newRow.id + "::" + (newRow.parent_class || "");
    if (existingKeys.has(rowKey)) {
      showToast("Skipped duplicate: " + newRow.id + " (same parent_class)", "error");
      skipped.add(i);
      return;
    }
    existingKeys.add(rowKey);

    // Record mapping: old AI id → new id
    if (cls.id && cls.id !== newRow.id) {
      idRemap[cls.id] = newRow.id;
    }

    newRows.push({ row: newRow, index: i });
  });

  // ---- Pass 2: remap parent_class ----
  newRows.forEach(item => {
    const row = item.row;
    if (row.parent_class && row.parent_class !== "Thing" && idRemap[row.parent_class]) {
      row.parent_class = idRemap[row.parent_class];
    }
  });

  // ---- Pass 3: insert rows into DOM ----
  newRows.forEach(item => {
    const newRow = item.row;
    classSources[newRow.id] = newRow.source;

    const tbody = document.getElementById("tbody-classes");
    const cols = TABLE_COLS.classes.concat(extraColumns.classes);
    let cells = `<td class="csel"><input type="checkbox" class="row-sel"></td>`;
    cols.forEach(c => {
      let extraAttrs = "";
      if (c === "parent_class") extraAttrs = ` list="class-suggestions" autocomplete="off"`;
      if (c === "iri") extraAttrs += ' readonly';
      // Lock id and label for externally-sourced classes
      if ((c === "id" || c === "label") && newRow.source !== "local" && newRow.source !== "") {
        extraAttrs += ' readonly';
      }
      cells += `<td><input type="text" value="${esc(newRow[c] || "")}" data-col="${c}"${extraAttrs}></td>`;
    });
    if (newRow.source !== "local" && newRow.source !== "") {
      const badgeClass = newRow.source === "BioPortal" ? "bioportal-badge" : "ols-badge";
      cells = cells.replace(
        /(<td><input type="text" value="[^"]*" data-col="label"[^>]*>)(<\/td>)/,
        `$1<span class="${badgeClass}">${esc(newRow.source)}</span>$2`
      );
    }
    const tr = document.createElement("tr");
    tr.innerHTML = cells;
    tr.dataset.source = newRow.source || "local";
    tbody.appendChild(tr);
    inserted++;
  });

  attachIRIListeners();
  updateClassSuggestions();
  closeAlignmentModal();

  // Auto-switch to Classes tab
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  const classesTab = document.querySelector(".tab[data-tab='classes']");
  if (classesTab) classesTab.classList.add("active");
  const classesPanel = document.getElementById("panel-classes");
  if (classesPanel) classesPanel.classList.add("active");

  showToast("Inserted " + inserted + " mapped classes");
}

// ========================================================================
// System prompt modal
// ========================================================================

async function openSystemPromptEditor() {
  const modal = document.getElementById("systemPromptModal");
  const textarea = document.getElementById("systemPromptEditorText");
  const status = document.getElementById("systemPromptStatus");
  status.textContent = "Loading…";

  try {
    const resp = await fetch("/api/prompt");
    const result = await resp.json();
    if (result.success) {
      textarea.value = result.prompt;
      currentSystemPrompt = result.prompt;
      status.textContent = result.is_custom ? "Custom prompt loaded" : "Built-in default loaded";
    }
  } catch (err) {
    textarea.value = "";
    status.textContent = "Failed to load prompt";
  }

  modal.style.display = "flex";
}

function closeSystemPromptEditor() {
  document.getElementById("systemPromptModal").style.display = "none";
}

async function saveSystemPrompt() {
  const textarea = document.getElementById("systemPromptEditorText");
  const status = document.getElementById("systemPromptStatus");
  const prompt = textarea.value;

  status.textContent = "Saving…";
  try {
    const resp = await fetch("/api/prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: prompt }),
    });
    const result = await resp.json();
    if (result.success) {
      currentSystemPrompt = prompt;
      status.textContent = "✓ Saved to config.json";
      showToast("System prompt saved");
      setTimeout(() => { closeSystemPromptEditor(); }, 600);
    } else {
      status.textContent = "Save failed";
    }
  } catch (err) {
    status.textContent = "Network error";
  }
}

async function resetSystemPrompt() {
  if (!confirm("Reset the system prompt to the built-in default? This will clear your custom prompt from config.json.")) return;

  const status = document.getElementById("systemPromptStatus");
  status.textContent = "Resetting…";
  try {
    await fetch("/api/prompt/reset", { method: "POST" });
    const resp = await fetch("/api/prompt");
    const result = await resp.json();
    if (result.success) {
      document.getElementById("systemPromptEditorText").value = result.prompt;
      currentSystemPrompt = result.prompt;
      status.textContent = "✓ Reset to built-in default";
      showToast("System prompt reset to default");
    }
  } catch (err) {
    status.textContent = "Reset failed";
  }
}

// ========================================================================
// Task prompt modal
// ========================================================================

async function openTaskPromptEditor() {
  const modal = document.getElementById("taskPromptModal");
  const textarea = document.getElementById("taskPromptEditorText");
  const status = document.getElementById("taskPromptStatus");
  status.textContent = "Loading…";

  try {
    const resp = await fetch("/api/task-prompt");
    const result = await resp.json();
    if (result.success) {
      textarea.value = result.prompt || "";
      currentTaskPrompt = result.prompt || "";
      status.textContent = result.prompt ? "Task prompt loaded" : "No task prompt set";
    }
  } catch (err) {
    textarea.value = "";
    status.textContent = "Failed to load task prompt";
  }

  modal.style.display = "flex";
}

function closeTaskPromptEditor() {
  document.getElementById("taskPromptModal").style.display = "none";
}

async function saveTaskPrompt() {
  const textarea = document.getElementById("taskPromptEditorText");
  const status = document.getElementById("taskPromptStatus");
  const prompt = textarea.value;

  status.textContent = "Saving…";
  currentTaskPrompt = prompt;
  try {
    const resp = await fetch("/api/task-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: prompt }),
    });
    const result = await resp.json();
    if (result.success) {
      status.textContent = "✓ Saved to config.json";
      showToast("Task prompt saved");
      setTimeout(() => { closeTaskPromptEditor(); }, 600);
    } else {
      status.textContent = "Save failed";
    }
  } catch (err) {
    status.textContent = "Network error";
  }
}

async function clearTaskPrompt() {
  if (!confirm("Clear the task prompt?")) return;

  const status = document.getElementById("taskPromptStatus");
  status.textContent = "Clearing…";
  try {
    await fetch("/api/task-prompt/reset", { method: "POST" });
    document.getElementById("taskPromptEditorText").value = "";
    currentTaskPrompt = "";
    status.textContent = "✓ Task prompt cleared";
    showToast("Task prompt cleared");
  } catch (err) {
    status.textContent = "Clear failed";
  }
}

// ========================================================================
// Initialise AI Assist on page load
// ========================================================================

onProviderChange();

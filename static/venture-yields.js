function ventureYieldSelection() {
  return {
    job: document.getElementById("venture-yields-job").value,
    world: document.getElementById("venture-yields-world").value,
    level: document.getElementById("venture-yields-level").value,
    stat: document.getElementById("venture-yields-stat").value,
  };
}

function ventureYieldStatus(text) {
  const status = document.getElementById("venture-yields-status");
  status.textContent = text || "";
  status.hidden = !text;
}

function ventureYieldRow(entry, rank) {
  const row = document.createElement("tr");
  const warned = entry.quantity > realisticWeekSales(entry.week_volume);
  if (warned) {
    row.className = "volume-warning";
  }
  row.appendChild(currencyYieldNameCell(entry, rank));
  row.appendChild(currencyYieldCell(entry.level));
  row.appendChild(currencyYieldCell(entry.quantity));
  row.appendChild(currencyYieldCell(entry.price));
  row.appendChild(currencyYieldCell(entry.avg_price));
  row.appendChild(currencyYieldCell(entry.min_sale));
  row.appendChild(currencyYieldCell(entry.max_sale));
  const yieldCell = currencyYieldCell(entry.yield);
  yieldCell.className = "yield-value";
  row.appendChild(yieldCell);
  row.appendChild(volumeCell(entry, warned));
  return row;
}

function renderVentureYields(entries) {
  const table = document.getElementById("venture-yields-table");
  const body = document.getElementById("venture-yields-body");
  body.innerHTML = "";
  table.hidden = true;
  if (entries === null) {
    ventureYieldStatus(msg("currency_yields_failed", "Market data is unavailable right now."));
    return;
  }
  if (entries.length === 0) {
    ventureYieldStatus(msg("venture_yields_empty", "No sellable venture rewards found."));
    return;
  }
  ventureYieldStatus("");
  table.hidden = false;
  let rank = 0;
  for (const entry of entries) {
    rank += 1;
    body.appendChild(ventureYieldRow(entry, rank));
  }
}

function fetchVentureYields() {
  const selection = ventureYieldSelection();
  if (!selection.job || !selection.world) {
    return;
  }
  document.getElementById("venture-yields-body").innerHTML = "";
  document.getElementById("venture-yields-table").hidden = true;
  ventureYieldStatus(msg("currency_yields_loading", "Fetching market prices…"));
  const params = new URLSearchParams(selection);
  fetch("/venture-yields?" + params)
    .then(function (response) { return response.json(); })
    .then(renderVentureYields)
    .catch(function () { renderVentureYields(null); });
}

function openVentureYields() {
  document.getElementById("venture-yields-modal").hidden = false;
  fetchVentureYields();
}

function saveVentureYieldSelection() {
  try {
    for (const [field, value] of Object.entries(ventureYieldSelection())) {
      localStorage.setItem("venture-yields-" + field, value);
    }
  } catch (error) {}
}

function restoreVentureYieldSelection() {
  try {
    for (const field of ["job", "world", "level", "stat"]) {
      const saved = localStorage.getItem("venture-yields-" + field);
      if (saved) {
        document.getElementById("venture-yields-" + field).value = saved;
      }
    }
    const worldSelect = document.getElementById("venture-yields-world");
    if (!worldSelect.value) {
      worldSelect.value = localStorage.getItem("currency-yields-world") || "";
    }
  } catch (error) {}
}

function setupVentureYields() {
  const modal = document.getElementById("venture-yields-modal");
  if (modal === null) {
    return;
  }
  restoreVentureYieldSelection();
  document.getElementById("venture-yields-open").addEventListener("click", openVentureYields);
  document.getElementById("venture-yields-close").addEventListener("click", function () {
    modal.hidden = true;
  });
  modal.addEventListener("click", function (event) {
    if (event.target === modal) {
      modal.hidden = true;
    }
  });
  for (const id of ["venture-yields-job", "venture-yields-world",
                    "venture-yields-level", "venture-yields-stat"]) {
    document.getElementById(id).addEventListener("change", function () {
      saveVentureYieldSelection();
      fetchVentureYields();
    });
  }
}

setupVentureYields();

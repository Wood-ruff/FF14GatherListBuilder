const VOLUME_WARNING_SHARE = 0.7;

let currencyYieldEntries = [];

function currencyYieldSelection() {
  return {
    currency: document.getElementById("currency-yields-currency").value,
    world: document.getElementById("currency-yields-world").value,
  };
}

function currencyYieldPlan() {
  const units = parseInt(document.getElementById("currency-yields-units").value, 10);
  const budget = parseInt(document.getElementById("currency-yields-budget").value, 10);
  return {
    units: units > 0 ? units : 0,
    budget: budget > 0 ? budget : 0,
    active: units > 0 || budget > 0,
  };
}

function plannedUnits(entry, plan) {
  let planned = plan.units;
  if (plan.budget > 0) {
    const affordable = Math.floor(plan.budget / entry.cost) * entry.amount;
    planned = plan.units > 0 ? Math.min(plan.units, affordable) : affordable;
  }
  return planned;
}

function projectedGil(entry, plan) {
  return plannedUnits(entry, plan) * entry.price;
}

/** Sales one seller can realistically capture in 7 days: 70% of the volume minus a √volume undercutting margin. */
function realisticWeekSales(weekVolume) {
  return Math.max(0, VOLUME_WARNING_SHARE * weekVolume - Math.sqrt(weekVolume));
}

function exceedsRealisticVolume(entry, plan) {
  return plannedUnits(entry, plan) > realisticWeekSales(entry.week_volume);
}

function orderedEntries(plan) {
  if (!plan.active) {
    return currencyYieldEntries;
  }
  return currencyYieldEntries.slice().sort(function (a, b) {
    return projectedGil(b, plan) - projectedGil(a, plan) || b.yield - a.yield;
  });
}

function currencyYieldStatus(text) {
  const status = document.getElementById("currency-yields-status");
  status.textContent = text || "";
  status.hidden = !text;
}

function currencyYieldCell(value) {
  const cell = document.createElement("td");
  cell.textContent = typeof value === "number" ? value.toLocaleString() : value;
  return cell;
}

function currencyYieldNameCell(entry, rank) {
  const cell = document.createElement("td");
  cell.appendChild(document.createTextNode("#" + rank + " " + entry.name));
  if (entry.locked) {
    const marker = document.createElement("span");
    marker.className = "lock-marker";
    marker.textContent = "🔒";
    marker.title = msg("craft_costs_locked", "needs unlock");
    cell.appendChild(marker);
  }
  const link = document.createElement("a");
  link.className = "market-link";
  link.href = "https://universalis.app/market/" + entry.game_id;
  link.target = "_blank";
  link.rel = "noopener";
  link.title = msg("market_tooltip", "Check market board prices on Universalis");
  const icon = document.createElement("img");
  icon.className = "market-icon";
  icon.src = "/market-icon";
  icon.alt = "MB";
  link.appendChild(icon);
  cell.appendChild(link);
  return cell;
}

function volumeCell(entry, warned) {
  const cell = currencyYieldCell(entry.week_volume);
  if (warned) {
    const marker = document.createElement("span");
    marker.className = "volume-warning-marker";
    marker.textContent = " ⚠";
    marker.title = msg("currency_yields_volume_warning",
      "Unlikely to sell within 7 days — planned amount exceeds what this trade volume realistically absorbs");
    cell.appendChild(marker);
  }
  return cell;
}

function currencyYieldRow(entry, rank, plan) {
  const row = document.createElement("tr");
  const warned = plan.active && exceedsRealisticVolume(entry, plan);
  if (warned) {
    row.className = "volume-warning";
  }
  row.appendChild(currencyYieldNameCell(entry, rank));
  row.appendChild(currencyYieldCell(entry.cost));
  row.appendChild(currencyYieldCell(entry.amount));
  row.appendChild(currencyYieldCell(entry.price));
  row.appendChild(currencyYieldCell(entry.avg_price));
  row.appendChild(currencyYieldCell(entry.min_sale));
  row.appendChild(currencyYieldCell(entry.max_sale));
  const yieldCell = currencyYieldCell(entry.yield);
  yieldCell.className = "yield-value";
  row.appendChild(yieldCell);
  row.appendChild(volumeCell(entry, warned));
  row.appendChild(currencyYieldCell(plan.active ? plannedUnits(entry, plan) : ""));
  const profitCell = currencyYieldCell(plan.active ? projectedGil(entry, plan) : "");
  profitCell.className = "yield-value";
  row.appendChild(profitCell);
  return row;
}

function renderCurrencyYields(entries) {
  currencyYieldEntries = entries || [];
  const table = document.getElementById("currency-yields-table");
  document.getElementById("currency-yields-body").innerHTML = "";
  table.hidden = true;
  if (entries === null) {
    currencyYieldStatus(msg("currency_yields_failed", "Market data is unavailable right now."));
    return;
  }
  if (entries.length === 0) {
    currencyYieldStatus(msg("currency_yields_empty", "Nothing sellable found for this currency."));
    return;
  }
  currencyYieldStatus("");
  table.hidden = false;
  renderCurrencyYieldRows();
}

function renderCurrencyYieldRows() {
  const body = document.getElementById("currency-yields-body");
  body.innerHTML = "";
  const plan = currencyYieldPlan();
  let rank = 0;
  for (const entry of orderedEntries(plan)) {
    rank += 1;
    body.appendChild(currencyYieldRow(entry, rank, plan));
  }
}

function fetchCurrencyYields() {
  const selection = currencyYieldSelection();
  if (!selection.currency || !selection.world) {
    return;
  }
  document.getElementById("currency-yields-body").innerHTML = "";
  document.getElementById("currency-yields-table").hidden = true;
  currencyYieldStatus(msg("currency_yields_loading", "Fetching market prices…"));
  const params = new URLSearchParams(selection);
  fetch("/currency-yields?" + params)
    .then(function (response) { return response.json(); })
    .then(renderCurrencyYields)
    .catch(function () { renderCurrencyYields(null); });
}

function openCurrencyYields() {
  document.getElementById("currency-yields-modal").hidden = false;
  fetchCurrencyYields();
}

function saveCurrencyYieldSelection() {
  try {
    const selection = currencyYieldSelection();
    localStorage.setItem("currency-yields-currency", selection.currency);
    localStorage.setItem("currency-yields-world", selection.world);
    localStorage.setItem("currency-yields-units", document.getElementById("currency-yields-units").value);
    localStorage.setItem("currency-yields-budget", document.getElementById("currency-yields-budget").value);
  } catch (error) {}
}

function restoreCurrencyYieldSelection() {
  try {
    for (const field of ["currency", "world", "units", "budget"]) {
      const saved = localStorage.getItem("currency-yields-" + field);
      if (saved) {
        document.getElementById("currency-yields-" + field).value = saved;
      }
    }
  } catch (error) {}
}

function setupCurrencyYields() {
  const modal = document.getElementById("currency-yields-modal");
  if (modal === null) {
    return;
  }
  restoreCurrencyYieldSelection();
  document.getElementById("currency-yields-open").addEventListener("click", openCurrencyYields);
  document.getElementById("currency-yields-close").addEventListener("click", function () {
    modal.hidden = true;
  });
  modal.addEventListener("click", function (event) {
    if (event.target === modal) {
      modal.hidden = true;
    }
  });
  for (const id of ["currency-yields-currency", "currency-yields-world"]) {
    document.getElementById(id).addEventListener("change", function () {
      saveCurrencyYieldSelection();
      fetchCurrencyYields();
    });
  }
  for (const id of ["currency-yields-units", "currency-yields-budget"]) {
    document.getElementById(id).addEventListener("input", function () {
      saveCurrencyYieldSelection();
      renderCurrencyYieldRows();
    });
  }
}

setupCurrencyYields();

function gatheringYieldSelection() {
  return {
    job: document.getElementById("gathering-yields-job").value,
    world: document.getElementById("gathering-yields-world").value,
    minlevel: document.getElementById("gathering-yields-minlevel").value,
    maxlevel: document.getElementById("gathering-yields-maxlevel").value,
    hideslow: document.getElementById("gathering-yields-hideslow").checked ? "1" : "0",
    quick: document.getElementById("gathering-yields-quick").checked ? "1" : "0",
    highvolume: document.getElementById("gathering-yields-highvolume").checked ? "1" : "0",
  };
}

function eorzeaClock(minutes) {
  const hours = String(Math.floor(minutes / 60) % 24).padStart(2, "0");
  const rest = String(Math.floor(minutes % 60)).padStart(2, "0");
  return hours + ":" + rest;
}

function openGatheringTimes(entry) {
  const spawn = nextSpawn(entry.windows, eorzeaNowMinutes());
  const time = formatRealDuration(spawn.etMinutes);
  const lines = [spawn.open
    ? msg("timer_up", "up now — {time} left").replace("{time}", time)
    : msg("timer_in", "in {time}").replace("{time}", time)];
  for (const window of entry.windows) {
    lines.push(eorzeaClock(window.start) + " – "
      + eorzeaClock((window.start + window.duration) % 1440) + " ET");
  }
  openModal(entry.name, lines.join("\n"));
}

function gatheringYieldStatus(text) {
  const status = document.getElementById("gathering-yields-status");
  status.textContent = text || "";
  status.hidden = !text;
}

function gatheringYieldNameCell(entry, rank) {
  const cell = currencyYieldNameCell(entry, rank);
  const link = cell.querySelector(".market-link");
  if (entry.timed) {
    const marker = document.createElement("span");
    marker.className = "timed-marker";
    marker.textContent = " ⏱";
    marker.title = msg("gathering_yields_timed", "Timed node — click for its current spawn times");
    if (entry.windows && entry.windows.length > 0) {
      marker.style.cursor = "pointer";
      marker.addEventListener("click", function () {
        openGatheringTimes(entry);
      });
    }
    cell.insertBefore(marker, link);
  }
  if (entry.hidden) {
    const marker = document.createElement("span");
    marker.className = "hidden-marker";
    marker.textContent = " 👁";
    marker.title = msg("gathering_yields_hidden", "Hidden item — needs its folklore or perception unlock to appear");
    cell.insertBefore(marker, link);
  }
  return cell;
}

function gatheringVolumeCell(entry, warned) {
  const cell = currencyYieldCell(entry.week_volume);
  if (warned) {
    const marker = document.createElement("span");
    marker.className = "volume-warning-marker";
    marker.textContent = " ⚠";
    marker.title = msg("gathering_yields_volume_warning",
      "Unlikely to sell within 7 days — one hour of gathering exceeds what this trade volume realistically absorbs");
    cell.appendChild(marker);
  }
  return cell;
}

function gatheringJobNames(jobs) {
  return jobs.map(function (job) {
    return msg("venture_yields_job_" + job, job);
  }).join(", ");
}

function gatheringYieldRow(entry, rank) {
  const row = document.createElement("tr");
  const warned = entry.hourly_items > realisticWeekSales(entry.week_volume);
  if (warned) {
    row.className = "volume-warning";
  }
  row.appendChild(gatheringYieldNameCell(entry, rank));
  row.appendChild(currencyYieldCell(entry.level + "★".repeat(entry.stars)));
  row.appendChild(currencyYieldCell(gatheringJobNames(entry.jobs)));
  row.appendChild(currencyYieldCell(entry.price));
  row.appendChild(currencyYieldCell(entry.avg_price));
  row.appendChild(currencyYieldCell(entry.timed ? entry.hourly_items : "—"));
  const yieldCell = currencyYieldCell(entry.yield);
  yieldCell.className = "yield-value";
  row.appendChild(yieldCell);
  row.appendChild(gatheringVolumeCell(entry, warned));
  return row;
}

function renderGatheringYields(entries) {
  const table = document.getElementById("gathering-yields-table");
  const body = document.getElementById("gathering-yields-body");
  body.innerHTML = "";
  table.hidden = true;
  if (entries === null) {
    gatheringYieldStatus(msg("currency_yields_failed", "Market data is unavailable right now."));
    return;
  }
  if (entries.length === 0) {
    gatheringYieldStatus(msg("gathering_yields_empty", "No sellable node items found."));
    return;
  }
  gatheringYieldStatus("");
  table.hidden = false;
  let rank = 0;
  for (const entry of entries) {
    rank += 1;
    body.appendChild(gatheringYieldRow(entry, rank));
  }
}

function fetchGatheringYields() {
  const selection = gatheringYieldSelection();
  if (!selection.world) {
    return;
  }
  document.getElementById("gathering-yields-body").innerHTML = "";
  document.getElementById("gathering-yields-table").hidden = true;
  gatheringYieldStatus(msg("currency_yields_loading", "Fetching market prices…"));
  const params = new URLSearchParams(selection);
  fetch("/gathering-yields?" + params)
    .then(function (response) { return response.json(); })
    .then(renderGatheringYields)
    .catch(function () { renderGatheringYields(null); });
}

function openGatheringYields() {
  document.getElementById("gathering-yields-modal").hidden = false;
  fetchGatheringYields();
}

function saveGatheringYieldSelection() {
  try {
    for (const [field, value] of Object.entries(gatheringYieldSelection())) {
      localStorage.setItem("gathering-yields-" + field, value);
    }
  } catch (error) {}
}

function restoreGatheringYieldSelection() {
  try {
    for (const field of ["job", "world", "minlevel", "maxlevel"]) {
      const saved = localStorage.getItem("gathering-yields-" + field);
      if (saved) {
        document.getElementById("gathering-yields-" + field).value = saved;
      }
    }
    document.getElementById("gathering-yields-hideslow").checked =
      localStorage.getItem("gathering-yields-hideslow") === "1";
    document.getElementById("gathering-yields-quick").checked =
      localStorage.getItem("gathering-yields-quick") === "1";
    document.getElementById("gathering-yields-highvolume").checked =
      localStorage.getItem("gathering-yields-highvolume") === "1";
    const worldSelect = document.getElementById("gathering-yields-world");
    if (!worldSelect.value) {
      worldSelect.value = localStorage.getItem("currency-yields-world") || "";
    }
  } catch (error) {}
}

function setupGatheringYields() {
  const modal = document.getElementById("gathering-yields-modal");
  if (modal === null) {
    return;
  }
  restoreGatheringYieldSelection();
  document.getElementById("gathering-yields-open").addEventListener("click", openGatheringYields);
  document.getElementById("gathering-yields-close").addEventListener("click", function () {
    modal.hidden = true;
  });
  modal.addEventListener("click", function (event) {
    if (event.target === modal) {
      modal.hidden = true;
    }
  });
  for (const id of ["gathering-yields-job", "gathering-yields-world",
                    "gathering-yields-minlevel", "gathering-yields-maxlevel",
                    "gathering-yields-hideslow", "gathering-yields-quick",
                    "gathering-yields-highvolume"]) {
    document.getElementById(id).addEventListener("change", function () {
      saveGatheringYieldSelection();
      fetchGatheringYields();
    });
  }
}

setupGatheringYields();

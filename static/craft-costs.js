let craftCostEntries = [];
let craftCostsPage = 1;
let craftCostsController = null;

const CRAFT_COSTS_PAGE_SIZE = 50;

const CRAFT_COSTS_CONTROLS = [
  "craft-costs-level", "craft-costs-job", "craft-costs-orange",
  "craft-costs-gemstone", "craft-costs-hide-loot", "craft-costs-hide-locked",
];


function craftCostsSettings() {
  return {
    level: document.getElementById("craft-costs-level").value || "100",
    job: document.getElementById("craft-costs-job").value,
    orange: document.getElementById("craft-costs-orange").checked,
    gemstone: document.getElementById("craft-costs-gemstone").checked,
    hideLoot: document.getElementById("craft-costs-hide-loot").checked,
    hideLocked: document.getElementById("craft-costs-hide-locked").checked,
  };
}

function setCraftCostsLoading(loading) {
  document.getElementById("craft-costs-spinner").hidden = !loading;
  if (loading) {
    document.getElementById("craft-costs-list").innerHTML = "";
    document.getElementById("craft-costs-pager").hidden = true;
  }
}

function fetchCraftCosts() {
  const settings = craftCostsSettings();
  const params = new URLSearchParams();
  params.set("level", settings.level);
  params.set("job", settings.job);
  params.set("scrips", settings.orange ? "orange" : "purple");
  params.set("gemstones", settings.gemstone ? "unlocked" : "locked");
  params.set("hideloot", settings.hideLoot ? "1" : "0");
  params.set("hidelocked", settings.hideLocked ? "1" : "0");
  setCraftCostsLoading(true);
  if (craftCostsController !== null) {
    craftCostsController.abort();
  }
  craftCostsController = new AbortController();
  fetch("/craft-costs?" + params, { signal: craftCostsController.signal })
    .then(function (response) { return response.json(); })
    .then(function (entries) {
      craftCostEntries = entries;
      craftCostsPage = 1;
      setCraftCostsLoading(false);
      renderCraftCosts();
    })
    .catch(function (error) {
      if (error.name !== "AbortError") {
        setCraftCostsLoading(false);
      }
    });
}

const MATERIAL_SOURCE_LABELS = {
  loot: ["craft_costs_loot", "mob drop"],
  gemstone: ["craft_costs_gemstone", "mob drop / gemstone vendor"],
  gil: ["craft_costs_gil", "gil vendor"],
  special: ["craft_costs_special", "currency vendor"],
};

function garlandLink(name, gameId) {
  const link = document.createElement("a");
  link.href = "https://www.garlandtools.org/db/#item/" + gameId;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = name;
  return link;
}

function craftCostName(entry, rank) {
  const name = document.createElement("div");
  name.appendChild(document.createTextNode(rank + ". "));
  name.appendChild(garlandLink(entry.name, entry.game_id));
  if (entry.has_loot) {
    const marker = document.createElement("span");
    marker.className = "loot-marker";
    marker.textContent = "⚔";
    marker.title = msg("craft_costs_loot_hint", "Needs materials dropped by enemies");
    name.appendChild(marker);
  }
  if (entry.has_locked) {
    const marker = document.createElement("span");
    marker.className = "lock-marker";
    marker.textContent = "🔒";
    marker.title = msg("craft_costs_locked_hint", "Needs a vendor that must be unlocked first");
    name.appendChild(marker);
  }
  return name;
}

function currencyIcon(currencyId) {
  const icon = document.createElement("img");
  icon.className = "currency-icon";
  icon.src = "/icons/" + currencyId;
  icon.alt = "";
  return icon;
}

function materialLabel(material) {
  if (material.scrip) {
    if (material.scrip.bundle > 1) {
      return msg("craft_costs_scrip_bundle", "{price} scrips per {bundle}")
        .replace("{price}", material.scrip.price).replace("{bundle}", material.scrip.bundle);
    }
    return msg("craft_costs_scrip_mat", "{price} scrips each").replace("{price}", material.scrip.price);
  }
  const label = MATERIAL_SOURCE_LABELS[material.source];
  return label ? msg(label[0], label[1]) : "";
}

function craftMaterialLine(material) {
  const line = document.createElement("div");
  line.className = "mat-" + material.source;
  line.appendChild(document.createTextNode(material.amount + "× "));
  line.appendChild(garlandLink(material.name, material.game_id));
  const label = materialLabel(material);
  if (label) {
    line.appendChild(document.createTextNode(" — "));
    if (material.currency) {
      line.appendChild(currencyIcon(material.currency));
    }
    line.appendChild(document.createTextNode(label));
  }
  let suffix = "";
  if (material.locked) {
    suffix += " · " + msg("craft_costs_locked", "needs unlock") + " 🔒";
  }
  if (material.timed) {
    suffix += " — " + msg("craft_costs_timed", "timed node");
  }
  if (suffix) {
    line.appendChild(document.createTextNode(suffix));
  }
  return line;
}

function addCraftItem(entry) {
  const listName = document.getElementById("craft-costs-target").value;
  if (!listName) {
    return;
  }
  const data = new FormData();
  data.set("list", listName);
  data.set("item", entry.name);
  data.set("amount", "1");
  fetch("/add", { method: "POST", body: data, keepalive: true })
    .then(function (response) {
      showToast(response.ok
        ? msg("toast_added", "Added: ") + entry.name
        : msg("toast_add_failed", "Adding failed"));
    })
    .catch(function () {
      showToast(msg("toast_add_failed", "Adding failed"));
    });
}

function craftAddButton(entry) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary craft-add";
  button.textContent = msg("add", "Add");
  button.disabled = !document.getElementById("craft-costs-target").value;
  button.addEventListener("click", function () {
    addCraftItem(entry);
  });
  return button;
}

function craftCostRow(entry, rank) {
  const row = document.createElement("div");
  row.className = "timer-entry";

  const info = document.createElement("div");
  const details = document.createElement("div");
  details.className = "muted";
  const jobs = entry.jobs.map(function (job) { return job.name; }).join(", ");
  let scripText = msg("craft_costs_scrips", "{scrips} scrips").replace("{scrips}", entry.scrips);
  if (entry.scrip_paid > 0) {
    scripText = msg("craft_costs_scrips_net", "{scrips} − {paid} paid = {net} scrips")
      .replace("{scrips}", entry.scrips)
      .replace("{paid}", entry.scrip_paid)
      .replace("{net}", entry.net_scrips);
  }
  details.textContent = jobs + " · Lv " + entry.level + " · " + scripText;
  info.appendChild(craftCostName(entry, rank));
  info.appendChild(details);

  const mats = document.createElement("div");
  mats.className = "node-items";
  const score = document.createElement("div");
  score.className = "craft-score";
  score.textContent = msg("craft_costs_score", "{score} effort per scrip")
    .replace("{score}", entry.score.toFixed(2));
  mats.appendChild(score);
  let hasNonCrystal = false;
  let crystalsStarted = false;
  for (const material of entry.materials) {
    const line = craftMaterialLine(material);
    if (material.source === "crystal" && hasNonCrystal && !crystalsStarted) {
      crystalsStarted = true;
      line.classList.add("crystal-split");
    }
    hasNonCrystal = hasNonCrystal || material.source !== "crystal";
    mats.appendChild(line);
  }

  row.appendChild(info);
  row.appendChild(mats);
  row.appendChild(craftAddButton(entry));
  return row;
}

function renderCraftCosts() {
  const list = document.getElementById("craft-costs-list");
  const pager = document.getElementById("craft-costs-pager");
  list.innerHTML = "";
  if (craftCostEntries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = msg("craft_costs_empty", "Nothing matches — check level and job.");
    list.appendChild(empty);
    pager.hidden = true;
    return;
  }
  const pageCount = Math.ceil(craftCostEntries.length / CRAFT_COSTS_PAGE_SIZE);
  craftCostsPage = Math.min(Math.max(craftCostsPage, 1), pageCount);
  const start = (craftCostsPage - 1) * CRAFT_COSTS_PAGE_SIZE;
  let rank = start;
  for (const entry of craftCostEntries.slice(start, start + CRAFT_COSTS_PAGE_SIZE)) {
    rank += 1;
    list.appendChild(craftCostRow(entry, rank));
  }
  pager.hidden = pageCount <= 1;
  document.getElementById("craft-costs-page").textContent = craftCostsPage + " / " + pageCount;
  document.getElementById("craft-costs-prev").disabled = craftCostsPage <= 1;
  document.getElementById("craft-costs-next").disabled = craftCostsPage >= pageCount;
}

function saveCraftCostsSettings() {
  try {
    const settings = craftCostsSettings();
    localStorage.setItem("craft-costs-level", settings.level);
    localStorage.setItem("craft-costs-job", settings.job);
    localStorage.setItem("craft-costs-orange", settings.orange ? "1" : "0");
    localStorage.setItem("craft-costs-gemstone", settings.gemstone ? "1" : "0");
    localStorage.setItem("craft-costs-hide-loot", settings.hideLoot ? "1" : "0");
    localStorage.setItem("craft-costs-hide-locked", settings.hideLocked ? "1" : "0");
  } catch (error) {}
}

function restoreCraftCostsSettings() {
  try {
    const level = localStorage.getItem("craft-costs-level");
    if (level) {
      document.getElementById("craft-costs-level").value = level;
    }
    const job = localStorage.getItem("craft-costs-job");
    if (job) {
      document.getElementById("craft-costs-job").value = job;
    }
    document.getElementById("craft-costs-orange").checked = localStorage.getItem("craft-costs-orange") === "1";
    document.getElementById("craft-costs-gemstone").checked = localStorage.getItem("craft-costs-gemstone") === "1";
    document.getElementById("craft-costs-hide-loot").checked = localStorage.getItem("craft-costs-hide-loot") === "1";
    document.getElementById("craft-costs-hide-locked").checked = localStorage.getItem("craft-costs-hide-locked") === "1";
  } catch (error) {}
}

function setupCraftCosts() {
  const button = document.getElementById("craft-costs-open");
  if (button === null) {
    return;
  }
  const modal = document.getElementById("craft-costs-modal");
  restoreCraftCostsSettings();

  button.addEventListener("click", function () {
    modal.hidden = false;
    fetchCraftCosts();
  });
  document.getElementById("craft-costs-close").addEventListener("click", function () {
    modal.hidden = true;
  });
  const box = modal.querySelector(".modal-box");
  document.getElementById("craft-costs-prev").addEventListener("click", function () {
    craftCostsPage -= 1;
    renderCraftCosts();
    box.scrollTop = 0;
  });
  document.getElementById("craft-costs-next").addEventListener("click", function () {
    craftCostsPage += 1;
    renderCraftCosts();
    box.scrollTop = 0;
  });
  modal.addEventListener("click", function (event) {
    if (event.target === modal) {
      modal.hidden = true;
    }
  });
  for (const id of CRAFT_COSTS_CONTROLS) {
    document.getElementById(id).addEventListener("change", function () {
      saveCraftCostsSettings();
      fetchCraftCosts();
    });
  }
}

setupCraftCosts();

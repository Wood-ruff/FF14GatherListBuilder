let craftCostEntries = [];

const CRAFT_COSTS_CONTROLS = ["craft-costs-level", "craft-costs-job", "craft-costs-orange", "craft-costs-gemstone"];


function craftCostsSettings() {
  return {
    level: document.getElementById("craft-costs-level").value || "100",
    job: document.getElementById("craft-costs-job").value,
    orange: document.getElementById("craft-costs-orange").checked,
    gemstone: document.getElementById("craft-costs-gemstone").checked,
  };
}

function fetchCraftCosts() {
  const settings = craftCostsSettings();
  const params = new URLSearchParams();
  params.set("level", settings.level);
  params.set("job", settings.job);
  params.set("scrips", settings.orange ? "orange" : "purple");
  params.set("gemstones", settings.gemstone ? "unlocked" : "locked");
  fetch("/craft-costs?" + params)
    .then(function (response) { return response.json(); })
    .then(function (entries) {
      craftCostEntries = entries;
      renderCraftCosts();
    })
    .catch(function () {});
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

function craftMaterialLine(material) {
  const line = document.createElement("div");
  line.className = "mat-" + material.source;
  line.appendChild(document.createTextNode(material.amount + "× "));
  line.appendChild(garlandLink(material.name, material.game_id));
  let suffix = "";
  const label = MATERIAL_SOURCE_LABELS[material.source];
  if (label) {
    suffix += " — " + msg(label[0], label[1]);
  }
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

function craftCostRow(entry, rank) {
  const row = document.createElement("div");
  row.className = "timer-entry";

  const info = document.createElement("div");
  const details = document.createElement("div");
  details.className = "muted";
  const jobs = entry.jobs.map(function (job) { return job.name; }).join(", ");
  details.textContent = jobs + " · Lv " + entry.level + " · "
    + msg("craft_costs_scrips", "{scrips} scrips").replace("{scrips}", entry.scrips);
  info.appendChild(craftCostName(entry, rank));
  info.appendChild(details);

  const mats = document.createElement("div");
  mats.className = "node-items";
  const score = document.createElement("div");
  score.className = "craft-score";
  score.textContent = msg("craft_costs_score", "{score} effort per scrip")
    .replace("{score}", entry.score.toFixed(2));
  mats.appendChild(score);
  for (const material of entry.materials) {
    mats.appendChild(craftMaterialLine(material));
  }

  row.appendChild(info);
  row.appendChild(mats);
  return row;
}

function renderCraftCosts() {
  const list = document.getElementById("craft-costs-list");
  list.innerHTML = "";
  if (craftCostEntries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = msg("craft_costs_empty", "Nothing matches — check level and job.");
    list.appendChild(empty);
    return;
  }
  let rank = 0;
  for (const entry of craftCostEntries) {
    rank += 1;
    list.appendChild(craftCostRow(entry, rank));
  }
}

function saveCraftCostsSettings() {
  try {
    const settings = craftCostsSettings();
    localStorage.setItem("craft-costs-level", settings.level);
    localStorage.setItem("craft-costs-job", settings.job);
    localStorage.setItem("craft-costs-orange", settings.orange ? "1" : "0");
    localStorage.setItem("craft-costs-gemstone", settings.gemstone ? "1" : "0");
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

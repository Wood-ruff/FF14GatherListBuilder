let rotationEntries = [];

const ROTATION_CONTROLS = ["rotation-level", "rotation-miner", "rotation-botanist", "rotation-fisher", "rotation-orange"];


function rotationSettings() {
  const jobs = [];
  for (const job of ["miner", "botanist", "fisher"]) {
    if (document.getElementById("rotation-" + job).checked) {
      jobs.push(job);
    }
  }
  return {
    level: document.getElementById("rotation-level").value || "100",
    jobs: jobs,
    orange: document.getElementById("rotation-orange").checked,
  };
}

function fetchRotation() {
  const settings = rotationSettings();
  const params = new URLSearchParams();
  params.set("level", settings.level);
  params.set("jobs", settings.jobs.join(","));
  params.set("scrips", settings.orange ? "orange" : "purple");
  fetch("/rotation?" + params)
    .then(function (response) { return response.json(); })
    .then(function (entries) {
      rotationEntries = entries;
      renderRotation();
    })
    .catch(function () {});
}

const ROTATION_NODES_PER_BATCH = 5;

function rotationNodes() {
  const nodes = new Map();
  for (const entry of rotationEntries) {
    const key = [entry.zone, entry.x, entry.y, entry.job].join("|");
    if (!nodes.has(key)) {
      nodes.set(key, {
        zone: entry.zone,
        x: entry.x,
        y: entry.y,
        aetheryte: entry.aetheryte,
        job: entry.job,
        level: entry.level,
        times: entry.times,
        items: [],
      });
    }
    const node = nodes.get(key);
    node.items.push(entry);
    node.level = Math.max(node.level, entry.level);
  }
  return Array.from(nodes.values());
}

function rotationBatches(now) {
  const batches = new Map();
  for (const node of rotationNodes()) {
    const spawn = nextSpawn(node.times, now);
    const key = spawn.open ? "open" : ((now + spawn.etMinutes) % 1440).toFixed(1);
    if (!batches.has(key)) {
      batches.set(key, { spawn: spawn, nodes: [] });
    }
    batches.get(key).nodes.push(node);
  }
  const sorted = Array.from(batches.values());
  sorted.sort(function (a, b) {
    if (a.spawn.open !== b.spawn.open) {
      return a.spawn.open ? -1 : 1;
    }
    return a.spawn.etMinutes - b.spawn.etMinutes;
  });
  for (const batch of sorted) {
    batch.nodes.sort(function (a, b) {
      return b.level - a.level || (a.zone || "").localeCompare(b.zone || "");
    });
    batch.nodes = batch.nodes.slice(0, ROTATION_NODES_PER_BATCH);
  }
  return sorted;
}

function rotationNodeRow(node) {
  const row = document.createElement("div");
  row.className = "timer-entry";

  const info = document.createElement("div");
  const name = document.createElement("div");
  let label = node.zone || "?";
  if (node.x !== null) {
    label += " (" + node.x + ", " + node.y + ")";
  }
  name.textContent = label;
  const details = document.createElement("div");
  details.className = "muted";
  details.textContent = node.job + " · Lv " + node.level + (node.aetheryte ? " — " + node.aetheryte : "");
  info.appendChild(name);
  info.appendChild(details);

  const itemList = document.createElement("div");
  itemList.className = "node-items";
  for (const item of node.items) {
    const line = document.createElement("div");
    line.textContent = item.name + " (Lv " + item.level + ")";
    itemList.appendChild(line);
  }

  row.appendChild(info);
  row.appendChild(itemList);
  return row;
}

function renderRotation() {
  const modal = document.getElementById("rotation-modal");
  if (modal === null || modal.hidden) {
    return;
  }
  const list = document.getElementById("rotation-list");
  list.innerHTML = "";
  const batches = rotationBatches(eorzeaNowMinutes());
  if (batches.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = msg("rotation_empty", "Nothing matches — check level and professions.");
    list.appendChild(empty);
    return;
  }
  for (const batch of batches) {
    const head = document.createElement("div");
    head.className = batch.spawn.open ? "rotation-batch open" : "rotation-batch";
    const time = formatRealDuration(batch.spawn.etMinutes);
    head.textContent = batch.spawn.open
      ? msg("timer_up", "up now — {time} left").replace("{time}", time)
      : msg("timer_in", "in {time}").replace("{time}", time);
    list.appendChild(head);
    for (const node of batch.nodes) {
      list.appendChild(rotationNodeRow(node));
    }
  }
}

function saveRotationSettings() {
  try {
    const settings = rotationSettings();
    localStorage.setItem("rotation-level", settings.level);
    localStorage.setItem("rotation-jobs", settings.jobs.join(","));
    localStorage.setItem("rotation-orange", settings.orange ? "1" : "0");
  } catch (error) {}
}

function restoreRotationSettings() {
  try {
    const level = localStorage.getItem("rotation-level");
    if (level) {
      document.getElementById("rotation-level").value = level;
    }
    const jobs = localStorage.getItem("rotation-jobs");
    if (jobs !== null) {
      for (const job of ["miner", "botanist", "fisher"]) {
        document.getElementById("rotation-" + job).checked = jobs.split(",").includes(job);
      }
    }
    document.getElementById("rotation-orange").checked = localStorage.getItem("rotation-orange") === "1";
  } catch (error) {}
}

function setupRotation() {
  const button = document.getElementById("rotation-open");
  if (button === null) {
    return;
  }
  const modal = document.getElementById("rotation-modal");
  restoreRotationSettings();

  button.addEventListener("click", function () {
    modal.hidden = false;
    fetchRotation();
  });
  document.getElementById("rotation-close").addEventListener("click", function () {
    modal.hidden = true;
  });
  modal.addEventListener("click", function (event) {
    if (event.target === modal) {
      modal.hidden = true;
    }
  });
  for (const id of ROTATION_CONTROLS) {
    document.getElementById(id).addEventListener("change", function () {
      saveRotationSettings();
      fetchRotation();
    });
  }
}

setupRotation();

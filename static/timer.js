const REAL_MS_PER_ET_MINUTE = 175000 / 60;
const ET_MINUTES_PER_DAY = 1440;

function eorzeaNowMinutes() {
  return (Date.now() / REAL_MS_PER_ET_MINUTE) % ET_MINUTES_PER_DAY;
}

function nextSpawn(times, now) {
  let shortestWait = null;
  for (const time of times) {
    const sinceStart = (now - time.start + ET_MINUTES_PER_DAY) % ET_MINUTES_PER_DAY;
    if (sinceStart < time.duration) {
      return { open: true, etMinutes: time.duration - sinceStart };
    }
    const wait = (time.start - now + ET_MINUTES_PER_DAY) % ET_MINUTES_PER_DAY;
    if (shortestWait === null || wait < shortestWait) {
      shortestWait = wait;
    }
  }
  return { open: false, etMinutes: shortestWait };
}

function formatRealDuration(etMinutes) {
  const totalSeconds = Math.max(0, Math.floor((etMinutes * REAL_MS_PER_ET_MINUTE) / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return minutes + "m " + seconds + "s";
}

let alarmSound = null;
let firstTimerRun = true;

function alarmEnabled() {
  try {
    return localStorage.getItem("alarm") === "on";
  } catch (error) {
    return false;
  }
}

function loadAlarmSound() {
  const select = document.getElementById("alarm-sound");
  alarmSound = new Audio("/static/alarms/" + select.value);
  alarmSound.volume = 0.25;
}

function playAlarm() {
  if (!alarmSound) {
    return;
  }
  alarmSound.currentTime = 0;
  alarmSound.play().catch(function () {});
}

function restoreAlarmSoundChoice(select) {
  let saved = null;
  try {
    saved = localStorage.getItem("alarmSound");
  } catch (error) {}
  const options = Array.from(select.options).map(function (option) { return option.value; });
  if (saved && options.includes(saved)) {
    select.value = saved;
  }
}

let preAlarmSound = null;

function preAlarmOn() {
  const toggle = document.getElementById("prealarm-toggle");
  return toggle !== null && toggle.checked;
}

function preAlarmThresholdMs() {
  const field = document.getElementById("prealarm-minutes");
  const minutes = field ? Number(field.value) : 0;
  return minutes > 0 ? minutes * 60000 : 0;
}

function loadPreAlarmSound() {
  const select = document.getElementById("prealarm-sound");
  if (select === null || !select.value) {
    return;
  }
  preAlarmSound = new Audio("/static/alarms/" + select.value);
  preAlarmSound.volume = 0.25;
}

function playPreAlarm() {
  if (preAlarmSound === null) {
    return;
  }
  preAlarmSound.currentTime = 0;
  preAlarmSound.play().catch(function () {});
}

function setupPreAlarm() {
  const toggle = document.getElementById("prealarm-toggle");
  if (toggle === null) {
    return;
  }
  const minutes = document.getElementById("prealarm-minutes");
  const select = document.getElementById("prealarm-sound");

  try {
    toggle.checked = localStorage.getItem("prealarm") === "on";
    const savedMinutes = localStorage.getItem("prealarm-minutes");
    if (savedMinutes) {
      minutes.value = savedMinutes;
    }
    const savedSound = localStorage.getItem("prealarm-sound");
    if (savedSound && Array.from(select.options).some(function (o) { return o.value === savedSound; })) {
      select.value = savedSound;
    }
  } catch (error) {}
  loadPreAlarmSound();

  toggle.addEventListener("change", function () {
    try { localStorage.setItem("prealarm", toggle.checked ? "on" : "off"); } catch (error) {}
  });
  minutes.addEventListener("change", function () {
    try { localStorage.setItem("prealarm-minutes", minutes.value); } catch (error) {}
  });
  select.addEventListener("change", function () {
    try { localStorage.setItem("prealarm-sound", select.value); } catch (error) {}
    loadPreAlarmSound();
    playPreAlarm();
  });
}

function setupAlarmToggle() {
  const toggle = document.getElementById("alarm-toggle");
  const select = document.getElementById("alarm-sound");
  toggle.value = alarmEnabled() ? "on" : "off";
  toggle.addEventListener("change", function () {
    try {
      localStorage.setItem("alarm", toggle.value);
    } catch (error) {}
  });

  restoreAlarmSoundChoice(select);
  if (select.value) {
    loadAlarmSound();
  }
  select.addEventListener("change", function () {
    try {
      localStorage.setItem("alarmSound", select.value);
    } catch (error) {}
    loadAlarmSound();
    playAlarm();
  });

  document.getElementById("alarm-test").addEventListener("click", playAlarm);
}

function alarmEligible(timer) {
  if (timer.dataset.alarm === "1") {
    return !alarmSuppressed(timer);
  }
  return alarmMarked(timer);
}

function checkPreWarning(timer, spawn) {
  if (spawn.open || !preAlarmOn() || !alarmEligible(timer)) {
    timer.dataset.preWarned = "0";
    return false;
  }
  const waitMs = spawn.etMinutes * REAL_MS_PER_ET_MINUTE;
  if (waitMs > preAlarmThresholdMs()) {
    timer.dataset.preWarned = "0";
    return false;
  }
  if (timer.dataset.preWarned === "1") {
    return false;
  }
  timer.dataset.preWarned = "1";
  return true;
}

function alarmMarked(timer) {
  if (typeof window.markedAlarmsOn !== "function" || !window.markedAlarmsOn()) {
    return false;
  }
  const row = timer.closest("tr");
  const mark = row ? row.querySelector(".alarm-mark") : null;
  return mark !== null && mark.checked;
}

function alarmSuppressed(timer) {
  const row = timer.closest("tr");
  if (!row) {
    return false;
  }
  const mute = row.querySelector(".mute-toggle");
  const done = row.querySelector(".done-toggle");
  return (mute !== null && mute.checked) || (done !== null && done.checked);
}

function updateTimers() {
  const now = eorzeaNowMinutes();
  let justOpened = false;
  let justWarned = false;
  for (const timer of document.querySelectorAll(".node-timer")) {
    const spawn = nextSpawn(JSON.parse(timer.dataset.times), now);
    const time = formatRealDuration(spawn.etMinutes);
    if (checkPreWarning(timer, spawn)) {
      justWarned = true;
    }
    if (spawn.open) {
      timer.textContent = msg("timer_up", "up now — {time} left").replace("{time}", time);
      timer.classList.add("open");
      if (timer.dataset.wasOpen !== "1") {
        timer.dataset.wasOpen = "1";
        if (alarmEligible(timer)) {
          justOpened = true;
        }
      }
    } else {
      timer.textContent = msg("timer_in", "in {time}").replace("{time}", time);
      timer.classList.remove("open");
      timer.dataset.wasOpen = "0";
    }
  }
  if (!firstTimerRun) {
    if (justOpened && alarmEnabled()) {
      playAlarm();
    } else if (justWarned) {
      playPreAlarm();
    }
  }
  firstTimerRun = false;
  renderTimersOverview();
  if (typeof renderRotation === "function") {
    renderRotation();
  }
}

function openModal(title, body) {
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-body").textContent = body;
  document.getElementById("modal").hidden = false;
}

function closeModal() {
  document.getElementById("modal").hidden = true;
}

function setupModal() {
  const modal = document.getElementById("modal");
  document.getElementById("modal-close").addEventListener("click", closeModal);
  modal.addEventListener("click", function (event) {
    if (event.target === modal) {
      closeModal();
    }
  });
}

function locationBody(element) {
  const lines = [];
  if (element.dataset.x) {
    lines.push("(" + element.dataset.x + ", " + element.dataset.y + ")");
  }
  const aetheryte = element.dataset.aetheryte;
  lines.push(aetheryte
    ? msg("modal_aetheryte", "Closest aetheryte: ") + aetheryte
    : msg("modal_no_aetheryte", "No aetheryte data"));
  return lines.join("\n");
}

function collectTimerEntries(now) {
  const entries = [];
  for (const timer of document.querySelectorAll(".node-timer")) {
    const row = timer.closest("tr");
    const nameElement = row ? row.querySelector(".copy-name") : null;
    const amountField = row ? row.querySelector('input[name="amount"]') : null;
    entries.push({
      name: nameElement ? nameElement.dataset.name : "?",
      amount: amountField ? amountField.value : "",
      spawn: nextSpawn(JSON.parse(timer.dataset.times), now),
      zone: timer.dataset.zone,
      x: timer.dataset.x,
      y: timer.dataset.y,
      aetheryte: timer.dataset.aetheryte,
    });
  }
  entries.sort(function (a, b) {
    if (a.spawn.open !== b.spawn.open) {
      return a.spawn.open ? -1 : 1;
    }
    if (a.spawn.open) {
      return b.spawn.etMinutes - a.spawn.etMinutes;
    }
    return a.spawn.etMinutes - b.spawn.etMinutes;
  });
  return entries;
}

function timerEntryLocation(entry) {
  let text = entry.zone || "?";
  if (entry.x) {
    text += " (" + entry.x + ", " + entry.y + ")";
  }
  if (entry.aetheryte) {
    text += " — " + entry.aetheryte;
  }
  return text;
}

function renderTimersOverview() {
  const modal = document.getElementById("timers-modal");
  if (modal === null || modal.hidden) {
    return;
  }
  const list = document.getElementById("timers-list");
  list.innerHTML = "";
  const entries = collectTimerEntries(eorzeaNowMinutes());
  if (entries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = msg("no_timed_items", "No timed items in this list.");
    list.appendChild(empty);
    return;
  }
  for (const entry of entries) {
    const row = document.createElement("div");
    row.className = entry.spawn.open ? "timer-entry open" : "timer-entry";

    const info = document.createElement("div");
    const name = document.createElement("div");
    name.textContent = entry.amount ? entry.name + " (" + entry.amount + ")" : entry.name;
    const location = document.createElement("div");
    location.className = "muted";
    location.textContent = timerEntryLocation(entry);
    info.appendChild(name);
    info.appendChild(location);

    const when = document.createElement("div");
    when.className = "when";
    const time = formatRealDuration(entry.spawn.etMinutes);
    when.textContent = entry.spawn.open
      ? msg("timer_up", "up now — {time} left").replace("{time}", time)
      : msg("timer_in", "in {time}").replace("{time}", time);

    row.appendChild(info);
    row.appendChild(when);
    list.appendChild(row);
  }
}

function setupTimersOverview() {
  const button = document.getElementById("timers-overview");
  if (button === null) {
    return;
  }
  const modal = document.getElementById("timers-modal");
  button.addEventListener("click", function () {
    modal.hidden = false;
    renderTimersOverview();
  });
  document.getElementById("timers-close").addEventListener("click", function () {
    modal.hidden = true;
  });
  modal.addEventListener("click", function (event) {
    if (event.target === modal) {
      modal.hidden = true;
    }
  });
}

function setupTimerClicks() {
  for (const element of document.querySelectorAll(".node-timer, .node-location")) {
    element.addEventListener("click", function () {
      openModal(element.dataset.zone, locationBody(element));
    });
  }
}

function startTicking() {
  try {
    const worker = new Worker("/static/timer-worker.js");
    worker.onmessage = function () {
      updateTimers();
    };
  } catch (error) {
    setInterval(updateTimers, 1000);
  }
}

setupModal();
setupAlarmToggle();
setupPreAlarm();
setupTimersOverview();
setupTimerClicks();
updateTimers();
startTicking();

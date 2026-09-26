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
  const seconds = totalSeconds % 60;
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

function updateTimers() {
  const now = eorzeaNowMinutes();
  let justOpened = false;
  for (const timer of document.querySelectorAll(".node-timer")) {
    const spawn = nextSpawn(JSON.parse(timer.dataset.times), now);
    if (spawn.open) {
      timer.textContent = "up now — " + formatRealDuration(spawn.etMinutes) + " left";
      timer.classList.add("open");
      if (timer.dataset.wasOpen !== "1") {
        timer.dataset.wasOpen = "1";
        justOpened = true;
      }
    } else {
      timer.textContent = "in " + formatRealDuration(spawn.etMinutes);
      timer.classList.remove("open");
      timer.dataset.wasOpen = "0";
    }
  }
  if (justOpened && !firstTimerRun && alarmEnabled()) {
    playAlarm();
  }
  firstTimerRun = false;
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

function setupTimerClicks() {
  for (const timer of document.querySelectorAll(".node-timer")) {
    timer.addEventListener("click", function () {
      const aetheryte = timer.dataset.aetheryte;
      const body = aetheryte ? "Closest aetheryte: " + aetheryte : "No aetheryte data";
      openModal(timer.dataset.zone, body);
    });
  }
}

setupModal();
setupAlarmToggle();
setupTimerClicks();
updateTimers();
setInterval(updateTimers, 1000);

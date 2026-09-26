const markedAlarmToggle = document.getElementById("marked-alarm-toggle");

window.markedAlarmsOn = function () {
  return markedAlarmToggle !== null && markedAlarmToggle.checked;
};

function loadAlarmMarks() {
  try {
    return JSON.parse(localStorage.getItem("alarm-marks") || "[]");
  } catch (error) {
    return [];
  }
}

function saveAlarmMark(id, marked) {
  try {
    const ids = new Set(loadAlarmMarks());
    if (marked) {
      ids.add(id);
    } else {
      ids.delete(id);
    }
    localStorage.setItem("alarm-marks", JSON.stringify(Array.from(ids)));
  } catch (error) {}
}

function applyMarkedFilter() {
  const only = document.getElementById("marked-filter").value === "marked";
  for (const mark of document.querySelectorAll(".alarm-mark")) {
    mark.closest("tr").hidden = only && !mark.checked;
  }
}

function setupAlarmMarks() {
  if (markedAlarmToggle === null) {
    return;
  }
  const saved = new Set(loadAlarmMarks());
  for (const mark of document.querySelectorAll(".alarm-mark")) {
    mark.checked = saved.has(mark.dataset.id);
    mark.addEventListener("change", function () {
      saveAlarmMark(mark.dataset.id, mark.checked);
      applyMarkedFilter();
    });
  }

  try {
    markedAlarmToggle.checked = localStorage.getItem("marked-alarms") === "on";
  } catch (error) {}
  markedAlarmToggle.addEventListener("change", function () {
    try {
      localStorage.setItem("marked-alarms", markedAlarmToggle.checked ? "on" : "off");
    } catch (error) {}
  });

  document.getElementById("marked-filter").addEventListener("change", applyMarkedFilter);
}

setupAlarmMarks();

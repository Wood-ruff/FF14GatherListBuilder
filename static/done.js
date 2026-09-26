function sendFlag(box, url, field) {
  const body = new URLSearchParams();
  body.set("list", box.dataset.list);
  body.set("id", box.dataset.id);
  body.set(field, box.checked ? "1" : "0");
  fetch(url, { method: "POST", body: body, keepalive: true })
    .catch(function () {});
}

function setupDoneToggle(box) {
  box.addEventListener("change", function () {
    box.closest("tr").classList.toggle("done", box.checked);
    sendFlag(box, "/toggle-done", "done");
  });
}

function setupFlagToggle(box, url, field) {
  box.addEventListener("change", function () {
    sendFlag(box, url, field);
  });
}

for (const box of document.querySelectorAll(".done-toggle")) {
  setupDoneToggle(box);
}

for (const box of document.querySelectorAll(".mute-toggle")) {
  setupFlagToggle(box, "/toggle-mute", "muted");
}

for (const box of document.querySelectorAll(".materials-toggle")) {
  setupFlagToggle(box, "/toggle-materials", "added");
}

function setupMaterialButtons() {
  const buttons = Array.from(document.querySelectorAll('button[form^="mats-"]'));
  for (const button of buttons) {
    const form = document.getElementById(button.getAttribute("form"));
    if (!form) {
      continue;
    }
    form.addEventListener("submit", function () {
      for (const each of buttons) {
        each.disabled = true;
      }
      const toggle = button.closest("tr").querySelector(".materials-toggle");
      if (toggle) {
        toggle.checked = true;
      }
    });
  }
}

setupMaterialButtons();

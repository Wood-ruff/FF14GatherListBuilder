function saveNote(field) {
  const body = new URLSearchParams();
  body.set("list", field.dataset.list);
  body.set("id", field.dataset.id);
  body.set("note", field.value);
  fetch("/set-note", { method: "POST", body: body, keepalive: true })
    .catch(function () {});
}

function setupNoteField(field) {
  let noteTimer = null;
  field.addEventListener("input", function () {
    clearTimeout(noteTimer);
    noteTimer = setTimeout(function () { saveNote(field); }, 600);
  });
  field.addEventListener("change", function () {
    clearTimeout(noteTimer);
    saveNote(field);
  });
}

function saveAmount(field) {
  const form = document.getElementById(field.getAttribute("form"));
  if (form === null || field.value === "" || Number(field.value) < 1) {
    return;
  }
  fetch(form.action, { method: "POST", body: new FormData(form), keepalive: true })
    .catch(function () {});
}

function setupAmountField(field) {
  let amountTimer = null;
  field.addEventListener("input", function () {
    clearTimeout(amountTimer);
    amountTimer = setTimeout(function () { saveAmount(field); }, 600);
  });
  field.addEventListener("change", function () {
    clearTimeout(amountTimer);
    saveAmount(field);
  });
}

function setupTrailToggle() {
  const toggle = document.getElementById("trail-toggle");
  const table = document.querySelector(".pin-table");
  if (toggle === null || table === null) {
    return;
  }
  let collapsed = true;
  try {
    collapsed = localStorage.getItem("list-trail-collapsed") !== "0";
  } catch (error) {}

  function apply() {
    table.classList.toggle("collapsed", collapsed);
    toggle.textContent = collapsed ? "⇤" : "⇥";
  }

  toggle.addEventListener("click", function () {
    collapsed = !collapsed;
    try {
      localStorage.setItem("list-trail-collapsed", collapsed ? "1" : "0");
    } catch (error) {}
    apply();
  });
  apply();
}

for (const field of document.querySelectorAll(".note-field")) {
  setupNoteField(field);
}

for (const field of document.querySelectorAll('input[name="amount"][form^="edit-"]')) {
  setupAmountField(field);
}

setupTrailToggle();

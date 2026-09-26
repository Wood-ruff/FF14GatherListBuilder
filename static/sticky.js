function updateStickyOffsets() {
  let offset = 0;
  for (const row of document.querySelectorAll("tbody tr.sticky")) {
    for (const cell of row.children) {
      cell.style.top = offset + "px";
    }
    offset += row.offsetHeight;
  }
}

function persistSticky(button, sticky) {
  if (button.dataset.store) {
    saveLocalSticky(button.dataset.store, button.dataset.id, sticky);
    return;
  }
  const body = new URLSearchParams();
  body.set("list", button.dataset.list);
  body.set("id", button.dataset.id);
  body.set("sticky", sticky ? "1" : "0");
  fetch("/toggle-sticky", { method: "POST", body: body, keepalive: true })
    .catch(function () {});
}

function loadLocalSticky(store) {
  try {
    return JSON.parse(localStorage.getItem("sticky-" + store) || "[]");
  } catch (error) {
    return [];
  }
}

function saveLocalSticky(store, id, sticky) {
  try {
    const ids = new Set(loadLocalSticky(store));
    if (sticky) {
      ids.add(id);
    } else {
      ids.delete(id);
    }
    localStorage.setItem("sticky-" + store, JSON.stringify(Array.from(ids)));
  } catch (error) {}
}

function restoreLocalSticky() {
  const stores = {};
  for (const button of document.querySelectorAll(".sticky-toggle[data-store]")) {
    const store = button.dataset.store;
    if (!(store in stores)) {
      stores[store] = loadLocalSticky(store);
    }
    if (stores[store].includes(button.dataset.id)) {
      button.closest("tr").classList.add("sticky");
    }
  }
}

function setupStickyToggles() {
  for (const button of document.querySelectorAll(".sticky-toggle")) {
    button.addEventListener("click", function () {
      const sticky = button.closest("tr").classList.toggle("sticky");
      persistSticky(button, sticky);
      updateStickyOffsets();
    });
  }
}

restoreLocalSticky();
setupStickyToggles();
updateStickyOffsets();

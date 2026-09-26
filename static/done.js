function setupDoneToggle(box) {
  box.addEventListener("change", function () {
    box.closest("tr").classList.toggle("done", box.checked);
    const body = new URLSearchParams();
    body.set("list", box.dataset.list);
    body.set("id", box.dataset.id);
    body.set("done", box.checked ? "1" : "0");
    fetch("/toggle-done", { method: "POST", body: body, keepalive: true })
      .catch(function () {});
  });
}

for (const box of document.querySelectorAll(".done-toggle")) {
  setupDoneToggle(box);
}

function setupBackgroundAdd(form) {
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    const item = form.querySelector('input[name="item"]').value;
    const doneMessage = form.dataset.doneMessage || msg("toast_added", "Added: ");
    fetch(form.action, { method: "POST", body: new FormData(form), keepalive: true })
      .then(function (response) {
        showToast(response.ok ? doneMessage + item : msg("toast_add_failed", "Adding failed"));
        watchPendingAdds();
      })
      .catch(function () {
        showToast(msg("toast_add_failed", "Adding failed"));
      });
  });
}

for (const form of document.querySelectorAll(".background-add")) {
  setupBackgroundAdd(form);
}

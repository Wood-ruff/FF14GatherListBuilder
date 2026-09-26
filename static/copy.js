const TOAST_DURATION_MS = 5000;

let toastTimer = null;

function setupCopyName(element) {
  element.addEventListener("click", function () {
    navigator.clipboard.writeText(element.dataset.name).then(function () {
      showToast("Item copied to clipboard — paste in chat and press Tab for a link");
    });
  });
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () {
    toast.classList.remove("show");
  }, TOAST_DURATION_MS);
}

for (const element of document.querySelectorAll(".copy-name")) {
  setupCopyName(element);
}

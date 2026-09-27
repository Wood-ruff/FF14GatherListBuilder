const TOAST_DURATION_MS = 5000;

let toastTimer = null;

function setupCopyName(element) {
  element.addEventListener("click", function () {
    navigator.clipboard.writeText(element.dataset.name).then(function () {
      showToast(msg("toast_copied", "Item copied to clipboard"));
    });
  });
}

function showToast(message) {
  displayToast(message, TOAST_DURATION_MS);
  try {
    sessionStorage.setItem("toast-message", message);
    sessionStorage.setItem("toast-until", String(Date.now() + TOAST_DURATION_MS));
  } catch (error) {}
}

function displayToast(message, duration) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () {
    toast.classList.remove("show");
  }, duration);
}

function restoreToast() {
  try {
    const remaining = Number(sessionStorage.getItem("toast-until")) - Date.now();
    if (remaining > 0) {
      displayToast(sessionStorage.getItem("toast-message") || "", remaining);
    }
  } catch (error) {}
}

for (const element of document.querySelectorAll(".copy-name")) {
  setupCopyName(element);
}

restoreToast();

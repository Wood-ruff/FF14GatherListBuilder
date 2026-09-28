const FETCHING_ACTIONS = [
  "/add", "/craft", "/add-materials", "/collectables/add", "/craftables/add",
  "/language", "/import", "/refetch-list", "/add-all-materials", "/refresh-prices",
];

const FETCHING_TOAST_MS = 30000;

function showFetchingToast() {
  displayToast(msg("toast_fetching", "Fetching game data…"), FETCHING_TOAST_MS);
}

function setupTabToast(tab) {
  tab.addEventListener("click", function (event) {
    if (!event.ctrlKey && !event.metaKey && !event.shiftKey && event.button === 0) {
      showFetchingToast();
    }
  });
}

function watchFetchingActions() {
  for (const form of document.querySelectorAll("form")) {
    if (FETCHING_ACTIONS.includes(form.getAttribute("action"))) {
      form.addEventListener("submit", showFetchingToast);
    }
  }
  for (const tab of document.querySelectorAll(".tabs .tab")) {
    setupTabToast(tab);
  }
}

watchFetchingActions();

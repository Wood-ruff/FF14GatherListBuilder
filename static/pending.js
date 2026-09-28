let watchingAdds = false;
let sawPendingAdds = false;

function watchPendingAdds() {
  if (watchingAdds) {
    return;
  }
  watchingAdds = true;
  pollPendingAdds();
}

function pollPendingAdds() {
  fetch("/pending")
    .then(function (response) { return response.json(); })
    .then(function (count) {
      if (count > 0) {
        sawPendingAdds = true;
        showBackgroundWorkingToast();
        setTimeout(pollPendingAdds, 2000);
      } else {
        watchingAdds = false;
        if (sawPendingAdds) {
          finishPendingAdds();
        }
      }
    })
    .catch(function () {
      watchingAdds = false;
    });
}

function showBackgroundWorkingToast() {
  const toast = document.getElementById("toast");
  if (!toast.classList.contains("show")) {
    displayToast(msg("toast_background_working", "Fetching data in the background…"), 2500);
  }
}

function finishPendingAdds() {
  sawPendingAdds = false;
  if (window.reloadWhenAddsFinish) {
    try {
      sessionStorage.setItem("addsFinished", "1");
    } catch (error) {}
    location.reload();
  } else {
    showToast(msg("toast_background_done", "Background adding finished"));
  }
}

function showFinishedToastAfterReload() {
  try {
    if (sessionStorage.getItem("addsFinished")) {
      sessionStorage.removeItem("addsFinished");
      showToast(msg("toast_background_done_reload", "Background adding finished — list updated"));
    }
    if (sessionStorage.getItem("fetchFinished")) {
      sessionStorage.removeItem("fetchFinished");
      showToast(msg("toast_fetch_done_reload", "Game data fetched — view updated"));
    }
  } catch (error) {}
}

let sawRunningFetch = false;

function watchServerFetches() {
  fetch("/fetching")
    .then(function (response) { return response.json(); })
    .then(function (running) {
      if (running) {
        sawRunningFetch = true;
      } else if (sawRunningFetch) {
        sawRunningFetch = false;
        refreshAfterFetch();
      }
      setTimeout(watchServerFetches, 3000);
    })
    .catch(function () {
      setTimeout(watchServerFetches, 10000);
    });
}

function refreshAfterFetch() {
  if (document.querySelector(".modal:not([hidden])")) {
    return;
  }
  try {
    sessionStorage.setItem("fetchFinished", "1");
  } catch (error) {}
  location.reload();
}

showFinishedToastAfterReload();
watchPendingAdds();
watchServerFetches();

const PINNABLE_MODALS = {
  "timers-modal": function () {
    document.getElementById("timers-modal").hidden = false;
    renderTimersOverview();
  },
  "sources-modal": function (context) {
    openSources(context.item);
  },
  "rotation-modal": function () {
    document.getElementById("rotation-modal").hidden = false;
    fetchRotation();
  },
  "craft-costs-modal": function () {
    document.getElementById("craft-costs-modal").hidden = false;
    fetchCraftCosts();
  },
};

const DRAG_HANDLE_HEIGHT = 48;

function loadPinnedPopups() {
  try {
    return JSON.parse(localStorage.getItem("pinned-popups")) || {};
  } catch (error) {
    return {};
  }
}

function storePinnedPopups(state) {
  try {
    localStorage.setItem("pinned-popups", JSON.stringify(state));
  } catch (error) {}
}

function modalContext(modal) {
  if (modal.id === "sources-modal") {
    return { list: modal.dataset.list, item: modal.dataset.itemId };
  }
  return null;
}

function contextMatches(modal, context) {
  if (modal.id !== "sources-modal") {
    return true;
  }
  return Boolean(context && context.item && context.list === modal.dataset.list);
}

function rememberPin(modal, box) {
  const state = loadPinnedPopups();
  const entry = { context: modalContext(modal) };
  if (box.style.position === "fixed") {
    entry.x = parseFloat(box.style.left);
    entry.y = parseFloat(box.style.top);
  }
  state[modal.id] = entry;
  storePinnedPopups(state);
}

function forgetPin(modal) {
  const state = loadPinnedPopups();
  delete state[modal.id];
  storePinnedPopups(state);
}

function setPinned(modal, pin, pinned) {
  modal.classList.toggle("pinned", pinned);
  pin.classList.toggle("active", pinned);
  for (const button of modal.querySelectorAll("button[id$='-close']")) {
    button.disabled = pinned;
  }
}

function placeModalBox(box, x, y) {
  box.style.position = "fixed";
  box.style.left = Math.max(0, Math.min(x, window.innerWidth - 100)) + "px";
  box.style.top = Math.max(0, Math.min(y, window.innerHeight - 60)) + "px";
  box.style.margin = "0";
}

function startModalDrag(modal, box, event, rect) {
  event.preventDefault();
  const offsetX = event.clientX - rect.left;
  const offsetY = event.clientY - rect.top;

  function move(moveEvent) {
    placeModalBox(box, moveEvent.clientX - offsetX, moveEvent.clientY - offsetY);
  }

  function stop() {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", stop);
    if (modal.classList.contains("pinned")) {
      rememberPin(modal, box);
    }
  }

  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", stop);
}

function setupModalDrag(modal, box) {
  box.addEventListener("pointerdown", function (event) {
    if (event.target.closest("button, input, select, a, img")) {
      return;
    }
    const rect = box.getBoundingClientRect();
    if (event.clientY - rect.top > DRAG_HANDLE_HEIGHT) {
      return;
    }
    startModalDrag(modal, box, event, rect);
  });
}

function setupModalPin(modal) {
  const box = modal.querySelector(".modal-box");
  if (box === null) {
    return;
  }
  const pin = document.createElement("button");
  pin.type = "button";
  pin.className = "modal-pin";
  pin.textContent = "📌";
  pin.title = msg("pin_popup", "Pin popup — it stays open and the page stays usable");
  pin.addEventListener("click", function () {
    const pinned = !modal.classList.contains("pinned");
    setPinned(modal, pin, pinned);
    if (pinned) {
      rememberPin(modal, box);
    } else {
      forgetPin(modal);
    }
  });
  box.prepend(pin);
  setupModalDrag(modal, box);
}

function restorePinnedPopups() {
  const state = loadPinnedPopups();
  for (const modalId of Object.keys(PINNABLE_MODALS)) {
    const saved = state[modalId];
    const modal = document.getElementById(modalId);
    if (!saved || modal === null || !contextMatches(modal, saved.context)) {
      continue;
    }
    const box = modal.querySelector(".modal-box");
    if (typeof saved.x === "number") {
      placeModalBox(box, saved.x, saved.y);
    }
    PINNABLE_MODALS[modalId](saved.context);
    setPinned(modal, box.querySelector(".modal-pin"), true);
  }
}

for (const modalId of Object.keys(PINNABLE_MODALS)) {
  const modal = document.getElementById(modalId);
  if (modal !== null) {
    setupModalPin(modal);
  }
}

window.addEventListener("load", restorePinnedPopups);

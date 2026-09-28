const SUGGEST_DELAY_MS = 1000;
const SUGGEST_MIN_LENGTH = 3;
const QUICK_ADD_AMOUNTS = [1, 2, 5, 10];

function setupSuggestBox(box) {
  const form = box.closest("form");
  const input = box.querySelector("input");
  const toggle = box.querySelector(".suggest-toggle");
  const list = box.querySelector(".suggest-list");
  let timer = null;
  let lastQuery = "";

  input.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(fetchSuggestions, SUGGEST_DELAY_MS);
  });

  toggle.addEventListener("click", function () {
    list.hidden = !list.hidden || list.children.length === 0;
  });

  document.addEventListener("click", function (event) {
    if (!box.contains(event.target)) {
      list.hidden = true;
    }
  });

  function fetchSuggestions() {
    const query = input.value.trim();
    if (query.length < SUGGEST_MIN_LENGTH) {
      return;
    }
    if (query === lastQuery) {
      list.hidden = list.children.length === 0;
      return;
    }
    lastQuery = query;
    fetch("/suggest?q=" + encodeURIComponent(query))
      .then(function (response) { return response.json(); })
      .then(showSuggestions);
  }

  function showSuggestions(names) {
    list.innerHTML = "";
    for (const name of names) {
      list.appendChild(buildOption(name));
    }
    list.hidden = names.length === 0;
  }

  function buildOption(name) {
    const option = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = name;
    option.appendChild(label);
    for (const amount of QUICK_ADD_AMOUNTS) {
      option.appendChild(buildQuickAddButton(name, amount));
    }
    option.addEventListener("click", function () {
      input.value = name;
      list.hidden = true;
    });
    return option;
  }

  function buildQuickAddButton(name, amount) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "suggest-quick-add";
    button.textContent = "+" + amount;
    button.title = msg("suggest_quick_add_title", "Add this amount to the list");
    button.addEventListener("click", function (event) {
      event.stopPropagation();
      quickAdd(name, amount);
    });
    return button;
  }

  function quickAdd(name, amount) {
    input.value = name;
    form.querySelector('input[name="amount"]').value = amount;
    list.hidden = true;
    form.requestSubmit();
  }
}

for (const box of document.querySelectorAll(".suggest-box")) {
  setupSuggestBox(box);
}

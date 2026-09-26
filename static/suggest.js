const SUGGEST_DELAY_MS = 2000;
const SUGGEST_MIN_LENGTH = 3;

function setupSuggestBox(box) {
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
    option.textContent = name;
    option.addEventListener("click", function () {
      input.value = name;
      list.hidden = true;
    });
    return option;
  }
}

for (const box of document.querySelectorAll(".suggest-box")) {
  setupSuggestBox(box);
}

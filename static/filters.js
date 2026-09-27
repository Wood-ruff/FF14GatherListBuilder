const FILTER_TYPE_DELAY_MS = 600;

function setupLiveFilters(form) {
  let filterTimer = null;

  for (const field of Array.from(form.elements)) {
    if (field.matches('select, input[type="checkbox"]')) {
      field.addEventListener("change", function () {
        form.submit();
      });
    } else if (field.matches('input[type="number"], input[name="q"]')) {
      field.addEventListener("input", function () {
        clearTimeout(filterTimer);
        filterTimer = setTimeout(function () { form.submit(); }, FILTER_TYPE_DELAY_MS);
      });
    }
  }
}

function refocusNameFilter(form) {
  const field = form.querySelector('input[name="q"]');
  if (field && field.value) {
    const end = field.value.length;
    field.focus();
    field.setSelectionRange(end, end);
  }
}

for (const form of document.querySelectorAll(".filters")) {
  setupLiveFilters(form);
  refocusNameFilter(form);
}

for (const button of document.querySelectorAll(".refresh-page")) {
  button.addEventListener("click", function () {
    location.reload();
  });
}

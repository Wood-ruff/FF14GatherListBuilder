const FILTER_TYPE_DELAY_MS = 600;

function setupLiveFilters(form) {
  let filterTimer = null;

  form.addEventListener("change", function (event) {
    if (event.target.matches("select")) {
      form.submit();
    }
  });

  form.addEventListener("input", function (event) {
    if (event.target.matches('input[type="number"], input[name="q"]')) {
      clearTimeout(filterTimer);
      filterTimer = setTimeout(function () { form.submit(); }, FILTER_TYPE_DELAY_MS);
    }
  });
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

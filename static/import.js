const importCorner = document.querySelector(".import-corner");
const importPanel = document.getElementById("import-panel");

document.getElementById("import-open").addEventListener("click", function () {
  importPanel.hidden = !importPanel.hidden;
});

document.getElementById("import-close").addEventListener("click", function () {
  importPanel.hidden = true;
});

document.addEventListener("click", function (event) {
  if (!importCorner.contains(event.target)) {
    importPanel.hidden = true;
  }
});

const PRICE_CHUNK_SIZE = 25;

function setupListPrices() {
  const table = document.querySelector(".pin-table");
  const worldSelect = document.getElementById("list-prices-world");
  const toggle = document.getElementById("trail-toggle");
  const cells = document.querySelectorAll(".listing-price");
  if (table === null || worldSelect === null || cells.length === 0) {
    return;
  }
  let loadedWorld = null;

  restoreWorld();
  worldSelect.addEventListener("change", function () {
    saveWorld(worldSelect.value);
    loadPrices();
  });
  if (toggle !== null) {
    toggle.addEventListener("click", loadPrices);
  }
  loadPrices();

  function loadPrices() {
    const world = worldSelect.value;
    if (!world || world === loadedWorld || table.classList.contains("collapsed")) {
      return;
    }
    loadedWorld = world;
    clearPrices();
    fetchPriceChunks(world, chunkedIds(), 0);
  }

  function fetchPriceChunks(world, chunks, index) {
    if (index >= chunks.length || world !== loadedWorld) {
      return;
    }
    const params = new URLSearchParams({
      list: worldSelect.dataset.list,
      world: world,
      ids: chunks[index].join(","),
    });
    fetch("/list-prices?" + params)
      .then(function (response) { return response.json(); })
      .then(function (prices) {
        showChunkPrices(chunks[index], prices || {});
        fetchPriceChunks(world, chunks, index + 1);
      })
      .catch(function () {});
  }

  function chunkedIds() {
    const ids = [];
    for (const cell of cells) {
      if (!ids.includes(cell.dataset.gameId)) {
        ids.push(cell.dataset.gameId);
      }
    }
    const chunks = [];
    for (let start = 0; start < ids.length; start += PRICE_CHUNK_SIZE) {
      chunks.push(ids.slice(start, start + PRICE_CHUNK_SIZE));
    }
    return chunks;
  }

  function showChunkPrices(ids, prices) {
    for (const cell of cells) {
      if (!ids.includes(cell.dataset.gameId)) {
        continue;
      }
      const entry = prices[cell.dataset.gameId];
      cell.textContent = entry ? formatPrices(entry) : "—";
    }
  }

  function formatPrices(entry) {
    const lowest = entry.lowest.toLocaleString();
    if (entry.stack === entry.lowest) {
      return lowest;
    }
    if (entry.stack === null) {
      return lowest + " / —";
    }
    return lowest + " / " + entry.stack.toLocaleString();
  }

  function clearPrices() {
    for (const cell of cells) {
      cell.textContent = "";
    }
  }

  function restoreWorld() {
    try {
      worldSelect.value = localStorage.getItem("list-prices-world")
        || localStorage.getItem("currency-yields-world") || "";
    } catch (error) {}
  }

  function saveWorld(value) {
    try {
      localStorage.setItem("list-prices-world", value);
    } catch (error) {}
  }
}

setupListPrices();

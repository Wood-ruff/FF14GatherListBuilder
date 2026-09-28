function sourceRow(tag, detail, currencyId) {
  const row = document.createElement("div");
  row.className = "source-row";
  const label = document.createElement("span");
  label.className = "source-tag";
  label.textContent = tag;
  const value = document.createElement("span");
  value.className = "source-info";
  if (currencyId) {
    const icon = document.createElement("img");
    icon.className = "currency-icon";
    icon.src = "/icons/" + currencyId;
    icon.alt = "";
    value.appendChild(icon);
  }
  value.appendChild(document.createTextNode(detail || ""));
  row.appendChild(label);
  row.appendChild(value);
  return row;
}

function priceText(price, currencyName) {
  return msg("sources_price", "{price} {currency}")
    .replace("{price}", price)
    .replace("{currency}", currencyName || "?");
}

function sourceRows(info) {
  const rows = [];
  if (info.crystal) {
    rows.push(sourceRow(msg("sources_crystal", "Crystal"), msg("sources_crystal_hint", "easy to get in many ways")));
  }
  if (info.gatherable) {
    rows.push(sourceRow(msg("sources_gather", "Gatherable"), info.timed ? msg("craft_costs_timed", "timed node") : ""));
  }
  if (info.craftable) {
    rows.push(sourceRow(msg("sources_craft", "Craftable"), ""));
  }
  if (info.reduction) {
    rows.push(sourceRow(msg("sources_reduction", "Aetherial Reduction"), msg("sources_reduction_hint", "from reducing gathered collectables")));
  }
  if (info.gil) {
    rows.push(sourceRow(msg("craft_costs_gil", "gil vendor"), "", 1));
  }
  if (info.scrip) {
    rows.push(sourceRow(msg("sources_scrip", "scrip vendor"), priceText(info.scrip.price, info.currency_name), info.scrip.currency));
  } else if (info.gemstone) {
    rows.push(sourceRow(msg("craft_costs_gemstone", "mob drop / gemstone vendor"),
      info.price ? priceText(info.price, info.currency_name) : "", info.currency));
  } else if (info.special) {
    let detail = info.price ? priceText(info.price, info.currency_name) : (info.currency_name || "");
    if (info.locked) {
      detail += (detail ? " · " : "") + msg("craft_costs_locked", "needs unlock") + " 🔒";
    }
    rows.push(sourceRow(msg("craft_costs_special", "currency vendor"), detail, info.currency));
  }
  if (info.loot) {
    rows.push(sourceRow(msg("sources_loot", "mob drops / desynthesis / other"), ""));
  }
  if (info.reducible) {
    rows.push(sourceRow(msg("sources_reducible", "Reducible"), msg("sources_reducible_hint", "can be aetherially reduced")));
  }
  return rows;
}


function offerCard(offer) {
  const card = document.createElement("div");
  card.className = "vendor-card";
  const head = document.createElement("div");
  head.className = "vendor-name";
  if (offer.currency) {
    const icon = document.createElement("img");
    icon.className = "currency-icon";
    icon.src = "/icons/" + offer.currency;
    icon.alt = "";
    head.appendChild(icon);
  }
  let title = offer.price ? priceText(offer.price, offer.currency_name) : (offer.currency_name || "");
  if (offer.vendor && offer.vendor.name) {
    title += " — " + msg("sources_vendor", "Vendor: {name}").replace("{name}", offer.vendor.name);
  }
  if (offer.shop) {
    title += " · " + offer.shop;
  }
  head.appendChild(document.createTextNode(title));
  card.appendChild(head);
  if (offer.vendor && offer.vendor.zone) {
    const where = document.createElement("div");
    where.className = "muted";
    let location = offer.vendor.zone;
    if (offer.vendor.x !== null && offer.vendor.x !== undefined) {
      location += " (" + offer.vendor.x + ", " + offer.vendor.y + ")";
    }
    if (offer.vendor.aetheryte) {
      location += " · ✦ " + offer.vendor.aetheryte;
    }
    where.textContent = location;
    card.appendChild(where);
  }
  return card;
}

function renderSources(info) {
  const list = document.getElementById("sources-list");
  list.innerHTML = "";
  document.getElementById("sources-title").textContent = info ? info.name : "";
  if (!info) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = msg("sources_none", "No sources known");
    list.appendChild(empty);
    return;
  }
  const rows = sourceRows(info);
  if (rows.length === 0) {
    rows.push(sourceRow(msg("sources_none", "No sources known"), ""));
  }
  for (const row of rows) {
    list.appendChild(row);
  }
  for (const offer of info.offers || []) {
    list.appendChild(offerCard(offer));
  }
}

function openSources(itemId) {
  const modal = document.getElementById("sources-modal");
  modal.dataset.itemId = itemId;
  modal.hidden = false;
  document.getElementById("sources-title").textContent = "";
  document.getElementById("sources-list").innerHTML = "";
  document.getElementById("sources-spinner").hidden = false;
  const params = new URLSearchParams();
  params.set("list", modal.dataset.list);
  params.set("id", itemId);
  fetch("/item-sources?" + params)
    .then(function (response) { return response.json(); })
    .then(function (info) {
      document.getElementById("sources-spinner").hidden = true;
      renderSources(info);
    })
    .catch(function () {
      document.getElementById("sources-spinner").hidden = true;
      renderSources(null);
    });
}

function setupSources() {
  const modal = document.getElementById("sources-modal");
  if (modal === null) {
    return;
  }
  for (const button of document.querySelectorAll(".sources-open")) {
    button.addEventListener("click", function () {
      openSources(button.dataset.id);
    });
  }
  document.getElementById("sources-close").addEventListener("click", function () {
    modal.hidden = true;
  });
  modal.addEventListener("click", function (event) {
    if (event.target === modal) {
      modal.hidden = true;
    }
  });
}

setupSources();

import json
import logging
import threading
from pathlib import Path
from urllib.parse import urlencode

from flask import Blueprint, jsonify, redirect, render_template, request, send_from_directory, url_for

import lists
import translations

routes = Blueprint("routes", __name__)


@routes.app_template_filter("shorten")
def shorten(name):
    """Cut a display name down to 24 characters with an ellipsis."""
    if len(name) <= 24:
        return name
    return name[:23] + "…"


@routes.app_context_processor
def inject_translations():
    """Provide the translator and all texts to every template."""
    texts = translations.all_texts(lists.get_language())

    def t(code):
        return texts.get(code, code)

    return {"t": t, "ui_messages": texts}

WRITE_LOCK = threading.Lock()
PENDING_ADDS = {"count": 0}

LOG = logging.getLogger(__name__)


def run_in_background(task):
    """Run one list changing task in a background thread, one at a time."""
    def locked_task():
        try:
            with WRITE_LOCK:
                task()
        except Exception:
            LOG.exception("background task failed")
        finally:
            PENDING_ADDS["count"] -= 1

    PENDING_ADDS["count"] += 1
    threading.Thread(target=locked_task, daemon=True).start()


def pagination_args(entries):
    """Slice the entries to the requested page and build the template values."""
    raw_page = request.args.get("page", "")
    raw_size = request.args.get("size", "")
    size = int(raw_size) if raw_size.isdigit() else lists.DEFAULT_PAGE_SIZE
    page_entries, page, page_count = lists.paginate(
        entries, int(raw_page) if raw_page.isdigit() else 1, size
    )
    base_query = urlencode([(key, value) for key, value in request.args.items() if key != "page"])
    return page_entries, {
        "page": page,
        "page_count": page_count,
        "size": size if size in lists.PAGE_SIZES else lists.DEFAULT_PAGE_SIZE,
        "page_sizes": lists.PAGE_SIZES,
        "base_query": base_query,
    }


def persisted_pins(store, entries):
    """Return the entries pinned in the browser, when pin persistence is switched on."""
    if request.cookies.get(f"pin-persist-{store}") != "1":
        return []
    raw = request.cookies.get(f"pins-{store}", "")
    ids = {int(part) for part in raw.split("-") if part.isdigit()}
    return [entry for entry in entries if entry["game_id"] in ids]


def with_pins_first(entries, pinned):
    """Put pinned entries first and drop their duplicates from the page entries."""
    pinned_ids = {entry["game_id"] for entry in pinned}
    return pinned + [entry for entry in entries if entry["game_id"] not in pinned_ids]


def page_context(selected, active_tab):
    """Build the template values shared by all pages."""
    return {
        "selected": selected,
        "active_tab": active_tab,
        "list_names": lists.get_list_names(),
        "language": lists.get_language(),
        "languages": lists.supported_languages(),
        "api_failed": lists.last_lookup_failed(),
        "alarm_sounds": lists.alarm_sounds(),
        "backgrounds": lists.background_images(),
    }


@routes.get("/")
def show_list():
    """Show the selected list and the controls to edit it."""
    selected = request.args.get("list", "").strip()
    name_filter = request.args.get("q", "").strip()
    timed_first = request.args.get("timed") == "1"
    items = lists.get_items(selected, timed_first) if selected else []
    if lists.needs_localization(items):
        run_in_background(lambda: lists.localize_list(selected))
    items = lists.filter_items(items, name_filter)
    return render_template(
        "index.html",
        items=items,
        q=name_filter,
        timed_first=timed_first,
        **page_context(selected, "lists"),
    )


@routes.get("/collectables")
def show_collectables():
    """Show all gathering collectables, filterable and sortable, with add buttons."""
    selected = request.args.get("list", "").strip()
    sort = request.args.get("sort", "level")
    direction = lists.normalize_direction(sort, request.args.get("dir", ""))
    job = request.args.get("job", "all")
    min_level = request.args.get("min", "").strip()
    max_level = request.args.get("max", "").strip()
    min_scrips = request.args.get("minscrips", "").strip()
    name_filter = request.args.get("q", "").strip()
    shop = request.args.get("shop", "all")
    if shop not in ("all", "scrip", "noscrip"):
        shop = "all"
    collectables = lists.get_collectables(
        sort,
        direction,
        job,
        int(min_level) if min_level.isdigit() else None,
        int(max_level) if max_level.isdigit() else None,
        int(min_scrips) if min_scrips.isdigit() else None,
        shop,
        name_filter,
    )
    pinned = persisted_pins("collectables", lists.get_collectables(sort, direction))
    collectables, pagination = pagination_args(collectables)
    collectables = with_pins_first(collectables, pinned)
    return render_template(
        "collectables.html",
        collectables=collectables,
        **pagination,
        sort=sort,
        dir=direction,
        job=job,
        min_level=min_level,
        max_level=max_level,
        min_scrips=min_scrips,
        shop=shop,
        q=name_filter,
        **page_context(selected, "collectables"),
    )


@routes.get("/craftables")
def show_craftables():
    """Show all craftable collectables, filterable and sortable, with add buttons."""
    selected = request.args.get("list", "").strip()
    sort = request.args.get("sort", "level")
    direction = lists.normalize_direction(sort, request.args.get("dir", ""))
    job = request.args.get("job", "all")
    min_level = request.args.get("min", "").strip()
    max_level = request.args.get("max", "").strip()
    min_scrips = request.args.get("minscrips", "").strip()
    name_filter = request.args.get("q", "").strip()
    shop = request.args.get("shop", "scrip")
    if shop not in ("all", "scrip", "noscrip"):
        shop = "scrip"
    craftables = lists.get_craftables(
        sort,
        direction,
        job,
        int(min_level) if min_level.isdigit() else None,
        int(max_level) if max_level.isdigit() else None,
        shop,
        int(min_scrips) if min_scrips.isdigit() else None,
        name_filter,
    )
    pinned = persisted_pins("craftables", lists.get_craftables(sort, direction, scrip_mode="all"))
    craftables, pagination = pagination_args(craftables)
    craftables = with_pins_first(craftables, pinned)
    return render_template(
        "craftables.html",
        craftables=craftables,
        **pagination,
        sort=sort,
        dir=direction,
        job=job,
        min_level=min_level,
        max_level=max_level,
        min_scrips=min_scrips,
        shop=shop,
        q=name_filter,
        **page_context(selected, "craftables"),
    )


@routes.get("/quick-buck")
def show_quick_buck():
    """Show the quick buck tab with its gil making features."""
    selected = request.args.get("list", "").strip()
    return render_template(
        "quickbuck.html",
        currencies=lists.get_currency_options(),
        worlds=lists.get_worlds(),
        **page_context(selected, "quickbuck"),
    )


@routes.get("/currency-yields")
def currency_yields():
    """Return the best ways to spend one currency on one world as JSON."""
    currency = request.args.get("currency", "")
    world = request.args.get("world", "")
    if not currency.isdigit() or not world.isdigit():
        return jsonify(None)
    return jsonify(lists.get_currency_yields(int(currency), int(world)))


@routes.post("/craftables/add")
def add_craftable():
    """Queue adding one craftable collectable with its materials to the selected list."""
    list_name = request.form.get("list", "").strip()
    item_name = request.form.get("item", "").strip()
    amount = request.form.get("amount", "").strip()

    if list_name and item_name and amount.isdigit():
        run_in_background(lambda: lists.add_craft_with_materials(list_name, item_name, int(amount)))

    return redirect(url_for("routes.show_craftables", list=list_name))


@routes.post("/collectables/add")
def add_collectable():
    """Add one collectable to the selected list, then show the collectables again."""
    list_name = request.form.get("list", "").strip()
    item_name = request.form.get("item", "").strip()
    amount = request.form.get("amount", "").strip()

    if list_name and item_name and amount.isdigit():
        lists.add_item(list_name, item_name, int(amount))

    return redirect(url_for(
        "routes.show_collectables",
        list=list_name,
        sort=request.form.get("sort", "level"),
    ))


@routes.get("/pending")
def pending_adds():
    """Tell how many background add tasks are still running."""
    return jsonify(PENDING_ADDS["count"])


@routes.get("/fetching")
def fetching():
    """Tell whether the server is currently fetching bigger game data."""
    return jsonify(lists.fetches_running())


@routes.get("/rotation")
def rotation():
    """Return timed scrip collectables for the farm rotation planner as JSON."""
    level = request.args.get("level", "")
    jobs = [job for job in request.args.get("jobs", "").split(",") if job]
    orange = request.args.get("scrips") == "orange"
    entries = lists.get_rotation(int(level) if level.isdigit() else 100, jobs, orange)
    return jsonify(entries)


@routes.get("/craft-costs")
def craft_costs():
    """Return scrip craftables ranked by material cost for the calculator popup as JSON."""
    level = request.args.get("level", "")
    job = request.args.get("job", "all")
    orange = request.args.get("scrips") == "orange"
    gemstones = request.args.get("gemstones") == "unlocked"
    hide_loot = request.args.get("hideloot") == "1"
    hide_locked = request.args.get("hidelocked") == "1"
    entries = lists.get_craft_costs(
        int(level) if level.isdigit() else 100, job, orange, gemstones, hide_loot, hide_locked
    )
    return jsonify(entries)


@routes.get("/item-sources")
def item_sources():
    """Return everything known about one list item's acquisition as JSON."""
    list_name = request.args.get("list", "").strip()
    item_id = request.args.get("id", "").strip()
    if not list_name or not item_id.isdigit():
        return jsonify(None)
    return jsonify(lists.get_item_sources(list_name, int(item_id)))


@routes.get("/venture-yields")
def venture_yields():
    """Return the best retainer ventures for one world as JSON."""
    world = request.args.get("world", "")
    job = request.args.get("job", "")
    level = request.args.get("level", "").strip()
    stat = request.args.get("stat", "").strip()
    if not world.isdigit() or job not in lists.VENTURE_JOBS:
        return jsonify(None)
    return jsonify(lists.get_venture_yields(
        int(world),
        job,
        int(level) if level.isdigit() else None,
        int(stat) if stat.isdigit() else None,
    ))


@routes.get("/suggest")
def suggest_items():
    """Return item name suggestions for a partial search as JSON."""
    return jsonify(lists.suggest_item_names(request.args.get("q", "")))


@routes.get("/icons/<int:game_id>")
def item_icon(game_id):
    """Serve one cached item icon."""
    return send_from_directory(lists.icon_folder(), f"{game_id}.png")


@routes.get("/job-icons/<int:type_id>")
def job_icon(type_id):
    """Serve one cached gathering job icon."""
    return send_from_directory(lists.icon_folder(), f"jobtype_{type_id}.png")


@routes.get("/market-icon")
def market_icon():
    """Serve the cached market board symbol icon."""
    return send_from_directory(lists.icon_folder(), lists.market_icon_file())


@routes.get("/craft-icons/<int:icon_id>")
def craft_icon(icon_id):
    """Serve one cached crafting job icon."""
    return send_from_directory(lists.icon_folder(), f"crafticon_{icon_id}.png")


@routes.post("/add")
def add_item():
    """Add one item to the selected list, then show the list again."""
    list_name = request.form.get("list", "").strip()
    item_name = request.form.get("item", "").strip()
    amount = request.form.get("amount", "").strip()

    if list_name and item_name and amount.isdigit():
        lists.add_item(list_name, item_name, int(amount))

    return redirect(url_for("routes.show_list", list=list_name))


@routes.post("/craft")
def craft_item():
    """Add all base materials for a craftable item, then show the list again."""
    list_name = request.form.get("list", "").strip()
    item_name = request.form.get("item", "").strip()
    amount = request.form.get("amount", "").strip()

    if list_name and item_name and amount.isdigit():
        lists.add_crafted_item(list_name, item_name, int(amount))

    return redirect(url_for("routes.show_list", list=list_name))


@routes.post("/add-materials")
def add_materials():
    """Add the base materials for one list item, then show the list again."""
    list_name = request.form.get("list", "").strip()
    item_id = request.form.get("id", "").strip()

    if list_name and item_id.isdigit():
        lists.add_materials_for(list_name, int(item_id))

    return redirect(url_for("routes.show_list", list=list_name))


@routes.post("/toggle-done")
def toggle_done():
    """Mark one list item as done or not done."""
    list_name = request.form.get("list", "").strip()
    item_id = request.form.get("id", "").strip()
    done = request.form.get("done") == "1"

    if list_name and item_id.isdigit():
        lists.set_done(list_name, int(item_id), done)

    return ("", 204)


@routes.post("/toggle-mute")
def toggle_mute():
    """Suppress or restore the alarm of one list item."""
    list_name = request.form.get("list", "").strip()
    item_id = request.form.get("id", "").strip()
    muted = request.form.get("muted") == "1"

    if list_name and item_id.isdigit():
        lists.set_muted(list_name, int(item_id), muted)

    return ("", 204)


@routes.post("/set-note")
def set_note():
    """Save the note of one list item."""
    list_name = request.form.get("list", "").strip()
    item_id = request.form.get("id", "").strip()
    note = request.form.get("note", "").strip()

    if list_name and item_id.isdigit():
        lists.set_note(list_name, int(item_id), note)

    return ("", 204)


@routes.post("/toggle-sticky")
def toggle_sticky():
    """Pin or unpin one list item."""
    list_name = request.form.get("list", "").strip()
    item_id = request.form.get("id", "").strip()
    sticky = request.form.get("sticky") == "1"

    if list_name and item_id.isdigit():
        lists.set_sticky(list_name, int(item_id), sticky)

    return ("", 204)


@routes.post("/toggle-materials")
def toggle_materials():
    """Mark whether one list item's materials were added."""
    list_name = request.form.get("list", "").strip()
    item_id = request.form.get("id", "").strip()
    added = request.form.get("added") == "1"

    if list_name and item_id.isdigit():
        lists.set_materials_added(list_name, int(item_id), added)

    return ("", 204)


@routes.post("/update")
def update_item():
    """Change one item's amount, then show the list again."""
    list_name = request.form.get("list", "").strip()
    item_id = request.form.get("id", "").strip()
    amount = request.form.get("amount", "").strip()

    if list_name and item_id.isdigit() and amount.isdigit():
        lists.update_item(list_name, int(item_id), int(amount))

    return redirect(url_for("routes.show_list", list=list_name))


@routes.post("/language")
def set_language():
    """Change the game data language, translate the open list, then show it again."""
    lists.set_language(request.form.get("language", ""))
    list_name = request.form.get("list", "").strip()
    if list_name:
        lists.localize_list(list_name)
    return redirect(url_for("routes.show_list", list=list_name))


@routes.get("/export")
def export_list():
    """Download the selected list as its JSON file."""
    list_name = request.args.get("list", "").strip()
    if list_name not in lists.get_list_names():
        return redirect(url_for("routes.show_list"))
    return send_from_directory(lists.lists_folder(), f"{list_name}.json", as_attachment=True)


@routes.post("/import")
def import_list():
    """Import an uploaded list file, then refresh its game data in the background."""
    file = request.files.get("file")
    if file is None or not file.filename:
        return redirect(url_for("routes.show_list"))
    try:
        items = json.loads(file.read(2_000_000).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return redirect(url_for("routes.show_list"))

    name = lists.import_list(Path(file.filename).stem, items)
    if name is None:
        return redirect(url_for("routes.show_list"))
    run_in_background(lambda: lists.refresh_list_data(name))
    return redirect(url_for("routes.show_list", list=name))


@routes.post("/create-list")
def create_list():
    """Create a new empty list, then open it on the page it was created from."""
    list_name = request.form.get("list", "").strip()
    if list_name:
        lists.create_list(list_name)
    if request.form.get("next") == "/collectables":
        return redirect(url_for("routes.show_collectables", list=list_name))
    return redirect(url_for("routes.show_list", list=list_name))


@routes.post("/add-all-materials")
def add_all_materials():
    """Queue adding the materials of every craftable item, then show the list again."""
    list_name = request.form.get("list", "").strip()
    if list_name:
        run_in_background(lambda: lists.add_all_materials(list_name))
    return redirect(url_for("routes.show_list", list=list_name))


@routes.post("/remove-materials")
def remove_materials():
    """Remove all materials and crystals from the selected list, then show it again."""
    list_name = request.form.get("list", "").strip()
    if list_name:
        lists.remove_materials(list_name)
    return redirect(url_for("routes.show_list", list=list_name))


@routes.post("/clear-list")
def clear_list():
    """Empty the selected list, then show it again."""
    list_name = request.form.get("list", "").strip()
    if list_name:
        lists.clear_items(list_name)
    return redirect(url_for("routes.show_list", list=list_name))


@routes.post("/delete-list")
def delete_list():
    """Delete a whole list, then show the start page."""
    list_name = request.form.get("list", "").strip()
    if list_name:
        lists.remove_list(list_name)
    return redirect(url_for("routes.show_list"))


@routes.post("/refetch-list")
def refetch_list():
    """Queue re-fetching all game data of the selected list, then show it again."""
    list_name = request.form.get("list", "").strip()
    if list_name:
        run_in_background(lambda: lists.refresh_list_data(list_name))
    return redirect(url_for("routes.show_list", list=list_name))


@routes.post("/clear-cache")
def clear_cache():
    """Clear all cached api data, then show the current list again."""
    lists.clear_caches()
    return redirect(url_for("routes.show_list", list=request.form.get("list", "")))


@routes.post("/delete")
def delete_item():
    """Remove one item from the selected list, then show the list again."""
    list_name = request.form.get("list", "").strip()
    item_id = request.form.get("id", "").strip()

    if list_name and item_id.isdigit():
        lists.remove_item(list_name, int(item_id))

    return redirect(url_for("routes.show_list", list=list_name))

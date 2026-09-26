import threading

from flask import Blueprint, jsonify, redirect, render_template, request, send_from_directory, url_for

import lists
import translations

routes = Blueprint("routes", __name__)


@routes.app_context_processor
def inject_translations():
    """Provide the translator and all texts to every template."""
    texts = translations.all_texts(lists.get_language())

    def t(code):
        return texts.get(code, code)

    return {"t": t, "ui_messages": texts}

WRITE_LOCK = threading.Lock()
PENDING_ADDS = {"count": 0}


def run_in_background(task):
    """Run one list changing task in a background thread, one at a time."""
    def locked_task():
        try:
            with WRITE_LOCK:
                task()
        finally:
            PENDING_ADDS["count"] -= 1

    PENDING_ADDS["count"] += 1
    threading.Thread(target=locked_task, daemon=True).start()


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
    }


@routes.get("/")
def show_list():
    """Show the selected list and the controls to edit it."""
    selected = request.args.get("list", "").strip()
    items = lists.get_items(selected) if selected else []
    return render_template("index.html", items=items, **page_context(selected, "lists"))


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
    return render_template(
        "collectables.html",
        collectables=collectables,
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
    return render_template(
        "craftables.html",
        craftables=craftables,
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
    """Change the game data language, then show the current list again."""
    lists.set_language(request.form.get("language", ""))
    return redirect(url_for("routes.show_list", list=request.form.get("list", "")))


@routes.post("/create-list")
def create_list():
    """Create a new empty list, then open it on the page it was created from."""
    list_name = request.form.get("list", "").strip()
    if list_name:
        lists.create_list(list_name)
    if request.form.get("next") == "/collectables":
        return redirect(url_for("routes.show_collectables", list=list_name))
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

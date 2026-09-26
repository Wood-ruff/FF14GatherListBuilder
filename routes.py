from flask import Blueprint, jsonify, redirect, render_template, request, send_from_directory, url_for

import lists

routes = Blueprint("routes", __name__)


@routes.get("/")
def show_list():
    """Show the selected list and the controls to edit it."""
    selected = request.args.get("list", "").strip()
    items = lists.get_items(selected) if selected else []
    return render_template(
        "index.html",
        list_names=lists.get_list_names(),
        selected=selected,
        items=items,
        language=lists.get_language(),
        languages=lists.supported_languages(),
        api_failed=lists.last_lookup_failed(),
    )


@routes.get("/suggest")
def suggest_items():
    """Return item name suggestions for a partial search as JSON."""
    return jsonify(lists.suggest_item_names(request.args.get("q", "")))


@routes.get("/icons/<int:game_id>")
def item_icon(game_id):
    """Serve one cached item icon."""
    return send_from_directory(lists.icon_folder(), f"{game_id}.png")


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

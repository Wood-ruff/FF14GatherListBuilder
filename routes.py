from flask import Blueprint, redirect, render_template, request, url_for

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
    )


@routes.post("/add")
def add_item():
    """Add one item to the selected list, then show the list again."""
    list_name = request.form.get("list", "").strip()
    item_name = request.form.get("item", "").strip()
    amount = request.form.get("amount", "").strip()

    if list_name and item_name and amount.isdigit():
        lists.add_item(list_name, item_name, int(amount))

    return redirect(url_for("routes.show_list", list=list_name))


@routes.post("/update")
def update_item():
    """Change one item's name and amount, then show the list again."""
    list_name = request.form.get("list", "").strip()
    item_id = request.form.get("id", "").strip()
    item_name = request.form.get("item", "").strip()
    amount = request.form.get("amount", "").strip()

    if list_name and item_id.isdigit() and item_name and amount.isdigit():
        lists.update_item(list_name, int(item_id), item_name, int(amount))

    return redirect(url_for("routes.show_list", list=list_name))


@routes.post("/delete")
def delete_item():
    """Remove one item from the selected list, then show the list again."""
    list_name = request.form.get("list", "").strip()
    item_id = request.form.get("id", "").strip()

    if list_name and item_id.isdigit():
        lists.remove_item(list_name, int(item_id))

    return redirect(url_for("routes.show_list", list=list_name))

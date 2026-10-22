"""Admin routes for equipment management."""
from flask import Blueprint, jsonify, request

from auth import admin_api, admin_only, frontend_redirect, redirect_with_message
from database import DatabaseError, delete_rows, first, get_rows, insert_row, log_audit, update_rows
from services import has_active_equipment_loan
from validators import parse_equipment_form

admin_equipment_bp = Blueprint("admin_equipment_routes", __name__)


@admin_equipment_bp.get("/equipment")
@admin_only
def equipment_page():
    return frontend_redirect("/equipment")


@admin_equipment_bp.get("/api/equipment")
@admin_api
def equipment_list():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    sort = request.args.get("sort", "name").strip()

    try:
        records = get_rows("equipment")
        if search:
            needle = search.lower()
            records = [
                row for row in records
                if needle in row["equipment_name"].lower()
                or needle in row["category"].lower()
                or needle in row["unit_type"].lower()
            ]
        for row in records:
            row["borrowed_stock"] = row["total_stock"] - row["available_stock"]
            row["status"] = (
                "Out of Stock" if row["available_stock"] == 0
                else "Low Stock" if row["available_stock"] < row["total_stock"]
                else "Available"
            )
        if status_filter:
            records = [row for row in records if row["status"] == status_filter]
        reverse = sort == "newest"
        if sort in ("newest", "oldest"):
            records.sort(key=lambda row: row.get("created_at") or "", reverse=reverse)
        elif sort == "status":
            records.sort(key=lambda row: (row["status"], row["equipment_name"].lower()))
        else:
            records.sort(key=lambda row: row["equipment_name"].lower())
        return jsonify(records)
    except DatabaseError:
        return jsonify(error="Unable to load equipment. Check the database connection."), 500


@admin_equipment_bp.post("/equipment/add")
@admin_only
def equipment_add():
    try:
        name, category, total_stock, unit_type = parse_equipment_form(request.form)
    except ValueError as error:
        return redirect_with_message("equipment_page", str(error))

    try:
        if any(row["equipment_name"].lower() == name.lower() for row in get_rows("equipment")):
            return redirect_with_message(
                "equipment_page", "An equipment record with that name already exists."
            )
        equipment = insert_row(
            "equipment",
            {
                "equipment_name": name,
                "category": category,
                "total_stock": total_stock,
                "available_stock": total_stock,
                "unit_type": unit_type,
            },
        )
        log_audit("CREATE", "equipment", equipment["equipment_id"], f"Added equipment: {name}")
        return redirect_with_message("equipment_page", "Equipment added successfully.")
    except DatabaseError:
        return redirect_with_message("equipment_page", "Unable to add equipment. Please try again.")


@admin_equipment_bp.post("/equipment/<int:equipment_id>/edit")
@admin_only
def equipment_edit(equipment_id):
    try:
        name, category, total_stock, unit_type = parse_equipment_form(request.form)
    except ValueError as error:
        return redirect_with_message("equipment_page", str(error))

    try:
        equipment = first([row for row in get_rows("equipment") if row["equipment_id"] == equipment_id])
        if not equipment:
            return redirect_with_message("equipment_page", "Equipment record was not found.")
        borrowed_stock = equipment["total_stock"] - equipment["available_stock"]
        if total_stock < borrowed_stock:
            return redirect_with_message(
                "equipment_page",
                f"Total quantity cannot be lower than the {borrowed_stock} item(s) currently borrowed.",
            )
        if any(
            row["equipment_id"] != equipment_id and row["equipment_name"].lower() == name.lower()
            for row in get_rows("equipment")
        ):
            return redirect_with_message(
                "equipment_page", "An equipment record with that name already exists."
            )
        update_rows(
            "equipment",
            {
                "equipment_name": name,
                "category": category,
                "total_stock": total_stock,
                "available_stock": total_stock - borrowed_stock,
                "unit_type": unit_type,
            },
            "equipment_id",
            equipment_id,
        )
        log_audit("UPDATE", "equipment", equipment_id, f"Updated equipment: {name}")
        return redirect_with_message("equipment_page", "Equipment updated successfully.")
    except DatabaseError:
        return redirect_with_message(
            "equipment_page", "Unable to update equipment. Please try again."
        )


@admin_equipment_bp.post("/equipment/<int:equipment_id>/delete")
@admin_only
def equipment_delete(equipment_id):
    try:
        current = first([row for row in get_rows("equipment") if row["equipment_id"] == equipment_id])
        if not current:
            return redirect_with_message("equipment_page", "Equipment record was not found.")
        if has_active_equipment_loan(equipment_id):
            return redirect_with_message(
                "equipment_page",
                "This equipment cannot be deleted because it is part of an active borrowing transaction.",
            )
        delete_rows("equipment", "equipment_id", equipment_id)
        log_audit("DELETE", "equipment", equipment_id, f"Deleted equipment: {current['equipment_name']}")
        return redirect_with_message("equipment_page", "Equipment deleted successfully.")
    except DatabaseError:
        return redirect_with_message(
            "equipment_page", "Unable to delete equipment. Please try again."
        )

"""Admin routes for equipment management."""
import mysql.connector
from flask import Blueprint, jsonify, render_template, request, session

from auth import admin_api, admin_only, redirect_with_message
from database import STATUS_SQL_EXPRESSION, get_db_connection, log_audit
from services import has_active_equipment_loan
from validators import parse_equipment_form

admin_equipment_bp = Blueprint("admin_equipment_routes", __name__)


@admin_equipment_bp.get("/equipment")
@admin_only
def equipment_page():
    return render_template(
        "equipment.html",
        full_name=session["full_name"],
        role=session.get("role", ""),
    )


@admin_equipment_bp.get("/api/equipment")
@admin_api
def equipment_list():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    sort = request.args.get("sort", "name").strip()

    try:
        with get_db_connection() as (db, cursor):
            where, values = [], []
            if search:
                where.append("(equipment_name LIKE %s OR category LIKE %s OR unit_type LIKE %s)")
                values.extend([f"%{search}%"] * 3)

            if status_filter == "Available":
                where.append("available_stock = total_stock")
            elif status_filter == "Out of Stock":
                where.append("available_stock = 0")
            elif status_filter == "Low Stock":
                where.append("available_stock > 0 AND available_stock < total_stock")

            sql = (
                f"SELECT equipment_id, equipment_name, category, total_stock, "
                f"available_stock, unit_type, created_at, updated_at, "
                f"{STATUS_SQL_EXPRESSION} AS status FROM equipment"
            )
            if where:
                sql += " WHERE " + " AND ".join(where)

            order_map = {
                "name": "equipment_name",
                "newest": "created_at DESC",
                "oldest": "created_at",
                "status": "equipment_name, status",
            }
            sql += " ORDER BY " + order_map.get(sort, "equipment_name")

            cursor.execute(sql, values)
            records = []
            for row in cursor.fetchall():
                row["borrowed_stock"] = row["total_stock"] - row["available_stock"]
                records.append(row)
            return jsonify(records)
    except mysql.connector.Error:
        return jsonify(error="Unable to load equipment. Check the MySQL connection."), 500


@admin_equipment_bp.post("/equipment/add")
@admin_only
def equipment_add():
    try:
        name, category, total_stock, unit_type = parse_equipment_form(request.form)
    except ValueError as error:
        return redirect_with_message("equipment_page", str(error))

    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT equipment_id FROM equipment WHERE LOWER(equipment_name) = LOWER(%s)",
                (name,),
            )
            if cursor.fetchone():
                return redirect_with_message(
                    "equipment_page", "An equipment record with that name already exists."
                )

            cursor.execute(
                "INSERT INTO equipment (equipment_name, category, total_stock, available_stock, unit_type) "
                "VALUES (%s, %s, %s, %s, %s)",
                (name, category, total_stock, total_stock, unit_type),
            )
            equipment_id = cursor.lastrowid
            log_audit(cursor, "CREATE", "equipment", equipment_id, f"Added equipment: {name}")
            db.commit()
            return redirect_with_message("equipment_page", "Equipment added successfully.")
    except mysql.connector.Error:
        return redirect_with_message("equipment_page", "Unable to add equipment. Please try again.")


@admin_equipment_bp.post("/equipment/<int:equipment_id>/edit")
@admin_only
def equipment_edit(equipment_id):
    try:
        name, category, total_stock, unit_type = parse_equipment_form(request.form)
    except ValueError as error:
        return redirect_with_message("equipment_page", str(error))

    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT total_stock, available_stock FROM equipment "
                "WHERE equipment_id = %s FOR UPDATE",
                (equipment_id,),
            )
            current = cursor.fetchone()
            if not current:
                return redirect_with_message("equipment_page", "Equipment record was not found.")
            borrowed_stock = current["total_stock"] - current["available_stock"]
            if total_stock < borrowed_stock:
                return redirect_with_message(
                    "equipment_page",
                    f"Total quantity cannot be lower than the {borrowed_stock} item(s) currently borrowed.",
                )

            cursor.execute(
                "SELECT equipment_id FROM equipment "
                "WHERE LOWER(equipment_name) = LOWER(%s) AND equipment_id <> %s",
                (name, equipment_id),
            )
            if cursor.fetchone():
                return redirect_with_message(
                    "equipment_page", "An equipment record with that name already exists."
                )

            available_stock = total_stock - borrowed_stock
            cursor.execute(
                "UPDATE equipment SET equipment_name = %s, category = %s, "
                "total_stock = %s, available_stock = %s, unit_type = %s "
                "WHERE equipment_id = %s",
                (name, category, total_stock, available_stock, unit_type, equipment_id),
            )
            log_audit(cursor, "UPDATE", "equipment", equipment_id, f"Updated equipment: {name}")
            db.commit()
            return redirect_with_message("equipment_page", "Equipment updated successfully.")
    except mysql.connector.Error:
        return redirect_with_message(
            "equipment_page", "Unable to update equipment. Please try again."
        )


@admin_equipment_bp.post("/equipment/<int:equipment_id>/delete")
@admin_only
def equipment_delete(equipment_id):
    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT equipment_name FROM equipment WHERE equipment_id = %s FOR UPDATE",
                (equipment_id,),
            )
            current = cursor.fetchone()
            if not current:
                return redirect_with_message("equipment_page", "Equipment record was not found.")
            if has_active_equipment_loan(cursor, equipment_id):
                db.rollback()
                return redirect_with_message(
                    "equipment_page",
                    "This equipment cannot be deleted because it is part of an active borrowing transaction.",
                )

            cursor.execute("DELETE FROM equipment WHERE equipment_id = %s", (equipment_id,))
            log_audit(
                cursor,
                "DELETE",
                "equipment",
                equipment_id,
                f"Deleted equipment: {current['equipment_name']}",
            )
            db.commit()
            return redirect_with_message("equipment_page", "Equipment deleted successfully.")
    except mysql.connector.Error:
        return redirect_with_message(
            "equipment_page", "Unable to delete equipment. Please try again."
        )

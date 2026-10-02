"""Admin routes for borrowing requests and direct loan creation."""
from datetime import date
import mysql.connector
from flask import Blueprint, jsonify, render_template, request, session

from auth import admin_api, admin_only, redirect_with_message
from database import get_db_connection, log_audit, serialize_date_fields
from services import validate_and_release_stock
from validators import parse_borrowing_form

admin_borrowings_bp = Blueprint("admin_borrowings_routes", __name__)


@admin_borrowings_bp.get("/borrowings")
@admin_only
def borrowings_page():
    return render_template(
        "borrowings.html",
        full_name=session["full_name"],
        role=session.get("role", ""),
        today=date.today().isoformat(),
    )


@admin_borrowings_bp.get("/api/borrowable-equipment")
@admin_api
def borrowable_equipment_list():
    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT equipment_id, equipment_name, category, available_stock, unit_type "
                "FROM equipment WHERE available_stock > 0 ORDER BY equipment_name"
            )
            return jsonify(cursor.fetchall())
    except mysql.connector.Error:
        return jsonify(error="Unable to load available equipment."), 500


@admin_borrowings_bp.post("/borrowings/create")
@admin_only
def borrowing_create():
    try:
        borrower_id, due_date, purpose_notes, items = parse_borrowing_form(request.form)
    except ValueError as error:
        return redirect_with_message("borrowings_page", str(error))

    try:
        with get_db_connection() as (db, cursor):
            db.start_transaction()
            cursor.execute(
                "SELECT borrower_id FROM borrowers WHERE borrower_id = %s FOR UPDATE",
                (borrower_id,),
            )
            if not cursor.fetchone():
                raise ValueError("The selected borrower no longer exists.")

            # Lock in a stable order so simultaneous transactions cannot oversell stock.
            locked_equipment = {}
            for equipment_id, quantity in sorted(items):
                cursor.execute(
                    "SELECT equipment_name, available_stock "
                    "FROM equipment WHERE equipment_id = %s FOR UPDATE",
                    (equipment_id,),
                )
                equipment = cursor.fetchone()
                if not equipment:
                    raise ValueError("One of the selected equipment records no longer exists.")
                if equipment["available_stock"] < quantity:
                    raise ValueError(
                        f"Insufficient stock for {equipment['equipment_name']}. "
                        f"Available: {equipment['available_stock']}."
                    )
                locked_equipment[equipment_id] = equipment

            cursor.execute(
                "INSERT INTO borrowings "
                "(borrower_id, processed_by, expected_return_date, purpose_notes, status) "
                "VALUES (%s, %s, %s, %s, 'Active')",
                (borrower_id, session["user_id"], due_date, purpose_notes),
            )
            borrowing_id = cursor.lastrowid
            for equipment_id, quantity in items:
                cursor.execute(
                    "INSERT INTO borrowing_items "
                    "(borrowing_id, equipment_id, quantity_borrowed, quantity_returned, remaining_quantity) "
                    "VALUES (%s, %s, %s, 0, %s)",
                    (borrowing_id, equipment_id, quantity, quantity),
                )
                cursor.execute(
                    "UPDATE equipment SET available_stock = available_stock - %s "
                    "WHERE equipment_id = %s AND available_stock >= %s",
                    (quantity, equipment_id, quantity),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("Stock changed while saving the transaction. Please try again.")

            log_audit(
                cursor,
                "CREATE",
                "borrowings",
                borrowing_id,
                f"Created borrowing transaction #{borrowing_id} with {len(items)} item(s)",
            )
            db.commit()
            return redirect_with_message(
                "borrowings_page",
                f"Borrowing transaction #{borrowing_id} saved successfully.",
            )
    except (mysql.connector.Error, ValueError, RuntimeError) as error:
        return redirect_with_message(
            "borrowings_page",
            str(error)
            if isinstance(error, (ValueError, RuntimeError))
            else "Unable to save the borrowing transaction. No stock was changed.",
        )


@admin_borrowings_bp.get("/admin/borrowing-requests")
@admin_only
def admin_request_review_page():
    return render_template(
        "admin_borrowing_requests.html",
        full_name=session["full_name"],
        role=session.get("role", "Admin"),
    )


@admin_borrowings_bp.get("/api/admin/borrowing-requests")
@admin_api
def admin_request_review_list():
    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT b.borrowing_id, COALESCE(u.full_name, br.full_name) AS borrower_name, "
                "  br.contact_number, e.equipment_id, e.equipment_name, e.category, "
                "  e.available_stock, e.unit_type, bi.quantity_borrowed, "
                "  b.purpose_notes, b.date_needed, b.expected_return_date, "
                "  b.additional_notes, b.created_at AS request_date, "
                "  b.status, b.processed_by "
                "FROM borrowings b "
                "JOIN borrowers br ON br.borrower_id = b.borrower_id "
                "LEFT JOIN users u ON u.user_id = br.user_id "
                "JOIN borrowing_items bi ON bi.borrowing_id = b.borrowing_id "
                "JOIN equipment e ON e.equipment_id = bi.equipment_id "
                "ORDER BY (b.status = 'Pending') DESC, (b.status = 'Approved') DESC, b.created_at DESC"
            )
            rows = serialize_date_fields(
                cursor.fetchall(),
                ["date_needed", "expected_return_date", "request_date"],
            )
            return jsonify(rows)
    except mysql.connector.Error:
        return jsonify(error="Unable to load borrowing requests."), 500


@admin_borrowings_bp.post("/admin/borrowing-requests/<int:borrowing_id>/<action>")
@admin_only
def admin_request_review_action(borrowing_id, action):
    if action not in ("approve", "reject", "cancel"):
        return redirect_with_message("admin_request_review_page", "Invalid request action.")

    status_map = {
        "approve": (
            "Approved",
            f"Approved borrowing request #{borrowing_id} for release",
            "Request approved for release; stock was not changed.",
        ),
        "reject": (
            "Rejected",
            f"Rejected borrowing request #{borrowing_id}",
            "Borrowing request rejected.",
        ),
        "cancel": (
            "Cancelled",
            f"Cancelled borrowing request #{borrowing_id}",
            "Borrowing request cancelled.",
        ),
    }

    try:
        with get_db_connection() as (db, cursor):
            db.start_transaction()
            cursor.execute(
                "SELECT status, processed_by FROM borrowings "
                "WHERE borrowing_id = %s FOR UPDATE",
                (borrowing_id,),
            )
            record = cursor.fetchone()
            if not record:
                raise ValueError("Borrowing request was not found.")

            if action == "approve" and record["status"] != "Pending":
                raise ValueError("Only Pending requests can be approved.")
            if action in ("reject", "cancel") and record["status"] not in ("Pending", "Approved"):
                raise ValueError("Only Pending or Approved requests can be rejected or cancelled.")

            new_status, description, user_msg = status_map[action]
            cursor.execute(
                "UPDATE borrowings SET status = %s, processed_by = %s "
                "WHERE borrowing_id = %s",
                (new_status, session["user_id"], borrowing_id),
            )
            log_audit(cursor, "UPDATE", "borrowings", borrowing_id, description)
            db.commit()
            return redirect_with_message("admin_request_review_page", user_msg)
    except (mysql.connector.Error, ValueError) as error:
        return redirect_with_message(
            "admin_request_review_page",
            str(error)
            if isinstance(error, ValueError)
            else "Unable to update the borrowing request.",
        )


@admin_borrowings_bp.post("/admin/borrowing-requests/<int:borrowing_id>/release")
@admin_only
def admin_request_release(borrowing_id):
    """Release a prepared request exactly once and decrease stock atomically."""
    try:
        with get_db_connection() as (db, cursor):
            db.start_transaction()
            cursor.execute(
                "SELECT borrowing_id, borrower_id, status, processed_by "
                "FROM borrowings WHERE borrowing_id = %s FOR UPDATE",
                (borrowing_id,),
            )
            request_record = cursor.fetchone()
            if not request_record:
                raise ValueError("Borrowing request was not found.")
            if request_record["status"] != "Approved":
                raise ValueError("Only Approved requests can be released.")

            cursor.execute(
                "SELECT borrower_id FROM borrowers WHERE borrower_id = %s FOR UPDATE",
                (request_record["borrower_id"],),
            )
            if not cursor.fetchone():
                raise ValueError("The borrower record is no longer valid.")

            validate_and_release_stock(cursor, borrowing_id)

            cursor.execute(
                "UPDATE borrowings SET status = 'Active', processed_by = %s, "
                "borrowed_at = NOW() WHERE borrowing_id = %s",
                (session["user_id"], borrowing_id),
            )
            log_audit(
                cursor,
                "UPDATE",
                "borrowings",
                borrowing_id,
                f"Released equipment for borrowing request #{borrowing_id}",
            )
            db.commit()
            return redirect_with_message(
                "admin_request_review_page",
                "Equipment released successfully. Stock and request status were updated.",
            )
    except (mysql.connector.Error, ValueError, RuntimeError) as error:
        return redirect_with_message(
            "admin_request_review_page",
            str(error)
            if isinstance(error, (ValueError, RuntimeError))
            else "Unable to release equipment. No stock was changed.",
        )

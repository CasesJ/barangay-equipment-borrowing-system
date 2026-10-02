"""Staff portal routes and API endpoints."""
import mysql.connector
from flask import Blueprint, jsonify, render_template, request, session

from auth import redirect_with_message, staff_api, staff_only
from database import get_db_connection, log_audit, serialize_date_fields
from services import validate_request_reservation
from validators import parse_staff_request_form

staff_bp = Blueprint("staff_routes", __name__)


@staff_bp.get("/staff/equipment")
@staff_only
def staff_equipment_page():
    return render_template("staff_equipment.html", full_name=session["full_name"])


@staff_bp.get("/api/staff/equipment")
@staff_api
def staff_equipment_list():
    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT equipment_id, equipment_name, category, available_stock, unit_type "
                "FROM equipment WHERE available_stock > 0 ORDER BY equipment_name"
            )
            return jsonify(cursor.fetchall())
    except mysql.connector.Error:
        return jsonify(error="Unable to load available equipment."), 500


@staff_bp.get("/staff/requests")
@staff_only
def staff_requests_page():
    return render_template("staff_requests.html", full_name=session["full_name"])


@staff_bp.get("/api/staff/requests")
@staff_api
def staff_request_list():
    """Return only requests owned by the authenticated Staff account."""
    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT b.borrowing_id, e.equipment_name, bi.quantity_borrowed, "
                "  b.purpose_notes, b.date_needed, b.expected_return_date, "
                "  b.additional_notes, b.created_at AS request_date, b.status, b.processed_by "
                "FROM borrowers br "
                "JOIN borrowings b ON b.borrower_id = br.borrower_id "
                "JOIN borrowing_items bi ON bi.borrowing_id = b.borrowing_id "
                "JOIN equipment e ON e.equipment_id = bi.equipment_id "
                "WHERE br.user_id = %s "
                "ORDER BY b.created_at DESC, b.borrowing_id DESC, e.equipment_name",
                (session["user_id"],),
            )
            rows = serialize_date_fields(
                cursor.fetchall(),
                ["date_needed", "expected_return_date", "request_date"],
            )
            return jsonify(rows)
    except mysql.connector.Error:
        return jsonify(error="Unable to load your borrowing requests."), 500


@staff_bp.post("/staff/requests/create")
@staff_only
def staff_request_create():
    try:
        (
            equipment_id,
            quantity,
            date_needed,
            expected_return,
            purpose,
            notes,
        ) = parse_staff_request_form(request.form)
    except ValueError as error:
        return redirect_with_message("staff_equipment_page", str(error))

    try:
        with get_db_connection() as (db, cursor):
            db.start_transaction()
            cursor.execute(
                "SELECT borrower_id FROM borrowers WHERE user_id = %s FOR UPDATE",
                (session["user_id"],),
            )
            borrower = cursor.fetchone()

            if not borrower:
                cursor.execute(
                    "SELECT full_name, contact_number, address, email "
                    "FROM users WHERE user_id = %s FOR UPDATE",
                    (session["user_id"],),
                )
                user = cursor.fetchone()
                if not user:
                    raise ValueError("User account not found.")

                # Check if there is an unlinked borrower record (matching email or full name)
                cursor.execute(
                    "SELECT borrower_id FROM borrowers "
                    "WHERE user_id IS NULL AND (email = %s OR full_name = %s) "
                    "LIMIT 1 FOR UPDATE",
                    (user.get("email"), user.get("full_name")),
                )
                unlinked = cursor.fetchone()
                if unlinked:
                    cursor.execute(
                        "UPDATE borrowers SET user_id = %s WHERE borrower_id = %s",
                        (session["user_id"], unlinked["borrower_id"]),
                    )
                    borrower_id = unlinked["borrower_id"]
                else:
                    cursor.execute(
                        "INSERT INTO borrowers (user_id, full_name, contact_number, address, email) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (
                            session["user_id"],
                            user["full_name"],
                            user.get("contact_number") or None,
                            user.get("address") or None,
                            user.get("email") or None,
                        ),
                    )
                    borrower_id = cursor.lastrowid
            else:
                borrower_id = borrower["borrower_id"]

            cursor.execute(
                "SELECT equipment_name, available_stock "
                "FROM equipment WHERE equipment_id = %s FOR UPDATE",
                (equipment_id,),
            )
            equipment = cursor.fetchone()
            if not equipment:
                raise ValueError("The selected equipment no longer exists.")
            if quantity > equipment["available_stock"]:
                raise ValueError(
                    f"Only {equipment['available_stock']} item(s) of "
                    f"{equipment['equipment_name']} are available."
                )
            validate_request_reservation(
                cursor, equipment_id, quantity, equipment["available_stock"]
            )

            cursor.execute(
                "INSERT INTO borrowings "
                "(borrower_id, date_needed, expected_return_date, purpose_notes, additional_notes, status) "
                "VALUES (%s, %s, %s, %s, %s, 'Pending')",
                (borrower_id, date_needed, expected_return, purpose, notes or None),
            )
            borrowing_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO borrowing_items "
                "(borrowing_id, equipment_id, quantity_borrowed, quantity_returned, remaining_quantity) "
                "VALUES (%s, %s, %s, 0, %s)",
                (borrowing_id, equipment_id, quantity, quantity),
            )
            log_audit(
                cursor,
                "CREATE",
                "borrowings",
                borrowing_id,
                f"Submitted borrowing request #{borrowing_id}",
            )
            db.commit()
            return redirect_with_message(
                "staff_requests_page",
                "Borrowing request submitted successfully. It is pending Admin review.",
            )
    except (mysql.connector.Error, ValueError) as error:
        return redirect_with_message(
            "staff_equipment_page",
            str(error)
            if isinstance(error, ValueError)
            else "Unable to submit your borrowing request. No request was saved.",
        )


@staff_bp.get("/staff/borrowed-items")
@staff_only
def staff_borrowed_items_page():
    return render_template("staff_borrowed_items.html", full_name=session["full_name"])


@staff_bp.get("/api/staff/borrowed-items")
@staff_api
def staff_borrowed_items_list():
    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT b.borrowing_id, e.equipment_name, bi.quantity_borrowed, "
                "  bi.quantity_returned, "
                "  GREATEST(bi.quantity_borrowed - bi.quantity_returned, 0) AS remaining_quantity, "
                "  b.borrowed_at, b.expected_return_date, b.status "
                "FROM borrowers br "
                "JOIN borrowings b ON b.borrower_id = br.borrower_id "
                "JOIN borrowing_items bi ON bi.borrowing_id = b.borrowing_id "
                "JOIN equipment e ON e.equipment_id = bi.equipment_id "
                "WHERE br.user_id = %s "
                "  AND b.status IN ('Active', 'Partially Returned', 'Returned') "
                "ORDER BY b.borrowed_at DESC, b.borrowing_id DESC",
                (session["user_id"],),
            )
            return jsonify(cursor.fetchall())
    except mysql.connector.Error:
        return jsonify(error="Unable to load your borrowed items."), 500


@staff_bp.get("/staff/profile")
@staff_only
def staff_profile_page():
    return render_template(
        "staff_profile.html",
        full_name=session["full_name"],
        username=session["username"],
        role=session["role"],
    )

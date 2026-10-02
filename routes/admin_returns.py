"""Admin routes for equipment returns processing."""
from datetime import date
import mysql.connector
from flask import Blueprint, jsonify, render_template, request, session

from auth import admin_api, admin_only, redirect_with_message
from database import get_db_connection, log_audit
from services import validate_and_return_stock
from validators import parse_return_form

admin_returns_bp = Blueprint("admin_returns_routes", __name__)


@admin_returns_bp.get("/returns")
@admin_only
def returns_page():
    return render_template(
        "returns.html",
        full_name=session["full_name"],
        role=session.get("role", ""),
        today=date.today().isoformat(),
    )


@admin_returns_bp.get("/api/returnable-borrowings")
@admin_api
def returnable_borrowings():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    date_field = request.args.get("date_field", "borrowed")
    sort = request.args.get("sort", "newest")

    try:
        with get_db_connection() as (db, cursor):
            sql = (
                "SELECT DISTINCT b.borrowing_id, b.borrowed_at, b.expected_return_date, "
                "b.status, br.full_name "
                "FROM borrowings b "
                "JOIN borrowers br ON br.borrower_id = b.borrower_id "
                "WHERE b.status IN ('Active', 'Partially Returned')"
            )
            values = []

            if search:
                sql += (
                    " AND (br.full_name LIKE %s "
                    "OR CAST(b.borrowing_id AS CHAR) LIKE %s "
                    "OR EXISTS ("
                    "  SELECT 1 FROM borrowing_items si "
                    "  JOIN equipment se ON se.equipment_id = si.equipment_id "
                    "  WHERE si.borrowing_id = b.borrowing_id "
                    "  AND se.equipment_name LIKE %s))"
                )
                values += [f"%{search}%"] * 3

            if status:
                sql += " AND b.status = %s"
                values.append(status)

            # Determine which date column to filter on
            date_column_map = {
                "expected": "DATE(b.expected_return_date)",
                "actual": (
                    "(SELECT MAX(rr.return_date) FROM return_records rr "
                    "JOIN borrowing_items ri ON ri.borrowing_item_id = rr.borrowing_item_id "
                    "WHERE ri.borrowing_id = b.borrowing_id)"
                ),
            }
            column = date_column_map.get(date_field, "DATE(b.borrowed_at)")

            if start_date:
                sql += f" AND {column} >= %s"
                values.append(start_date)
            if end_date:
                sql += f" AND {column} <= %s"
                values.append(end_date)

            order_map = {
                "newest": "b.borrowed_at DESC",
                "oldest": "b.borrowed_at",
                "borrower": "br.full_name",
                "status": "b.status, b.borrowed_at DESC",
                "expected": "b.expected_return_date",
            }
            sql += " ORDER BY " + order_map.get(sort, "b.borrowed_at DESC")

            cursor.execute(sql, values)
            return jsonify(cursor.fetchall())
    except mysql.connector.Error:
        return jsonify(error="Unable to load borrowing transactions."), 500


@admin_returns_bp.get("/api/borrowings/<int:borrowing_id>/items")
@admin_api
def return_items(borrowing_id):
    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT b.borrowing_id, b.borrowed_at, b.expected_return_date, "
                "  b.status, br.full_name, br.contact_number, br.address "
                "FROM borrowings b "
                "JOIN borrowers br ON br.borrower_id = b.borrower_id "
                "WHERE b.borrowing_id = %s",
                (borrowing_id,),
            )
            loan = cursor.fetchone()
            if not loan:
                return jsonify(error="Borrowing transaction not found."), 404

            cursor.execute(
                "SELECT bi.borrowing_item_id, e.equipment_name, e.unit_type, "
                "  bi.quantity_borrowed, bi.quantity_returned, "
                "  GREATEST(bi.quantity_borrowed - bi.quantity_returned, 0) AS remaining_quantity "
                "FROM borrowing_items bi "
                "JOIN equipment e ON e.equipment_id = bi.equipment_id "
                "WHERE bi.borrowing_id = %s ORDER BY e.equipment_name",
                (borrowing_id,),
            )
            loan["items"] = cursor.fetchall()
            return jsonify(loan)
    except mysql.connector.Error:
        return jsonify(error="Unable to load loan items."), 500


@admin_returns_bp.post("/returns/save")
@admin_only
def return_save():
    try:
        borrowing_id, return_date, items, return_notes = parse_return_form(request.form)
    except ValueError as error:
        return redirect_with_message("returns_page", str(error))

    try:
        with get_db_connection() as (db, cursor):
            db.start_transaction()
            new_status = validate_and_return_stock(
                cursor, borrowing_id, items, return_date,
                session["user_id"], return_notes,
            )
            log_audit(
                cursor,
                "RETURN",
                "borrowings",
                borrowing_id,
                f"Recorded return for transaction #{borrowing_id}; status: {new_status}",
            )
            db.commit()
            return redirect_with_message(
                "returns_page",
                f"Return saved successfully. Transaction status: {new_status}.",
            )
    except (mysql.connector.Error, ValueError, RuntimeError) as error:
        return redirect_with_message(
            "returns_page",
            str(error)
            if isinstance(error, (ValueError, RuntimeError))
            else "Unable to save return. No stock was changed.",
        )


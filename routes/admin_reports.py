"""Admin routes for generating inventory and transaction reports."""
import mysql.connector
from flask import Blueprint, jsonify, render_template, request, session

from auth import admin_api, admin_only
from database import STATUS_SQL_EXPRESSION, get_db_connection

admin_reports_bp = Blueprint("admin_reports_routes", __name__)


@admin_reports_bp.get("/reports")
@admin_only
def reports_page():
    return render_template("reports.html", full_name=session["full_name"])


@admin_reports_bp.get("/api/reports")
@admin_api
def reports_data():
    report = request.args.get("type", "inventory")
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    start = request.args.get("start_date", "").strip()
    end = request.args.get("end_date", "").strip()
    borrower = request.args.get("borrower_id", "").strip()

    try:
        with get_db_connection() as (db, cursor):
            values = []

            if report in ("inventory", "available"):
                sql = (
                    f"SELECT equipment_id AS 'Equipment ID', "
                    f"  equipment_name AS 'Equipment Name', "
                    f"  category AS Category, "
                    f"  total_stock AS 'Total Quantity', "
                    f"  available_stock AS 'Available Quantity', "
                    f"  (total_stock - available_stock) AS 'Borrowed Quantity', "
                    f"  unit_type AS Unit, "
                    f"  {STATUS_SQL_EXPRESSION} AS Status "
                    f"FROM equipment WHERE 1=1"
                )
                if report == "available":
                    sql += " AND available_stock > 0"
                if search:
                    sql += " AND (equipment_name LIKE %s OR category LIKE %s OR unit_type LIKE %s)"
                    values += [f"%{search}%"] * 3
                if status:
                    sql += f" AND ({STATUS_SQL_EXPRESSION}) = %s"
                    values.append(status)
                sql += " ORDER BY equipment_name"

            elif report in ("active", "returned", "transaction", "history"):
                sql = (
                    "SELECT b.borrowing_id AS 'Loan ID', "
                    "  br.full_name AS Borrower, "
                    "  e.equipment_name AS Equipment, "
                    "  bi.quantity_borrowed AS Quantity, "
                    "  bi.quantity_returned AS 'Quantity Returned', "
                    "  bi.remaining_quantity AS Remaining, "
                    "  DATE(b.borrowed_at) AS 'Borrow Date', "
                    "  b.expected_return_date AS 'Expected Return Date', "
                    "  b.status AS Status, "
                    "  (SELECT MAX(rr.return_date) FROM return_records rr "
                    "   WHERE rr.borrowing_item_id = bi.borrowing_item_id) AS 'Return Date' "
                    "FROM borrowings b "
                    "JOIN borrowers br ON br.borrower_id = b.borrower_id "
                    "JOIN borrowing_items bi ON bi.borrowing_id = b.borrowing_id "
                    "JOIN equipment e ON e.equipment_id = bi.equipment_id "
                    "WHERE 1=1"
                )
                if report == "active":
                    sql += " AND b.status IN ('Active', 'Partially Returned')"
                if report == "returned":
                    sql += " AND b.status = 'Returned'"
                if report == "history":
                    sql += " AND b.status IN ('Active', 'Partially Returned', 'Returned')"
                    if borrower:
                        sql += " AND b.borrower_id = %s"
                        values.append(borrower)
                if search:
                    sql += (
                        " AND (br.full_name LIKE %s OR e.equipment_name LIKE %s "
                        "OR CAST(b.borrowing_id AS CHAR) LIKE %s)"
                    )
                    values += [f"%{search}%"] * 3
                if status:
                    sql += " AND b.status = %s"
                    values.append(status)
                if start:
                    sql += " AND DATE(b.borrowed_at) >= %s"
                    values.append(start)
                if end:
                    sql += " AND DATE(b.borrowed_at) <= %s"
                    values.append(end)
                sql += " ORDER BY b.borrowed_at DESC, b.borrowing_id, e.equipment_name"

            elif report == "current_borrowers":
                sql = (
                    "SELECT br.full_name AS Borrower, "
                    "  br.contact_number AS 'Contact Number', "
                    "  br.address AS Address, "
                    "  GROUP_CONCAT(DISTINCT b.borrowing_id ORDER BY b.borrowing_id SEPARATOR ', ') AS 'Active Loan IDs', "
                    "  GROUP_CONCAT(DISTINCT e.equipment_name ORDER BY e.equipment_name SEPARATOR ', ') AS 'Borrowed Equipment', "
                    "  SUM(bi.quantity_borrowed - bi.quantity_returned) AS 'Items Currently Borrowed' "
                    "FROM borrowings b "
                    "JOIN borrowers br ON br.borrower_id = b.borrower_id "
                    "JOIN borrowing_items bi ON bi.borrowing_id = b.borrowing_id "
                    "JOIN equipment e ON e.equipment_id = bi.equipment_id "
                    "WHERE b.status IN ('Active', 'Partially Returned')"
                )
                if search:
                    sql += " AND (br.full_name LIKE %s OR e.equipment_name LIKE %s OR CAST(b.borrowing_id AS CHAR) LIKE %s)"
                    values += [f"%{search}%"] * 3
                if start:
                    sql += " AND DATE(b.borrowed_at) >= %s"
                    values.append(start)
                if end:
                    sql += " AND DATE(b.borrowed_at) <= %s"
                    values.append(end)
                if borrower:
                    sql += " AND b.borrower_id = %s"
                    values.append(borrower)
                sql += " GROUP BY br.borrower_id, br.full_name, br.contact_number, br.address ORDER BY br.full_name"

            else:
                return jsonify(error="Unknown report type."), 400

            cursor.execute(sql, values)
            return jsonify(cursor.fetchall())
    except mysql.connector.Error:
        return jsonify(error="Unable to generate report."), 500

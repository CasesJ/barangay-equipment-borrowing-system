"""Dashboard routes for Admin and Staff users."""
from flask import Blueprint, render_template, session

from auth import admin_only, staff_only
from database import DatabaseError, get_rows
from services import dashboard_statistics

dashboard_bp = Blueprint("dashboard_routes", __name__)


@dashboard_bp.get("/dashboard")
@admin_only
def dashboard():
    stats, database_connected = dashboard_statistics()
    return render_template(
        "dashboard.html",
        stats=stats,
        database_connected=database_connected,
        full_name=session["full_name"],
        role=session.get("role", ""),
        show_user_management=session.get("role", "").lower() == "admin",
    )


@dashboard_bp.get("/staff-dashboard")
@staff_only
def staff_dashboard():
    stats = {
        "available_equipment": 0,
        "pending_requests": 0,
        "approved_requests": 0,
        "currently_borrowed": 0,
        "returned_items": 0,
    }
    database_connected = False
    try:
        equipment = get_rows("equipment")
        borrowers = {row["borrower_id"] for row in get_rows("borrowers") if row.get("user_id") == session["user_id"]}
        borrowings = [row for row in get_rows("borrowings") if row["borrower_id"] in borrowers]
        returned_ids = {row["borrowing_id"] for row in borrowings if row["status"] == "Returned"}
        stats["available_equipment"] = sum(row["available_stock"] for row in equipment)
        stats["pending_requests"] = sum(row["status"] == "Pending" for row in borrowings)
        stats["approved_requests"] = sum(row["status"] == "Approved" for row in borrowings)
        stats["currently_borrowed"] = sum(
            row["status"] in ("Active", "Partially Returned") for row in borrowings
        )
        stats["returned_items"] = sum(
            row["quantity_returned"]
            for row in get_rows("borrowing_items")
            if row["borrowing_id"] in returned_ids
        )
        database_connected = True
    except DatabaseError:
        pass

    return render_template(
        "staff_dashboard.html",
        stats=stats,
        database_connected=database_connected,
        full_name=session["full_name"],
        role=session.get("role", ""),
    )

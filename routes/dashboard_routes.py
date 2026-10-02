"""Dashboard routes for Admin and Staff users."""
import mysql.connector
from flask import Blueprint, render_template, session

from auth import admin_only, staff_only
from database import get_db_connection
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
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT COALESCE(SUM(available_stock), 0) AS available_equipment "
                "FROM equipment"
            )
            stats.update(cursor.fetchone())
            cursor.execute(
                "SELECT "
                "  COUNT(DISTINCT CASE WHEN b.status = 'Pending' THEN b.borrowing_id END) AS pending_requests, "
                "  COUNT(DISTINCT CASE WHEN b.status = 'Approved' THEN b.borrowing_id END) AS approved_requests, "
                "  COUNT(DISTINCT CASE WHEN b.status IN ('Active', 'Partially Returned') THEN b.borrowing_id END) AS currently_borrowed, "
                "  COALESCE(SUM(CASE WHEN b.status = 'Returned' "
                "    THEN bi.quantity_returned ELSE 0 END), 0) AS returned_items "
                "FROM borrowers br "
                "JOIN borrowings b ON b.borrower_id = br.borrower_id "
                "LEFT JOIN borrowing_items bi ON bi.borrowing_id = b.borrowing_id "
                "WHERE br.user_id = %s",
                (session["user_id"],),
            )
            stats.update({k: v or 0 for k, v in cursor.fetchone().items()})
            database_connected = True
    except mysql.connector.Error:
        pass

    return render_template(
        "staff_dashboard.html",
        stats=stats,
        database_connected=database_connected,
        full_name=session["full_name"],
        role=session.get("role", ""),
    )

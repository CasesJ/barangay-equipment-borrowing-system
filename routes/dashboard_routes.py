"""Dashboard routes for Admin and Staff users."""
from flask import Blueprint

from auth import admin_only, frontend_redirect, staff_only
from database import DatabaseError, get_rows
from services import dashboard_statistics

dashboard_bp = Blueprint("dashboard_routes", __name__)


@dashboard_bp.get("/dashboard")
@admin_only
def dashboard():
    return frontend_redirect("/dashboard")


@dashboard_bp.get("/staff-dashboard")
@staff_only
def staff_dashboard():
    return frontend_redirect("/staff-dashboard")

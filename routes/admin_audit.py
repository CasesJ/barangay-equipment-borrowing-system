"""Admin routes for viewing system audit logs."""
import mysql.connector
from flask import Blueprint, jsonify, render_template, request, session

from auth import admin_api, admin_only
from database import get_db_connection

admin_audit_bp = Blueprint("admin_audit_routes", __name__)


@admin_audit_bp.get("/audit-logs")
@admin_only
def audit_logs_page():
    return render_template(
        "audit_logs.html",
        full_name=session["full_name"],
        role=session.get("role", ""),
    )


@admin_audit_bp.get("/api/audit-logs")
@admin_api
def audit_log_list():
    search = request.args.get("search", "").strip()
    action = request.args.get("action", "").strip()
    table = request.args.get("table", "").strip()
    start = request.args.get("start_date", "").strip()
    end = request.args.get("end_date", "").strip()

    try:
        with get_db_connection() as (db, cursor):
            sql = (
                "SELECT a.audit_id, a.action, a.table_name, a.record_id, "
                "  a.description, a.created_at, u.full_name, u.username "
                "FROM audit_logs a "
                "JOIN users u ON u.user_id = a.user_id "
                "WHERE 1=1"
            )
            values = []
            if search:
                sql += (
                    " AND (u.full_name LIKE %s OR u.username LIKE %s "
                    "OR a.description LIKE %s OR CAST(a.record_id AS CHAR) LIKE %s)"
                )
                values += [f"%{search}%"] * 4
            if action:
                sql += " AND a.action = %s"
                values.append(action)
            if table:
                sql += " AND a.table_name = %s"
                values.append(table)
            if start:
                sql += " AND DATE(a.created_at) >= %s"
                values.append(start)
            if end:
                sql += " AND DATE(a.created_at) <= %s"
                values.append(end)

            cursor.execute(sql + " ORDER BY a.created_at DESC, a.audit_id DESC", values)
            return jsonify(cursor.fetchall())
    except mysql.connector.Error:
        return jsonify(error="Unable to load audit logs."), 500

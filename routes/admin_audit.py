"""Admin routes for viewing system audit logs."""
from flask import Blueprint, jsonify, request

from auth import admin_api, admin_only, frontend_redirect
from database import DatabaseError, get_rows

admin_audit_bp = Blueprint("admin_audit_routes", __name__)


@admin_audit_bp.get("/audit-logs")
@admin_only
def audit_logs_page():
    return frontend_redirect("/audit-logs")


@admin_audit_bp.get("/api/audit-logs")
@admin_api
def audit_log_list():
    search = request.args.get("search", "").strip()
    action = request.args.get("action", "").strip()
    table = request.args.get("table", "").strip()
    start = request.args.get("start_date", "").strip()
    end = request.args.get("end_date", "").strip()

    try:
        users = {row["user_id"]: row for row in get_rows("users")}
        needle = search.lower()
        rows = []
        for record in get_rows("audit_logs"):
            user = users.get(record.get("user_id"), {})
            created_date = (record.get("created_at") or "")[:10]
            if action and record["action"] != action: continue
            if table and record["table_name"] != table: continue
            if start and created_date < start: continue
            if end and created_date > end: continue
            if search and not any(needle in str(value).lower() for value in (user.get("full_name", ""), user.get("username", ""), record.get("description", ""), record.get("record_id", ""))): continue
            rows.append({**record, "full_name": user.get("full_name"), "username": user.get("username")})
        return jsonify(sorted(rows, key=lambda row: (row.get("created_at") or "", row["audit_id"]), reverse=True))
    except DatabaseError:
        return jsonify(error="Unable to load audit logs."), 500

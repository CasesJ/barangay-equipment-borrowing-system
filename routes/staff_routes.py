"""Staff portal routes and API endpoints."""
from flask import Blueprint, jsonify, render_template, request, session

from auth import redirect_with_message, staff_api, staff_only
from database import DatabaseError, call_rpc, get_rows, serialize_date_fields
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
        rows = [row for row in get_rows("equipment") if row["available_stock"] > 0]
        return jsonify(sorted(rows, key=lambda row: row["equipment_name"].lower()))
    except DatabaseError:
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
        borrower_ids = {row["borrower_id"] for row in get_rows("borrowers") if row.get("user_id") == session["user_id"]}
        equipment = {row["equipment_id"]: row for row in get_rows("equipment")}
        rows = []
        for borrowing in get_rows("borrowings"):
            if borrowing["borrower_id"] not in borrower_ids:
                continue
            for item in get_rows("borrowing_items"):
                if item["borrowing_id"] != borrowing["borrowing_id"]:
                    continue
                asset = equipment.get(item["equipment_id"])
                if asset:
                    rows.append({
                        "borrowing_id": borrowing["borrowing_id"], "equipment_name": asset["equipment_name"],
                        "quantity_borrowed": item["quantity_borrowed"], "purpose_notes": borrowing.get("purpose_notes"),
                        "date_needed": borrowing.get("date_needed"), "expected_return_date": borrowing.get("expected_return_date"),
                        "additional_notes": borrowing.get("additional_notes"), "request_date": borrowing.get("created_at"),
                        "status": borrowing["status"], "processed_by": borrowing.get("processed_by"),
                    })
        rows.sort(key=lambda row: (row.get("request_date") or "", row["borrowing_id"], row["equipment_name"]), reverse=True)
        return jsonify(serialize_date_fields(rows, ["date_needed", "expected_return_date", "request_date"]))
    except DatabaseError:
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
        call_rpc(
            "api_submit_staff_request",
            {
                "p_user_id": session["user_id"], "p_equipment_id": equipment_id, "p_quantity": quantity,
                # Supabase sends RPC arguments as JSON; ``date`` objects are
                # not JSON serializable by the HTTP client.  PostgreSQL accepts
                # the ISO-8601 strings below as ``date`` parameters.
                "p_date_needed": date_needed.isoformat(),
                "p_expected_return": expected_return.isoformat(),
                "p_purpose": purpose, "p_notes": notes or None,
            },
        )
        return redirect_with_message(
            "staff_requests_page", "Borrowing request submitted successfully. It is pending Admin review."
        )
    except (DatabaseError, ValueError) as error:
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
        borrower_ids = {row["borrower_id"] for row in get_rows("borrowers") if row.get("user_id") == session["user_id"]}
        equipment = {row["equipment_id"]: row for row in get_rows("equipment")}
        borrowings = {
            row["borrowing_id"]: row for row in get_rows("borrowings")
            if row["borrower_id"] in borrower_ids and row["status"] in ("Active", "Partially Returned", "Returned")
        }
        rows = []
        for item in get_rows("borrowing_items"):
            borrowing = borrowings.get(item["borrowing_id"])
            asset = equipment.get(item["equipment_id"])
            if borrowing and asset:
                rows.append({
                    "borrowing_id": borrowing["borrowing_id"], "equipment_name": asset["equipment_name"],
                    "quantity_borrowed": item["quantity_borrowed"], "quantity_returned": item["quantity_returned"],
                    "remaining_quantity": max(item["quantity_borrowed"] - item["quantity_returned"], 0),
                    "borrowed_at": borrowing.get("borrowed_at"), "expected_return_date": borrowing.get("expected_return_date"),
                    "status": borrowing["status"],
                })
        return jsonify(sorted(rows, key=lambda row: (row.get("borrowed_at") or "", row["borrowing_id"]), reverse=True))
    except DatabaseError:
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

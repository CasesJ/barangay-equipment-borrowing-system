"""Admin routes for borrowing requests and direct loan creation."""
from datetime import date
from flask import Blueprint, jsonify, render_template, request, session

from auth import admin_api, admin_only, redirect_with_message
from database import DatabaseError, call_rpc, first, get_rows, log_audit, serialize_date_fields, update_rows
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
        rows = [row for row in get_rows("equipment") if row["available_stock"] > 0]
        return jsonify(sorted(rows, key=lambda row: row["equipment_name"].lower()))
    except DatabaseError:
        return jsonify(error="Unable to load available equipment."), 500


@admin_borrowings_bp.post("/borrowings/create")
@admin_only
def borrowing_create():
    try:
        borrower_id, due_date, purpose_notes, items = parse_borrowing_form(request.form)
    except ValueError as error:
        return redirect_with_message("borrowings_page", str(error))

    try:
        result = call_rpc(
            "api_create_direct_borrowing",
            {
                "p_borrower_id": borrower_id,
                "p_processed_by": session["user_id"],
                "p_due_date": due_date,
                "p_purpose": purpose_notes,
                "p_items": [{"equipment_id": item_id, "quantity": quantity} for item_id, quantity in items],
            },
        )
        borrowing_id = result.get("borrowing_id") if isinstance(result, dict) else result[0]["borrowing_id"]
        return redirect_with_message(
            "borrowings_page", f"Borrowing transaction #{borrowing_id} saved successfully."
        )
    except (DatabaseError, ValueError, RuntimeError) as error:
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
        users = {row["user_id"]: row for row in get_rows("users")}
        borrowers = {row["borrower_id"]: row for row in get_rows("borrowers")}
        equipment = {row["equipment_id"]: row for row in get_rows("equipment")}
        rows = []
        for borrowing in get_rows("borrowings"):
            borrower = borrowers.get(borrowing["borrower_id"])
            if not borrower:
                continue
            account = users.get(borrower.get("user_id"), {})
            for item in get_rows("borrowing_items"):
                if item["borrowing_id"] != borrowing["borrowing_id"]:
                    continue
                asset = equipment.get(item["equipment_id"])
                if not asset:
                    continue
                rows.append({
                    "borrowing_id": borrowing["borrowing_id"], "borrower_name": account.get("full_name", borrower["full_name"]),
                    "contact_number": borrower.get("contact_number"), "equipment_id": asset["equipment_id"],
                    "equipment_name": asset["equipment_name"], "category": asset["category"],
                    "available_stock": asset["available_stock"], "unit_type": asset["unit_type"],
                    "quantity_borrowed": item["quantity_borrowed"], "purpose_notes": borrowing.get("purpose_notes"),
                    "date_needed": borrowing.get("date_needed"), "expected_return_date": borrowing.get("expected_return_date"),
                    "additional_notes": borrowing.get("additional_notes"), "request_date": borrowing.get("created_at"),
                    "status": borrowing["status"], "processed_by": borrowing.get("processed_by"),
                })
        priority = {"Pending": 0, "Approved": 1}
        rows.sort(key=lambda row: (priority.get(row["status"], 2), row.get("request_date") or ""))
        return jsonify(serialize_date_fields(rows, ["date_needed", "expected_return_date", "request_date"]))
    except DatabaseError:
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
        record = first([row for row in get_rows("borrowings") if row["borrowing_id"] == borrowing_id])
        if not record:
            raise ValueError("Borrowing request was not found.")
        if action == "approve" and record["status"] != "Pending":
            raise ValueError("Only Pending requests can be approved.")
        if action in ("reject", "cancel") and record["status"] not in ("Pending", "Approved"):
            raise ValueError("Only Pending or Approved requests can be rejected or cancelled.")
        new_status, description, user_msg = status_map[action]
        update_rows("borrowings", {"status": new_status, "processed_by": session["user_id"]}, "borrowing_id", borrowing_id)
        log_audit("UPDATE", "borrowings", borrowing_id, description)
        return redirect_with_message("admin_request_review_page", user_msg)
    except (DatabaseError, ValueError) as error:
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
        call_rpc(
            "api_release_borrowing_request",
            {"p_borrowing_id": borrowing_id, "p_processed_by": session["user_id"]},
        )
        return redirect_with_message(
            "admin_request_review_page",
            "Equipment released successfully. Stock and request status were updated.",
        )
    except (DatabaseError, ValueError, RuntimeError) as error:
        return redirect_with_message(
            "admin_request_review_page",
            str(error)
            if isinstance(error, (ValueError, RuntimeError))
            else "Unable to release equipment. No stock was changed.",
        )

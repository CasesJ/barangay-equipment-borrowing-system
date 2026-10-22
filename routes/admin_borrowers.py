"""Admin routes for borrower management."""
from flask import Blueprint, jsonify, render_template, request, session

from auth import admin_api, admin_only, redirect_with_message
from database import DatabaseError, call_rpc, delete_rows, first, get_rows, insert_row, log_audit, update_rows
from services import has_active_borrower_loan
from validators import parse_borrower_form

admin_borrowers_bp = Blueprint("admin_borrowers_routes", __name__)


@admin_borrowers_bp.get("/borrowers")
@admin_only
def borrowers_page():
    return render_template(
        "borrowers.html",
        full_name=session["full_name"],
        role=session.get("role", ""),
    )


@admin_borrowers_bp.get("/api/borrowers")
@admin_api
def borrower_list():
    search = request.args.get("search", "").strip()
    try:
        pending_borrowers = {
            row["borrower_id"] for row in get_rows("borrowings") if row["status"] == "Pending"
        }
        rows = get_rows("borrowers")
        if search:
            needle = search.lower()
            rows = [
                row for row in rows
                if needle in row["full_name"].lower()
                or needle in (row.get("contact_number") or "").lower()
                or needle in (row.get("address") or "").lower()
                or needle in (row.get("email") or "").lower()
            ]
        for row in rows:
            row["has_pending_request"] = row["borrower_id"] in pending_borrowers
        return jsonify(sorted(rows, key=lambda row: row["full_name"].lower()))
    except DatabaseError:
        return jsonify(error="Unable to load borrowers. Check the database connection."), 500


@admin_borrowers_bp.post("/borrowers/add")
@admin_only
def borrower_add():
    try:
        full_name, contact_number, address, email = parse_borrower_form(request.form)
    except ValueError as error:
        return redirect_with_message("borrowers_page", str(error))

    try:
        borrower = insert_row(
            "borrowers",
            {"full_name": full_name, "contact_number": contact_number, "address": address, "email": email},
        )
        log_audit("CREATE", "borrowers", borrower["borrower_id"], f"Added borrower: {full_name}")
        return redirect_with_message("borrowers_page", "Borrower added successfully.")
    except DatabaseError:
        return redirect_with_message("borrowers_page", "Unable to add borrower. Please try again.")


@admin_borrowers_bp.post("/borrowers/<int:borrower_id>/edit")
@admin_only
def borrower_edit(borrower_id):
    try:
        full_name, contact_number, address, email = parse_borrower_form(request.form)
    except ValueError as error:
        return redirect_with_message("borrowers_page", str(error))

    try:
        if not first([row for row in get_rows("borrowers") if row["borrower_id"] == borrower_id]):
            return redirect_with_message("borrowers_page", "Borrower record was not found.")
        update_rows(
            "borrowers",
            {"full_name": full_name, "contact_number": contact_number, "address": address, "email": email},
            "borrower_id",
            borrower_id,
        )
        log_audit("UPDATE", "borrowers", borrower_id, f"Updated borrower: {full_name}")
        return redirect_with_message("borrowers_page", "Borrower updated successfully.")
    except DatabaseError:
        return redirect_with_message(
            "borrowers_page", "Unable to update borrower. Please try again."
        )


@admin_borrowers_bp.post("/borrowers/<int:borrower_id>/delete")
@admin_only
def borrower_delete(borrower_id):
    try:
        borrower = first([row for row in get_rows("borrowers") if row["borrower_id"] == borrower_id])
        if not borrower:
            return redirect_with_message("borrowers_page", "Borrower record was not found.")
        if has_active_borrower_loan(borrower_id):
            return redirect_with_message(
                "borrowers_page",
                "This borrower cannot be deleted because they have an active borrowing transaction.",
            )
        delete_rows("borrowers", "borrower_id", borrower_id)
        log_audit("DELETE", "borrowers", borrower_id, f"Deleted borrower: {borrower['full_name']}")
        return redirect_with_message("borrowers_page", "Borrower deleted successfully.")
    except DatabaseError:
        return redirect_with_message(
            "borrowers_page", "Unable to delete borrower. Please try again."
        )


@admin_borrowers_bp.post("/borrowers/<int:borrower_id>/approve-pending-request")
@admin_only
def borrower_approve_pending_request(borrower_id):
    """Approve and release the borrower's oldest pending request in one transaction."""
    try:
        call_rpc(
            "api_approve_pending_request",
            {"p_borrower_id": borrower_id, "p_processed_by": session["user_id"]},
        )
        return redirect_with_message(
            "borrowers_page",
            "Borrowing request approved and equipment released successfully.",
        )
    except (DatabaseError, ValueError, RuntimeError) as error:
        return redirect_with_message(
            "borrowers_page",
            str(error)
            if isinstance(error, (ValueError, RuntimeError))
            else "Unable to approve the borrowing request. No stock was changed.",
        )

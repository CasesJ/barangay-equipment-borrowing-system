"""Admin routes for borrower management."""
import mysql.connector
from flask import Blueprint, jsonify, render_template, request, session

from auth import admin_api, admin_only, redirect_with_message
from database import get_db_connection, log_audit
from services import has_active_borrower_loan, validate_and_release_stock
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
        with get_db_connection() as (db, cursor):
            sql = (
                "SELECT br.borrower_id, br.full_name, br.contact_number, br.address, "
                "br.email, br.created_at, br.updated_at, "
                "EXISTS("
                "  SELECT 1 FROM borrowings b "
                "  WHERE b.borrower_id = br.borrower_id AND b.status = 'Pending'"
                ") AS has_pending_request "
                "FROM borrowers br"
            )
            values = []
            if search:
                sql += (
                    " WHERE br.full_name LIKE %s OR br.contact_number LIKE %s "
                    "OR br.address LIKE %s OR br.email LIKE %s"
                )
                values = [f"%{search}%"] * 4
            cursor.execute(sql + " ORDER BY br.full_name", values)
            return jsonify(cursor.fetchall())
    except mysql.connector.Error:
        return jsonify(error="Unable to load borrowers. Check the MySQL connection."), 500


@admin_borrowers_bp.post("/borrowers/add")
@admin_only
def borrower_add():
    try:
        full_name, contact_number, address, email = parse_borrower_form(request.form)
    except ValueError as error:
        return redirect_with_message("borrowers_page", str(error))

    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "INSERT INTO borrowers (full_name, contact_number, address, email) "
                "VALUES (%s, %s, %s, %s)",
                (full_name, contact_number, address, email),
            )
            borrower_id = cursor.lastrowid
            log_audit(cursor, "CREATE", "borrowers", borrower_id, f"Added borrower: {full_name}")
            db.commit()
            return redirect_with_message("borrowers_page", "Borrower added successfully.")
    except mysql.connector.Error:
        return redirect_with_message("borrowers_page", "Unable to add borrower. Please try again.")


@admin_borrowers_bp.post("/borrowers/<int:borrower_id>/edit")
@admin_only
def borrower_edit(borrower_id):
    try:
        full_name, contact_number, address, email = parse_borrower_form(request.form)
    except ValueError as error:
        return redirect_with_message("borrowers_page", str(error))

    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "UPDATE borrowers SET full_name = %s, contact_number = %s, "
                "address = %s, email = %s WHERE borrower_id = %s",
                (full_name, contact_number, address, email, borrower_id),
            )
            if not cursor.rowcount:
                db.rollback()
                return redirect_with_message("borrowers_page", "Borrower record was not found.")
            log_audit(cursor, "UPDATE", "borrowers", borrower_id, f"Updated borrower: {full_name}")
            db.commit()
            return redirect_with_message("borrowers_page", "Borrower updated successfully.")
    except mysql.connector.Error:
        return redirect_with_message(
            "borrowers_page", "Unable to update borrower. Please try again."
        )


@admin_borrowers_bp.post("/borrowers/<int:borrower_id>/delete")
@admin_only
def borrower_delete(borrower_id):
    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT full_name FROM borrowers WHERE borrower_id = %s FOR UPDATE",
                (borrower_id,),
            )
            borrower = cursor.fetchone()
            if not borrower:
                return redirect_with_message("borrowers_page", "Borrower record was not found.")
            if has_active_borrower_loan(cursor, borrower_id):
                db.rollback()
                return redirect_with_message(
                    "borrowers_page",
                    "This borrower cannot be deleted because they have an active borrowing transaction.",
                )

            cursor.execute("DELETE FROM borrowers WHERE borrower_id = %s", (borrower_id,))
            log_audit(
                cursor,
                "DELETE",
                "borrowers",
                borrower_id,
                f"Deleted borrower: {borrower['full_name']}",
            )
            db.commit()
            return redirect_with_message("borrowers_page", "Borrower deleted successfully.")
    except mysql.connector.Error:
        return redirect_with_message(
            "borrowers_page", "Unable to delete borrower. Please try again."
        )


@admin_borrowers_bp.post("/borrowers/<int:borrower_id>/approve-pending-request")
@admin_only
def borrower_approve_pending_request(borrower_id):
    """Approve and release the borrower's oldest pending request in one transaction."""
    try:
        with get_db_connection() as (db, cursor):
            db.start_transaction()
            cursor.execute(
                "SELECT borrowing_id FROM borrowings "
                "WHERE borrower_id = %s AND status = 'Pending' "
                "ORDER BY created_at, borrowing_id LIMIT 1 FOR UPDATE",
                (borrower_id,),
            )
            pending_request = cursor.fetchone()
            if not pending_request:
                raise ValueError("This borrower has no pending borrowing request to approve.")
            borrowing_id = pending_request["borrowing_id"]

            validate_and_release_stock(cursor, borrowing_id)

            cursor.execute(
                "UPDATE borrowings SET status = 'Active', processed_by = %s, "
                "borrowed_at = NOW() WHERE borrowing_id = %s",
                (session["user_id"], borrowing_id),
            )
            log_audit(
                cursor,
                "UPDATE",
                "borrowings",
                borrowing_id,
                f"Approved and released borrowing request #{borrowing_id}",
            )
            db.commit()
            return redirect_with_message(
                "borrowers_page",
                "Borrowing request approved and equipment released successfully.",
            )
    except (mysql.connector.Error, ValueError, RuntimeError) as error:
        return redirect_with_message(
            "borrowers_page",
            str(error)
            if isinstance(error, (ValueError, RuntimeError))
            else "Unable to approve the borrowing request. No stock was changed.",
        )

"""Admin routes for equipment returns processing."""
from datetime import date
from flask import Blueprint, jsonify, render_template, request, session

from auth import admin_api, admin_only, redirect_with_message
from database import DatabaseError, call_rpc, first, get_rows
from validators import parse_return_form

admin_returns_bp = Blueprint("admin_returns_routes", __name__)


@admin_returns_bp.get("/returns")
@admin_only
def returns_page():
    return render_template(
        "returns.html",
        full_name=session["full_name"],
        role=session.get("role", ""),
        today=date.today().isoformat(),
    )


@admin_returns_bp.get("/api/returnable-borrowings")
@admin_api
def returnable_borrowings():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    date_field = request.args.get("date_field", "borrowed")
    sort = request.args.get("sort", "newest")

    try:
        borrowers = {row["borrower_id"]: row for row in get_rows("borrowers")}
        equipment = {row["equipment_id"]: row for row in get_rows("equipment")}
        item_names = {}
        for item in get_rows("borrowing_items"):
            item_names.setdefault(item["borrowing_id"], []).append(equipment.get(item["equipment_id"], {}).get("equipment_name", ""))
        rows = []
        for row in get_rows("borrowings"):
            if row["status"] not in ("Active", "Partially Returned"):
                continue
            borrower = borrowers.get(row["borrower_id"])
            if not borrower or (status and row["status"] != status):
                continue
            date_value = row.get("expected_return_date") if date_field == "expected" else row.get("borrowed_at")
            if start_date and (date_value or "")[:10] < start_date:
                continue
            if end_date and (date_value or "")[:10] > end_date:
                continue
            if search:
                needle = search.lower()
                if not (
                    needle in borrower["full_name"].lower()
                    or needle in str(row["borrowing_id"])
                    or any(needle in name.lower() for name in item_names.get(row["borrowing_id"], []))
                ):
                    continue
            rows.append({
                "borrowing_id": row["borrowing_id"], "borrowed_at": row.get("borrowed_at"),
                "expected_return_date": row.get("expected_return_date"), "status": row["status"],
                "full_name": borrower["full_name"],
            })
        if sort == "borrower": rows.sort(key=lambda row: row["full_name"].lower())
        elif sort == "status": rows.sort(key=lambda row: (row["status"], row.get("borrowed_at") or ""), reverse=True)
        elif sort == "expected": rows.sort(key=lambda row: row.get("expected_return_date") or "")
        else: rows.sort(key=lambda row: row.get("borrowed_at") or "", reverse=sort != "oldest")
        return jsonify(rows)
    except DatabaseError:
        return jsonify(error="Unable to load borrowing transactions."), 500


@admin_returns_bp.get("/api/borrowings/<int:borrowing_id>/items")
@admin_api
def return_items(borrowing_id):
    try:
        loan = first([row for row in get_rows("borrowings") if row["borrowing_id"] == borrowing_id])
        if not loan:
            return jsonify(error="Borrowing transaction not found."), 404
        borrower = first([row for row in get_rows("borrowers") if row["borrower_id"] == loan["borrower_id"]])
        equipment = {row["equipment_id"]: row for row in get_rows("equipment")}
        loan = dict(loan)
        loan.update({key: borrower.get(key) for key in ("full_name", "contact_number", "address")})
        loan["items"] = sorted([
            {
                "borrowing_item_id": item["borrowing_item_id"], "equipment_name": equipment[item["equipment_id"]]["equipment_name"],
                "unit_type": equipment[item["equipment_id"]]["unit_type"], "quantity_borrowed": item["quantity_borrowed"],
                "quantity_returned": item["quantity_returned"], "remaining_quantity": max(item["quantity_borrowed"] - item["quantity_returned"], 0),
            }
            for item in get_rows("borrowing_items") if item["borrowing_id"] == borrowing_id and item["equipment_id"] in equipment
        ], key=lambda item: item["equipment_name"].lower())
        return jsonify(loan)
    except DatabaseError:
        return jsonify(error="Unable to load loan items."), 500


@admin_returns_bp.post("/returns/save")
@admin_only
def return_save():
    try:
        borrowing_id, return_date, items, return_notes = parse_return_form(request.form)
    except ValueError as error:
        return redirect_with_message("returns_page", str(error))

    try:
        result = call_rpc(
            "api_save_return",
            {
                "p_borrowing_id": borrowing_id, "p_return_date": return_date,
                "p_items": [{"borrowing_item_id": item_id, "quantity": quantity} for item_id, quantity in items],
                "p_received_by": session["user_id"], "p_notes": return_notes,
            },
        )
        new_status = result.get("status") if isinstance(result, dict) else result[0]["status"]
        return redirect_with_message("returns_page", f"Return saved successfully. Transaction status: {new_status}.")
    except (DatabaseError, ValueError, RuntimeError) as error:
        return redirect_with_message(
            "returns_page",
            str(error)
            if isinstance(error, (ValueError, RuntimeError))
            else "Unable to save return. No stock was changed.",
        )


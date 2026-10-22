"""Admin routes for generating inventory and transaction reports."""
from flask import Blueprint, jsonify, request

from auth import admin_api, admin_only, frontend_redirect
from database import DatabaseError, get_rows

admin_reports_bp = Blueprint("admin_reports_routes", __name__)


@admin_reports_bp.get("/reports")
@admin_only
def reports_page():
    return frontend_redirect("/reports")


@admin_reports_bp.get("/api/reports")
@admin_api
def reports_data():
    report = request.args.get("type", "inventory")
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    start = request.args.get("start_date", "").strip()
    end = request.args.get("end_date", "").strip()
    borrower = request.args.get("borrower_id", "").strip()

    try:
        equipment = {row["equipment_id"]: row for row in get_rows("equipment")}
        borrowers = {row["borrower_id"]: row for row in get_rows("borrowers")}
        borrowings = get_rows("borrowings")
        items = get_rows("borrowing_items")
        returns = get_rows("return_records")
        needle = search.lower()
        if report in ("inventory", "available"):
            rows = []
            for asset in equipment.values():
                asset_status = "Out of Stock" if asset["available_stock"] == 0 else "Low Stock" if asset["available_stock"] < asset["total_stock"] else "Available"
                if report == "available" and asset["available_stock"] <= 0: continue
                if status and asset_status != status: continue
                if search and not any(needle in str(asset[key]).lower() for key in ("equipment_name", "category", "unit_type")): continue
                rows.append({"Equipment ID": asset["equipment_id"], "Equipment Name": asset["equipment_name"], "Category": asset["category"], "Total Quantity": asset["total_stock"], "Available Quantity": asset["available_stock"], "Borrowed Quantity": asset["total_stock"] - asset["available_stock"], "Unit": asset["unit_type"], "Status": asset_status})
            return jsonify(sorted(rows, key=lambda row: row["Equipment Name"].lower()))
        if report in ("active", "returned", "transaction", "history"):
            allowed = {"Active", "Partially Returned"} if report == "active" else {"Returned"} if report == "returned" else {"Active", "Partially Returned", "Returned"} if report == "history" else None
            return_by_item = {}
            for record in returns: return_by_item[record["borrowing_item_id"]] = record.get("return_date")
            rows = []
            for loan in borrowings:
                if allowed and loan["status"] not in allowed: continue
                if borrower and str(loan["borrower_id"]) != borrower: continue
                borrowed_date = (loan.get("borrowed_at") or "")[:10]
                if start and borrowed_date < start: continue
                if end and borrowed_date > end: continue
                for item in items:
                    asset = equipment.get(item["equipment_id"])
                    owner = borrowers.get(loan["borrower_id"])
                    if item["borrowing_id"] != loan["borrowing_id"] or not asset or not owner: continue
                    if status and loan["status"] != status: continue
                    if search and not (needle in owner["full_name"].lower() or needle in asset["equipment_name"].lower() or needle in str(loan["borrowing_id"])): continue
                    rows.append({"Loan ID": loan["borrowing_id"], "Borrower": owner["full_name"], "Equipment": asset["equipment_name"], "Quantity": item["quantity_borrowed"], "Quantity Returned": item["quantity_returned"], "Remaining": item.get("remaining_quantity", item["quantity_borrowed"] - item["quantity_returned"]), "Borrow Date": borrowed_date, "Expected Return Date": loan.get("expected_return_date"), "Status": loan["status"], "Return Date": return_by_item.get(item["borrowing_item_id"])})
            return jsonify(sorted(rows, key=lambda row: (row["Borrow Date"], row["Loan ID"], row["Equipment"]), reverse=True))
        if report == "current_borrowers":
            grouped = {}
            for loan in borrowings:
                if loan["status"] not in ("Active", "Partially Returned"): continue
                if borrower and str(loan["borrower_id"]) != borrower: continue
                borrowed_date = (loan.get("borrowed_at") or "")[:10]
                if start and borrowed_date < start: continue
                if end and borrowed_date > end: continue
                owner = borrowers.get(loan["borrower_id"])
                if not owner: continue
                group = grouped.setdefault(loan["borrower_id"], {"Borrower": owner["full_name"], "Contact Number": owner.get("contact_number"), "Address": owner.get("address"), "loans": set(), "equipment": set(), "count": 0})
                group["loans"].add(str(loan["borrowing_id"]))
                for item in items:
                    if item["borrowing_id"] == loan["borrowing_id"] and item["equipment_id"] in equipment:
                        asset = equipment[item["equipment_id"]]
                        if search and not (needle in owner["full_name"].lower() or needle in asset["equipment_name"].lower() or needle in str(loan["borrowing_id"])): continue
                        group["equipment"].add(asset["equipment_name"]); group["count"] += item["quantity_borrowed"] - item["quantity_returned"]
            rows = [{"Borrower": row["Borrower"], "Contact Number": row["Contact Number"], "Address": row["Address"], "Active Loan IDs": ", ".join(sorted(row["loans"])), "Borrowed Equipment": ", ".join(sorted(row["equipment"])), "Items Currently Borrowed": row["count"]} for row in grouped.values()]
            return jsonify(sorted(rows, key=lambda row: row["Borrower"].lower()))
        return jsonify(error="Unknown report type."), 400
    except DatabaseError:
        return jsonify(error="Unable to generate report."), 500

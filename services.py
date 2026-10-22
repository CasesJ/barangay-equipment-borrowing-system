"""Business helpers built on the Supabase Data API."""
from database import DatabaseError, get_rows


def compute_stock_status(total_stock, available_stock):
    """Return the human-readable stock status label."""
    if available_stock <= 0:
        return "Out of Stock"
    if available_stock < total_stock:
        return "Low Stock"
    return "Available"


def has_active_equipment_loan(equipment_id):
    """Check active loans through Supabase table APIs."""
    active_ids = {
        row["borrowing_id"]
        for row in get_rows("borrowings")
        if row["status"] in ("Active", "Partially Returned")
    }
    return any(
        item["equipment_id"] == equipment_id and item["borrowing_id"] in active_ids
        for item in get_rows("borrowing_items")
    )


def has_active_borrower_loan(borrower_id):
    """Check active loans through Supabase table APIs."""
    return any(
        row["borrower_id"] == borrower_id
        and row["status"] in ("Active", "Partially Returned")
        for row in get_rows("borrowings")
    )


def validate_and_release_stock(borrowing_id, processed_by):
    """Release a request atomically through the Supabase RPC endpoint."""
    from database import call_rpc
    return call_rpc(
        "api_release_borrowing_request",
        {"p_borrowing_id": borrowing_id, "p_processed_by": processed_by},
    )


def validate_and_return_stock(
    cursor, borrowing_id, items, return_date, received_by, return_notes
):
    """Validate every return item and apply stock restoration in a single pass.

    Expects the caller to have already started a transaction.

    Steps per item (single loop — no redundant queries):
      1. Fetch item + equipment details (with FOR UPDATE lock).
      2. Validate remaining quantity and stock integrity.
      3. Increment quantity_returned, recompute remaining_quantity.
      4. Restore available_stock on the equipment row.
      5. Insert a return_records entry.

    After all items: recompute the borrowing status (Returned vs.
    Partially Returned) and update the borrowings row.

    Returns the new status string.
    Raises ValueError on business-rule violations, RuntimeError on
    integrity failures.
    """
    # Lock the borrowing and confirm it is returnable.
    cursor.execute(
        "SELECT borrowing_id FROM borrowings "
        "WHERE borrowing_id = %s AND status IN ('Active', 'Partially Returned') "
        "FOR UPDATE",
        (borrowing_id,),
    )
    if not cursor.fetchone():
        raise ValueError(
            "This borrowing transaction is not active or was not found."
        )

    # Single pass: validate then apply each item immediately.
    for item_id, quantity in sorted(items):
        cursor.execute(
            "SELECT bi.borrowing_item_id, bi.equipment_id, bi.quantity_borrowed, "
            "  bi.quantity_returned, "
            "  e.equipment_name, e.total_stock, e.available_stock "
            "FROM borrowing_items bi "
            "JOIN equipment e ON e.equipment_id = bi.equipment_id "
            "WHERE bi.borrowing_item_id = %s AND bi.borrowing_id = %s "
            "FOR UPDATE",
            (item_id, borrowing_id),
        )
        item = cursor.fetchone()
        if not item:
            raise ValueError(
                "One return item does not belong to this transaction."
            )

        remaining_quantity = max(
            item["quantity_borrowed"] - item["quantity_returned"], 0
        )
        if quantity > remaining_quantity:
            raise ValueError(
                f"Returned quantity for {item['equipment_name']} cannot exceed "
                f"its remaining quantity of {remaining_quantity}."
            )
        if item["available_stock"] + quantity > item["total_stock"]:
            raise RuntimeError(
                f"Stock integrity check failed for {item['equipment_name']}."
            )

        # Apply — update borrowing_items
        cursor.execute(
            "UPDATE borrowing_items "
            "SET quantity_returned = quantity_returned + %s, "
            "    remaining_quantity = quantity_borrowed - quantity_returned "
            "WHERE borrowing_item_id = %s "
            "  AND quantity_returned + %s <= quantity_borrowed",
            (quantity, item_id, quantity),
        )
        if cursor.rowcount != 1:
            raise RuntimeError(
                "This item was already fully returned. Please refresh and try again."
            )

        # Apply — restore stock
        cursor.execute(
            "UPDATE equipment SET available_stock = available_stock + %s "
            "WHERE equipment_id = %s",
            (quantity, item["equipment_id"]),
        )

        # Apply — record the return
        cursor.execute(
            "INSERT INTO return_records "
            "(borrowing_item_id, received_by, quantity_returned, return_date, notes) "
            "VALUES (%s, %s, %s, %s, %s)",
            (item_id, received_by, quantity, return_date, return_notes),
        )

    # Determine new borrowing status.
    cursor.execute(
        "SELECT COALESCE(SUM(GREATEST(quantity_borrowed - quantity_returned, 0)), 0) "
        "AS remaining FROM borrowing_items WHERE borrowing_id = %s",
        (borrowing_id,),
    )
    remaining = cursor.fetchone()["remaining"]
    new_status = "Returned" if remaining == 0 else "Partially Returned"
    cursor.execute(
        "UPDATE borrowings SET status = %s WHERE borrowing_id = %s",
        (new_status, borrowing_id),
    )
    return new_status


def validate_request_reservation(cursor, equipment_id, quantity, available_stock):
    """Ensure pending and approved requests do not overbook available stock.

    Pending and Approved requests have not reduced inventory yet, but their
    quantities are reserved for review/release. This check is called while
    the equipment row is locked, so submissions for the same equipment are
    serialized and cannot collectively promise more than is available.
    """
    cursor.execute(
        "SELECT bi.quantity_borrowed "
        "FROM borrowing_items bi "
        "JOIN borrowings b ON b.borrowing_id = bi.borrowing_id "
        "WHERE bi.equipment_id = %s AND b.status IN ('Pending', 'Approved') "
        "FOR UPDATE",
        (equipment_id,),
    )
    reserved_quantity = sum(row["quantity_borrowed"] for row in cursor.fetchall())
    reservable_quantity = available_stock - reserved_quantity
    if quantity > reservable_quantity:
        raise ValueError(
            f"Only {max(reservable_quantity, 0)} item(s) remain available for new requests. "
            f"{reserved_quantity} item(s) are already in Pending or Approved requests."
        )


def dashboard_statistics():
    """Calculate dashboard totals from Supabase Data API responses."""
    stats = {"total_equipment": 0, "available_equipment": 0, "active_borrowings": 0, "total_borrowers": 0}
    try:
        equipment = get_rows("equipment")
        borrowings = get_rows("borrowings")
        stats.update(
            total_equipment=len(equipment),
            available_equipment=sum(row["available_stock"] for row in equipment),
            active_borrowings=sum(row["status"] in ("Active", "Partially Returned") for row in borrowings),
            total_borrowers=len(get_rows("borrowers")),
        )
        return stats, True
    except DatabaseError:
        return stats, False

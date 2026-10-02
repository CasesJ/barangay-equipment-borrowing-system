"""Business services and inventory/borrowing domain logic."""
import mysql.connector
from database import get_db_connection, table_exists


def compute_stock_status(total_stock, available_stock):
    """Return the human-readable stock status label."""
    if available_stock <= 0:
        return "Out of Stock"
    if available_stock < total_stock:
        return "Low Stock"
    return "Available"


def has_active_equipment_loan(cursor, equipment_id):
    """Check whether equipment is part of an active or partially returned borrowing."""
    if not table_exists(cursor, "borrowing_items") or not table_exists(cursor, "borrowings"):
        return False
    cursor.execute(
        "SELECT 1 FROM borrowing_items bi "
        "JOIN borrowings b ON b.borrowing_id = bi.borrowing_id "
        "WHERE bi.equipment_id = %s "
        "  AND b.status IN ('Active', 'Partially Returned') "
        "LIMIT 1",
        (equipment_id,),
    )
    return cursor.fetchone() is not None


def has_active_borrower_loan(cursor, borrower_id):
    """Check whether a borrower has any active or partially returned borrowing transaction."""
    if not table_exists(cursor, "borrowings"):
        return False
    cursor.execute(
        "SELECT 1 FROM borrowings "
        "WHERE borrower_id = %s AND status IN ('Active', 'Partially Returned') "
        "LIMIT 1",
        (borrower_id,),
    )
    return cursor.fetchone() is not None


def validate_and_release_stock(cursor, borrowing_id):
    """Lock borrowing items, validate stock availability, and decrement atomically.

    Returns the list of (item, equipment) pairs that were released.
    Raises ValueError or RuntimeError on validation failure.
    """
    cursor.execute(
        "SELECT borrowing_item_id, equipment_id, quantity_borrowed "
        "FROM borrowing_items WHERE borrowing_id = %s "
        "ORDER BY equipment_id FOR UPDATE",
        (borrowing_id,),
    )
    items = cursor.fetchall()
    if not items:
        raise ValueError("This request has no equipment items.")

    equipment_rows = []
    for item in items:
        if item["quantity_borrowed"] <= 0:
            raise ValueError("Requested quantity must be greater than zero.")
        cursor.execute(
            "SELECT equipment_name, total_stock, available_stock "
            "FROM equipment WHERE equipment_id = %s FOR UPDATE",
            (item["equipment_id"],),
        )
        equipment = cursor.fetchone()
        if not equipment:
            raise ValueError("One requested equipment record no longer exists.")
        if item["quantity_borrowed"] > equipment["available_stock"]:
            raise ValueError(
                f"Insufficient stock for {equipment['equipment_name']}. "
                f"Available: {equipment['available_stock']}."
            )
        equipment_rows.append((item, equipment))

    for item, _ in equipment_rows:
        cursor.execute(
            "UPDATE equipment SET available_stock = available_stock - %s "
            "WHERE equipment_id = %s AND available_stock >= %s",
            (item["quantity_borrowed"], item["equipment_id"], item["quantity_borrowed"]),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("Stock changed while releasing equipment. Please try again.")
        cursor.execute(
            "UPDATE borrowing_items SET remaining_quantity = quantity_borrowed - quantity_returned "
            "WHERE borrowing_item_id = %s",
            (item["borrowing_item_id"],),
        )

    return equipment_rows


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
    """Read dashboard totals from the existing MySQL schema."""
    stats = {
        "total_equipment": 0,
        "available_equipment": 0,
        "active_borrowings": 0,
        "total_borrowers": 0,
    }
    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT COUNT(*) AS total_equipment, "
                "COALESCE(SUM(available_stock), 0) AS available_equipment "
                "FROM equipment"
            )
            stats.update(cursor.fetchone())

            borrower_table = "borrowers" if table_exists(cursor, "borrowers") else "users"
            cursor.execute(f"SELECT COUNT(*) AS total_borrowers FROM {borrower_table}")
            stats.update(cursor.fetchone())

            if table_exists(cursor, "borrowings"):
                cursor.execute(
                    "SELECT COUNT(*) AS active_borrowings FROM borrowings "
                    "WHERE status IN ('Active', 'Partially Returned')"
                )
                stats.update(cursor.fetchone())
            return stats, True
    except mysql.connector.Error:
        return stats, False

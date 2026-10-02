"""Focused tests for the returning and inventory tracking module.

Tests cover both layers:
  - HTTP route tests (via Flask test client) verify that the route
    handler delegates correctly and returns the expected redirects.
  - Service unit tests (direct calls to validate_and_return_stock)
    verify the SQL execution order, stock updates, and error paths
    without touching HTTP at all.
"""
import json
from datetime import date
from unittest.mock import MagicMock, call, patch

import pytest

from app import create_app
from config import Config
from services import validate_and_return_stock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "return-test-secret"


def _make_client():
    """Create a test client with an Admin session."""
    app = create_app(TestConfig)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess.update(user_id=1, role="Admin", full_name="Admin")
    return client


def _post_return(client, *, borrowing_item_id, quantity):
    """POST a single-item return through the /returns/save endpoint."""
    return client.post(
        "/returns/save",
        data={
            "borrowing_id": "1",
            "return_date": date.today().isoformat(),
            "items": json.dumps(
                [{"borrowing_item_id": borrowing_item_id, "quantity": quantity}]
            ),
            "notes": "Test return",
        },
    )


def _mock_cursor(*, item_row, remaining, rowcount=1):
    """Build a MagicMock cursor pre-loaded for a single-item return.

    The cursor.fetchone() side-effect sequence matches the SQL execution
    order inside validate_and_return_stock (single loop):
      1. Borrowing lock check
      2. Item + equipment detail fetch
      3. Remaining-quantity aggregate
    """
    cursor = MagicMock()
    cursor.rowcount = rowcount
    cursor.fetchone.side_effect = [
        {"borrowing_id": 1},       # FOR UPDATE lock on borrowings
        item_row,                   # Item + equipment JOIN
        {"remaining": remaining},   # SUM aggregate after updates
    ]
    return cursor


# ===========================================================================
# HTTP Route Tests  — verify the route delegates and redirects correctly
# ===========================================================================

class TestReturnableEndpoints:
    """Read-only API endpoints remain unchanged and still work."""

    def test_returnable_borrowings_only_lists_outstanding_loans(self):
        client = _make_client()
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        db = MagicMock()
        with patch("routes.admin_returns.get_db_connection") as conn:
            conn.return_value.__enter__.return_value = (db, cursor)
            response = client.get("/api/returnable-borrowings")

        assert response.status_code == 200
        sql = cursor.execute.call_args.args[0]
        assert "b.status IN ('Active', 'Partially Returned')" in sql

    def test_return_items_derives_remaining_quantity(self):
        client = _make_client()
        cursor = MagicMock()
        cursor.fetchone.return_value = {"borrowing_id": 1, "full_name": "Borrower"}
        cursor.fetchall.return_value = []
        db = MagicMock()
        with patch("routes.admin_returns.get_db_connection") as conn:
            conn.return_value.__enter__.return_value = (db, cursor)
            response = client.get("/api/borrowings/1/items")

        assert response.status_code == 200
        item_sql = cursor.execute.call_args_list[1].args[0]
        assert "quantity_borrowed - bi.quantity_returned" in item_sql


class TestReturnSaveRoute:
    """POST /returns/save — delegates to validate_and_return_stock."""

    def test_full_return_commits_and_redirects(self):
        client = _make_client()
        with patch("routes.admin_returns.get_db_connection") as conn, \
             patch("routes.admin_returns.validate_and_return_stock", return_value="Returned") as svc:
            db = MagicMock()
            cursor = MagicMock()
            conn.return_value.__enter__.return_value = (db, cursor)
            response = _post_return(client, borrowing_item_id=10, quantity=3)

        assert response.status_code == 302
        svc.assert_called_once()
        assert db.commit.called

    def test_partial_return_commits_and_redirects(self):
        client = _make_client()
        with patch("routes.admin_returns.get_db_connection") as conn, \
             patch("routes.admin_returns.validate_and_return_stock", return_value="Partially Returned") as svc:
            db = MagicMock()
            cursor = MagicMock()
            conn.return_value.__enter__.return_value = (db, cursor)
            response = _post_return(client, borrowing_item_id=20, quantity=2)

        assert response.status_code == 302
        svc.assert_called_once()
        assert db.commit.called

    def test_service_valueerror_prevents_commit(self):
        client = _make_client()
        with patch("routes.admin_returns.get_db_connection") as conn, \
             patch("routes.admin_returns.validate_and_return_stock",
                   side_effect=ValueError("Over-return")):
            db = MagicMock()
            cursor = MagicMock()
            conn.return_value.__enter__.return_value = (db, cursor)
            response = _post_return(client, borrowing_item_id=30, quantity=99)

        assert response.status_code == 302
        assert not db.commit.called


# ===========================================================================
# Service Unit Tests  — validate_and_return_stock directly
# ===========================================================================

class TestValidateAndReturnStockFullReturn:
    """When all items are returned, status must be 'Returned'."""

    def test_status_returned_and_stock_incremented(self):
        cursor = _mock_cursor(
            item_row={
                "borrowing_item_id": 10,
                "equipment_id": 5,
                "quantity_borrowed": 3,
                "quantity_returned": 0,
                "equipment_name": "Megaphone",
                "total_stock": 10,
                "available_stock": 7,
            },
            remaining=0,
        )

        status = validate_and_return_stock(
            cursor, borrowing_id=1, items=[(10, 3)],
            return_date=date.today(), received_by=1, return_notes="All back",
        )

        assert status == "Returned"

        # Verify stock was restored (+3 to equipment_id=5)
        stock_call = _find_execute_call(cursor, "UPDATE equipment SET available_stock")
        assert stock_call is not None
        assert stock_call[1] == (3, 5)

        # Verify borrowing status was set
        status_call = _find_execute_call(cursor, "UPDATE borrowings SET status")
        assert status_call[1] == ("Returned", 1)

    def test_remaining_quantity_formula_correct(self):
        cursor = _mock_cursor(
            item_row={
                "borrowing_item_id": 2,
                "equipment_id": 3,
                "quantity_borrowed": 4,
                "quantity_returned": 1,
                "equipment_name": "Tent",
                "total_stock": 10,
                "available_stock": 7,
            },
            remaining=1,
        )

        validate_and_return_stock(
            cursor, borrowing_id=1, items=[(2, 2)],
            return_date=date.today(), received_by=1, return_notes=None,
        )

        update_sql = _find_execute_call(cursor, "UPDATE borrowing_items")
        assert update_sql is not None
        sql_text = update_sql[0]
        assert "remaining_quantity = quantity_borrowed - quantity_returned" in sql_text
        # Old buggy pattern must not appear in the SET clause
        set_clause = sql_text.split("SET")[1].split("WHERE")[0]
        assert "(quantity_returned + %s)" not in set_clause


class TestValidateAndReturnStockPartialReturn:
    """When remaining > 0, status must be 'Partially Returned'."""

    def test_partial_return_status(self):
        cursor = _mock_cursor(
            item_row={
                "borrowing_item_id": 20,
                "equipment_id": 6,
                "quantity_borrowed": 5,
                "quantity_returned": 0,
                "equipment_name": "Chair",
                "total_stock": 20,
                "available_stock": 15,
            },
            remaining=3,
        )

        status = validate_and_return_stock(
            cursor, borrowing_id=1, items=[(20, 2)],
            return_date=date.today(), received_by=1, return_notes=None,
        )

        assert status == "Partially Returned"
        status_call = _find_execute_call(cursor, "UPDATE borrowings SET status")
        assert status_call[1] == ("Partially Returned", 1)


class TestValidateAndReturnStockRejections:
    """Business-rule violations must raise without applying changes."""

    def test_over_return_raises_valueerror(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"borrowing_id": 1},
            {
                "borrowing_item_id": 30,
                "equipment_id": 7,
                "quantity_borrowed": 4,
                "quantity_returned": 3,
                "equipment_name": "Table",
                "total_stock": 10,
                "available_stock": 9,
            },
        ]

        with pytest.raises(ValueError, match="remaining quantity"):
            validate_and_return_stock(
                cursor, borrowing_id=1, items=[(30, 2)],
                return_date=date.today(), received_by=1, return_notes=None,
            )

    def test_stock_integrity_violation_raises_runtimeerror(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"borrowing_id": 1},
            {
                "borrowing_item_id": 40,
                "equipment_id": 8,
                "quantity_borrowed": 5,
                "quantity_returned": 0,
                "equipment_name": "Speaker",
                "total_stock": 10,
                "available_stock": 8,  # 8 + 5 = 13 > 10
            },
        ]

        with pytest.raises(RuntimeError, match="Stock integrity"):
            validate_and_return_stock(
                cursor, borrowing_id=1, items=[(40, 5)],
                return_date=date.today(), received_by=1, return_notes=None,
            )

    def test_non_active_borrowing_raises_valueerror(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None  # borrowing not found

        with pytest.raises(ValueError, match="not active"):
            validate_and_return_stock(
                cursor, borrowing_id=999, items=[(1, 1)],
                return_date=date.today(), received_by=1, return_notes=None,
            )

    def test_item_not_in_transaction_raises_valueerror(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"borrowing_id": 1},   # borrowing exists
            None,                   # item not found in this transaction
        ]

        with pytest.raises(ValueError, match="does not belong"):
            validate_and_return_stock(
                cursor, borrowing_id=1, items=[(999, 1)],
                return_date=date.today(), received_by=1, return_notes=None,
            )

    def test_already_fully_returned_raises_runtimeerror(self):
        cursor = MagicMock()
        cursor.rowcount = 0  # UPDATE affected 0 rows
        cursor.fetchone.side_effect = [
            {"borrowing_id": 1},
            {
                "borrowing_item_id": 50,
                "equipment_id": 9,
                "quantity_borrowed": 2,
                "quantity_returned": 0,
                "equipment_name": "Projector",
                "total_stock": 5,
                "available_stock": 3,
            },
        ]

        with pytest.raises(RuntimeError, match="already fully returned"):
            validate_and_return_stock(
                cursor, borrowing_id=1, items=[(50, 2)],
                return_date=date.today(), received_by=1, return_notes=None,
            )


class TestReturnRecordInsertion:
    """The return_records INSERT must use the correct values."""

    def test_return_record_inserted_with_correct_values(self):
        today = date.today()
        cursor = _mock_cursor(
            item_row={
                "borrowing_item_id": 10,
                "equipment_id": 5,
                "quantity_borrowed": 3,
                "quantity_returned": 0,
                "equipment_name": "Megaphone",
                "total_stock": 10,
                "available_stock": 7,
            },
            remaining=0,
        )

        validate_and_return_stock(
            cursor, borrowing_id=1, items=[(10, 3)],
            return_date=today, received_by=42, return_notes="Good condition",
        )

        insert_call = _find_execute_call(cursor, "INSERT INTO return_records")
        assert insert_call is not None
        assert insert_call[1] == (10, 42, 3, today, "Good condition")


# ---------------------------------------------------------------------------
# Test utilities
# ---------------------------------------------------------------------------

def _find_execute_call(cursor, sql_prefix):
    """Find the first cursor.execute() call whose SQL starts with *sql_prefix*.

    Returns (sql_string, params) or None.
    """
    for args, _ in cursor.execute.call_args_list:
        if args[0].startswith(sql_prefix):
            return args
    return None

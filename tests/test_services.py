"""Unit tests for services, stock status calculation, and business rules."""
from unittest.mock import MagicMock
import pytest

from services import (
    compute_stock_status,
    has_active_equipment_loan,
    has_active_borrower_loan,
    validate_request_reservation,
    validate_and_release_stock,
)


def test_compute_stock_status():
    """Verify stock status labels according to stock quantities."""
    assert compute_stock_status(10, 10) == "Available"
    assert compute_stock_status(10, 5) == "Low Stock"
    assert compute_stock_status(10, 1) == "Low Stock"
    assert compute_stock_status(10, 0) == "Out of Stock"
    assert compute_stock_status(10, -1) == "Out of Stock"


def test_has_active_equipment_loan():
    cursor = MagicMock()

    # When table doesn't exist
    cursor.execute.return_value = None
    cursor.fetchone.return_value = None
    assert has_active_equipment_loan(cursor, 1) is False

    # When table exists and loan is found
    def mock_fetchone_side_effect():
        return {"1": 1}

    cursor.fetchone.side_effect = [{"Tables_in_db": "borrowing_items"}, {"Tables_in_db": "borrowings"}, {"1": 1}]
    assert has_active_equipment_loan(cursor, 1) is True


def test_validate_request_reservation_exceeds_stock():
    """Validation must fail if requested quantity exceeds available minus reserved quantity."""
    cursor = MagicMock()
    # Mock existing reserved rows with total 4 items in pending/approved requests
    cursor.fetchall.return_value = [{"quantity_borrowed": 2}, {"quantity_borrowed": 2}]

    # Available stock = 5, reserved = 4 -> Reservable = 1. Requesting 2 should raise ValueError.
    with pytest.raises(ValueError, match="Only 1 item\\(s\\) remain available for new requests."):
        validate_request_reservation(cursor, equipment_id=1, quantity=2, available_stock=5)


def test_validate_request_reservation_passes():
    """Validation succeeds when within reservable limit."""
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"quantity_borrowed": 2}]

    # Available stock = 10, reserved = 2 -> Reservable = 8. Requesting 5 should succeed.
    validate_request_reservation(cursor, equipment_id=1, quantity=5, available_stock=10)


def test_validate_and_release_stock_empty():
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    with pytest.raises(ValueError, match="This request has no equipment items."):
        validate_and_release_stock(cursor, borrowing_id=99)


def test_validate_and_release_stock_insufficient():
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {"borrowing_item_id": 1, "equipment_id": 10, "quantity_borrowed": 5}
    ]
    cursor.fetchone.return_value = {
        "equipment_name": "Generator",
        "total_stock": 5,
        "available_stock": 3,
    }

    with pytest.raises(ValueError, match="Insufficient stock for Generator. Available: 3."):
        validate_and_release_stock(cursor, borrowing_id=1)

"""Unit tests for form validators and parser functions."""
import json
from datetime import date, timedelta
import pytest

from validators import (
    parse_equipment_form,
    parse_borrower_form,
    parse_borrowing_form,
    parse_staff_request_form,
    parse_return_form,
)


def test_parse_equipment_form_valid():
    form = {
        "equipment_name": "  Foldable Tent  ",
        "category": "Shelter",
        "unit_type": "unit",
        "total_stock": "15",
    }
    name, category, total_stock, unit_type = parse_equipment_form(form)
    assert name == "Foldable Tent"
    assert category == "Shelter"
    assert total_stock == 15
    assert unit_type == "unit"


def test_parse_equipment_form_missing_required():
    with pytest.raises(ValueError, match="Equipment name, category, total quantity, and unit type are required."):
        parse_equipment_form({"equipment_name": "", "category": "Tools", "unit_type": "pcs", "total_stock": "5"})


def test_parse_equipment_form_invalid_stock():
    with pytest.raises(ValueError, match="Total quantity must be a whole number."):
        parse_equipment_form({"equipment_name": "Megaphone", "category": "Audio", "unit_type": "pcs", "total_stock": "abc"})

    with pytest.raises(ValueError, match="Total quantity must be greater than zero."):
        parse_equipment_form({"equipment_name": "Megaphone", "category": "Audio", "unit_type": "pcs", "total_stock": "0"})


def test_parse_borrower_form_valid():
    form = {
        "full_name": "  Juan Dela Cruz  ",
        "contact_number": "0912-345-6789",
        "address": "Zone 4, Barangay Hall",
        "email": "JUAN@example.com ",
    }
    name, contact, address, email = parse_borrower_form(form)
    assert name == "Juan Dela Cruz"
    assert contact == "0912-345-6789"
    assert address == "Zone 4, Barangay Hall"
    assert email == "juan@example.com"


def test_parse_borrower_form_invalid():
    # Missing required
    with pytest.raises(ValueError, match="Full name, contact number, and address are required."):
        parse_borrower_form({"full_name": "", "contact_number": "09123456789", "address": "Brgy"})

    # Invalid contact format
    with pytest.raises(ValueError, match="Enter a valid contact number."):
        parse_borrower_form({"full_name": "Juan", "contact_number": "abc", "address": "Brgy"})

    # Invalid email format
    with pytest.raises(ValueError, match="Enter a valid email address."):
        parse_borrower_form({"full_name": "Juan", "contact_number": "09123456789", "address": "Brgy", "email": "invalid-email"})


def test_parse_borrowing_form_valid():
    future_date = (date.today() + timedelta(days=2)).isoformat()
    form = {
        "borrower_id": "3",
        "expected_return_date": future_date,
        "purpose_notes": "Community cleanup",
        "items": json.dumps([{"equipment_id": 1, "quantity": 2}, {"equipment_id": 4, "quantity": 1}]),
    }
    borrower_id, due_date, purpose, items = parse_borrowing_form(form)
    assert borrower_id == 3
    assert due_date.isoformat() == future_date
    assert purpose == "Community cleanup"
    assert items == [(1, 2), (4, 1)]


def test_parse_borrowing_form_past_date():
    past_date = (date.today() - timedelta(days=1)).isoformat()
    form = {
        "borrower_id": "1",
        "expected_return_date": past_date,
        "items": json.dumps([{"equipment_id": 1, "quantity": 1}]),
    }
    with pytest.raises(ValueError, match="Expected return date cannot be in the past."):
        parse_borrowing_form(form)


def test_parse_borrowing_form_duplicate_equipment():
    future_date = (date.today() + timedelta(days=1)).isoformat()
    form = {
        "borrower_id": "1",
        "expected_return_date": future_date,
        "items": json.dumps([
            {"equipment_id": 2, "quantity": 1},
            {"equipment_id": 2, "quantity": 3},
        ]),
    }
    with pytest.raises(ValueError, match="Duplicate equipment cannot be added to one transaction."):
        parse_borrowing_form(form)


def test_parse_staff_request_form():
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=3)).isoformat()
    form = {
        "equipment_id": "2",
        "quantity": "5",
        "date_needed": today,
        "expected_return_date": future,
        "purpose_notes": "Medical mission setup",
        "additional_notes": "Handle with care",
    }
    eq_id, qty, needed, expected, purpose, notes = parse_staff_request_form(form)
    assert eq_id == 2
    assert qty == 5
    assert needed.isoformat() == today
    assert expected.isoformat() == future
    assert purpose == "Medical mission setup"
    assert notes == "Handle with care"


def test_parse_return_form_valid():
    today = date.today().isoformat()
    form = {
        "borrowing_id": "10",
        "return_date": today,
        "notes": "Returned in good condition",
        "items": json.dumps([{"borrowing_item_id": 1, "quantity": 2}]),
    }
    b_id, ret_date, items, notes = parse_return_form(form)
    assert b_id == 10
    assert ret_date.isoformat() == today
    assert items == [(1, 2)]
    assert notes == "Returned in good condition"

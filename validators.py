"""Form input parsing and validation utilities."""
import json
import re
from datetime import date


def parse_equipment_form(form):
    """Validate and normalize an equipment form without trusting client input."""
    name = form.get("equipment_name", "").strip()
    category = form.get("category", "").strip()
    unit_type = form.get("unit_type", "").strip()
    quantity_text = form.get("total_stock", "").strip()

    if not name or not category or not unit_type:
        raise ValueError("Equipment name, category, total quantity, and unit type are required.")
    if len(name) > 100 or len(category) > 100 or len(unit_type) > 50:
        raise ValueError("One or more equipment fields are too long.")

    try:
        total_stock = int(quantity_text)
    except (ValueError, TypeError) as error:
        raise ValueError("Total quantity must be a whole number.") from error

    if total_stock <= 0:
        raise ValueError("Total quantity must be greater than zero.")

    return name, category, total_stock, unit_type


def parse_borrower_form(form):
    """Validate and normalize a borrower form."""
    full_name = form.get("full_name", "").strip()
    contact_number = form.get("contact_number", "").strip()
    address = form.get("address", "").strip()
    email = form.get("email", "").strip().lower()

    if not full_name or not contact_number or not address:
        raise ValueError("Full name, contact number, and address are required.")
    if len(full_name) > 150 or len(contact_number) > 30 or len(address) > 255 or len(email) > 100:
        raise ValueError("One or more borrower fields are too long.")
    if not re.fullmatch(r"[0-9+() .-]{7,30}", contact_number):
        raise ValueError("Enter a valid contact number.")
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Enter a valid email address.")

    return full_name, contact_number, address, email or None


def parse_borrowing_form(form):
    """Validate and normalize a borrowing transaction form."""
    try:
        borrower_id = int(form.get("borrower_id", ""))
    except (ValueError, TypeError) as error:
        raise ValueError("Select a valid borrower.") from error

    if borrower_id <= 0:
        raise ValueError("Select a valid borrower.")

    expected_return_date = form.get("expected_return_date", "").strip()
    try:
        due_date = date.fromisoformat(expected_return_date)
    except (ValueError, TypeError) as error:
        raise ValueError("Enter a valid expected return date.") from error

    if due_date < date.today():
        raise ValueError("Expected return date cannot be in the past.")

    try:
        raw_items = json.loads(form.get("items", "[]"))
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("Transaction items are invalid.") from error

    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("Add at least one equipment item to the transaction.")

    items, seen = [], set()
    for item in raw_items:
        try:
            equipment_id = int(item["equipment_id"])
            quantity = int(item["quantity"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Each transaction item must have valid equipment and quantity.") from error

        if equipment_id <= 0 or quantity <= 0:
            raise ValueError("Item quantities must be greater than zero.")
        if equipment_id in seen:
            raise ValueError("Duplicate equipment cannot be added to one transaction.")
        seen.add(equipment_id)
        items.append((equipment_id, quantity))

    purpose_notes = form.get("purpose_notes", "").strip()
    if len(purpose_notes) > 2000:
        raise ValueError("Purpose/notes cannot exceed 2,000 characters.")

    return borrower_id, due_date, purpose_notes or None, items


def parse_staff_request_form(form):
    """Validate and normalize a staff borrowing request form."""
    try:
        equipment_id = int(form.get("equipment_id", ""))
        quantity = int(form.get("quantity", ""))
        date_needed = date.fromisoformat(form.get("date_needed", ""))
        expected_return = date.fromisoformat(form.get("expected_return_date", ""))
        purpose = form.get("purpose_notes", "").strip()
        notes = form.get("additional_notes", "").strip()
    except (TypeError, ValueError) as error:
        raise ValueError("Request information is invalid.") from error

    if equipment_id <= 0 or quantity <= 0 or not purpose:
        raise ValueError("Equipment, a positive quantity, purpose, and both dates are required.")
    if date_needed < date.today():
        raise ValueError("Date needed cannot be in the past.")
    if expected_return < date_needed:
        raise ValueError("Expected return date cannot be earlier than the date needed.")
    if len(purpose) > 2000 or len(notes) > 2000:
        raise ValueError("Purpose and additional notes cannot exceed 2,000 characters.")

    return equipment_id, quantity, date_needed, expected_return, purpose, notes


def parse_return_form(form):
    """Validate and normalize an equipment return form."""
    try:
        borrowing_id = int(form.get("borrowing_id", ""))
        return_date = date.fromisoformat(form.get("return_date", ""))
        raw_items = json.loads(form.get("items", "[]"))
        notes = form.get("notes", "").strip()
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise ValueError("Return information is invalid.") from error

    if len(notes) > 2000:
        raise ValueError("Return notes cannot exceed 2,000 characters.")
    if borrowing_id <= 0 or not raw_items:
        raise ValueError("Select a transaction and enter at least one returned quantity.")
    if return_date > date.today():
        raise ValueError("Return date cannot be in the future.")

    items, seen = [], set()
    for item in raw_items:
        try:
            item_id = int(item["borrowing_item_id"])
            quantity = int(item["quantity"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Return items contain invalid item ID or quantity.") from error

        if item_id <= 0 or quantity <= 0:
            raise ValueError("Returned quantities must be greater than zero.")
        if item_id in seen:
            raise ValueError("Duplicate return items are not allowed.")
        seen.add(item_id)
        items.append((item_id, quantity))

    return borrowing_id, return_date, items, notes or None

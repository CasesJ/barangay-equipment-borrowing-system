"""Focused coverage for API-only service helpers."""
from services import has_active_equipment_loan


def test_active_equipment_check_uses_supabase_rows(monkeypatch):
    def fake_rows(table):
        return {
            "borrowings": [{"borrowing_id": 4, "status": "Active"}],
            "borrowing_items": [{"borrowing_id": 4, "equipment_id": 1}],
        }[table]

    monkeypatch.setattr("services.get_rows", fake_rows)
    assert has_active_equipment_loan(1) is True
    assert has_active_equipment_loan(2) is False

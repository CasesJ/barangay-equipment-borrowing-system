"""Integration tests for application routes, endpoints, and role guards."""
import pytest
from app import create_app
from config import Config


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"


@pytest.fixture
def client():
    app = create_app(TestConfig)
    return app.test_client()


def test_legacy_page_urls_forward_to_next_frontend(client):
    """The API service must forward browser page URLs to the Next.js UI."""
    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")

    resp = client.get("/signup.html")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/signup")


def test_admin_routes_redirect_unauthenticated(client):
    """Admin page routes should redirect unauthenticated requests to login."""
    protected_pages = [
        "/dashboard",
        "/equipment",
        "/borrowers",
        "/borrowings",
        "/returns",
        "/reports",
        "/audit-logs",
        "/admin/borrowing-requests",
    ]
    for path in protected_pages:
        resp = client.get(path)
        assert resp.status_code == 302
        assert "/login.html" in resp.headers["Location"]


def test_admin_apis_require_auth(client):
    """Admin API routes should return 401 Unauthorized for unauthenticated requests."""
    admin_apis = [
        "/api/equipment",
        "/api/borrowers",
        "/api/borrowable-equipment",
        "/api/returnable-borrowings",
        "/api/reports",
        "/api/audit-logs",
        "/api/admin/borrowing-requests",
    ]
    for path in admin_apis:
        resp = client.get(path)
        assert resp.status_code == 401
        data = resp.get_json()
        assert data == {"error": "Please log in first."}


def test_staff_routes_redirect_unauthenticated(client):
    """Staff page routes should redirect unauthenticated requests to login."""
    staff_pages = [
        "/staff-dashboard",
        "/staff/equipment",
        "/staff/requests",
        "/staff/borrowed-items",
        "/staff/profile",
    ]
    for path in staff_pages:
        resp = client.get(path)
        assert resp.status_code == 302
        assert "/login.html" in resp.headers["Location"]


def test_staff_apis_require_auth(client):
    """Staff API routes should return 403 for unauthenticated or non-staff users."""
    staff_apis = [
        "/api/staff/equipment",
        "/api/staff/requests",
        "/api/staff/borrowed-items",
    ]
    for path in staff_apis:
        resp = client.get(path)
        assert resp.status_code == 403


def test_admin_forbidden_from_staff_apis(client):
    """Admin users attempting to access Staff-specific APIs should receive 403 Forbidden."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["role"] = "Admin"
        sess["full_name"] = "Admin User"

    resp = client.get("/api/staff/requests")
    assert resp.status_code == 403
    assert "only User accounts" in resp.get_json()["error"]


def test_staff_forbidden_from_admin_apis(client):
    """Staff users attempting to access Admin-specific APIs should receive 403 Forbidden."""
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["role"] = "User"
        sess["full_name"] = "Portal User"

    resp = client.get("/api/equipment")
    assert resp.status_code == 403
    assert "only Admin users" in resp.get_json()["error"]


def test_staff_request_serializes_dates_for_supabase(client, monkeypatch):
    """Staff request dates must be JSON values before calling the RPC."""
    submitted = {}

    def fake_call_rpc(name, params):
        submitted["name"] = name
        submitted["params"] = params
        return {"borrowing_id": 1, "status": "Pending"}

    monkeypatch.setattr("routes.staff_routes.call_rpc", fake_call_rpc)
    with client.session_transaction() as sess:
        sess.update(user_id=2, role="User", full_name="Portal User", username="user")

    resp = client.post(
        "/staff/requests/create",
        data={
            "equipment_id": "1",
            "quantity": "2",
            "date_needed": "2026-10-22",
            "expected_return_date": "2026-10-23",
            "purpose_notes": "Community event",
            "additional_notes": "",
        },
    )

    assert resp.status_code == 302
    assert submitted["name"] == "api_submit_staff_request"
    assert submitted["params"]["p_date_needed"] == "2026-10-22"
    assert submitted["params"]["p_expected_return"] == "2026-10-23"


def test_logout(client):
    """Logout endpoint should clear session and redirect to login."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["role"] = "Admin"

    resp = client.get("/logout")
    assert resp.status_code == 302
    assert "/login.html" in resp.headers["Location"]

    # Verify session is cleared
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_signup_accepts_a_password_without_a_length_requirement(client, monkeypatch):
    """All four character types are required, but there is no minimum length."""
    inserted = []

    monkeypatch.setattr("routes.auth_routes.get_rows", lambda table: [])

    def fake_insert_row(table, values):
        inserted.append((table, values))
        return {"user_id": 7} if table == "users" else {"borrower_id": 4}

    monkeypatch.setattr("routes.auth_routes.insert_row", fake_insert_row)
    monkeypatch.setattr("routes.auth_routes.log_audit", lambda *args: None)

    response = client.post(
        "/signup",
        data={
            "full_name": "New User",
            "username": "newuser",
            "contact_number": "09123456789",
            "address": "Barangay Test",
            "email": "new@example.com",
            "password": "Aa1!",
            "confirm_password": "Aa1!",
        },
    )

    assert response.status_code == 302
    assert "Account+created" in response.headers["Location"]
    assert [table for table, _ in inserted] == ["users", "borrowers"]

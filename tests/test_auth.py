"""Unit tests for authentication, password validation, and access control decorators."""
import pytest
from flask import Flask, session
from auth import (
    is_admin,
    is_strong_password,
    logged_in,
    login_required,
    admin_only,
    admin_api,
    staff_only,
    staff_api,
    redirect_with_message,
)


def test_is_strong_password_valid():
    """Passwords with >=12 chars, upper, lower, digit, and symbol should pass."""
    assert is_strong_password("AdminSecurePass!1") is True
    assert is_strong_password("Barangay#2026Strong") is True


def test_is_strong_password_invalid():
    """Weak passwords should fail validation."""
    assert is_strong_password("short") is False
    assert is_strong_password("nouppercase123!") is False
    assert is_strong_password("NOLOWERCASE123!") is False
    assert is_strong_password("NoDigitsHere!Pass") is False
    assert is_strong_password("NoSpecialChar1234") is False
    assert is_strong_password("") is False
    assert is_strong_password(None) is False


def test_logged_in_and_is_admin():
    """Check session authentication and role determination predicates."""
    app = Flask(__name__)
    app.secret_key = "test-secret"

    with app.test_request_context("/"):
        assert logged_in() is False
        assert is_admin() is False

        session["user_id"] = 1
        session["role"] = "User"
        assert logged_in() is True
        assert is_admin() is False

        session["role"] = "Admin"
        assert is_admin() is True

        # Case-insensitive Admin check
        session["role"] = "admin"
        assert is_admin() is True


def test_login_required_decorator():
    """login_required should redirect unauthenticated users to login_page."""
    app = Flask(__name__)
    app.secret_key = "test-secret"

    @app.get("/login.html")
    def login_page():
        return "Login Page"

    @app.get("/protected")
    @login_required
    def protected():
        return "Protected Content"

    client = app.test_client()

    # Unauthenticated
    resp = client.get("/protected")
    assert resp.status_code == 302
    assert "/login.html" in resp.headers["Location"]

    # Authenticated
    with client.session_transaction() as sess:
        sess["user_id"] = 10
    resp = client.get("/protected")
    assert resp.status_code == 200
    assert b"Protected Content" in resp.data


def test_admin_api_guard():
    """admin_api decorator should return 401/403 JSON responses appropriately."""
    app = Flask(__name__)
    app.secret_key = "test-secret"

    @app.get("/api/admin-data")
    @admin_api
    def admin_data():
        return {"status": "ok"}

    client = app.test_client()

    # Unauthenticated -> 401
    resp = client.get("/api/admin-data")
    assert resp.status_code == 401
    assert resp.get_json() == {"error": "Please log in first."}

    # Authenticated as User -> 403
    with client.session_transaction() as sess:
        sess["user_id"] = 5
        sess["role"] = "User"
    resp = client.get("/api/admin-data")
    assert resp.status_code == 403
    assert "Access denied" in resp.get_json()["error"]

    # Authenticated as Admin -> 200
    with client.session_transaction() as sess:
        sess["role"] = "Admin"
    resp = client.get("/api/admin-data")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_staff_api_guard():
    """staff_api decorator should allow User but return 403 for Admin or unauthenticated."""
    app = Flask(__name__)
    app.secret_key = "test-secret"

    @app.get("/api/staff-data")
    @staff_api
    def staff_data():
        return {"status": "ok"}

    client = app.test_client()

    # Unauthenticated -> 403
    resp = client.get("/api/staff-data")
    assert resp.status_code == 403

    # Authenticated as Admin -> 403
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["role"] = "Admin"
    resp = client.get("/api/staff-data")
    assert resp.status_code == 403

    # Authenticated as User -> 200
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["role"] = "User"
    resp = client.get("/api/staff-data")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}

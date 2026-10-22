"""Unit tests for the Supabase Data API configuration."""
import pytest
from flask import Flask

from database import DatabaseError, _is_private_supabase_key, get_supabase


def test_supabase_url_and_secret_key_are_required():
    app = Flask(__name__)
    app.config.update(SUPABASE_URL="", SUPABASE_SECRET_KEY="")

    with app.app_context(), pytest.raises(DatabaseError, match="SUPABASE_URL"):
        get_supabase()


def test_publishable_key_is_rejected_for_server_access():
    app = Flask(__name__)
    app.config.update(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="sb_publishable_not_for_server",
    )

    with app.app_context(), pytest.raises(DatabaseError, match="private"):
        get_supabase()


def test_legacy_service_role_key_is_accepted():
    # Payload is deliberately unsigned: this helper only identifies the key
    # type; Supabase validates the signature on each request.
    legacy_key = "header.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.signature"
    assert _is_private_supabase_key(legacy_key) is True
    assert _is_private_supabase_key("sb_publishable_not_for_server") is False

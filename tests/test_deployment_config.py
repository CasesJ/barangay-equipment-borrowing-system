"""Deployment-focused configuration checks that do not contact Supabase."""
import pytest

from app import create_app
from config import Config


class ProductionConfig(Config):
    APP_ENV = "production"
    DEBUG = False
    SECRET_KEY = "test-production-secret"
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"


def test_production_session_cookie_is_hardened():
    app = create_app(ProductionConfig)
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_production_requires_a_secret_key():
    class MissingSecretConfig(ProductionConfig):
        SECRET_KEY = ""

    with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
        create_app(MissingSecretConfig)


def test_health_check_does_not_require_database_access():
    app = create_app(ProductionConfig)
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}

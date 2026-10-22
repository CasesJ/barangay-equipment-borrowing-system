"""Configuration settings for the Barangay Equipment Borrowing System."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")


def env_bool(name, default=False):
    """Read a conventional boolean environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Base application configuration."""
    APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
    DEBUG = env_bool("FLASK_DEBUG", False)
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "")
    SUPABASE_URL = os.environ.get(
        "SUPABASE_URL", os.environ.get("VITE_SUPABASE_URL", "")
    )
    # This key is used only by Flask on the server. It must be an sb_secret_*
    # key and must never be sent to the browser.
    SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")
    # Sessions are issued to the Vercel origin by the Next.js proxy, not to
    # the separately hosted Flask origin.
    SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "barangay_session")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", APP_ENV == "production")
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    # Flask is API and session middleware only; the browser UI is served by Next.js.
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    ROOT_DIR = ROOT_DIR

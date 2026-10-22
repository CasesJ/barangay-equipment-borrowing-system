"""Configuration settings for the Barangay Equipment Borrowing System."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")


class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get(
        "FLASK_SECRET_KEY", "change-this-to-a-random-secret-before-deploying"
    )
    SUPABASE_URL = os.environ.get(
        "SUPABASE_URL", os.environ.get("VITE_SUPABASE_URL", "")
    )
    # This key is used only by Flask on the server. It must be an sb_secret_*
    # key and must never be sent to the browser.
    SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")
    ROOT_DIR = ROOT_DIR

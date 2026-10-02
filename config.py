"""Configuration settings for the Barangay Equipment Borrowing System."""
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent


class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get(
        "FLASK_SECRET_KEY", "change-this-to-a-random-secret-before-deploying"
    )
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "barangay_equipment_db")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    ROOT_DIR = ROOT_DIR

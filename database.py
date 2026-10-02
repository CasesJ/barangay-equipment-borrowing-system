"""Database connection management and utility functions."""
from contextlib import contextmanager
from flask import current_app, session
import mysql.connector

STATUS_SQL_EXPRESSION = (
    "CASE "
    "WHEN available_stock = 0 THEN 'Out of Stock' "
    "WHEN available_stock < total_stock THEN 'Low Stock' "
    "ELSE 'Available' "
    "END"
)


@contextmanager
def get_db_connection():
    """Yield a (connection, cursor) pair and clean up automatically."""
    config = current_app.config
    db = mysql.connector.connect(
        host=config["MYSQL_HOST"],
        port=config["MYSQL_PORT"],
        database=config["MYSQL_DATABASE"],
        user=config["MYSQL_USER"],
        password=config["MYSQL_PASSWORD"],
    )
    cursor = db.cursor(dictionary=True)
    try:
        yield db, cursor
    finally:
        cursor.close()
        if db.is_connected():
            db.close()


def table_exists(cursor, table_name):
    """Check whether a table exists in the current database."""
    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    return cursor.fetchone() is not None


def log_audit(cursor, action, table_name, record_id, description):
    """Insert a row into audit_logs for the currently logged-in user."""
    user_id = session.get("user_id")
    cursor.execute(
        "INSERT INTO audit_logs (user_id, action, table_name, record_id, description) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, action, table_name, record_id, description),
    )


def serialize_date_fields(rows, fields):
    """Convert date/datetime values to ISO strings for JSON serialization."""
    for row in rows:
        for field in fields:
            value = row.get(field)
            if hasattr(value, "isoformat"):
                row[field] = value.isoformat()
    return rows

"""Supabase Data API helpers used by the Flask application.

There is deliberately no direct Postgres/SQL connection in this module. All
application data access goes through the official Supabase Python client.
"""
from functools import lru_cache

from flask import current_app, session
from supabase import create_client


class DatabaseError(RuntimeError):
    """Raised when a Supabase API operation cannot be completed."""


@lru_cache(maxsize=4)
def _client(url, secret_key):
    return create_client(url, secret_key)


def get_supabase():
    """Return the server-only Supabase API client."""
    url = current_app.config.get("SUPABASE_URL", "").strip()
    secret_key = current_app.config.get("SUPABASE_SECRET_KEY", "").strip()
    if not url or not secret_key:
        raise DatabaseError("SUPABASE_URL and SUPABASE_SECRET_KEY must be configured.")
    if not secret_key.startswith("sb_secret_"):
        raise DatabaseError("SUPABASE_SECRET_KEY must be a private sb_secret_ key.")
    try:
        return _client(url, secret_key)
    except Exception as error:
        raise DatabaseError("Unable to initialize the Supabase client.") from error


def _execute(operation):
    try:
        response = operation.execute()
        return response.data or []
    except Exception as error:
        raise DatabaseError("Supabase could not complete the database operation.") from error


def get_rows(table, columns="*"):
    """Fetch rows from a public Supabase table through the Data API."""
    return _execute(get_supabase().table(table).select(columns))


def insert_row(table, values):
    """Insert one row and return its API representation."""
    rows = _execute(get_supabase().table(table).insert(values))
    return rows[0] if rows else None


def update_rows(table, values, column, value):
    """Update matching rows and return the changed records."""
    return _execute(get_supabase().table(table).update(values).eq(column, value))


def delete_rows(table, column, value):
    """Delete matching rows and return deleted records when available."""
    return _execute(get_supabase().table(table).delete().eq(column, value))


def call_rpc(name, params=None):
    """Call a whitelist-backed transactional function hosted in Supabase."""
    return _execute(get_supabase().rpc(name, params or {}))


def first(rows):
    """Return the first row from a Supabase response, if present."""
    return rows[0] if rows else None


def log_audit(action, table_name, record_id, description):
    """Append an audit record through the Supabase Data API."""
    insert_row(
        "audit_logs",
        {
            "user_id": session.get("user_id"),
            "action": action,
            "table_name": table_name,
            "record_id": record_id,
            "description": description,
        },
    )


def serialize_date_fields(rows, fields):
    """Keep JSON date values consistent for templates and API callers."""
    for row in rows:
        for field in fields:
            value = row.get(field)
            if hasattr(value, "isoformat"):
                row[field] = value.isoformat()
    return rows

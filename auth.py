"""Authentication predicates, decorators, and security helpers."""
from functools import wraps
from flask import current_app, jsonify, redirect, session, url_for
from werkzeug.routing import BuildError


def redirect_with_message(page, text):
    """Redirect to *page* with a query-string message (flash-style)."""
    try:
        return redirect(url_for(page, message=text))
    except BuildError:
        # If passed without blueprint prefix, find matching view function
        for endpoint in current_app.view_functions:
            if endpoint == page or endpoint.endswith("." + page):
                return redirect(url_for(endpoint, message=text))
        raise


def frontend_redirect(path="/"):
    """Send direct backend page visits to the Next.js frontend."""
    return redirect(f"{current_app.config['FRONTEND_URL']}{path}")


def is_strong_password(password):
    """Check if password satisfies 12+ chars with upper, lower, digit, and symbol."""
    if not isinstance(password, str):
        return False
    return (
        len(password) >= 12
        and any(c.islower() for c in password)
        and any(c.isupper() for c in password)
        and any(c.isdigit() for c in password)
        and any(not c.isalnum() for c in password)
    )


def logged_in():
    """Return True if a user is currently authenticated in the session."""
    return "user_id" in session


def is_admin():
    """Return True if the logged-in user has the Admin role."""
    return str(session.get("role", "")).lower() == "admin"


def login_required(f):
    """Redirect unauthenticated users to the login page."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not logged_in():
            return redirect_with_message("login_page", "Please log in first.")
        return f(*args, **kwargs)
    return decorated


def admin_only(f):
    """Page guard: login + Admin role required."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not logged_in():
            return redirect_with_message("login_page", "Please log in first.")
        if not is_admin():
            return redirect_with_message(
                "dashboard", "Access denied: only Admin users can perform this action."
            )
        return f(*args, **kwargs)
    return decorated


def admin_api(f):
    """API guard: login + Admin role required (returns JSON errors)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not logged_in():
            return jsonify(error="Please log in first."), 401
        if not is_admin():
            return jsonify(error="Access denied: only Admin users can perform this action."), 403
        return f(*args, **kwargs)
    return decorated


def staff_only(f):
    """Page guard: login + non-Admin (Staff) role required."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if logged_in() and not is_admin():
            return f(*args, **kwargs)
        if logged_in():
            return redirect(url_for("dashboard_routes.dashboard"))
        return redirect_with_message("login_page", "Please log in first.")
    return decorated


def staff_api(f):
    """API guard: login + non-Admin (Staff) role required (returns JSON errors)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if logged_in() and not is_admin():
            return f(*args, **kwargs)
        return jsonify(error="Access denied: only Staff users can perform this action."), 403
    return decorated

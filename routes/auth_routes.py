"""Authentication and general public routes."""
from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from auth import frontend_redirect, is_admin, is_strong_password, login_required, redirect_with_message
from database import DatabaseError, get_rows, insert_row, log_audit

auth_bp = Blueprint("auth_routes", __name__)


@auth_bp.get("/api/session")
def session_details():
    """Expose the minimum authenticated identity needed by the SPA shell."""
    if "user_id" not in session:
        return jsonify(authenticated=False), 401
    return jsonify(
        authenticated=True,
        user_id=session["user_id"],
        full_name=session.get("full_name", ""),
        username=session.get("username", ""),
        role=session.get("role", ""),
    )


@auth_bp.get("/")
@auth_bp.get("/login.html")
def login_page():
    return frontend_redirect("/")


@auth_bp.get("/signup.html")
def signup_page():
    return frontend_redirect("/signup")


@auth_bp.post("/signup")
def signup():
    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip()
    contact_number = request.form.get("contact_number", "").strip()
    address = request.form.get("address", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not all([full_name, username, contact_number, address, email, password]):
        return redirect_with_message("login_page", "Complete all fields.")
    if password != confirm_password:
        return redirect_with_message("signup_page", "Passwords do not match.")
    if not is_strong_password(password):
        return redirect_with_message(
            "signup_page",
            "Use a password with uppercase, lowercase, number, and symbol characters.",
        )

    try:
        if any(
            row["username"].lower() == username.lower() or row["email"].lower() == email
            for row in get_rows("users")
        ):
            return redirect_with_message("signup_page", "That username or email is already registered.")

        user = insert_row(
            "users",
            {
                "full_name": full_name,
                "username": username,
                "password": generate_password_hash(password),
                "contact_number": contact_number,
                "address": address,
                "email": email,
                "role": "User",
                "status": "Active",
            },
        )
        if not user:
            raise DatabaseError("Supabase did not return the new user.")
        user_id = user["user_id"]
        insert_row(
            "borrowers",
            {
                "user_id": user_id,
                "full_name": full_name,
                "contact_number": contact_number,
                "address": address,
                "email": email,
            },
        )
        log_audit("CREATE", "users", user_id, f"Account created for {username}")
        return redirect_with_message("login_page", "Account created. You can now log in.")
    except DatabaseError:
        current_app.logger.exception("Account creation could not reach Supabase.")
        return redirect_with_message(
            "signup_page",
            "Account creation is temporarily unavailable. Please try again shortly.",
        )


@auth_bp.post("/login")
def login():
    identity = request.form.get("identity", "").strip()
    password = request.form.get("password", "")
    try:
        identity_lower = identity.lower()
        user = next(
            (
                row
                for row in get_rows("users")
                if row["username"].lower() == identity_lower
                or row["email"].lower() == identity_lower
            ),
            None,
        )
        if (
            not user
            or str(user["status"]).lower() != "active"
            or not check_password_hash(user["password"], password)
        ):
            return redirect_with_message("login_page", "Invalid username/email or password.")

        session.clear()
        session.update(
            user_id=user["user_id"],
            full_name=user["full_name"],
            username=user["username"],
            role=user["role"],
        )
        if is_admin():
            return redirect(url_for("dashboard_routes.dashboard"))
        return redirect(url_for("dashboard_routes.staff_dashboard"))
    except DatabaseError:
        return redirect_with_message(
            "login_page", "The database is unavailable. Please try again shortly."
        )


@auth_bp.get("/about")
@login_required
def about_page():
    return frontend_redirect("/about")


@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect_with_message("login_page", "You have been logged out.")

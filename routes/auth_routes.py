"""Authentication and general public routes."""
import mysql.connector
from flask import Blueprint, current_app, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from auth import is_admin, is_strong_password, login_required, redirect_with_message
from database import get_db_connection, log_audit

auth_bp = Blueprint("auth_routes", __name__)


@auth_bp.get("/")
@auth_bp.get("/login.html")
def login_page():
    return send_from_directory(current_app.config["ROOT_DIR"], "login.html")


@auth_bp.get("/signup.html")
def signup_page():
    return send_from_directory(current_app.config["ROOT_DIR"], "signup.html")


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
            "Use a strong password: 12+ characters with uppercase, lowercase, number, and symbol.",
        )

    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT user_id FROM users WHERE username = %s OR email = %s",
                (username, email),
            )
            if cursor.fetchone():
                return redirect_with_message("signup_page", "That username or email is already registered.")

            cursor.execute(
                "INSERT INTO users (full_name, username, password, contact_number, address, email, role, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    full_name,
                    username,
                    generate_password_hash(password),
                    contact_number,
                    address,
                    email,
                    "Staff",
                    "Active",
                ),
            )
            user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO borrowers (user_id, full_name, contact_number, address, email) "
                "VALUES (%s, %s, %s, %s, %s)",
                (user_id, full_name, contact_number, address, email),
            )
            log_audit(cursor, "CREATE", "users", user_id, f"Account created for {username}")
            db.commit()
            return redirect_with_message("login_page", "Account created. You can now log in.")
    except mysql.connector.Error:
        return redirect_with_message(
            "signup_page", "Database connection failed. Check XAMPP MySQL and app.py settings."
        )


@auth_bp.post("/login")
def login():
    identity = request.form.get("identity", "").strip()
    password = request.form.get("password", "")
    try:
        with get_db_connection() as (db, cursor):
            cursor.execute(
                "SELECT user_id, full_name, username, password, role, status "
                "FROM users WHERE username = %s OR email = %s",
                (identity, identity),
            )
            user = cursor.fetchone()
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
    except mysql.connector.Error:
        return redirect_with_message(
            "login_page", "Database connection failed. Check XAMPP MySQL and app.py settings."
        )


@auth_bp.get("/about")
@login_required
def about_page():
    return render_template("about.html", full_name=session["full_name"])


@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect_with_message("login_page", "You have been logged out.")

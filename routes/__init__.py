"""Blueprint registration and route setup."""
from routes.admin_audit import admin_audit_bp
from routes.admin_borrowers import admin_borrowers_bp
from routes.admin_borrowings import admin_borrowings_bp
from routes.admin_equipment import admin_equipment_bp
from routes.admin_reports import admin_reports_bp
from routes.admin_returns import admin_returns_bp
from routes.auth_routes import auth_bp
from routes.dashboard_routes import dashboard_bp
from routes.staff_routes import staff_bp


def register_routes(app):
    """Register all modular application blueprints on the Flask app."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(admin_equipment_bp)
    app.register_blueprint(admin_borrowers_bp)
    app.register_blueprint(admin_borrowings_bp)
    app.register_blueprint(admin_returns_bp)
    app.register_blueprint(admin_reports_bp)
    app.register_blueprint(admin_audit_bp)

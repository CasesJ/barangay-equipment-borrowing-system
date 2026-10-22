"""Flask application entry point for Barangay Equipment Borrowing System."""
import os
from datetime import date, datetime

from flask import Flask, jsonify, request
from flask.json.provider import DefaultJSONProvider
from werkzeug.exceptions import HTTPException

from config import ROOT_DIR, Config
from routes import register_routes


class CustomJSONProvider(DefaultJSONProvider):
    """Serialize date and datetime objects to ISO format in JSON responses."""

    def default(self, o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        return super().default(o)


def create_app(config_class=Config):
    """Application factory for creating and configuring the Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.config["APP_ENV"] == "production":
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError("FLASK_SECRET_KEY must be configured in production.")
        if app.config.get("DEBUG"):
            raise RuntimeError("FLASK_DEBUG must be disabled in production.")
        if not app.config.get("SESSION_COOKIE_SECURE"):
            raise RuntimeError("SESSION_COOKIE_SECURE must be enabled in production.")

    # Register custom JSON serializer for date/datetime
    app.json = CustomJSONProvider(app)

    # Register global error handling
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Keep implementation details out of ordinary-user error responses."""
        if isinstance(error, HTTPException):
            return error
        app.logger.exception("Unexpected application error")
        if request.path.startswith("/api/"):
            return jsonify(error="Unable to complete the request. Please try again."), 500
        return "Unable to complete the request. No changes were saved. Please try again.", 500

    # Register all modular blueprints
    register_routes(app)

    @app.get("/api/health")
    def health_check():
        """Liveness check for the hosting platform; it does not query Supabase."""
        return jsonify(status="ok"), 200

    return app


# Root directory for static asset and template serving
ROOT = ROOT_DIR

# Default application instance
app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=app.config["DEBUG"],
    )

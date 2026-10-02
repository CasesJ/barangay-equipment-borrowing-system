"""Flask application entry point for Barangay Equipment Borrowing System."""
from datetime import date, datetime

from flask import Flask, jsonify, request
from flask.json.provider import DefaultJSONProvider
from werkzeug.exceptions import HTTPException

from config import ROOT_DIR, Config
from database import get_db_connection, log_audit, serialize_date_fields, table_exists
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

    return app


# Root directory for static asset and template serving
ROOT = ROOT_DIR

# Default application instance
app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

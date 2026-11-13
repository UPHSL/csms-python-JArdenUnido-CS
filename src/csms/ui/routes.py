"""Web routes for the CSMS user interface."""

from flask import Blueprint, current_app, jsonify, render_template

main_blueprint = Blueprint("main", __name__)


@main_blueprint.get("/")
def index() -> str:
    """Display the Sprint 0 welcome page."""
    return render_template(
        "index.html",
        application_name=current_app.config["APP_NAME"],
        application_version=current_app.config["APP_VERSION"],
        current_sprint=current_app.config["CURRENT_SPRINT"],
    )


@main_blueprint.get("/health")
def health():
    """Return the application health response with version and status.
    
    Returns a JSON response identifying the application, release version,
    and health status. Does not expose sensitive information.
    """
    return jsonify(
        {
            "application": current_app.config["APP_SHORT_NAME"],
            "application_name": current_app.config["APP_NAME"],
            "version": current_app.config["APP_VERSION"],
            "status": "healthy",
        }
    )
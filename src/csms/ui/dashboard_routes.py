"""CSMS Dashboard presentation layer (T14).

This module provides the dashboard route that displays system-wide
operational summaries to the user.

Responsibilities:

* Receive GET /dashboard requests.
* Call the Dashboard Service to compose summary information.
* Render the dashboard template with summarized data.

What this module does NOT do:

* Perform aggregation in the controller.
* Query persistence directly.
* Modify any Resident or Service Request.
"""

from flask import Blueprint, current_app, render_template

from csms.repositories.resident_repository import ResidentRepository
from csms.repositories.service_request_repository import (
    ServiceRequestRepository,
)
from csms.services.dashboard_service import DashboardService

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="")


def _resident_repo() -> ResidentRepository:
    """Return a Resident repository using the application-configured database path."""
    return ResidentRepository(current_app.config["DATABASE_PATH"])


def _sr_repo() -> ServiceRequestRepository:
    """Return a Service Request repository using the application-configured database path."""
    return ServiceRequestRepository(current_app.config["DATABASE_PATH"])


@dashboard_bp.get("/dashboard")
def dashboard():
    """Display the CSMS Dashboard with operational summaries."""
    resident_repo = _resident_repo()
    sr_repo = _sr_repo()
    dashboard_service = DashboardService(resident_repo, sr_repo)

    summary = dashboard_service.get_dashboard_summary()

    return render_template(
        "dashboard.html",
        application_name=current_app.config["APP_NAME"],
        summary=summary,
    )

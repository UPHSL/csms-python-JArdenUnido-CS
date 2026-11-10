"""Service Request Management presentation layer (T13).

This module wires the existing Service Request application capabilities
(T09-T11) to Flask routes so that a browser user can manage Service Requests
without interacting with the application code or database directly.

Responsibilities:
* Receive HTTP requests.
* Read form/query parameters.
* Call the appropriate existing application service.
* Render a template or redirect.
* Display validation and eligibility feedback.
* Return safe 404 responses for missing Service Requests.

What this module intentionally does NOT do:
* Write SQL.
* Re-implement T09 validation rules.
* Re-implement T09 Resident eligibility logic.
* Re-implement T10 workflow transition rules.
* Re-implement T11 search/filter/ordering logic.
* Generate Service Request IDs.
* Import or use the database layer directly.
"""

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from csms.models.service_request import ServiceRequest
from csms.repositories.service_request_repository import ServiceRequestRepository
from csms.repositories.resident_repository import ResidentRepository
from csms.services.service_request_submission_service import ServiceRequestSubmissionService
from csms.services.service_request_query_service import ServiceRequestQueryService
from csms.services.service_request_status_service import ServiceRequestStatusService

service_requests_bp = Blueprint("service_requests", __name__, url_prefix="/service-requests")


def _repo() -> ServiceRequestRepository:
    """Return a repository using the application-configured database path."""
    return ServiceRequestRepository(current_app.config["DATABASE_PATH"])


# ---------------------------------------------------------------------------
# GET /service-requests  — list / search / filter
# ---------------------------------------------------------------------------

@service_requests_bp.get("/")
def list_requests():
    """Display the Service Request Management page with search and status filtering."""
    query = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    repo = _repo()
    query_service = ServiceRequestQueryService(repo)

    requests = query_service.search_service_requests(
        search_term=query,
        status_filter=status_filter if status_filter else None,
    )

    return render_template(
        "service_requests/list.html",
        application_name=current_app.config["APP_NAME"],
        requests=requests,
        query=request.args.get("q", ""),
        status=request.args.get("status", ""),
    )


# ---------------------------------------------------------------------------
# GET /service-requests/new  — submission form
# ---------------------------------------------------------------------------

@service_requests_bp.get("/new")
def new_form():
    """Display the blank Service Request submission form."""
    return render_template(
        "service_requests/new.html",
        application_name=current_app.config["APP_NAME"],
        errors=[],
        form_data={},
    )


# ---------------------------------------------------------------------------
# POST /service-requests  — process submission
# ---------------------------------------------------------------------------

@service_requests_bp.post("/")
def submit_request():
    """Process the Service Request submission form."""
    import datetime
    form = request.form
    form_data = {
        "resident_id":    form.get("resident_id",    ""),
        "service_type":   form.get("service_type",   ""),
        "description":    form.get("description",    ""),
        "date_requested": form.get("date_requested", ""),
    }

    # Parse resident_id as integer.
    try:
        resident_id = int(form_data["resident_id"]) if form_data["resident_id"] else None
    except (ValueError, TypeError):
        resident_id = None

    # Parse date_requested as datetime.date.
    try:
        if form_data["date_requested"]:
            date_requested = datetime.date.fromisoformat(form_data["date_requested"])
        else:
            date_requested = None
    except (ValueError, TypeError):
        date_requested = None
        # Add validation error for clearer feedback
        # (T09 validators will also validate date_requested and provide error message)

    candidate = ServiceRequest(
        resident_id=resident_id,
        service_type=form_data["service_type"],
        description=form_data["description"],
        date_requested=date_requested,
        status="Pending",
    )

    # T09 submission requires both repos.
    repo_resident = ResidentRepository(current_app.config["DATABASE_PATH"])
    repo_sr = _repo()
    service = ServiceRequestSubmissionService(repo_resident, repo_sr)
    result = service.submit(candidate)

    if not result.success:
        # Convert result flags to error messages if not already populated.
        errors = result.errors
        if not errors:
            if result.resident_not_found:
                errors = ["Resident not found."]
            elif result.resident_inactive:
                errors = ["Inactive Residents cannot submit new Service Requests."]
            else:
                errors = ["Service Request submission failed."]
        
        return render_template(
            "service_requests/new.html",
            application_name=current_app.config["APP_NAME"],
            errors=errors,
            form_data=form_data,
        ), 422

    flash("Service Request submitted successfully.", "success")
    return redirect(url_for("service_requests.list_requests"))


# ---------------------------------------------------------------------------
# GET /service-requests/<id>  — view details
# ---------------------------------------------------------------------------

@service_requests_bp.get("/<int:request_id>")
def view_request(request_id: int):
    """Display the details of one Service Request."""
    repo = _repo()
    query_service = ServiceRequestQueryService(repo)

    sr = query_service.view_service_request(request_id)
    if sr is None:
        abort(404)

    return render_template(
        "service_requests/view.html",
        application_name=current_app.config["APP_NAME"],
        request=sr,
    )


# ---------------------------------------------------------------------------
# POST /service-requests/<id>/start  — Pending to In Progress
# ---------------------------------------------------------------------------

@service_requests_bp.post("/<int:request_id>/start")
def start_processing(request_id: int):
    """Transition a Pending Service Request to In Progress."""
    repo = _repo()
    status_service = ServiceRequestStatusService(repo)

    result = status_service.change_status(request_id, "In Progress")

    if result.not_found:
        abort(404)

    if not result.success:
        flash("Could not start processing.", "error")
    else:
        flash("Service Request is now In Progress.", "success")

    return redirect(url_for("service_requests.view_request", request_id=request_id))


# ---------------------------------------------------------------------------
# POST /service-requests/<id>/complete  — In Progress to Completed
# ---------------------------------------------------------------------------

@service_requests_bp.post("/<int:request_id>/complete")
def complete_request(request_id: int):
    """Transition an In Progress Service Request to Completed."""
    repo = _repo()
    status_service = ServiceRequestStatusService(repo)

    result = status_service.change_status(request_id, "Completed")

    if result.not_found:
        abort(404)

    if not result.success:
        flash("Could not complete request.", "error")
    else:
        flash("Service Request completed successfully.", "success")

    return redirect(url_for("service_requests.view_request", request_id=request_id))


# ---------------------------------------------------------------------------
# POST /service-requests/<id>/cancel  — Pending/In Progress to Cancelled
# ---------------------------------------------------------------------------

@service_requests_bp.post("/<int:request_id>/cancel")
def cancel_request(request_id: int):
    """Transition a Pending or In Progress Service Request to Cancelled."""
    repo = _repo()
    status_service = ServiceRequestStatusService(repo)

    result = status_service.change_status(request_id, "Cancelled")

    if result.not_found:
        abort(404)

    if not result.success:
        flash("Could not cancel request.", "error")
    else:
        flash("Service Request cancelled successfully.", "success")

    return redirect(url_for("service_requests.view_request", request_id=request_id))

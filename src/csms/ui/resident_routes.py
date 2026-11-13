"""Resident Management presentation layer (T12).

This module wires the existing Resident application capabilities (T04-T07)
to Flask routes so that a browser user can manage Residents without
interacting with the application code or database directly.

Responsibilities:
* Receive HTTP requests.
* Read form/query parameters.
* Call the appropriate existing application service.
* Render a template or redirect.
* Display validation feedback via flash messages or template context.
* Return safe 404 responses for missing Residents.

What this module intentionally does NOT do:
* Write SQL.
* Re-implement T02 validation rules.
* Re-implement T05 search logic.
* Generate Resident IDs.
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

from csms.models.resident import Resident
from csms.repositories.resident_repository import ResidentRepository
from csms.services.resident_deactivation_service import ResidentDeactivationService
from csms.services.resident_query_service import ResidentQueryService
from csms.services.resident_service import ResidentRegistrationService
from csms.services.resident_update_service import ResidentUpdateService

residents_bp = Blueprint("residents", __name__, url_prefix="/residents")


def _repo() -> ResidentRepository:
    """Return a repository using the application-configured database path."""
    return ResidentRepository(current_app.config["DATABASE_PATH"])


# ---------------------------------------------------------------------------
# GET /residents  — list / search
# ---------------------------------------------------------------------------

@residents_bp.get("/")
def list_residents():
    """Display the Resident Management page with optional name search."""
    query = request.args.get("q", "").strip()
    repo = _repo()
    query_service = ResidentQueryService(repo)

    residents = query_service.search_residents(query)

    return render_template(
        "residents/list.html",
        application_name=current_app.config["APP_NAME"],
        residents=residents,
        query=request.args.get("q", ""),
    )


# ---------------------------------------------------------------------------
# GET /residents/register  — registration form
# ---------------------------------------------------------------------------

@residents_bp.get("/register")
def register_form():
    """Display the blank Resident registration form."""
    return render_template(
        "residents/register.html",
        application_name=current_app.config["APP_NAME"],
        errors=[],
        form_data={},
    )


# ---------------------------------------------------------------------------
# POST /residents/register  — process registration
# ---------------------------------------------------------------------------

@residents_bp.post("/register")
def register_submit():
    """Process the Resident registration form submission."""
    form = request.form
    form_data = {
        "first_name":     form.get("first_name",     ""),
        "last_name":      form.get("last_name",      ""),
        "address":        form.get("address",        ""),
        "contact_number": form.get("contact_number", ""),
        "email":          form.get("email",          ""),
    }

    candidate = Resident(
        first_name=form_data["first_name"],
        last_name=form_data["last_name"],
        address=form_data["address"],
        contact_number=form_data["contact_number"],
        email=form_data["email"],
    )

    repo = _repo()
    service = ResidentRegistrationService(repo)
    result = service.register(candidate)

    if not result.success:
        return render_template(
            "residents/register.html",
            application_name=current_app.config["APP_NAME"],
            errors=result.errors,
            form_data=form_data,
        ), 422

    flash("Resident registered successfully.", "success")
    return redirect(url_for("residents.list_residents"))


# ---------------------------------------------------------------------------
# GET /residents/<id>/edit  — pre-filled edit form
# ---------------------------------------------------------------------------

@residents_bp.get("/<int:resident_id>/edit")
def edit_form(resident_id: int):
    """Display the Resident edit form pre-filled with current information."""
    repo = _repo()
    resident = repo.find_by_id(resident_id)
    if resident is None:
        abort(404)

    return render_template(
        "residents/edit.html",
        application_name=current_app.config["APP_NAME"],
        resident=resident,
        errors=[],
        form_data={},
    )


# ---------------------------------------------------------------------------
# POST /residents/<id>/edit  — process update
# ---------------------------------------------------------------------------

@residents_bp.post("/<int:resident_id>/edit")
def edit_submit(resident_id: int):
    """Process the Resident update form submission."""
    repo = _repo()
    existing = repo.find_by_id(resident_id)
    if existing is None:
        abort(404)

    form = request.form
    form_data = {
        "first_name":     form.get("first_name",     ""),
        "last_name":      form.get("last_name",      ""),
        "address":        form.get("address",        ""),
        "contact_number": form.get("contact_number", ""),
        "email":          form.get("email",          ""),
    }

    service = ResidentUpdateService(repo)
    result = service.update(
        resident_id=resident_id,
        first_name=form_data["first_name"],
        last_name=form_data["last_name"],
        address=form_data["address"],
        contact_number=form_data["contact_number"],
        email=form_data["email"],
    )

    if not result.success:
        return render_template(
            "residents/edit.html",
            application_name=current_app.config["APP_NAME"],
            resident=existing,
            errors=result.errors,
            form_data=form_data,
        ), 422

    flash("Resident information updated successfully.", "success")
    return redirect(url_for("residents.list_residents"))


# ---------------------------------------------------------------------------
# POST /residents/<id>/deactivate  — soft deactivation
# ---------------------------------------------------------------------------

@residents_bp.post("/<int:resident_id>/deactivate")
def deactivate(resident_id: int):
    """Deactivate an Active Resident (soft — record is preserved)."""
    repo = _repo()
    service = ResidentDeactivationService(repo)
    result = service.deactivate(resident_id)

    if result.not_found:
        abort(404)

    if result.already_inactive:
        flash("Resident is already Inactive.", "info")
    else:
        flash("Resident deactivated successfully.", "success")

    return redirect(url_for("residents.list_residents"))

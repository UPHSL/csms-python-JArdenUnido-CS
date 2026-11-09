"""Presentation/integration tests for the Resident Management Interface (T12).

These tests verify that the Flask routes correctly integrate with the existing
Resident application services (T04-T07) and render appropriate responses.

Every test receives a fresh application instance backed by an isolated
temporary database through the ``app_with_db`` and ``client`` fixtures.

Test inventory
--------------
 1. test_resident_management_page_loads_successfully
 2. test_resident_list_displays_persisted_residents
 3. test_resident_search_uses_existing_search_behavior
 4. test_blank_search_displays_all_residents
 5. test_registration_form_is_accessible
 6. test_valid_registration_persists_resident
 7. test_invalid_registration_shows_validation_feedback
 8. test_edit_form_displays_existing_resident_information
 9. test_valid_update_persists_changes
10. test_invalid_update_does_not_modify_resident
11. test_missing_resident_edit_is_handled_safely
12. test_active_resident_can_be_deactivated_through_interface
13. test_inactive_resident_remains_visible
14. test_get_requests_do_not_deactivate_residents
"""

import pytest
from flask import Flask
from flask.testing import FlaskClient

from csms import create_app
from csms.models.resident import Resident
from csms.repositories.resident_repository import ResidentRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app_with_db(tmp_path) -> Flask:
    """Create a test application with an isolated temporary SQLite database."""
    db = str(tmp_path / "t12_test.db")
    application = create_app({
        "TESTING":       True,
        "DEBUG":         False,
        "SECRET_KEY":    "t12-test-secret",
        "DATABASE_PATH": db,
    })
    yield application


@pytest.fixture()
def client(app_with_db: Flask) -> FlaskClient:
    return app_with_db.test_client()


@pytest.fixture()
def repo(app_with_db: Flask) -> ResidentRepository:
    return ResidentRepository(app_with_db.config["DATABASE_PATH"])


def _save_resident(repo: ResidentRepository, **overrides) -> Resident:
    defaults = {
        "first_name": "Juan", "last_name": "Dela Cruz",
        "address": "Barangay A", "contact_number": "09171234567",
        "email": "juan@example.com", "status": "Active",
    }
    defaults.update(overrides)
    r = Resident(**defaults)
    repo.save(r)
    return r


# ---------------------------------------------------------------------------
# TEST 1 – Resident Management Page Loads Successfully
# ---------------------------------------------------------------------------

def test_resident_management_page_loads_successfully(client: FlaskClient) -> None:
    response = client.get("/residents/")
    assert response.status_code == 200
    assert b"Resident Management" in response.data


# ---------------------------------------------------------------------------
# TEST 2 – Resident List Displays Persisted Residents
# ---------------------------------------------------------------------------

def test_resident_list_displays_persisted_residents(
    client: FlaskClient, repo: ResidentRepository
) -> None:
    _save_resident(repo, first_name="Maria", last_name="Santos",
                   email="maria@example.com", contact_number="09981234567")
    _save_resident(repo, first_name="Pedro", last_name="Reyes",
                   email="pedro@example.com", contact_number="09081234567")

    response = client.get("/residents/")

    assert response.status_code == 200
    assert b"Santos" in response.data
    assert b"Reyes"  in response.data


# ---------------------------------------------------------------------------
# TEST 3 – Resident Search Uses Existing Search Behavior
# ---------------------------------------------------------------------------

def test_resident_search_uses_existing_search_behavior(
    client: FlaskClient, repo: ResidentRepository
) -> None:
    _save_resident(repo, first_name="Maria",   last_name="Santos",
                   email="maria@example.com",  contact_number="09981234567")
    _save_resident(repo, first_name="Pedro",   last_name="Reyes",
                   email="pedro@example.com",  contact_number="09081234567")

    response = client.get("/residents/?q=mar")

    assert response.status_code == 200
    assert b"Maria"  in response.data
    assert b"Santos" in response.data
    assert b"Pedro"  not in response.data


# ---------------------------------------------------------------------------
# TEST 4 – Blank Search Displays All Residents
# ---------------------------------------------------------------------------

def test_blank_search_displays_all_residents(
    client: FlaskClient, repo: ResidentRepository
) -> None:
    _save_resident(repo, first_name="Ana",   last_name="Garcia",
                   email="ana@example.com",  contact_number="09171234561")
    _save_resident(repo, first_name="Luis",  last_name="Torres",
                   email="luis@example.com", contact_number="09171234562")

    response = client.get("/residents/?q=   ")

    assert response.status_code == 200
    assert b"Garcia" in response.data
    assert b"Torres" in response.data


# ---------------------------------------------------------------------------
# TEST 5 – Registration Form Is Accessible
# ---------------------------------------------------------------------------

def test_registration_form_is_accessible(client: FlaskClient) -> None:
    response = client.get("/residents/register")

    assert response.status_code == 200
    assert b"Register Resident"  in response.data
    assert b"first_name"         in response.data
    assert b"last_name"          in response.data
    assert b"address"            in response.data
    assert b"contact_number"     in response.data
    assert b"email"              in response.data
    # ID and status must not be user-editable fields on the form.
    assert b'name="id"'     not in response.data
    assert b'name="status"' not in response.data


# ---------------------------------------------------------------------------
# TEST 6 – Valid Registration Persists Resident
# ---------------------------------------------------------------------------

def test_valid_registration_persists_resident(
    client: FlaskClient, repo: ResidentRepository
) -> None:
    response = client.post("/residents/register", data={
        "first_name":     "Ana",
        "last_name":      "Reyes",
        "address":        "Barangay Uno",
        "contact_number": "09171234599",
        "email":          "ana.reyes@example.com",
    }, follow_redirects=False)

    # Should redirect after success.
    assert response.status_code == 302

    all_residents = repo.find_all()
    assert any(r.first_name == "Ana" and r.last_name == "Reyes" for r in all_residents)

    ana = next(r for r in all_residents if r.first_name == "Ana")
    assert ana.id is not None
    assert ana.status == "Active"


# ---------------------------------------------------------------------------
# TEST 7 – Invalid Registration Shows Validation Feedback and Does Not Persist
# ---------------------------------------------------------------------------

def test_invalid_registration_shows_validation_feedback(
    client: FlaskClient, repo: ResidentRepository
) -> None:
    response = client.post("/residents/register", data={
        "first_name":     "",           # invalid – required
        "last_name":      "Santos",
        "address":        "Somewhere",
        "contact_number": "09171234567",
        "email":          "ok@example.com",
    })

    assert response.status_code in (200, 422)
    assert b"required" in response.data.lower() or b"first name" in response.data.lower()
    assert repo.find_all() == []


# ---------------------------------------------------------------------------
# TEST 8 – Edit Form Displays Existing Resident Information
# ---------------------------------------------------------------------------

def test_edit_form_displays_existing_resident_information(
    client: FlaskClient, repo: ResidentRepository
) -> None:
    resident = _save_resident(repo, first_name="Miguel", last_name="Santos",
                              email="miguel@example.com",
                              contact_number="09171234598")

    response = client.get(f"/residents/{resident.id}/edit")

    assert response.status_code == 200
    assert b"Miguel" in response.data
    assert b"Santos" in response.data
    # ID displayed but not in an editable name="id" field.
    assert b'name="id"'     not in response.data
    assert b'name="status"' not in response.data


# ---------------------------------------------------------------------------
# TEST 9 – Valid Update Persists Changes
# ---------------------------------------------------------------------------

def test_valid_update_persists_changes(
    client: FlaskClient, repo: ResidentRepository
) -> None:
    resident = _save_resident(repo, first_name="Old", last_name="Name",
                              email="old@example.com",
                              contact_number="09171234596")
    original_id = resident.id

    response = client.post(f"/residents/{resident.id}/edit", data={
        "first_name":     "New",
        "last_name":      "Name",
        "address":        "New Address",
        "contact_number": "09171234597",
        "email":          "new@example.com",
    }, follow_redirects=False)

    assert response.status_code == 302

    updated = repo.find_by_id(original_id)
    assert updated is not None
    assert updated.first_name == "New"
    assert updated.id         == original_id
    assert updated.status     == "Active"


# ---------------------------------------------------------------------------
# TEST 10 – Invalid Update Does Not Modify Resident
# ---------------------------------------------------------------------------

def test_invalid_update_does_not_modify_resident(
    client: FlaskClient, repo: ResidentRepository
) -> None:
    resident = _save_resident(repo, first_name="Keep", last_name="This",
                              email="keep@example.com",
                              contact_number="09171234595")

    response = client.post(f"/residents/{resident.id}/edit", data={
        "first_name":     "",          # invalid
        "last_name":      "This",
        "address":        "Somewhere",
        "contact_number": "09171234595",
        "email":          "keep@example.com",
    })

    assert response.status_code in (200, 422)
    still_there = repo.find_by_id(resident.id)
    assert still_there is not None
    assert still_there.first_name == "Keep"


# ---------------------------------------------------------------------------
# TEST 11 – Missing Resident Edit Is Handled Safely
# ---------------------------------------------------------------------------

def test_missing_resident_edit_is_handled_safely(client: FlaskClient) -> None:
    response = client.get("/residents/99999/edit")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# TEST 12 – Active Resident Can Be Deactivated Through the Interface
# ---------------------------------------------------------------------------

def test_active_resident_can_be_deactivated_through_interface(
    client: FlaskClient, repo: ResidentRepository
) -> None:
    resident = _save_resident(repo)

    response = client.post(
        f"/residents/{resident.id}/deactivate",
        follow_redirects=False,
    )

    assert response.status_code == 302

    updated = repo.find_by_id(resident.id)
    assert updated is not None
    assert updated.status == "Inactive"


# ---------------------------------------------------------------------------
# TEST 13 – Inactive Resident Remains Visible
# ---------------------------------------------------------------------------

def test_inactive_resident_remains_visible(
    client: FlaskClient, repo: ResidentRepository
) -> None:
    resident = _save_resident(repo, first_name="InactiveJuan",
                              last_name="Cruz",
                              email="inactive@example.com",
                              contact_number="09171234594")
    # Deactivate via POST.
    client.post(f"/residents/{resident.id}/deactivate")

    response = client.get("/residents/")
    assert response.status_code == 200
    assert b"InactiveJuan" in response.data
    assert b"Inactive"     in response.data


# ---------------------------------------------------------------------------
# TEST 14 – GET Requests Do Not Deactivate Residents
# ---------------------------------------------------------------------------

def test_get_requests_do_not_deactivate_residents(
    client: FlaskClient, repo: ResidentRepository
) -> None:
    resident = _save_resident(repo)

    # Simply viewing the list page must not change status.
    client.get("/residents/")
    client.get(f"/residents/{resident.id}/edit")
    client.get("/residents/register")

    still_active = repo.find_by_id(resident.id)
    assert still_active is not None
    assert still_active.status == "Active"

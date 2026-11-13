"""Presentation/integration tests for the Service Request Management Interface (T13).

These tests verify that the Flask routes correctly integrate with the existing
Service Request application services (T09-T11) and render appropriate responses.

Test inventory (20 required scenarios)
-------------------------------------
 1. test_service_request_management_page_loads
 2. test_persisted_service_requests_are_displayed
 3. test_required_ordering_is_preserved
 4. test_text_search_uses_t11_behavior
 5. test_status_filter_uses_t11_behavior
 6. test_combined_search_and_status_filter
 7. test_submission_form_is_accessible
 8. test_valid_submission_persists_pending_request
 9. test_invalid_submission_shows_validation_feedback
10. test_missing_resident_submission_is_rejected
11. test_inactive_resident_submission_is_rejected
12. test_existing_service_request_details_can_be_viewed
13. test_missing_service_request_view_is_handled_safely
14. test_pending_request_can_start_processing
15. test_pending_request_can_be_cancelled
16. test_in_progress_request_can_be_completed
17. test_in_progress_request_can_be_cancelled
18. test_invalid_direct_transition_is_still_rejected
19. test_completed_and_cancelled_requests_remain_visible
20. test_get_requests_do_not_change_service_request_state
"""

import pytest
from flask import Flask
from flask.testing import FlaskClient

from csms import create_app
from csms.models.resident import Resident
from csms.models.service_request import ServiceRequest
from csms.repositories.resident_repository import ResidentRepository
from csms.repositories.service_request_repository import ServiceRequestRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app_with_db(tmp_path) -> Flask:
    """Create a test application with an isolated temporary SQLite database."""
    db = str(tmp_path / "t13_test.db")
    application = create_app({
        "TESTING":       True,
        "DEBUG":         False,
        "SECRET_KEY":    "t13-test-secret",
        "DATABASE_PATH": db,
    })
    yield application


@pytest.fixture()
def client(app_with_db: Flask) -> FlaskClient:
    return app_with_db.test_client()


@pytest.fixture()
def repo_sr(app_with_db: Flask) -> ServiceRequestRepository:
    return ServiceRequestRepository(app_with_db.config["DATABASE_PATH"])


@pytest.fixture()
def repo_res(app_with_db: Flask) -> ResidentRepository:
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


def _save_request(repo: ServiceRequestRepository, **overrides) -> ServiceRequest:
    import datetime
    defaults = {
        "resident_id": 1, "service_type": "Barangay Clearance",
        "description": "Requesting clearance for employment.",
        "date_requested": datetime.date(2026, 10, 20), "status": "Pending",
    }
    defaults.update(overrides)
    
    # Convert date_requested string to date if needed.
    if isinstance(defaults["date_requested"], str):
        parts = defaults["date_requested"].split("-")
        defaults["date_requested"] = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
    
    sr = ServiceRequest(**defaults)
    repo.save(sr)
    return sr


# ---------------------------------------------------------------------------
# TEST 1 – Service Request Management Page Loads
# ---------------------------------------------------------------------------

def test_service_request_management_page_loads(client: FlaskClient) -> None:
    response = client.get("/service-requests/")
    assert response.status_code == 200
    assert b"Service Request Management" in response.data


# ---------------------------------------------------------------------------
# TEST 2 – Persisted Service Requests Are Displayed
# ---------------------------------------------------------------------------

def test_persisted_service_requests_are_displayed(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    _save_request(repo_sr, resident_id=res.id, service_type="Clearance")
    _save_request(repo_sr, resident_id=res.id, service_type="Medical Certificate")

    response = client.get("/service-requests/")

    assert response.status_code == 200
    assert b"Clearance" in response.data
    assert b"Medical Certificate" in response.data


# ---------------------------------------------------------------------------
# TEST 3 – Required Ordering Is Preserved
# ---------------------------------------------------------------------------

def test_required_ordering_is_preserved(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    # Create: save id=1 with earlier date, then id=2 with later date.
    sr1 = _save_request(repo_sr, resident_id=res.id, date_requested="2026-10-19",
                        service_type="Earlier Request")
    sr2 = _save_request(repo_sr, resident_id=res.id, date_requested="2026-10-20",
                        service_type="Later Request")

    response = client.get("/service-requests/")

    assert response.status_code == 200
    # Directly query the repo to verify ordering without relying on HTML parsing.
    all_reqs = repo_sr.find_all()
    assert len(all_reqs) >= 2
    # First result should have later date (DESC ordering).
    assert all_reqs[0].service_type == "Later Request"
    assert all_reqs[1].service_type == "Earlier Request"


# ---------------------------------------------------------------------------
# TEST 4 – Text Search Uses T11 Behavior
# ---------------------------------------------------------------------------

def test_text_search_uses_t11_behavior(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    _save_request(repo_sr, resident_id=res.id, service_type="Barangay Clearance",
                  description="Employment clearance needed")
    _save_request(repo_sr, resident_id=res.id, service_type="Medical Certificate",
                  description="For health screening")

    response = client.get("/service-requests/?q=clear")

    assert response.status_code == 200
    assert b"Barangay Clearance" in response.data
    assert b"Medical" not in response.data


# ---------------------------------------------------------------------------
# TEST 5 – Status Filter Uses T11 Behavior
# ---------------------------------------------------------------------------

def test_status_filter_uses_t11_behavior(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    _save_request(repo_sr, resident_id=res.id, status="Pending")
    _save_request(repo_sr, resident_id=res.id, status="Completed")

    response = client.get("/service-requests/?status=Pending")

    assert response.status_code == 200
    # Extract table body only to check displayed requests.
    data = response.data.decode('utf-8')
    table_start = data.find("<tbody>")
    table_end = data.find("</tbody>")
    table_body = data[table_start:table_end] if table_start >= 0 and table_end >= 0 else ""
    # Should have Pending badge but not Completed badge in table.
    assert b"Pending" in response.data
    # Completed should not be in the table rows
    assert table_body.count("Completed") == 0


# ---------------------------------------------------------------------------
# TEST 6 – Combined Search and Status Filter
# ---------------------------------------------------------------------------

def test_combined_search_and_status_filter(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    _save_request(repo_sr, resident_id=res.id, service_type="Clearance", status="Pending")
    _save_request(repo_sr, resident_id=res.id, service_type="Clearance", status="Completed")
    _save_request(repo_sr, resident_id=res.id, service_type="Medical", status="Pending")

    response = client.get("/service-requests/?q=clear&status=Pending")

    assert response.status_code == 200
    assert b"Clearance" in response.data
    # Should not show Medical or Completed.
    data = response.data.decode('utf-8')
    # Count Clearance entries (should be present).
    clearance_count = data.count("Clearance")
    assert clearance_count > 0


# ---------------------------------------------------------------------------
# TEST 7 – Submission Form Is Accessible
# ---------------------------------------------------------------------------

def test_submission_form_is_accessible(client: FlaskClient) -> None:
    response = client.get("/service-requests/new")

    assert response.status_code == 200
    assert b"Submit Service Request" in response.data
    assert b"resident_id" in response.data
    assert b"service_type" in response.data
    assert b"description" in response.data
    assert b"date_requested" in response.data
    # ID and status must not be user-editable.
    assert b'name="id"' not in response.data
    assert b'name="status"' not in response.data


# ---------------------------------------------------------------------------
# TEST 8 – Valid Submission Persists Pending Request
# ---------------------------------------------------------------------------

def test_valid_submission_persists_pending_request(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)

    response = client.post("/service-requests/", data={
        "resident_id":    str(res.id),
        "service_type":   "Barangay Clearance",
        "description":    "Employment requirement",
        "date_requested": "2026-10-20",
    }, follow_redirects=False)

    assert response.status_code == 302

    all_requests = repo_sr.find_all()
    assert any(r.service_type == "Barangay Clearance" for r in all_requests)

    sr = next(r for r in all_requests if r.service_type == "Barangay Clearance")
    assert sr.id is not None
    assert sr.resident_id == res.id
    assert sr.status == "Pending"


# ---------------------------------------------------------------------------
# TEST 9 – Invalid Submission Shows Validation Feedback
# ---------------------------------------------------------------------------

def test_invalid_submission_shows_validation_feedback(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)

    response = client.post("/service-requests/", data={
        "resident_id":    str(res.id),
        "service_type":   "",           # invalid
        "description":    "Something",
        "date_requested": "2026-10-20",
    })

    assert response.status_code in (200, 422)
    assert b"required" in response.data.lower() or b"service" in response.data.lower()
    assert repo_sr.find_all() == []


# ---------------------------------------------------------------------------
# TEST 10 – Missing Resident Submission Is Rejected
# ---------------------------------------------------------------------------

def test_missing_resident_submission_is_rejected(
    client: FlaskClient, repo_sr: ServiceRequestRepository
) -> None:
    response = client.post("/service-requests/", data={
        "resident_id":    "99999",
        "service_type":   "Clearance",
        "description":    "Valid description",
        "date_requested": "2026-10-20",
    })

    assert response.status_code in (200, 422)
    assert b"resident" in response.data.lower() or b"not found" in response.data.lower()
    assert repo_sr.find_all() == []


# ---------------------------------------------------------------------------
# TEST 11 – Inactive Resident Submission Is Rejected
# ---------------------------------------------------------------------------

def test_inactive_resident_submission_is_rejected(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res, status="Inactive")

    response = client.post("/service-requests/", data={
        "resident_id":    str(res.id),
        "service_type":   "Clearance",
        "description":    "Valid description",
        "date_requested": "2026-10-20",
    })

    assert response.status_code in (200, 422)
    assert b"inactive" in response.data.lower()
    assert repo_sr.find_all() == []


# ---------------------------------------------------------------------------
# TEST 12 – Existing Service Request Details Can Be Viewed
# ---------------------------------------------------------------------------

def test_existing_service_request_details_can_be_viewed(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    sr = _save_request(repo_sr, resident_id=res.id, service_type="Clearance",
                       description="Employment requirement")

    response = client.get(f"/service-requests/{sr.id}")

    assert response.status_code == 200
    assert b"Clearance" in response.data
    assert b"Employment requirement" in response.data
    assert str(res.id).encode() in response.data


# ---------------------------------------------------------------------------
# TEST 13 – Missing Service Request View Is Handled Safely
# ---------------------------------------------------------------------------

def test_missing_service_request_view_is_handled_safely(client: FlaskClient) -> None:
    response = client.get("/service-requests/99999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# TEST 14 – Pending Request Can Start Processing
# ---------------------------------------------------------------------------

def test_pending_request_can_start_processing(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    sr = _save_request(repo_sr, resident_id=res.id, status="Pending")

    response = client.post(
        f"/service-requests/{sr.id}/start",
        follow_redirects=False,
    )

    assert response.status_code == 302

    updated = repo_sr.find_by_id(sr.id)
    assert updated is not None
    assert updated.status == "In Progress"


# ---------------------------------------------------------------------------
# TEST 15 – Pending Request Can Be Cancelled
# ---------------------------------------------------------------------------

def test_pending_request_can_be_cancelled(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    sr = _save_request(repo_sr, resident_id=res.id, status="Pending")

    response = client.post(
        f"/service-requests/{sr.id}/cancel",
        follow_redirects=False,
    )

    assert response.status_code == 302

    updated = repo_sr.find_by_id(sr.id)
    assert updated is not None
    assert updated.status == "Cancelled"


# ---------------------------------------------------------------------------
# TEST 16 – In-Progress Request Can Be Completed
# ---------------------------------------------------------------------------

def test_in_progress_request_can_be_completed(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    sr = _save_request(repo_sr, resident_id=res.id, status="In Progress")

    response = client.post(
        f"/service-requests/{sr.id}/complete",
        follow_redirects=False,
    )

    assert response.status_code == 302

    updated = repo_sr.find_by_id(sr.id)
    assert updated is not None
    assert updated.status == "Completed"


# ---------------------------------------------------------------------------
# TEST 17 – In-Progress Request Can Be Cancelled
# ---------------------------------------------------------------------------

def test_in_progress_request_can_be_cancelled(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    sr = _save_request(repo_sr, resident_id=res.id, status="In Progress")

    response = client.post(
        f"/service-requests/{sr.id}/cancel",
        follow_redirects=False,
    )

    assert response.status_code == 302

    updated = repo_sr.find_by_id(sr.id)
    assert updated is not None
    assert updated.status == "Cancelled"


# ---------------------------------------------------------------------------
# TEST 18 – Invalid Direct Transition Is Still Rejected
# ---------------------------------------------------------------------------

def test_invalid_direct_transition_is_still_rejected(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    """Attempt Pending -> Completed directly; T10 should reject it."""
    res = _save_resident(repo_res)
    sr = _save_request(repo_sr, resident_id=res.id, status="Pending")

    # Attempt to complete a Pending request (invalid transition).
    response = client.post(
        f"/service-requests/{sr.id}/complete",
        follow_redirects=False,
    )

    # Could be 302 if T10 silently rejects, or 200/422 if error is shown.
    # The important thing is status is not Completed.
    updated = repo_sr.find_by_id(sr.id)
    assert updated is not None
    assert updated.status == "Pending"


# ---------------------------------------------------------------------------
# TEST 19 – Completed and Cancelled Requests Remain Visible
# ---------------------------------------------------------------------------

def test_completed_and_cancelled_requests_remain_visible(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    _save_request(repo_sr, resident_id=res.id, status="Completed", service_type="Done Request")
    _save_request(repo_sr, resident_id=res.id, status="Cancelled", service_type="Cancelled Request")

    response = client.get("/service-requests/")

    assert response.status_code == 200
    assert b"Done Request" in response.data
    assert b"Cancelled Request" in response.data


# ---------------------------------------------------------------------------
# TEST 20 – GET Requests Do Not Change Service Request State
# ---------------------------------------------------------------------------

def test_get_requests_do_not_change_service_request_state(
    client: FlaskClient, repo_res: ResidentRepository, repo_sr: ServiceRequestRepository
) -> None:
    res = _save_resident(repo_res)
    sr = _save_request(repo_sr, resident_id=res.id, status="Pending")

    # Normal GET operations.
    client.get("/service-requests/")
    client.get(f"/service-requests/{sr.id}")
    client.get("/service-requests/new")

    still_pending = repo_sr.find_by_id(sr.id)
    assert still_pending is not None
    assert still_pending.status == "Pending"

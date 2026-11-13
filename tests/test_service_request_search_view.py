"""Automated tests for Service Request search and view (T11).

These tests verify that :class:`~csms.services.service_request_query_service.ServiceRequestQueryService`
correctly implements listing, view-by-ID, text search, status filtering,
and combined querying over real SQLite persistence.

Every test receives a fresh database through the ``db_path`` fixture.

Test inventory
--------------
 1. test_list_all_persisted_service_requests
 2. test_empty_listing_returns_empty_collection
 3. test_listing_uses_required_ordering
 4. test_view_existing_service_request_by_id
 5. test_viewing_unknown_id_is_handled_safely
 6. test_partial_service_type_search_is_case_insensitive
 7. test_partial_description_search_is_case_insensitive
 8. test_blank_search_returns_all_service_requests
 9. test_no_text_match_returns_empty_collection
10. test_status_filter_returns_only_matching_status
11. test_unfiltered_query_includes_all_statuses
12. test_combined_text_search_and_status_filter
13. test_matching_service_request_is_not_duplicated
14. test_query_result_preserves_complete_service_request_information
"""

import datetime

import pytest

from csms.models.resident import Resident
from csms.models.service_request import ServiceRequest
from csms.repositories.resident_repository import ResidentRepository
from csms.repositories.service_request_repository import ServiceRequestRepository
from csms.services.service_request_query_service import ServiceRequestQueryService
from csms.services.service_request_status_service import ServiceRequestStatusService
from csms.services.service_request_submission_service import (
    ServiceRequestSubmissionService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path: object) -> str:
    return str(tmp_path / "test_t11.db")  # type: ignore[operator]


@pytest.fixture()
def res_repo(db_path: str) -> ResidentRepository:
    return ResidentRepository(db_path)


@pytest.fixture()
def sr_repo(db_path: str) -> ServiceRequestRepository:
    return ServiceRequestRepository(db_path)


@pytest.fixture()
def query_service(sr_repo: ServiceRequestRepository) -> ServiceRequestQueryService:
    return ServiceRequestQueryService(sr_repo)


@pytest.fixture()
def submission_service(
    res_repo: ResidentRepository,
    sr_repo: ServiceRequestRepository,
) -> ServiceRequestSubmissionService:
    return ServiceRequestSubmissionService(res_repo, sr_repo)


@pytest.fixture()
def status_service(sr_repo: ServiceRequestRepository) -> ServiceRequestStatusService:
    return ServiceRequestStatusService(sr_repo)


def _save_resident(repo: ResidentRepository, **overrides: object) -> Resident:
    defaults: dict[str, object] = {
        "first_name": "Juan", "last_name": "Dela Cruz",
        "address": "Barangay A", "contact_number": "09171234567",
        "email": "juan@example.com", "status": "Active",
    }
    defaults.update(overrides)
    r = Resident(**defaults)  # type: ignore[arg-type]
    repo.save(r)
    return r


def _submit(
    submission_service: ServiceRequestSubmissionService,
    resident: Resident,
    service_type: str = "Barangay Clearance",
    description: str = "For employment purposes.",
    date_requested: datetime.date = datetime.date(2026, 10, 5),
) -> ServiceRequest:
    sr = ServiceRequest(
        resident_id=resident.id,  # type: ignore[arg-type]
        service_type=service_type,
        description=description,
        date_requested=date_requested,
    )
    result = submission_service.submit(sr)
    assert result.success, "Test setup: submission failed"
    return result.service_request  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# TEST 1 – List All Persisted Service Requests
# ---------------------------------------------------------------------------

def test_list_all_persisted_service_requests(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    _submit(submission_service, resident, service_type="Barangay Clearance")
    _submit(submission_service, resident, service_type="Certificate Request")
    _submit(submission_service, resident, service_type="Community Assistance")

    result = query_service.list_service_requests()

    assert len(result) == 3
    types = {sr.service_type for sr in result}
    assert types == {"Barangay Clearance", "Certificate Request", "Community Assistance"}


# ---------------------------------------------------------------------------
# TEST 2 – Empty Listing Returns an Empty Collection
# ---------------------------------------------------------------------------

def test_empty_listing_returns_empty_collection(
    query_service: ServiceRequestQueryService,
) -> None:
    result = query_service.list_service_requests()

    assert result == []
    assert result is not None


# ---------------------------------------------------------------------------
# TEST 3 – Listing Uses Required Ordering (dateRequested DESC, id DESC)
# ---------------------------------------------------------------------------

def test_listing_uses_required_ordering(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    # Insert in wrong order; expected: ID15(18th), ID12(18th), ID8(15th), ID20(10th)
    # We can't control auto-generated IDs, so we verify relative ordering by date.
    sr_a = _submit(submission_service, resident,
                   description="A", date_requested=datetime.date(2026, 9, 15))
    sr_b = _submit(submission_service, resident,
                   description="B", date_requested=datetime.date(2026, 9, 18))
    sr_c = _submit(submission_service, resident,
                   description="C", date_requested=datetime.date(2026, 9, 18))
    sr_d = _submit(submission_service, resident,
                   description="D", date_requested=datetime.date(2026, 9, 10))

    result = query_service.list_service_requests()

    assert len(result) == 4
    # Both 2026-09-18 entries come first.
    assert result[0].date_requested == datetime.date(2026, 9, 18)
    assert result[1].date_requested == datetime.date(2026, 9, 18)
    # Same date → higher id first.
    assert result[0].id > result[1].id  # type: ignore[operator]
    # Then 2026-09-15, then 2026-09-10.
    assert result[2].date_requested == datetime.date(2026, 9, 15)
    assert result[3].date_requested == datetime.date(2026, 9, 10)


# ---------------------------------------------------------------------------
# TEST 4 – View Existing Service Request by ID
# ---------------------------------------------------------------------------

def test_view_existing_service_request_by_id(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    sr = _submit(submission_service, resident)

    result = query_service.view_service_request(sr.id)  # type: ignore[arg-type]

    assert result is not None
    assert result.id == sr.id


# ---------------------------------------------------------------------------
# TEST 5 – Viewing an Unknown ID Is Handled Safely
# ---------------------------------------------------------------------------

def test_viewing_unknown_id_is_handled_safely(
    query_service: ServiceRequestQueryService,
    sr_repo: ServiceRequestRepository,
) -> None:
    result = query_service.view_service_request(99999)

    assert result is None
    assert sr_repo.find_by_id(99999) is None


# ---------------------------------------------------------------------------
# TEST 6 – Partial Service-Type Search Is Case-Insensitive
# ---------------------------------------------------------------------------

def test_partial_service_type_search_is_case_insensitive(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    target = _submit(submission_service, resident,
                     service_type="Barangay Clearance",
                     description="No match text here.")
    other  = _submit(submission_service, resident,
                     service_type="Community Assistance",
                     description="Unrelated description.")

    result = query_service.search_service_requests("cLeAr")

    ids = [sr.id for sr in result]
    assert target.id in ids
    assert other.id not in ids


# ---------------------------------------------------------------------------
# TEST 7 – Partial Description Search Is Case-Insensitive
# ---------------------------------------------------------------------------

def test_partial_description_search_is_case_insensitive(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    target = _submit(submission_service, resident,
                     service_type="Permit Request",
                     description="Requesting clearance for employment.")

    result = query_service.search_service_requests("EMPLOYMENT")

    ids = [sr.id for sr in result]
    assert target.id in ids


# ---------------------------------------------------------------------------
# TEST 8 – Blank Search Returns All Service Requests
# ---------------------------------------------------------------------------

def test_blank_search_returns_all_service_requests(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    _submit(submission_service, resident, service_type="Type A")
    _submit(submission_service, resident, service_type="Type B")

    blank_result = query_service.search_service_requests("   ")
    list_result  = query_service.list_service_requests()

    assert len(blank_result) == len(list_result) == 2
    assert [sr.id for sr in blank_result] == [sr.id for sr in list_result]


# ---------------------------------------------------------------------------
# TEST 9 – No Text Match Returns an Empty Collection
# ---------------------------------------------------------------------------

def test_no_text_match_returns_empty_collection(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    _submit(submission_service, resident, service_type="Barangay Clearance")

    result = query_service.search_service_requests("ZZZNoMatchXXX")

    assert result == []
    assert result is not None


# ---------------------------------------------------------------------------
# TEST 10 – Status Filter Returns Only Matching Status
# ---------------------------------------------------------------------------

def test_status_filter_returns_only_matching_status(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    pending  = _submit(submission_service, resident, description="stays pending")
    in_prog  = _submit(submission_service, resident, description="moves to in progress")
    status_service.change_status(in_prog.id, "In Progress")  # type: ignore[arg-type]

    result = query_service.search_service_requests("", status_filter="Pending")

    statuses = {sr.status for sr in result}
    assert statuses == {"Pending"}
    ids = [sr.id for sr in result]
    assert pending.id in ids
    assert in_prog.id not in ids


# ---------------------------------------------------------------------------
# TEST 11 – Unfiltered Query Includes All Statuses
# ---------------------------------------------------------------------------

def test_unfiltered_query_includes_all_statuses(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    pending   = _submit(submission_service, resident)
    in_prog   = _submit(submission_service, resident,
                        description="in progress one",
                        date_requested=datetime.date(2026, 10, 4))
    completed = _submit(submission_service, resident,
                        description="completed one",
                        date_requested=datetime.date(2026, 10, 3))
    cancelled = _submit(submission_service, resident,
                        description="cancelled one",
                        date_requested=datetime.date(2026, 10, 2))

    status_service.change_status(in_prog.id, "In Progress")   # type: ignore[arg-type]
    status_service.change_status(completed.id, "In Progress") # type: ignore[arg-type]
    status_service.change_status(completed.id, "Completed")   # type: ignore[arg-type]
    status_service.change_status(cancelled.id, "Cancelled")   # type: ignore[arg-type]

    result = query_service.list_service_requests()

    statuses = {sr.status for sr in result}
    assert "Pending"     in statuses
    assert "In Progress" in statuses
    assert "Completed"   in statuses
    assert "Cancelled"   in statuses


# ---------------------------------------------------------------------------
# TEST 12 – Combined Text Search and Status Filter
# ---------------------------------------------------------------------------

def test_combined_text_search_and_status_filter(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    # Matches text AND status (Pending).
    match_both = _submit(submission_service, resident,
                         service_type="Barangay Clearance",
                         description="For employment.")
    # Matches text but NOT status (Completed).
    text_only  = _submit(submission_service, resident,
                         service_type="Barangay Clearance",
                         description="Other reason.",
                         date_requested=datetime.date(2026, 10, 4))
    status_service.change_status(text_only.id, "In Progress")  # type: ignore[arg-type]
    status_service.change_status(text_only.id, "Completed")    # type: ignore[arg-type]
    # Matches status but NOT text.
    status_only = _submit(submission_service, resident,
                          service_type="Community Assistance",
                          description="Unrelated.",
                          date_requested=datetime.date(2026, 10, 3))
    # Matches neither.
    neither = _submit(submission_service, resident,
                      service_type="Community Assistance",
                      description="Nothing here.",
                      date_requested=datetime.date(2026, 10, 2))
    status_service.change_status(neither.id, "In Progress")  # type: ignore[arg-type]
    status_service.change_status(neither.id, "Completed")    # type: ignore[arg-type]

    result = query_service.search_service_requests(
        "clearance", status_filter="Pending"
    )

    ids = [sr.id for sr in result]
    assert match_both.id  in ids
    assert text_only.id  not in ids
    assert status_only.id not in ids
    assert neither.id    not in ids


# ---------------------------------------------------------------------------
# TEST 13 – Matching Service Request Is Not Duplicated
# ---------------------------------------------------------------------------

def test_matching_service_request_is_not_duplicated(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    # Both service_type and description contain "assistance".
    sr = _submit(submission_service, resident,
                 service_type="Community Assistance",
                 description="Assistance requested for medical support.")

    result = query_service.search_service_requests("assistance")

    assert len(result) == 1
    assert result[0].id == sr.id


# ---------------------------------------------------------------------------
# TEST 14 – Query Result Preserves Complete Service Request Information
# ---------------------------------------------------------------------------

def test_query_result_preserves_complete_service_request_information(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    query_service: ServiceRequestQueryService,
) -> None:
    resident = _save_resident(res_repo)
    sr = _submit(
        submission_service, resident,
        service_type="Certificate Request",
        description="School enrollment requirement.",
        date_requested=datetime.date(2026, 10, 1),
    )

    result = query_service.search_service_requests("Certificate")

    assert len(result) == 1
    r = result[0]
    assert r.id             == sr.id
    assert r.resident_id    == resident.id
    assert r.service_type   == "Certificate Request"
    assert r.description    == "School enrollment requirement."
    assert r.date_requested == datetime.date(2026, 10, 1)
    assert r.status         == "Pending"

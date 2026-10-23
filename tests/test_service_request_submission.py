"""Automated tests for Service Request validation and submission (T09).

These tests verify that:
- :class:`~csms.utils.service_request_validators.validate_service_request`
  correctly enforces the T09 intrinsic validation rules.
- :class:`~csms.services.service_request_submission_service.ServiceRequestSubmissionService`
  correctly coordinates validation, Resident eligibility, and persistence.

Every test receives fresh SQLite databases through the ``db_path`` fixture.

Test inventory
--------------
 1. test_valid_submission_succeeds
 2. test_submitted_request_receives_generated_id
 3. test_submitted_request_is_persisted_and_retrievable
 4. test_submitted_request_information_is_preserved
 5. test_submitted_request_status_is_pending
 6. test_blank_service_type_fails_validation
 7. test_blank_description_fails_validation
 8. test_invalid_request_does_not_reach_persistence
 9. test_nonexistent_resident_prevents_submission
10. test_inactive_resident_cannot_submit
11. test_non_pending_initial_status_is_rejected
12. test_persists_across_repository_access
13. test_submission_does_not_modify_resident
14. test_invalid_date_fails_validation  (date validation test)
"""

import datetime

import pytest

from csms.models.resident import Resident
from csms.models.service_request import ServiceRequest
from csms.repositories.resident_repository import ResidentRepository
from csms.repositories.service_request_repository import ServiceRequestRepository
from csms.services.service_request_submission_service import (
    ServiceRequestSubmissionService,
    SubmissionResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path: object) -> str:
    return str(tmp_path / "test_t09.db")  # type: ignore[operator]


@pytest.fixture()
def res_repo(db_path: str) -> ResidentRepository:
    return ResidentRepository(db_path)


@pytest.fixture()
def sr_repo(db_path: str) -> ServiceRequestRepository:
    return ServiceRequestRepository(db_path)


@pytest.fixture()
def service(
    res_repo: ResidentRepository,
    sr_repo: ServiceRequestRepository,
) -> ServiceRequestSubmissionService:
    return ServiceRequestSubmissionService(res_repo, sr_repo)


TEST_DATE = datetime.date(2026, 9, 27)


def _save_active_resident(repo: ResidentRepository, **overrides: object) -> Resident:
    defaults: dict[str, object] = {
        "first_name":     "Juan",
        "last_name":      "Dela Cruz",
        "address":        "Barangay Santo Tomas",
        "contact_number": "09171234567",
        "email":          "juan@example.com",
        "status":         "Active",
    }
    defaults.update(overrides)
    r = Resident(**defaults)  # type: ignore[arg-type]
    repo.save(r)
    return r


def _make_sr(resident_id: int, **overrides: object) -> ServiceRequest:
    defaults: dict[str, object] = {
        "resident_id":    resident_id,
        "service_type":   "Barangay Clearance",
        "description":    "Request for employment.",
        "date_requested": TEST_DATE,
    }
    defaults.update(overrides)
    return ServiceRequest(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TEST 1 – Valid Service Request Submission Succeeds
# ---------------------------------------------------------------------------

def test_valid_submission_succeeds(
    res_repo: ResidentRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    resident = _save_active_resident(res_repo)
    sr = _make_sr(resident.id)  # type: ignore[arg-type]

    result = service.submit(sr)

    assert isinstance(result, SubmissionResult)
    assert result.success is True
    assert result.resident_not_found is False
    assert result.resident_inactive is False
    assert result.errors == []


# ---------------------------------------------------------------------------
# TEST 2 – Submitted Request Receives a Generated ID
# ---------------------------------------------------------------------------

def test_submitted_request_receives_generated_id(
    res_repo: ResidentRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    resident = _save_active_resident(res_repo)
    sr = _make_sr(resident.id)  # type: ignore[arg-type]
    assert sr.id is None

    result = service.submit(sr)

    assert result.success is True
    assert result.service_request is not None
    assert result.service_request.id is not None
    assert isinstance(result.service_request.id, int)


# ---------------------------------------------------------------------------
# TEST 3 – Submitted Request Is Persisted and Retrievable
# ---------------------------------------------------------------------------

def test_submitted_request_is_persisted_and_retrievable(
    res_repo: ResidentRepository,
    sr_repo: ServiceRequestRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    resident = _save_active_resident(res_repo)
    sr = _make_sr(resident.id)  # type: ignore[arg-type]

    result = service.submit(sr)
    assert result.success is True

    retrieved = sr_repo.find_by_id(result.service_request.id)  # type: ignore[union-attr]
    assert retrieved is not None
    assert retrieved.id == result.service_request.id


# ---------------------------------------------------------------------------
# TEST 4 – Submitted Request Information Is Preserved
# ---------------------------------------------------------------------------

def test_submitted_request_information_is_preserved(
    res_repo: ResidentRepository,
    sr_repo: ServiceRequestRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    resident = _save_active_resident(res_repo)
    sr = _make_sr(
        resident.id,  # type: ignore[arg-type]
        service_type="Certificate Request",
        description="Needs a certificate for school.",
        date_requested=datetime.date(2026, 10, 1),
    )

    result = service.submit(sr)
    assert result.success is True

    retrieved = sr_repo.find_by_id(result.service_request.id)  # type: ignore[union-attr]
    assert retrieved is not None
    assert retrieved.resident_id    == resident.id
    assert retrieved.service_type   == "Certificate Request"
    assert retrieved.description    == "Needs a certificate for school."
    assert retrieved.date_requested == datetime.date(2026, 10, 1)
    assert retrieved.status         == "Pending"


# ---------------------------------------------------------------------------
# TEST 5 – Submitted Request Status Is Pending
# ---------------------------------------------------------------------------

def test_submitted_request_status_is_pending(
    res_repo: ResidentRepository,
    sr_repo: ServiceRequestRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    resident = _save_active_resident(res_repo)
    sr = _make_sr(resident.id)  # type: ignore[arg-type]

    result = service.submit(sr)
    assert result.success is True

    retrieved = sr_repo.find_by_id(result.service_request.id)  # type: ignore[union-attr]
    assert retrieved is not None
    assert retrieved.status == "Pending"


# ---------------------------------------------------------------------------
# TEST 6 – Blank Service Type Fails Validation
# ---------------------------------------------------------------------------

def test_blank_service_type_fails_validation(
    res_repo: ResidentRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    resident = _save_active_resident(res_repo)
    sr = _make_sr(resident.id, service_type="   ")  # type: ignore[arg-type]

    result = service.submit(sr)

    assert result.success is False
    assert result.resident_not_found is False
    assert result.resident_inactive  is False
    assert len(result.errors) > 0
    service_type_errors = [e for e in result.errors if "service_type" in e.lower()]
    assert len(service_type_errors) > 0


# ---------------------------------------------------------------------------
# TEST 7 – Blank Description Fails Validation
# ---------------------------------------------------------------------------

def test_blank_description_fails_validation(
    res_repo: ResidentRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    resident = _save_active_resident(res_repo)
    sr = _make_sr(resident.id, description="")  # type: ignore[arg-type]

    result = service.submit(sr)

    assert result.success is False
    assert len(result.errors) > 0
    description_errors = [e for e in result.errors if "description" in e.lower()]
    assert len(description_errors) > 0


# ---------------------------------------------------------------------------
# TEST 8 – Invalid Request Does Not Reach Persistence
# ---------------------------------------------------------------------------

def test_invalid_request_does_not_reach_persistence(
    res_repo: ResidentRepository,
    sr_repo: ServiceRequestRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    resident = _save_active_resident(res_repo)
    invalid_sr = _make_sr(resident.id, service_type="")  # type: ignore[arg-type]

    result = service.submit(invalid_sr)
    assert result.success is False

    # No service request should exist in the DB.
    assert invalid_sr.id is None
    # Attempting to retrieve id=1 returns None since nothing was saved.
    assert sr_repo.find_by_id(1) is None


# ---------------------------------------------------------------------------
# TEST 9 – Nonexistent Resident Prevents Submission
# ---------------------------------------------------------------------------

def test_nonexistent_resident_prevents_submission(
    sr_repo: ServiceRequestRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    sr = _make_sr(99999)  # no resident with this id

    result = service.submit(sr)

    assert result.success           is False
    assert result.resident_not_found is True
    assert result.resident_inactive  is False
    assert result.service_request   is None
    assert sr_repo.find_by_id(1)   is None


# ---------------------------------------------------------------------------
# TEST 10 – Inactive Resident Cannot Submit a New Service Request
# ---------------------------------------------------------------------------

def test_inactive_resident_cannot_submit(
    res_repo: ResidentRepository,
    sr_repo: ServiceRequestRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    inactive = _save_active_resident(
        res_repo,
        status="Inactive",
        email="inactive@example.com",
        contact_number="09081234567",
    )
    sr = _make_sr(inactive.id)  # type: ignore[arg-type]

    result = service.submit(sr)

    assert result.success            is False
    assert result.resident_inactive  is True
    assert result.resident_not_found is False
    assert result.service_request    is None
    assert sr_repo.find_by_id(1)    is None

    # Resident must remain unchanged.
    stored = res_repo.find_by_id(inactive.id)  # type: ignore[arg-type]
    assert stored is not None
    assert stored.status == "Inactive"


# ---------------------------------------------------------------------------
# TEST 11 – Non-Pending Initial Status Is Rejected
# ---------------------------------------------------------------------------

def test_non_pending_initial_status_is_rejected(
    res_repo: ResidentRepository,
    sr_repo: ServiceRequestRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    resident = _save_active_resident(res_repo)
    sr = ServiceRequest(
        resident_id=resident.id,  # type: ignore[arg-type]
        service_type="Barangay Clearance",
        description="Some request.",
        date_requested=TEST_DATE,
        status="Completed",   # not Pending — must be rejected
    )

    result = service.submit(sr)

    assert result.success is False
    assert sr_repo.find_by_id(1) is None


# ---------------------------------------------------------------------------
# TEST 12 – Persists Across Repository Access
# ---------------------------------------------------------------------------

def test_persists_across_repository_access(
    db_path: str,
    res_repo: ResidentRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    """Data saved through the submission service is visible to a new repo instance."""
    resident = _save_active_resident(res_repo)
    sr = _make_sr(resident.id)  # type: ignore[arg-type]

    result = service.submit(sr)
    assert result.success is True
    saved_id = result.service_request.id  # type: ignore[union-attr]

    # New independent repository instance.
    repo2 = ServiceRequestRepository(db_path)
    retrieved = repo2.find_by_id(saved_id)  # type: ignore[arg-type]
    assert retrieved is not None
    assert retrieved.id == saved_id


# ---------------------------------------------------------------------------
# TEST 13 – Submission Does Not Modify the Resident
# ---------------------------------------------------------------------------

def test_submission_does_not_modify_resident(
    res_repo: ResidentRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    resident = _save_active_resident(
        res_repo,
        first_name="Maria",
        last_name="Santos",
        contact_number="09981234567",
        email="maria@example.com",
    )
    sr = _make_sr(resident.id)  # type: ignore[arg-type]

    result = service.submit(sr)
    assert result.success is True

    stored = res_repo.find_by_id(resident.id)  # type: ignore[arg-type]
    assert stored is not None
    assert stored.id             == resident.id
    assert stored.first_name     == "Maria"
    assert stored.last_name      == "Santos"
    assert stored.contact_number == "09981234567"
    assert stored.email          == "maria@example.com"
    assert stored.status         == "Active"


# ---------------------------------------------------------------------------
# TEST 14 – Invalid Date Fails Validation (date validation test)
# ---------------------------------------------------------------------------

def test_invalid_date_fails_validation(
    res_repo: ResidentRepository,
    service: ServiceRequestSubmissionService,
) -> None:
    """A Service Request with a non-date date_requested must be rejected."""
    resident = _save_active_resident(res_repo)

    # Directly construct with a string instead of datetime.date.
    sr = ServiceRequest(
        resident_id=resident.id,  # type: ignore[arg-type]
        service_type="Barangay Clearance",
        description="Some request.",
        date_requested="not-a-date",  # type: ignore[arg-type]
        status="Pending",
    )

    result = service.submit(sr)

    assert result.success is False
    date_errors = [e for e in result.errors if "date_requested" in e.lower()]
    assert len(date_errors) > 0

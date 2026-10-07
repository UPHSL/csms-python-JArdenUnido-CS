"""Automated tests for Service Request status management (T10).

These tests verify that :class:`~csms.services.service_request_status_service.ServiceRequestStatusService`
correctly enforces the Service Request processing lifecycle.

Every test uses a fresh SQLite database (``db_path`` fixture) so tests are
fully isolated.

Required test inventory (13)
-----------------------------
 1. test_pending_can_move_to_in_progress
 2. test_pending_can_move_to_cancelled
 3. test_in_progress_can_move_to_completed
 4. test_in_progress_can_move_to_cancelled
 5. test_pending_cannot_move_directly_to_completed
 6. test_in_progress_cannot_return_to_pending
 7. test_completed_is_terminal
 8. test_cancelled_is_terminal
 9. test_unsupported_status_is_rejected
10. test_nonexistent_service_request_is_handled_safely
11. test_successful_transition_preserves_service_request_information
12. test_invalid_transition_does_not_modify_persistence
13. test_same_status_request_is_rejected

Student-designed test (1)
--------------------------
14. test_sequential_valid_transitions_work_correctly
    Verifies that a Service Request can progress through its full lifecycle
    in the correct order: Pending → In Progress → Completed.  This test
    checks multi-step workflow correctness that is not captured by any
    single-step required test.
"""

import datetime

import pytest

from csms.models.resident import Resident
from csms.models.service_request import ServiceRequest
from csms.repositories.resident_repository import ResidentRepository
from csms.repositories.service_request_repository import ServiceRequestRepository
from csms.services.service_request_status_service import (
    ServiceRequestStatusService,
    StatusResult,
)
from csms.services.service_request_submission_service import (
    ServiceRequestSubmissionService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path: object) -> str:
    return str(tmp_path / "test_t10.db")  # type: ignore[operator]


@pytest.fixture()
def res_repo(db_path: str) -> ResidentRepository:
    return ResidentRepository(db_path)


@pytest.fixture()
def sr_repo(db_path: str) -> ServiceRequestRepository:
    return ServiceRequestRepository(db_path)


@pytest.fixture()
def status_service(sr_repo: ServiceRequestRepository) -> ServiceRequestStatusService:
    return ServiceRequestStatusService(sr_repo)


@pytest.fixture()
def submission_service(
    res_repo: ResidentRepository,
    sr_repo: ServiceRequestRepository,
) -> ServiceRequestSubmissionService:
    return ServiceRequestSubmissionService(res_repo, sr_repo)


TEST_DATE = datetime.date(2026, 10, 5)


def _register_active_resident(repo: ResidentRepository) -> Resident:
    r = Resident(
        first_name="Juan",
        last_name="Dela Cruz",
        address="Barangay Santo Tomas",
        contact_number="09171234567",
        email="juan@example.com",
        status="Active",
    )
    repo.save(r)
    return r


def _submit_pending_sr(
    resident: Resident,
    submission_service: ServiceRequestSubmissionService,
    **overrides: object,
) -> ServiceRequest:
    """Submit a valid Service Request and return the persisted object."""
    defaults: dict[str, object] = {
        "resident_id":    resident.id,
        "service_type":   "Barangay Clearance",
        "description":    "For employment purposes.",
        "date_requested": TEST_DATE,
    }
    defaults.update(overrides)
    sr = ServiceRequest(**defaults)  # type: ignore[arg-type]
    result = submission_service.submit(sr)
    assert result.success, "Test setup: submission should succeed"
    return result.service_request  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# TEST 1 – Pending → In Progress
# ---------------------------------------------------------------------------

def test_pending_can_move_to_in_progress(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)

    result = status_service.change_status(sr.id, "In Progress")  # type: ignore[arg-type]

    assert isinstance(result, StatusResult)
    assert result.success is True
    assert result.not_found is False
    assert result.invalid_transition is False
    stored = sr_repo.find_by_id(sr.id)  # type: ignore[arg-type]
    assert stored is not None
    assert stored.status == "In Progress"


# ---------------------------------------------------------------------------
# TEST 2 – Pending → Cancelled
# ---------------------------------------------------------------------------

def test_pending_can_move_to_cancelled(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)

    result = status_service.change_status(sr.id, "Cancelled")  # type: ignore[arg-type]

    assert result.success is True
    assert sr_repo.find_by_id(sr.id).status == "Cancelled"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# TEST 3 – In Progress → Completed
# ---------------------------------------------------------------------------

def test_in_progress_can_move_to_completed(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)
    # Advance to In Progress using the legitimate workflow.
    status_service.change_status(sr.id, "In Progress")  # type: ignore[arg-type]

    result = status_service.change_status(sr.id, "Completed")  # type: ignore[arg-type]

    assert result.success is True
    assert sr_repo.find_by_id(sr.id).status == "Completed"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# TEST 4 – In Progress → Cancelled
# ---------------------------------------------------------------------------

def test_in_progress_can_move_to_cancelled(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)
    status_service.change_status(sr.id, "In Progress")  # type: ignore[arg-type]

    result = status_service.change_status(sr.id, "Cancelled")  # type: ignore[arg-type]

    assert result.success is True
    assert sr_repo.find_by_id(sr.id).status == "Cancelled"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# TEST 5 – Pending cannot jump directly to Completed
# ---------------------------------------------------------------------------

def test_pending_cannot_move_directly_to_completed(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)

    result = status_service.change_status(sr.id, "Completed")  # type: ignore[arg-type]

    assert result.success is False
    assert result.invalid_transition is True
    assert sr_repo.find_by_id(sr.id).status == "Pending"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# TEST 6 – In Progress cannot return to Pending
# ---------------------------------------------------------------------------

def test_in_progress_cannot_return_to_pending(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)
    status_service.change_status(sr.id, "In Progress")  # type: ignore[arg-type]

    result = status_service.change_status(sr.id, "Pending")  # type: ignore[arg-type]

    assert result.success is False
    assert result.invalid_transition is True
    assert sr_repo.find_by_id(sr.id).status == "In Progress"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# TEST 7 – Completed is terminal
# ---------------------------------------------------------------------------

def test_completed_is_terminal(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)
    status_service.change_status(sr.id, "In Progress")  # type: ignore[arg-type]
    status_service.change_status(sr.id, "Completed")  # type: ignore[arg-type]

    # Attempt every possible transition out of Completed.
    for target in ("Pending", "In Progress", "Cancelled", "Completed"):
        result = status_service.change_status(sr.id, target)  # type: ignore[arg-type]
        assert result.success is False, f"Completed → {target} should be rejected"
        assert sr_repo.find_by_id(sr.id).status == "Completed"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# TEST 8 – Cancelled is terminal
# ---------------------------------------------------------------------------

def test_cancelled_is_terminal(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)
    status_service.change_status(sr.id, "Cancelled")  # type: ignore[arg-type]

    for target in ("Pending", "In Progress", "Completed", "Cancelled"):
        result = status_service.change_status(sr.id, target)  # type: ignore[arg-type]
        assert result.success is False, f"Cancelled → {target} should be rejected"
        assert sr_repo.find_by_id(sr.id).status == "Cancelled"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# TEST 9 – Unsupported status is rejected
# ---------------------------------------------------------------------------

def test_unsupported_status_is_rejected(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)

    result = status_service.change_status(sr.id, "Approved")  # type: ignore[arg-type]

    assert result.success is False
    assert result.unsupported_status is True
    assert result.invalid_transition is False
    assert sr_repo.find_by_id(sr.id).status == "Pending"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# TEST 10 – Nonexistent Service Request is handled safely
# ---------------------------------------------------------------------------

def test_nonexistent_service_request_is_handled_safely(
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    result = status_service.change_status(99999, "In Progress")

    assert result.success is False
    assert result.not_found is True
    assert sr_repo.find_by_id(99999) is None
    assert sr_repo.find_by_id(1) is None  # no record was created


# ---------------------------------------------------------------------------
# TEST 11 – Successful transition preserves all other fields
# ---------------------------------------------------------------------------

def test_successful_transition_preserves_service_request_information(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(
        resident,
        submission_service,
        service_type="Certificate Request",
        description="School enrollment requirement.",
        date_requested=datetime.date(2026, 10, 1),
    )
    original_id = sr.id

    result = status_service.change_status(sr.id, "In Progress")  # type: ignore[arg-type]
    assert result.success is True

    stored = sr_repo.find_by_id(original_id)  # type: ignore[arg-type]
    assert stored is not None
    assert stored.id             == original_id
    assert stored.resident_id    == resident.id
    assert stored.service_type   == "Certificate Request"
    assert stored.description    == "School enrollment requirement."
    assert stored.date_requested == datetime.date(2026, 10, 1)
    assert stored.status         == "In Progress"


# ---------------------------------------------------------------------------
# TEST 12 – Invalid transition does not modify persistence
# ---------------------------------------------------------------------------

def test_invalid_transition_does_not_modify_persistence(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)

    # Attempt invalid Pending → Completed.
    result = status_service.change_status(sr.id, "Completed")  # type: ignore[arg-type]
    assert result.success is False

    stored = sr_repo.find_by_id(sr.id)  # type: ignore[arg-type]
    assert stored is not None
    assert stored.status         == "Pending"
    assert stored.id             == sr.id
    assert stored.resident_id    == sr.resident_id
    assert stored.service_type   == sr.service_type
    assert stored.description    == sr.description
    assert stored.date_requested == sr.date_requested


# ---------------------------------------------------------------------------
# TEST 13 – Same-status request is rejected
# ---------------------------------------------------------------------------

def test_same_status_request_is_rejected(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)

    # Pending → Pending must be rejected.
    result = status_service.change_status(sr.id, "Pending")  # type: ignore[arg-type]

    assert result.success is False
    assert result.invalid_transition is True
    assert sr_repo.find_by_id(sr.id).status == "Pending"  # type: ignore[union-attr]

    # Also verify In Progress → In Progress.
    status_service.change_status(sr.id, "In Progress")  # type: ignore[arg-type]
    result2 = status_service.change_status(sr.id, "In Progress")  # type: ignore[arg-type]
    assert result2.success is False
    assert result2.invalid_transition is True


# ---------------------------------------------------------------------------
# TEST 14 (Student-Designed) – Sequential valid transitions work correctly
#
# What it verifies:
#   A Service Request can progress through its complete valid lifecycle in
#   order: Pending → In Progress → Completed.  Each intermediate state is
#   verified in persistence before the next transition is attempted.
#
# Why I added this test:
#   The thirteen required tests each verify a single transition in isolation.
#   This test confirms that the transition table works correctly when
#   transitions are applied *sequentially* on the same persisted record —
#   a realistic workflow scenario that could expose bugs in how the service
#   reads the *current persisted status* rather than a cached in-memory copy.
# ---------------------------------------------------------------------------

def test_sequential_valid_transitions_work_correctly(
    res_repo: ResidentRepository,
    submission_service: ServiceRequestSubmissionService,
    status_service: ServiceRequestStatusService,
    sr_repo: ServiceRequestRepository,
) -> None:
    """Full lifecycle: Pending → In Progress → Completed via sequential calls."""
    resident = _register_active_resident(res_repo)
    sr = _submit_pending_sr(resident, submission_service)

    # Step 1: Pending → In Progress
    r1 = status_service.change_status(sr.id, "In Progress")  # type: ignore[arg-type]
    assert r1.success is True
    assert sr_repo.find_by_id(sr.id).status == "In Progress"  # type: ignore[union-attr]

    # Step 2: In Progress → Completed
    r2 = status_service.change_status(sr.id, "Completed")  # type: ignore[arg-type]
    assert r2.success is True
    assert sr_repo.find_by_id(sr.id).status == "Completed"  # type: ignore[union-attr]

    # Step 3: Completed is terminal — no further transitions allowed
    for target in ("Pending", "In Progress", "Cancelled", "Completed"):
        r3 = status_service.change_status(sr.id, target)  # type: ignore[arg-type]
        assert r3.success is False
        assert sr_repo.find_by_id(sr.id).status == "Completed"  # type: ignore[union-attr]

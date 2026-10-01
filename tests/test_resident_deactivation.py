"""Automated tests for Resident deactivation (T07).

These tests verify that :class:`~csms.services.resident_deactivation_service.ResidentDeactivationService`
correctly implements soft deactivation of an existing Resident.

Every test uses a fresh SQLite database through the ``db_path`` fixture so
tests are fully isolated.

Test inventory
--------------
 1. test_active_resident_can_be_deactivated           – deactivation reports success.
 2. test_resident_status_becomes_inactive_in_persistence – status written to DB.
 3. test_resident_id_is_preserved                     – id unchanged after deactivation.
 4. test_resident_information_is_preserved            – all non-status fields unchanged.
 5. test_deactivated_resident_remains_retrievable     – T03 find-by-id still works.
 6. test_deactivated_resident_available_through_t05   – T05 search still finds it.
 7. test_already_inactive_resident_is_handled_safely  – repeated call is idempotent.
 8. test_nonexistent_resident_is_handled_safely       – unknown id → not_found.
 9. test_nonexistent_deactivation_does_not_change_records – no insert/delete on miss.
10. test_deactivating_one_resident_does_not_affect_another – other Residents unchanged.
"""

import pytest

from csms.models.resident import Resident
from csms.repositories.resident_repository import ResidentRepository
from csms.services.resident_deactivation_service import (
    DeactivationResult,
    ResidentDeactivationService,
)
from csms.services.resident_query_service import ResidentQueryService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path: object) -> str:
    """Fresh SQLite database file for one test."""
    return str(tmp_path / "test_t07.db")  # type: ignore[operator]


@pytest.fixture()
def repo(db_path: str) -> ResidentRepository:
    return ResidentRepository(db_path)


@pytest.fixture()
def service(repo: ResidentRepository) -> ResidentDeactivationService:
    return ResidentDeactivationService(repo)


def _register(repo: ResidentRepository, **kwargs: object) -> Resident:
    """Create and persist a Resident, returning it with its assigned id."""
    defaults: dict[str, object] = {
        "first_name": "Juan",
        "last_name": "Dela Cruz",
        "address": "Barangay Santo Tomas",
        "contact_number": "09171234567",
        "email": "juan@example.com",
        "status": "Active",
    }
    defaults.update(kwargs)
    r = Resident(**defaults)  # type: ignore[arg-type]
    repo.save(r)
    return r


# ---------------------------------------------------------------------------
# TEST 1 – Active Resident Can Be Deactivated
# ---------------------------------------------------------------------------

def test_active_resident_can_be_deactivated(
    repo: ResidentRepository,
    service: ResidentDeactivationService,
) -> None:
    """Deactivating an Active Resident must report success."""
    resident = _register(repo, status="Active")

    result = service.deactivate(resident.id)  # type: ignore[arg-type]

    assert isinstance(result, DeactivationResult)
    assert result.success is True
    assert result.not_found is False
    assert result.already_inactive is False
    assert result.resident is not None


# ---------------------------------------------------------------------------
# TEST 2 – Resident Status Becomes Inactive in Persistence
# ---------------------------------------------------------------------------

def test_resident_status_becomes_inactive_in_persistence(
    repo: ResidentRepository,
    service: ResidentDeactivationService,
) -> None:
    """After deactivation the status must be 'Inactive' in the database."""
    resident = _register(repo, status="Active")

    service.deactivate(resident.id)  # type: ignore[arg-type]

    # Re-fetch directly from persistence to confirm the write.
    stored = repo.find_by_id(resident.id)  # type: ignore[arg-type]
    assert stored is not None
    assert stored.status == "Inactive"


# ---------------------------------------------------------------------------
# TEST 3 – Resident ID Is Preserved
# ---------------------------------------------------------------------------

def test_resident_id_is_preserved(
    repo: ResidentRepository,
    service: ResidentDeactivationService,
) -> None:
    """The Resident's id must be the same before and after deactivation."""
    resident = _register(repo)
    original_id = resident.id

    result = service.deactivate(original_id)  # type: ignore[arg-type]

    assert result.success is True
    assert result.resident is not None
    assert result.resident.id == original_id

    stored = repo.find_by_id(original_id)  # type: ignore[arg-type]
    assert stored is not None
    assert stored.id == original_id


# ---------------------------------------------------------------------------
# TEST 4 – Resident Information Is Preserved
# ---------------------------------------------------------------------------

def test_resident_information_is_preserved(
    repo: ResidentRepository,
    service: ResidentDeactivationService,
) -> None:
    """T07 must change only status; all other fields must remain unchanged."""
    resident = _register(
        repo,
        first_name="Maria",
        last_name="Santos",
        address="456 Mabini Street",
        contact_number="09181234567",
        email="maria.santos@example.com",
        status="Active",
    )

    service.deactivate(resident.id)  # type: ignore[arg-type]

    stored = repo.find_by_id(resident.id)  # type: ignore[arg-type]
    assert stored is not None
    assert stored.first_name     == "Maria"
    assert stored.last_name      == "Santos"
    assert stored.address        == "456 Mabini Street"
    assert stored.contact_number == "09181234567"
    assert stored.contact_number.startswith("0")   # leading zero preserved
    assert isinstance(stored.contact_number, str)
    assert stored.email          == "maria.santos@example.com"
    assert stored.status         == "Inactive"


# ---------------------------------------------------------------------------
# TEST 5 – Deactivated Resident Remains Persisted and Retrievable
# ---------------------------------------------------------------------------

def test_deactivated_resident_remains_retrievable(
    repo: ResidentRepository,
    service: ResidentDeactivationService,
) -> None:
    """T07 is soft deactivation — the Resident must still exist in persistence."""
    resident = _register(repo)

    service.deactivate(resident.id)  # type: ignore[arg-type]

    # The Resident must still be findable by its original id.
    stored = repo.find_by_id(resident.id)  # type: ignore[arg-type]
    assert stored is not None          # not deleted
    assert stored.id     == resident.id
    assert stored.status == "Inactive"


# ---------------------------------------------------------------------------
# TEST 6 – Deactivated Resident Available Through T05
# ---------------------------------------------------------------------------

def test_deactivated_resident_available_through_t05(
    repo: ResidentRepository,
    service: ResidentDeactivationService,
) -> None:
    """T05 must still return the Resident after deactivation (status=Inactive)."""
    resident = _register(repo, first_name="Pedro", last_name="Reyes")

    service.deactivate(resident.id)  # type: ignore[arg-type]

    query_service = ResidentQueryService(repo)

    # T05 listing must include the deactivated Resident.
    all_residents = query_service.list_residents()
    ids = [r.id for r in all_residents]
    assert resident.id in ids

    # T05 search must also find it.
    search_results = query_service.search_residents("Pedro")
    found = [r for r in search_results if r.id == resident.id]
    assert len(found) == 1
    assert found[0].status == "Inactive"


# ---------------------------------------------------------------------------
# TEST 7 – Already-Inactive Resident Is Handled Safely
# ---------------------------------------------------------------------------

def test_already_inactive_resident_is_handled_safely(
    repo: ResidentRepository,
    service: ResidentDeactivationService,
) -> None:
    """Deactivating an already-Inactive Resident must succeed without changes."""
    resident = _register(repo, status="Inactive")
    original_id = resident.id

    result = service.deactivate(original_id)  # type: ignore[arg-type]

    assert result.success         is True
    assert result.already_inactive is True
    assert result.not_found       is False
    assert result.resident        is not None

    # id and status must be unchanged.
    stored = repo.find_by_id(original_id)  # type: ignore[arg-type]
    assert stored is not None
    assert stored.id     == original_id
    assert stored.status == "Inactive"

    # No new record was created — there is exactly one Resident.
    assert len(repo.find_all()) == 1


# ---------------------------------------------------------------------------
# TEST 8 – Nonexistent Resident Is Handled Safely
# ---------------------------------------------------------------------------

def test_nonexistent_resident_is_handled_safely(
    service: ResidentDeactivationService,
) -> None:
    """Deactivating an unknown id must return not_found without crashing."""
    result = service.deactivate(99999)

    assert result.success   is False
    assert result.not_found is True
    assert result.resident  is None


# ---------------------------------------------------------------------------
# TEST 9 – Nonexistent Deactivation Does Not Create or Delete Records
# ---------------------------------------------------------------------------

def test_nonexistent_deactivation_does_not_change_records(
    repo: ResidentRepository,
    service: ResidentDeactivationService,
) -> None:
    """A not-found deactivation attempt must leave the database unchanged."""
    # Persist one Resident so we can verify it survives untouched.
    existing = _register(repo, first_name="Ana")

    service.deactivate(99999)  # unknown id

    all_residents = repo.find_all()
    assert len(all_residents) == 1
    assert all_residents[0].id         == existing.id
    assert all_residents[0].first_name == "Ana"
    assert all_residents[0].status     == "Active"


# ---------------------------------------------------------------------------
# TEST 10 – Deactivating One Resident Does Not Affect Another
# ---------------------------------------------------------------------------

def test_deactivating_one_resident_does_not_affect_another(
    repo: ResidentRepository,
    service: ResidentDeactivationService,
) -> None:
    """Only the targeted Resident must become Inactive; others stay Active."""
    r1 = _register(repo, first_name="Ana",   email="ana@example.com",
                   contact_number="09171234567")
    r2 = _register(repo, first_name="Pedro", email="pedro@example.com",
                   contact_number="09981234567")
    r3 = _register(repo, first_name="Maria", email="maria@example.com",
                   contact_number="09081234567")

    # Deactivate only r2.
    result = service.deactivate(r2.id)  # type: ignore[arg-type]
    assert result.success is True

    stored_r1 = repo.find_by_id(r1.id)  # type: ignore[arg-type]
    stored_r2 = repo.find_by_id(r2.id)  # type: ignore[arg-type]
    stored_r3 = repo.find_by_id(r3.id)  # type: ignore[arg-type]

    assert stored_r1 is not None and stored_r1.status == "Active"
    assert stored_r2 is not None and stored_r2.status == "Inactive"
    assert stored_r3 is not None and stored_r3.status == "Active"

    # Other Residents' information must also be unchanged.
    assert stored_r1.first_name == "Ana"
    assert stored_r3.first_name == "Maria"

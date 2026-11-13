"""Automated tests for Resident information update (T06).

These tests verify that :class:`~csms.services.resident_update_service.ResidentUpdateService`
correctly coordinates lookup, validation, and persistence when updating an
existing Resident's permitted information.

Every test receives a fresh SQLite database through the ``db_path`` fixture
so tests are fully isolated.

Test inventory
--------------
 1. test_valid_resident_update_succeeds           – valid update reports success.
 2. test_resident_id_is_preserved                 – id unchanged after update.
 3. test_permitted_information_is_persisted       – all 5 editable fields saved.
 4. test_resident_status_is_preserved             – status (Active/Inactive) unchanged.
 5. test_invalid_update_fails                     – invalid info rejected (validation).
 6. test_invalid_update_does_not_modify_persisted – stored data unchanged after fail.
 7. test_updating_nonexistent_resident_is_safe    – unknown id → not_found result.
 8. test_nonexistent_update_does_not_create       – no new row created on unknown id.
 9. test_updated_resident_visible_through_t05     – T05 search reflects update.
10. test_updated_information_and_contact_preserved – leading zero + all fields + id/status.
"""

import pytest

from csms.models.resident import Resident
from csms.repositories.resident_repository import ResidentRepository
from csms.services.resident_query_service import ResidentQueryService
from csms.services.resident_update_service import UpdateResult, ResidentUpdateService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path: object) -> str:
    """Fresh SQLite database file for one test."""
    return str(tmp_path / "test_t06.db")  # type: ignore[operator]


@pytest.fixture()
def repo(db_path: str) -> ResidentRepository:
    return ResidentRepository(db_path)


@pytest.fixture()
def service(repo: ResidentRepository) -> ResidentUpdateService:
    return ResidentUpdateService(repo)


def _register(repo: ResidentRepository, **kwargs: object) -> Resident:
    """Helper: create and persist a Resident, returning it with its assigned id."""
    defaults: dict[str, object] = {
        "first_name": "Juan",
        "last_name": "Dela Cruz",
        "address": "Barangay Santo Tomas",
        "contact_number": "09171234567",
        "email": "juan@example.com",
        "status": "Active",
    }
    defaults.update(kwargs)
    resident = Resident(**defaults)  # type: ignore[arg-type]
    repo.save(resident)
    return resident


def _do_update(service: ResidentUpdateService, resident: Resident, **overrides: str) -> UpdateResult:
    """Helper: call service.update() with a resident's id and optional field overrides."""
    fields: dict[str, str] = {
        "first_name":     resident.first_name,
        "last_name":      resident.last_name,
        "address":        resident.address,
        "contact_number": resident.contact_number,
        "email":          resident.email,
    }
    fields.update(overrides)
    return service.update(
        resident_id=resident.id,  # type: ignore[arg-type]
        first_name=fields["first_name"],
        last_name=fields["last_name"],
        address=fields["address"],
        contact_number=fields["contact_number"],
        email=fields["email"],
    )


# ---------------------------------------------------------------------------
# TEST 1 – Valid Resident Update Succeeds
# ---------------------------------------------------------------------------

def test_valid_resident_update_succeeds(
    repo: ResidentRepository,
    service: ResidentUpdateService,
) -> None:
    """An update containing valid information must report success."""
    resident = _register(repo)

    result = _do_update(service, resident, first_name="Juan Miguel")

    assert isinstance(result, UpdateResult)
    assert result.success is True
    assert result.not_found is False
    assert result.errors == []
    assert result.resident is not None


# ---------------------------------------------------------------------------
# TEST 2 – Resident ID Is Preserved
# ---------------------------------------------------------------------------

def test_resident_id_is_preserved(
    repo: ResidentRepository,
    service: ResidentUpdateService,
) -> None:
    """The Resident's id must remain the same after a successful update."""
    resident = _register(repo)
    original_id = resident.id

    result = _do_update(service, resident, first_name="Miguel", last_name="Santos")

    assert result.success is True
    assert result.resident is not None
    assert result.resident.id == original_id


# ---------------------------------------------------------------------------
# TEST 3 – Permitted Resident Information Is Persisted
# ---------------------------------------------------------------------------

def test_permitted_information_is_persisted(
    repo: ResidentRepository,
    service: ResidentUpdateService,
) -> None:
    """All five permitted fields must be written to the database."""
    resident = _register(repo)

    result = service.update(
        resident_id=resident.id,  # type: ignore[arg-type]
        first_name="Maria",
        last_name="Santos",
        address="456 Mabini Street",
        contact_number="09981234567",
        email="maria.santos@example.com",
    )

    assert result.success is True

    # Re-retrieve from persistence to confirm the write landed.
    retrieved = repo.find_by_id(resident.id)  # type: ignore[arg-type]
    assert retrieved is not None
    assert retrieved.first_name    == "Maria"
    assert retrieved.last_name     == "Santos"
    assert retrieved.address       == "456 Mabini Street"
    assert retrieved.contact_number == "09981234567"
    assert retrieved.email         == "maria.santos@example.com"


# ---------------------------------------------------------------------------
# TEST 4 – Resident Status Is Preserved
# ---------------------------------------------------------------------------

def test_resident_status_is_preserved(
    repo: ResidentRepository,
    service: ResidentUpdateService,
) -> None:
    """T06 must not change status — both Active and Inactive must be preserved."""
    active   = _register(repo, status="Active")
    inactive = _register(repo, status="Inactive",
                         email="inactive@example.com",
                         contact_number="09081234567")

    _do_update(service, active,   first_name="Updated Active")
    _do_update(service, inactive, first_name="Updated Inactive")

    assert repo.find_by_id(active.id).status   == "Active"    # type: ignore[union-attr]
    assert repo.find_by_id(inactive.id).status == "Inactive"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# TEST 5 – Invalid Update Fails
# ---------------------------------------------------------------------------

def test_invalid_update_fails(
    repo: ResidentRepository,
    service: ResidentUpdateService,
) -> None:
    """An update with invalid information (empty first name) must fail."""
    resident = _register(repo)

    result = _do_update(service, resident, first_name="")

    assert result.success is False
    assert result.not_found is False
    assert len(result.errors) > 0
    assert result.resident is None


# ---------------------------------------------------------------------------
# TEST 6 – Invalid Update Does Not Modify Persisted Information
# ---------------------------------------------------------------------------

def test_invalid_update_does_not_modify_persisted_information(
    repo: ResidentRepository,
    service: ResidentUpdateService,
) -> None:
    """After a failed update the stored Resident must be exactly as before."""
    resident = _register(repo, first_name="Juan", contact_number="09171234567")

    # Attempt an update that is invalid (bad contact number).
    _do_update(service, resident,
               first_name="Miguel",
               contact_number="INVALID")

    # Re-retrieve and confirm the original values are unchanged.
    stored = repo.find_by_id(resident.id)  # type: ignore[arg-type]
    assert stored is not None
    assert stored.first_name    == "Juan"
    assert stored.contact_number == "09171234567"


# ---------------------------------------------------------------------------
# TEST 7 – Updating a Nonexistent Resident Is Handled Safely
# ---------------------------------------------------------------------------

def test_updating_nonexistent_resident_is_handled_safely(
    service: ResidentUpdateService,
) -> None:
    """An update request for an unknown id must return not_found, not crash."""
    result = service.update(
        resident_id=99999,
        first_name="Ghost",
        last_name="Resident",
        address="Nowhere",
        contact_number="09171234567",
        email="ghost@example.com",
    )

    assert result.success   is False
    assert result.not_found is True
    assert result.errors    == []
    assert result.resident  is None


# ---------------------------------------------------------------------------
# TEST 8 – Nonexistent Update Does Not Create a Resident
# ---------------------------------------------------------------------------

def test_nonexistent_update_does_not_create_a_resident(
    repo: ResidentRepository,
    service: ResidentUpdateService,
) -> None:
    """No new row must be created when the requested id does not exist."""
    # Confirm starting state: zero Residents.
    assert repo.find_all() == []

    service.update(
        resident_id=99999,
        first_name="Ghost",
        last_name="Resident",
        address="Nowhere",
        contact_number="09171234567",
        email="ghost@example.com",
    )

    # Confirm still zero Residents after the attempted update.
    assert repo.find_all() == []


# ---------------------------------------------------------------------------
# TEST 9 – Updated Resident Is Visible Through T05 Querying
# ---------------------------------------------------------------------------

def test_updated_resident_visible_through_t05_querying(
    repo: ResidentRepository,
    service: ResidentUpdateService,
) -> None:
    """After a successful update the T05 search must return the new values."""
    resident = _register(repo, first_name="Juan", last_name="Cruz")

    result = _do_update(service, resident,
                        first_name="Miguel",
                        last_name="Santos")
    assert result.success is True

    query_service = ResidentQueryService(repo)

    # Old name must NOT match.
    old_results = query_service.search_residents("Cruz")
    assert not any(r.id == resident.id for r in old_results)

    # New name MUST match.
    new_results = query_service.search_residents("Santos")
    assert any(r.id == resident.id and r.first_name == "Miguel" for r in new_results)


# ---------------------------------------------------------------------------
# TEST 10 – Updated Information and Contact Number Are Preserved
# ---------------------------------------------------------------------------

def test_updated_information_and_contact_number_are_preserved(
    repo: ResidentRepository,
    service: ResidentUpdateService,
) -> None:
    """All permitted fields, leading zero, original id, and status must survive."""
    resident = _register(repo, status="Active")
    original_id = resident.id

    result = service.update(
        resident_id=original_id,  # type: ignore[arg-type]
        first_name="Pedro",
        last_name="Reyes",
        address="789 Bonifacio Ave",
        contact_number="09181234567",
        email="pedro.reyes@example.com",
    )

    assert result.success is True

    retrieved = repo.find_by_id(original_id)  # type: ignore[arg-type]
    assert retrieved is not None
    # Permitted fields updated.
    assert retrieved.first_name     == "Pedro"
    assert retrieved.last_name      == "Reyes"
    assert retrieved.address        == "789 Bonifacio Ave"
    assert retrieved.contact_number == "09181234567"
    assert retrieved.email          == "pedro.reyes@example.com"
    # Leading zero preserved.
    assert retrieved.contact_number.startswith("0")
    assert isinstance(retrieved.contact_number, str)
    # Identity and status unchanged.
    assert retrieved.id     == original_id
    assert retrieved.status == "Active"

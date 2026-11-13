"""Automated tests for Resident registration (T04).

These tests verify that :class:`~csms.services.resident_service.ResidentRegistrationService`
correctly coordinates the T02 validator and the T03 repository to implement
the complete Resident registration operation.

Every test receives a fresh SQLite database through the ``db_path`` fixture
so tests are fully isolated from each other and from the development database.

Test inventory
--------------
1. test_register_a_valid_resident                  – Valid Resident registers successfully.
2. test_registered_resident_receives_an_identifier – Registered Resident gets a DB-assigned id.
3. test_registered_resident_is_persisted           – Registered Resident exists in the repository.
4. test_registered_resident_information_is_preserved – All fields survive registration + retrieval.
5. test_default_active_status_is_preserved         – Default Active status survives.
6. test_invalid_resident_registration_fails        – Invalid Resident registration is rejected.
7. test_invalid_resident_is_not_persisted          – Invalid Resident is never saved to the DB.
8. test_validation_failure_can_be_identified       – Errors identify the failing field.
"""

import pytest

from csms.models.resident import Resident
from csms.repositories.resident_repository import ResidentRepository
from csms.services.resident_service import RegistrationResult, ResidentRegistrationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path: object) -> str:
    """Return a path to a fresh, empty SQLite database file for one test."""
    return str(tmp_path / "test_t04.db")  # type: ignore[operator]


@pytest.fixture()
def repo(db_path: str) -> ResidentRepository:
    """Return a ResidentRepository backed by the per-test database."""
    return ResidentRepository(db_path)


@pytest.fixture()
def service(repo: ResidentRepository) -> ResidentRegistrationService:
    """Return a ResidentRegistrationService wired to the per-test repository."""
    return ResidentRegistrationService(repo)


def make_resident(**overrides: object) -> Resident:
    """Build an unsaved Resident with valid defaults.

    ``id`` is left at ``None`` (its T01 default) to represent an unsaved
    Resident whose identifier will be assigned by the persistence layer.
    """
    values: dict[str, object] = {
        "first_name": "Juan",
        "last_name": "Dela Cruz",
        "address": "Barangay Santo Tomas",
        "contact_number": "09171234567",
        "email": "juan@example.com",
        "status": "Active",
    }
    values.update(overrides)
    return Resident(**values)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TEST 1 – Register a Valid Resident
# ---------------------------------------------------------------------------

def test_register_a_valid_resident(service: ResidentRegistrationService) -> None:
    """Registration of a valid Resident must succeed."""
    resident = make_resident()

    result = service.register(resident)

    assert isinstance(result, RegistrationResult)
    assert result.success is True
    assert result.errors == []


# ---------------------------------------------------------------------------
# TEST 2 – Registered Resident Receives an Identifier
# ---------------------------------------------------------------------------

def test_registered_resident_receives_an_identifier(
    service: ResidentRegistrationService,
) -> None:
    """After successful registration the Resident has a DB-assigned integer id.

    The id must not be None and must not have been manually hard-coded; it
    comes from SQLite AUTOINCREMENT via the T03 repository.
    """
    resident = make_resident()
    assert resident.id is None  # starts without an id

    result = service.register(resident)

    assert result.success is True
    assert result.resident is not None
    assert result.resident.id is not None
    assert isinstance(result.resident.id, int)


# ---------------------------------------------------------------------------
# TEST 3 – Registered Resident Is Persisted
# ---------------------------------------------------------------------------

def test_registered_resident_is_persisted(
    service: ResidentRegistrationService,
    repo: ResidentRepository,
) -> None:
    """A successfully registered Resident must actually exist in the repository.

    This verifies that registration is not merely an in-memory operation:
    the Resident can be retrieved by id from the T03 persistence layer after
    registration.
    """
    resident = make_resident()
    result = service.register(resident)

    assert result.success is True
    retrieved = repo.find_by_id(result.resident.id)  # type: ignore[union-attr]

    assert retrieved is not None
    assert retrieved.id == result.resident.id


# ---------------------------------------------------------------------------
# TEST 4 – Registered Resident Information Is Preserved
# ---------------------------------------------------------------------------

def test_registered_resident_information_is_preserved(
    service: ResidentRegistrationService,
    repo: ResidentRepository,
) -> None:
    """All Resident fields survive the register-and-retrieve round-trip intact."""
    resident = make_resident(
        first_name="Maria",
        last_name="Santos",
        address="123 Rizal Street",
        contact_number="09981234567",
        email="maria.santos@example.com",
        status="Active",
    )

    result = service.register(resident)
    assert result.success is True

    retrieved = repo.find_by_id(result.resident.id)  # type: ignore[union-attr]
    assert retrieved is not None
    assert retrieved.first_name == "Maria"
    assert retrieved.last_name == "Santos"
    assert retrieved.address == "123 Rizal Street"
    assert retrieved.contact_number == "09981234567"
    assert retrieved.email == "maria.santos@example.com"
    assert retrieved.status == "Active"


# ---------------------------------------------------------------------------
# TEST 5 – Default Active Status Is Preserved
# ---------------------------------------------------------------------------

def test_default_active_status_is_preserved(
    service: ResidentRegistrationService,
    repo: ResidentRepository,
) -> None:
    """A Resident created with the T01 default status registers and remains Active."""
    # Do not supply status — rely on the T01 default.
    resident = Resident(
        first_name="Pedro",
        last_name="Reyes",
        address="Barangay San Jose",
        contact_number="09081234567",
        email="pedro.reyes@example.com",
    )
    assert resident.status == "Active"  # T01 default confirmed

    result = service.register(resident)
    assert result.success is True

    retrieved = repo.find_by_id(result.resident.id)  # type: ignore[union-attr]
    assert retrieved is not None
    assert retrieved.status == "Active"


# ---------------------------------------------------------------------------
# TEST 6 – Invalid Resident Registration Fails
# ---------------------------------------------------------------------------

def test_invalid_resident_registration_fails(
    service: ResidentRegistrationService,
) -> None:
    """Registration of a Resident with invalid information must be rejected."""
    # Violate T02 rule: first_name is empty.
    invalid = make_resident(first_name="")

    result = service.register(invalid)

    assert result.success is False
    assert result.resident is None


# ---------------------------------------------------------------------------
# TEST 7 – Invalid Resident Is Not Persisted
# ---------------------------------------------------------------------------

def test_invalid_resident_is_not_persisted(
    service: ResidentRegistrationService,
    repo: ResidentRepository,
) -> None:
    """After a failed registration attempt no Resident record must exist in the DB.

    This confirms that the service validates *before* calling the repository —
    invalid data is never written to the database.
    """
    invalid = make_resident(contact_number="not-a-valid-number")

    result = service.register(invalid)
    assert result.success is False

    # id was never assigned because the repository was never called.
    assert invalid.id is None

    # Verify nothing was actually written by checking a made-up id.
    assert repo.find_by_id(1) is None


# ---------------------------------------------------------------------------
# TEST 8 – Validation Failure Can Be Identified
# ---------------------------------------------------------------------------

def test_validation_failure_can_be_identified(
    service: ResidentRegistrationService,
) -> None:
    """When registration fails the result must identify the failing validation rule.

    The errors list must be non-empty so the caller knows what went wrong.
    When first_name is empty the error message must mention the first name
    field so callers can identify it.
    """
    invalid = make_resident(first_name="")

    result = service.register(invalid)

    assert result.success is False
    assert len(result.errors) > 0
    # At least one error must mention "first name" (case-insensitive) so the
    # caller can identify which field failed.
    first_name_errors = [
        e for e in result.errors if "first name" in e.lower()
    ]
    assert len(first_name_errors) > 0

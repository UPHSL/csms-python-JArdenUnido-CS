"""Automated tests for Resident search and listing (T05).

These tests verify that :class:`~csms.services.resident_query_service.ResidentQueryService`
and the extended :class:`~csms.repositories.resident_repository.ResidentRepository`
correctly implement listing and name-search operations over real SQLite
persistence.

Every test receives a fresh database through the ``db_path`` fixture so
tests are fully isolated from each other.

Test inventory
--------------
 1. test_list_all_persisted_residents         – all saved Residents are returned.
 2. test_empty_listing                        – empty DB returns empty list, not None.
 3. test_listing_uses_required_ordering       – order is last→first→id, not insertion order.
 4. test_partial_first_name_search_is_case_insensitive  – "jUa" matches "Juan".
 5. test_partial_last_name_search_is_case_insensitive   – "cRuZ" matches "Dela Cruz".
 6. test_blank_search_returns_all_residents   – "   " behaves like list_residents().
 7. test_search_with_no_match_returns_empty   – unknown term → empty list, no error.
 8. test_search_results_preserve_information  – all fields including leading zero survive.
 9. test_active_and_inactive_residents_included – status filter is NOT applied.
10. test_matching_resident_is_not_duplicated  – term matching both names → one result.
"""

import pytest

from csms.models.resident import Resident
from csms.repositories.resident_repository import ResidentRepository
from csms.services.resident_query_service import ResidentQueryService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path: object) -> str:
    """Fresh SQLite database file for one test."""
    return str(tmp_path / "test_t05.db")  # type: ignore[operator]


@pytest.fixture()
def repo(db_path: str) -> ResidentRepository:
    return ResidentRepository(db_path)


@pytest.fixture()
def service(repo: ResidentRepository) -> ResidentQueryService:
    return ResidentQueryService(repo)


def _save(repo: ResidentRepository, **kwargs: object) -> Resident:
    """Helper: create and persist a Resident with sensible defaults."""
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
# TEST 1 – List All Persisted Residents
# ---------------------------------------------------------------------------

def test_list_all_persisted_residents(
    repo: ResidentRepository,
    service: ResidentQueryService,
) -> None:
    """All saved Residents must appear in the listing result."""
    _save(repo, first_name="Juan", last_name="Cruz")
    _save(repo, first_name="Maria", last_name="Santos")
    _save(repo, first_name="Pedro", last_name="Reyes")

    result = service.list_residents()

    assert len(result) == 3
    last_names = {r.last_name for r in result}
    assert last_names == {"Cruz", "Santos", "Reyes"}


# ---------------------------------------------------------------------------
# TEST 2 – Empty Resident Listing
# ---------------------------------------------------------------------------

def test_empty_listing(service: ResidentQueryService) -> None:
    """An empty database must return an empty list, never None."""
    result = service.list_residents()

    assert result == []
    assert result is not None


# ---------------------------------------------------------------------------
# TEST 3 – Resident Listing Uses Required Ordering
# ---------------------------------------------------------------------------

def test_listing_uses_required_ordering(
    repo: ResidentRepository,
    service: ResidentQueryService,
) -> None:
    """Results must be ordered last_name ASC → first_name ASC → id ASC,
    regardless of insertion order.

    Inserted in this order:  Santos/Ana, Cruz/Pedro, Andres/Maria, Cruz/Juan.
    Expected result order:   Andres/Maria, Cruz/Juan, Cruz/Pedro, Santos/Ana.
    """
    _save(repo, first_name="Ana",   last_name="Santos")
    _save(repo, first_name="Pedro", last_name="Cruz")
    _save(repo, first_name="Maria", last_name="Andres")
    _save(repo, first_name="Juan",  last_name="Cruz")

    result = service.list_residents()

    assert len(result) == 4
    assert result[0].last_name == "Andres" and result[0].first_name == "Maria"
    assert result[1].last_name == "Cruz"   and result[1].first_name == "Juan"
    assert result[2].last_name == "Cruz"   and result[2].first_name == "Pedro"
    assert result[3].last_name == "Santos" and result[3].first_name == "Ana"


# ---------------------------------------------------------------------------
# TEST 4 – Partial First Name Search Is Case-Insensitive
# ---------------------------------------------------------------------------

def test_partial_first_name_search_is_case_insensitive(
    repo: ResidentRepository,
    service: ResidentQueryService,
) -> None:
    """Searching 'jUa' must match a Resident with first_name='Juan'."""
    _save(repo, first_name="Juan", last_name="Dela Cruz")

    result = service.search_residents("jUa")

    assert len(result) == 1
    assert result[0].first_name == "Juan"


# ---------------------------------------------------------------------------
# TEST 5 – Partial Last Name Search Is Case-Insensitive
# ---------------------------------------------------------------------------

def test_partial_last_name_search_is_case_insensitive(
    repo: ResidentRepository,
    service: ResidentQueryService,
) -> None:
    """Searching 'cRuZ' must match a Resident with last_name='Dela Cruz'."""
    _save(repo, first_name="Juan", last_name="Dela Cruz")

    result = service.search_residents("cRuZ")

    assert len(result) == 1
    assert result[0].last_name == "Dela Cruz"


# ---------------------------------------------------------------------------
# TEST 6 – Blank Search Returns All Residents
# ---------------------------------------------------------------------------

def test_blank_search_returns_all_residents(
    repo: ResidentRepository,
    service: ResidentQueryService,
) -> None:
    """A whitespace-only search term must behave exactly like list_residents()."""
    _save(repo, first_name="Ana",   last_name="Santos")
    _save(repo, first_name="Pedro", last_name="Reyes")

    blank_result = service.search_residents("   ")
    list_result  = service.list_residents()

    assert len(blank_result) == len(list_result) == 2
    assert [r.id for r in blank_result] == [r.id for r in list_result]


# ---------------------------------------------------------------------------
# TEST 7 – Search With No Match Returns Empty Collection
# ---------------------------------------------------------------------------

def test_search_with_no_match_returns_empty(
    service: ResidentQueryService,
) -> None:
    """A term that matches nothing must return an empty list without errors."""
    result = service.search_residents("ZzzUnknownResident")

    assert result == []
    assert result is not None


# ---------------------------------------------------------------------------
# TEST 8 – Search Results Preserve Resident Information
# ---------------------------------------------------------------------------

def test_search_results_preserve_information(
    repo: ResidentRepository,
    service: ResidentQueryService,
) -> None:
    """Every field, including the contact-number leading zero, must survive."""
    _save(
        repo,
        first_name="Maria",
        last_name="Santos",
        address="123 Rizal Street",
        contact_number="09981234567",
        email="maria.santos@example.com",
        status="Active",
    )

    result = service.search_residents("Maria")

    assert len(result) == 1
    r = result[0]
    assert r.first_name == "Maria"
    assert r.last_name == "Santos"
    assert r.address == "123 Rizal Street"
    assert r.contact_number == "09981234567"
    assert r.contact_number.startswith("0")   # leading zero preserved
    assert isinstance(r.contact_number, str)
    assert r.email == "maria.santos@example.com"
    assert r.status == "Active"
    assert r.id is not None


# ---------------------------------------------------------------------------
# TEST 9 – Active and Inactive Residents Are Both Included
# ---------------------------------------------------------------------------

def test_active_and_inactive_residents_included(
    repo: ResidentRepository,
    service: ResidentQueryService,
) -> None:
    """T05 must not apply a status filter — both Active and Inactive are returned."""
    _save(repo, first_name="Ana",   last_name="Active",   status="Active")
    _save(repo, first_name="Pedro", last_name="Inactive", status="Inactive")

    result = service.list_residents()

    statuses = {r.status for r in result}
    assert "Active"   in statuses
    assert "Inactive" in statuses
    assert len(result) == 2


# ---------------------------------------------------------------------------
# TEST 10 – Matching Resident Is Not Duplicated
# ---------------------------------------------------------------------------

def test_matching_resident_is_not_duplicated(
    repo: ResidentRepository,
    service: ResidentQueryService,
) -> None:
    """A Resident whose first AND last name both match the term must appear once.

    For example, if first_name='Cruz' and last_name='Cruz', searching for
    'Cruz' must return that Resident exactly once because the SQL uses OR
    inside a single WHERE clause, not a UNION, so no duplicate rows arise.
    """
    _save(repo, first_name="Cruz", last_name="Cruz")

    result = service.search_residents("Cruz")

    assert len(result) == 1
    assert result[0].first_name == "Cruz"
    assert result[0].last_name  == "Cruz"

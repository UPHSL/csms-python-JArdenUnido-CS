"""Tests for the Service Request domain model (T08).

These tests verify that :class:`~csms.models.service_request.ServiceRequest`
correctly represents Service Request information without requiring any
database, validation, or persistence.

Test inventory
--------------
1. test_service_request_can_be_created          – object constructs without error.
2. test_service_request_information_is_accessible – all supplied fields readable.
3. test_resident_id_is_preserved               – resident_id stores exact value.
4. test_new_service_request_has_unassigned_id  – id defaults to None.
5. test_new_service_request_defaults_to_pending – status defaults to "Pending".
6. test_service_request_information_is_independent – two objects don't share data.
"""

import datetime

from csms.models.service_request import ServiceRequest


# ---------------------------------------------------------------------------
# Shared test data helpers
# ---------------------------------------------------------------------------

TEST_DATE = datetime.date(2026, 9, 27)


def make_service_request(**overrides: object) -> ServiceRequest:
    """Build a ServiceRequest with sensible defaults, allowing field overrides."""
    defaults: dict[str, object] = {
        "resident_id":    25,
        "service_type":   "Barangay Clearance",
        "description":    "Request for employment requirement.",
        "date_requested": TEST_DATE,
    }
    defaults.update(overrides)
    return ServiceRequest(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TEST 1 – Service Request Can Be Created
# ---------------------------------------------------------------------------

def test_service_request_can_be_created() -> None:
    """A ServiceRequest must be constructible from its required fields."""
    sr = make_service_request()

    assert isinstance(sr, ServiceRequest)


# ---------------------------------------------------------------------------
# TEST 2 – Service Request Information Is Accessible
# ---------------------------------------------------------------------------

def test_service_request_information_is_accessible() -> None:
    """All supplied field values must be readable from the object."""
    sr = make_service_request(
        resident_id=25,
        service_type="Barangay Clearance",
        description="Request for employment requirement.",
        date_requested=TEST_DATE,
    )

    assert sr.resident_id    == 25
    assert sr.service_type   == "Barangay Clearance"
    assert sr.description    == "Request for employment requirement."
    assert sr.date_requested == TEST_DATE


# ---------------------------------------------------------------------------
# TEST 3 – Resident ID Is Preserved
# ---------------------------------------------------------------------------

def test_resident_id_is_preserved() -> None:
    """The Service Request must store the exact Resident ID supplied."""
    sr = make_service_request(resident_id=25)

    assert sr.resident_id == 25


# ---------------------------------------------------------------------------
# TEST 4 – New Service Request Has an Unassigned ID
# ---------------------------------------------------------------------------

def test_new_service_request_has_unassigned_id() -> None:
    """Before persistence, a new Service Request must have id = None."""
    sr = make_service_request()

    assert sr.id is None


# ---------------------------------------------------------------------------
# TEST 5 – New Service Request Defaults to Pending
# ---------------------------------------------------------------------------

def test_new_service_request_defaults_to_pending() -> None:
    """A Service Request created without an explicit status must be 'Pending'."""
    sr = make_service_request()

    assert sr.status == "Pending"


# ---------------------------------------------------------------------------
# TEST 6 – Service Request Information Is Independent Between Objects
# ---------------------------------------------------------------------------

def test_service_request_information_is_independent() -> None:
    """Two distinct Service Request objects must not share field values."""
    sr1 = make_service_request(
        resident_id=10,
        service_type="Barangay Clearance",
        description="First request.",
        date_requested=datetime.date(2026, 9, 1),
    )
    sr2 = make_service_request(
        resident_id=20,
        service_type="Certificate Request",
        description="Second request.",
        date_requested=datetime.date(2026, 9, 15),
    )

    # Each object must carry only its own values.
    assert sr1.resident_id    == 10
    assert sr1.service_type   == "Barangay Clearance"
    assert sr1.description    == "First request."
    assert sr1.date_requested == datetime.date(2026, 9, 1)

    assert sr2.resident_id    == 20
    assert sr2.service_type   == "Certificate Request"
    assert sr2.description    == "Second request."
    assert sr2.date_requested == datetime.date(2026, 9, 15)

    # Verify the objects do not reference the same data inadvertently.
    assert sr1.resident_id  != sr2.resident_id
    assert sr1.service_type != sr2.service_type

"""Tests for the Resident domain model."""

from csms.models.resident import Resident


def test_resident_creation():
    """Verify that a Resident can be created with valid information."""
    resident = Resident(
        id=1,
        first_name="Juan",
        last_name="Dela Cruz",
        address="123 Main Street",
        contact_number="09171234567",
        email="juan.delacruz@example.com",
        status="Active",
    )

    assert isinstance(resident, Resident)


def test_resident_information_access():
    """Verify that Resident information can be assigned and retrieved."""
    resident = Resident(
        id=1,
        first_name="Juan",
        last_name="Dela Cruz",
        address="123 Main Street",
        contact_number="09171234567",
        email="juan.delacruz@example.com",
        status="Active",
    )

    assert resident.id == 1
    assert resident.first_name == "Juan"
    assert resident.last_name == "Dela Cruz"
    assert resident.address == "123 Main Street"
    assert resident.contact_number == "09171234567"
    assert resident.email == "juan.delacruz@example.com"


def test_resident_status():
    """Verify that a Resident can represent Active status."""
    resident = Resident(
        id=1,
        first_name="Juan",
        last_name="Dela Cruz",
        address="123 Main Street",
        contact_number="09171234567",
        email="juan.delacruz@example.com",
        status="Active",
    )

    assert resident.status == "Active"
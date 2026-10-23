"""Tests for Resident information validation (T02).

These tests exercise the validation rules without any database persistence,
building directly on the T01 Resident domain model.
"""

import pytest

from csms.models.resident import Resident
from csms.utils.validators import ValidationResult, validate_resident


def make_resident(**overrides: object) -> Resident:
    """Build a Resident with valid defaults, overriding specific fields."""
    values: dict[str, object] = {
        "id": 1,
        "first_name": "Juan",
        "last_name": "Dela Cruz",
        "address": "Barangay Santo Tomas",
        "contact_number": "09171234567",
        "email": "juan@example.com",
        "status": "Active",
    }
    values.update(overrides)
    return Resident(**values)  # type: ignore[arg-type]


# TEST 1 - VALID RESIDENT
def test_valid_resident_passes_validation() -> None:
    """Valid Resident information should pass validation."""
    resident = make_resident()

    result = validate_resident(resident)

    assert isinstance(result, ValidationResult)
    assert result.is_valid
    assert result.errors == []


# TEST 2 - MISSING FIRST NAME
def test_missing_first_name_is_rejected() -> None:
    """An empty first name should be rejected."""
    result = validate_resident(make_resident(first_name=""))

    assert not result.is_valid


# TEST 3 - MISSING LAST NAME
def test_missing_last_name_is_rejected() -> None:
    """An empty last name should be rejected."""
    result = validate_resident(make_resident(last_name=""))

    assert not result.is_valid


# TEST 4 - MISSING ADDRESS
def test_missing_address_is_rejected() -> None:
    """An empty address should be rejected."""
    result = validate_resident(make_resident(address=""))

    assert not result.is_valid


# TEST 5 - WHITESPACE-ONLY REQUIRED INFORMATION
def test_whitespace_only_first_name_is_rejected() -> None:
    """A whitespace-only required value must not count as valid information."""
    result = validate_resident(make_resident(first_name="   "))

    assert not result.is_valid


def test_whitespace_only_last_name_is_rejected() -> None:
    """A whitespace-only last name must be rejected."""
    result = validate_resident(make_resident(last_name="     "))

    assert not result.is_valid


def test_whitespace_only_address_is_rejected() -> None:
    """A whitespace-only address must be rejected."""
    result = validate_resident(make_resident(address="   "))

    assert not result.is_valid


# TEST 6 - INVALID CONTACT NUMBER
@pytest.mark.parametrize(
    "contact_number",
    [
        "9171234567",  # missing leading zero / too short
        "0917123456",  # only 10 characters
        "091712345678",  # 12 characters
        "0917ABC4567",  # contains letters
        "08171234567",  # does not start with 09
        "0917 1234567",  # contains a space
    ],
)
def test_invalid_contact_number_is_rejected(contact_number: str) -> None:
    """Contact numbers that break the 09XXXXXXXXX format are rejected."""
    result = validate_resident(make_resident(contact_number=contact_number))

    assert not result.is_valid


@pytest.mark.parametrize(
    "contact_number",
    ["09171234567", "09981234567", "09081234567"],
)
def test_valid_contact_number_is_accepted(contact_number: str) -> None:
    """Well-formed 11-digit contact numbers are accepted."""
    result = validate_resident(make_resident(contact_number=contact_number))

    assert result.is_valid


# TEST 7 - INVALID EMAIL
def test_invalid_email_is_rejected() -> None:
    """An address without an @ separator is rejected."""
    result = validate_resident(make_resident(email="juan.example.com"))

    assert not result.is_valid


@pytest.mark.parametrize(
    "email",
    [
        "juan",
        "juan@",
        "@example.com",
        "juan.example.com",
        "juan@example",
        "juan@@example.com",
        "",
    ],
)
def test_various_invalid_emails_are_rejected(email: str) -> None:
    """A range of malformed email addresses are rejected."""
    result = validate_resident(make_resident(email=email))

    assert not result.is_valid


@pytest.mark.parametrize(
    "email",
    [
        "juan@example.com",
        "maria.santos@example.com",
        "student@uphsl.edu.ph",
    ],
)
def test_basic_valid_emails_are_accepted(email: str) -> None:
    """Basic, well-formed email addresses are accepted."""
    result = validate_resident(make_resident(email=email))

    assert result.is_valid


# TEST 8 - SUPPORTED STATUS
@pytest.mark.parametrize("status", ["Active", "Inactive"])
def test_supported_status_is_accepted(status: str) -> None:
    """Both Active and Inactive are supported statuses."""
    result = validate_resident(make_resident(status=status))

    assert result.is_valid


# TEST 9 - UNSUPPORTED STATUS
@pytest.mark.parametrize("status", ["Unknown", "Deleted", "Pending", "Disabled"])
def test_unsupported_status_is_rejected(status: str) -> None:
    """Statuses outside the supported set are rejected."""
    result = validate_resident(make_resident(status=status))

    assert not result.is_valid


# T01 REGRESSION - default Active status still validates.
def test_default_status_is_active_and_valid() -> None:
    """A Resident created without a status defaults to Active and is valid."""
    resident = Resident(
        id=2,
        first_name="Maria",
        last_name="Santos",
        address="Barangay San Jose",
        contact_number="09981234567",
        email="maria.santos@example.com",
    )

    assert resident.status == "Active"
    assert validate_resident(resident).is_valid

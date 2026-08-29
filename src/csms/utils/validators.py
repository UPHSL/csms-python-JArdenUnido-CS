"""Resident information validation (T02).

This module validates the information held by a :class:`~csms.models.resident.Resident`
before it is used by other parts of the Community Services Management System.

Validation lives in the utility/application layer so that it is kept separate from
the UI/presentation layer and works purely in memory, without any database
persistence. It does not modify or normalize the values it inspects; it only
reports whether the information is valid.
"""

from dataclasses import dataclass, field

from csms.models.resident import Resident

# The Resident status values supported in T02.
VALID_STATUSES: tuple[str, ...] = ("Active", "Inactive")

# A valid contact number is exactly 11 characters: "09" followed by 9 digits.
CONTACT_NUMBER_LENGTH = 11


@dataclass
class ValidationResult:
    """The outcome of validating Resident information.

    Attributes:
        errors: Human-readable messages describing each validation failure.
            An empty list means the information is valid.
    """

    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return ``True`` when no validation errors were recorded."""
        return not self.errors

    def add_error(self, message: str) -> None:
        """Record a single validation failure."""
        self.errors.append(message)


def _is_blank(value: object) -> bool:
    """Return ``True`` when ``value`` is missing, empty, or whitespace only."""
    return not isinstance(value, str) or value.strip() == ""


def is_valid_required_text(value: object) -> bool:
    """Return ``True`` when a required text field contains real content.

    A required text value must be provided, must not be empty, and must not
    consist only of whitespace.
    """
    return not _is_blank(value)


def is_valid_contact_number(value: object) -> bool:
    """Return ``True`` when ``value`` is a valid ``09XXXXXXXXX`` contact number.

    The contact number is treated as text (not a number) so the leading zero is
    preserved. It must be exactly 11 characters, begin with ``09``, and contain
    digits only.
    """
    if not isinstance(value, str):
        return False
    if len(value) != CONTACT_NUMBER_LENGTH:
        return False
    if not value.startswith("09"):
        return False
    return value.isdigit()


def is_valid_email(value: object) -> bool:
    """Return ``True`` for a basic, valid email address.

    This is intentionally simple (not RFC-compliant). The value must contain
    exactly one ``@`` with text on both sides, and the domain part must contain a
    dot with text before and after it.
    """
    if not isinstance(value, str) or value == "":
        return False

    if value.count("@") != 1:
        return False

    local_part, domain_part = value.split("@")
    if local_part == "" or domain_part == "":
        return False

    if "." not in domain_part:
        return False

    domain_name, _, domain_suffix = domain_part.rpartition(".")
    return domain_name != "" and domain_suffix != ""


def is_valid_status(value: object) -> bool:
    """Return ``True`` when ``value`` is a supported Resident status."""
    return value in VALID_STATUSES


def validate_resident(resident: Resident) -> ValidationResult:
    """Validate the information held by a :class:`Resident`.

    Args:
        resident: The Resident whose information should be checked.

    Returns:
        A :class:`ValidationResult`. ``result.is_valid`` is ``True`` when every
        field is valid; otherwise ``result.errors`` explains each problem.
    """
    result = ValidationResult()

    if not is_valid_required_text(resident.first_name):
        result.add_error("First name is required.")

    if not is_valid_required_text(resident.last_name):
        result.add_error("Last name is required.")

    if not is_valid_required_text(resident.address):
        result.add_error("Address is required.")

    if not is_valid_contact_number(resident.contact_number):
        result.add_error(
            "Contact number must be 11 digits in the format 09XXXXXXXXX."
        )

    if not is_valid_email(resident.email):
        result.add_error("Email must be a valid address, for example name@example.com.")

    if not is_valid_status(resident.status):
        supported = ", ".join(VALID_STATUSES)
        result.add_error(f"Status must be one of: {supported}.")

    return result

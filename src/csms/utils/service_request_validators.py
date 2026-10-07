"""Service Request information validation (T09).

This module validates the intrinsic information held by a
:class:`~csms.models.service_request.ServiceRequest` before it is submitted
for persistence.

Intrinsic validation means checking the Service Request's own fields.

This validator does NOT:

* Query the Resident database to verify that ``resident_id`` exists.
* Check whether the referenced Resident is Active or Inactive.

Those cross-domain checks are the responsibility of the submission service
(:mod:`csms.services.service_request_submission_service`).  Keeping database
queries out of this validator preserves the separation of concerns.

Validation rules
----------------
1. ``id`` must be unassigned (``None``) — a new submission cannot already have
   a persisted ID.
2. ``resident_id`` must be a positive integer — structural check only.
3. ``service_type`` must be present and not whitespace-only.
4. ``description`` must be present and not whitespace-only.
5. ``date_requested`` must be a :class:`datetime.date` instance — confirms that
   a valid date was supplied.
6. ``status`` must be ``'Pending'`` — a new submission must start in the
   initial lifecycle state.
"""

import datetime
from dataclasses import dataclass, field

from csms.models.service_request import ServiceRequest


@dataclass
class ServiceRequestValidationResult:
    """The outcome of validating a :class:`ServiceRequest`.

    Attributes:
        errors: Human-readable messages for each validation failure.  An
            empty list means every rule passed.
    """

    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return ``True`` when no validation errors were recorded."""
        return not self.errors

    def add_error(self, message: str) -> None:
        """Record a single validation failure."""
        self.errors.append(message)


def validate_service_request(
    sr: ServiceRequest,
) -> ServiceRequestValidationResult:
    """Validate the intrinsic information of a :class:`ServiceRequest`.

    This function checks the Service Request's own fields only — it does
    not perform any database queries.

    Args:
        sr: The :class:`ServiceRequest` to validate.

    Returns:
        A :class:`ServiceRequestValidationResult`.  ``result.is_valid`` is
        ``True`` when every rule passes; otherwise ``result.errors`` lists
        the problems.
    """
    result = ServiceRequestValidationResult()

    # Rule 1: id must be unassigned.
    if sr.id is not None:
        result.add_error(
            "Service Request id must be unassigned for a new submission."
        )

    # Rule 2: resident_id must be a positive integer.
    if not isinstance(sr.resident_id, int) or sr.resident_id <= 0:
        result.add_error(
            "resident_id must be a positive integer identifying a Resident."
        )

    # Rule 3: service_type is required and must not be whitespace-only.
    if not isinstance(sr.service_type, str) or sr.service_type.strip() == "":
        result.add_error("service_type is required and cannot be blank.")

    # Rule 4: description is required and must not be whitespace-only.
    if not isinstance(sr.description, str) or sr.description.strip() == "":
        result.add_error("description is required and cannot be blank.")

    # Rule 5: date_requested must be a datetime.date.
    if not isinstance(sr.date_requested, datetime.date):
        result.add_error(
            "date_requested must be a valid date (datetime.date)."
        )

    # Rule 6: status must be Pending for a new submission.
    if sr.status != "Pending":
        result.add_error(
            "A new Service Request must have status 'Pending'."
        )

    return result

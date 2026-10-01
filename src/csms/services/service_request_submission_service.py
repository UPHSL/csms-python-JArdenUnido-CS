"""Service Request submission service (T09).

This module provides :class:`ServiceRequestSubmissionService`, the
application-level component that coordinates the complete Service Request
submission workflow.

The workflow, in order:

1. **Validate** — call :func:`~csms.utils.service_request_validators.validate_service_request`
   on the incoming Service Request.  No database access at this stage.
2. **Reject invalid** — if validation fails, return a failure result with
   the validation errors.  Persistence is never called.
3. **Resident lookup** — use the existing T03
   :class:`~csms.repositories.resident_repository.ResidentRepository` to
   find the Resident identified by ``resident_id``.
4. **Resident-not-found guard** — if no Resident exists for that ID, return
   a not-found result.
5. **Active-status check** — if the Resident's status is not ``'Active'``,
   return an Inactive-resident result.
6. **Persist** — call :meth:`~csms.repositories.service_request_repository.ServiceRequestRepository.save`
   to INSERT the Service Request and obtain its database-generated ``id``.
7. **Return** — return a success result carrying the persisted Service Request.

What this service intentionally does NOT do:

* Duplicate T09 validator rules.
* Write SQL directly.
* Generate Service Request IDs.
* Modify the Resident.
* Implement Service Request status transitions (T10).
* Handle search, listing, updates, or deletion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from csms.models.service_request import ServiceRequest
from csms.repositories.resident_repository import ResidentRepository
from csms.repositories.service_request_repository import ServiceRequestRepository
from csms.utils.service_request_validators import validate_service_request


@dataclass
class SubmissionResult:
    """The outcome of a Service Request submission attempt.

    Exactly one of the four semantic states below applies:

    * **Success**: ``success=True``, ``service_request`` set, no errors,
      ``resident_not_found=False``, ``resident_inactive=False``.
    * **Validation failure**: ``success=False``, ``errors`` non-empty.
    * **Resident not found**: ``success=False``, ``resident_not_found=True``.
    * **Resident inactive**: ``success=False``, ``resident_inactive=True``.

    Attributes:
        success:            ``True`` when the request passed all checks and
                            was persisted.
        service_request:    The persisted :class:`ServiceRequest` (with its
                            generated ``id``) on success; ``None`` otherwise.
        errors:             Validation-failure messages; populated only when a
                            validation rule failed.
        resident_not_found: ``True`` when the ``resident_id`` does not match
                            any persisted Resident.
        resident_inactive:  ``True`` when the referenced Resident exists but
                            has ``status = 'Inactive'``.
    """

    success: bool
    service_request: ServiceRequest | None = None
    errors: list[str] = field(default_factory=list)
    resident_not_found: bool = False
    resident_inactive: bool = False


class ServiceRequestSubmissionService:
    """Coordinate Service Request validation, eligibility check, and persistence.

    Args:
        resident_repository: Used to verify the referenced Resident's
            existence and Active status.
        service_request_repository: Used to persist the Service Request and
            retrieve it after a successful save.
    """

    def __init__(
        self,
        resident_repository: ResidentRepository,
        service_request_repository: ServiceRequestRepository,
    ) -> None:
        self._resident_repo = resident_repository
        self._sr_repo = service_request_repository

    def submit(self, service_request: ServiceRequest) -> SubmissionResult:
        """Attempt to submit and persist a new Service Request.

        Args:
            service_request: The :class:`ServiceRequest` to submit.  Its
                ``id`` must be ``None`` and its ``status`` must be
                ``'Pending'`` (these are validated in step 1).

        Returns:
            A :class:`SubmissionResult` that clearly distinguishes success,
            validation failure, Resident-not-found, and Resident-inactive
            outcomes.
        """
        # Step 1 & 2: intrinsic validation — no DB access.
        validation = validate_service_request(service_request)
        if not validation.is_valid:
            return SubmissionResult(success=False, errors=validation.errors)

        # Step 3 & 4: verify the Resident exists.
        resident = self._resident_repo.find_by_id(service_request.resident_id)
        if resident is None:
            return SubmissionResult(
                success=False,
                resident_not_found=True,
            )

        # Step 5: verify the Resident is Active.
        if resident.status != "Active":
            return SubmissionResult(
                success=False,
                resident_inactive=True,
            )

        # Step 6 & 7: persist and return.
        persisted = self._sr_repo.save(service_request)
        return SubmissionResult(
            success=True,
            service_request=persisted,
        )

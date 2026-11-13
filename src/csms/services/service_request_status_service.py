"""Service Request status-management service (T10).

This module provides :class:`ServiceRequestStatusService`, the
application-level component that enforces the controlled Service Request
processing lifecycle.

Supported statuses
------------------
* ``Pending``     — initial state after submission (T09)
* ``In Progress`` — request is being processed
* ``Completed``   — request has been fulfilled (terminal)
* ``Cancelled``   — request has been cancelled (terminal)

Allowed transitions
-------------------
+------------------+-----------------------+
| Current status   | Allowed next statuses |
+==================+=======================+
| Pending          | In Progress, Cancelled|
+------------------+-----------------------+
| In Progress      | Completed, Cancelled  |
+------------------+-----------------------+
| Completed        | (none — terminal)     |
+------------------+-----------------------+
| Cancelled        | (none — terminal)     |
+------------------+-----------------------+

Any transition not listed above is rejected — including requests to move to
the *same* status, requests to use an unsupported status string, and attempts
to transition out of a terminal state.

What this service intentionally does NOT do:

* It does not write SQL directly — that is the repository's responsibility.
* It does not modify the Resident or any other entity.
* It does not create new Service Requests.
* It does not implement search, listing, or any T11 features.
* It does not render pages or handle HTTP requests.
"""

from __future__ import annotations

from dataclasses import dataclass

from csms.models.service_request import ServiceRequest
from csms.repositories.service_request_repository import ServiceRequestRepository

# The complete set of status values recognised by T10.
SUPPORTED_STATUSES: frozenset[str] = frozenset(
    {"Pending", "In Progress", "Completed", "Cancelled"}
)

# Maps each current status to the set of statuses it may transition TO.
# A status absent from the map (or with an empty set) is terminal.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "Pending":     frozenset({"In Progress", "Cancelled"}),
    "In Progress": frozenset({"Completed",   "Cancelled"}),
    "Completed":   frozenset(),   # terminal
    "Cancelled":   frozenset(),   # terminal
}


@dataclass
class StatusResult:
    """The outcome of a Service Request status-management operation.

    Exactly one of the four semantic states below applies:

    * **Success**: ``success=True``, ``service_request`` carries the updated
      Resident with its new ``status``.
    * **Not found**: ``success=False``, ``not_found=True``.
    * **Unsupported status**: ``success=False``, ``unsupported_status=True``.
    * **Invalid transition**: ``success=False``, ``invalid_transition=True``.

    Attributes:
        success:            ``True`` when the transition was valid and
                            persisted.
        service_request:    The updated :class:`ServiceRequest` on success;
                            ``None`` otherwise.
        not_found:          ``True`` when no Service Request exists for the
                            requested ID.
        unsupported_status: ``True`` when the requested target status is not
                            one of the four recognised values.
        invalid_transition: ``True`` when both statuses are recognised but
                            the transition from the current status to the
                            requested status is not allowed (including
                            same-status requests).
    """

    success: bool
    service_request: ServiceRequest | None = None
    not_found: bool = False
    unsupported_status: bool = False
    invalid_transition: bool = False


class ServiceRequestStatusService:
    """Enforce the controlled Service Request status lifecycle.

    This service reuses the T09
    :class:`~csms.repositories.service_request_repository.ServiceRequestRepository`
    for both lookup and the status-update persistence operation.

    Args:
        repository: The :class:`ServiceRequestRepository` used to retrieve
            and update Service Request records.
    """

    def __init__(self, repository: ServiceRequestRepository) -> None:
        self._repository = repository

    def change_status(
        self, sr_id: int, requested_status: str
    ) -> StatusResult:
        """Attempt to transition an existing Service Request to a new status.

        The operation performs the following checks **before** modifying
        persistence:

        1. **Lookup** — retrieve the existing Service Request.
        2. **Not-found guard** — stop if the Service Request does not exist.
        3. **Supported-status check** — stop if ``requested_status`` is not
           one of ``Pending``, ``In Progress``, ``Completed``, ``Cancelled``.
        4. **Transition-rules check** — stop if the move from the current
           status to ``requested_status`` is not in :data:`ALLOWED_TRANSITIONS`
           (this also catches same-status requests, since a status is not in
           its own allowed-next set).
        5. **Persist** — call
           :meth:`~csms.repositories.service_request_repository.ServiceRequestRepository.update_status`
           with a parameterised UPDATE targeting only the correct row.
        6. **Re-fetch and return** — retrieve the updated Service Request from
           persistence and return it in a success result.

        Args:
            sr_id:            The persisted ID of the Service Request.
            requested_status: The desired new status.

        Returns:
            A :class:`StatusResult` that clearly distinguishes success,
            not-found, unsupported-status, and invalid-transition outcomes.
        """
        # Step 1 & 2: lookup + not-found guard.
        existing = self._repository.find_by_id(sr_id)
        if existing is None:
            return StatusResult(success=False, not_found=True)

        # Step 3: supported-status check.
        if requested_status not in SUPPORTED_STATUSES:
            return StatusResult(success=False, unsupported_status=True)

        # Step 4: transition-rules check (also catches same-status requests).
        allowed_next = ALLOWED_TRANSITIONS.get(existing.status, frozenset())
        if requested_status not in allowed_next:
            return StatusResult(success=False, invalid_transition=True)

        # Step 5: persist the change.
        self._repository.update_status(sr_id, requested_status)

        # Step 6: re-fetch and return the authoritative persisted state.
        updated = self._repository.find_by_id(sr_id)
        return StatusResult(success=True, service_request=updated)

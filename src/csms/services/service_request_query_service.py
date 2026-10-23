"""Service Request query service (T11).

This module provides :class:`ServiceRequestQueryService`, the application-level
component that coordinates read/query operations over persisted Service Requests.

Responsibilities (T11 scope only):

* **list_service_requests** — return all persisted Service Requests in the
  required deterministic order (``date_requested DESC, id DESC``).
* **view_service_request** — return one Service Request by its ``id``, or
  ``None`` when no record with that ID exists.
* **search_service_requests** — accept a raw search term and an optional
  status filter, normalise the term, decide whether to list-all or search,
  validate the status filter, and delegate the actual database query to the
  repository.

What this service intentionally does NOT do:

* It does not write SQL — that is the repository's responsibility.
* It does not modify any Service Request or Resident.
* It does not implement T10 status-transition logic.
* It does not paginate, sort by user-selected columns, or filter by date ranges.
* It does not render pages or handle HTTP requests.
"""

from __future__ import annotations

from csms.models.service_request import ServiceRequest
from csms.repositories.service_request_repository import ServiceRequestRepository

# The four lifecycle statuses recognised as valid filter values.
VALID_STATUS_FILTERS: frozenset[str] = frozenset(
    {"Pending", "In Progress", "Completed", "Cancelled"}
)


class ServiceRequestQueryService:
    """Coordinate read/query operations over persisted Service Requests.

    Args:
        repository: The :class:`ServiceRequestRepository` used for all
            database queries.
    """

    def __init__(self, repository: ServiceRequestRepository) -> None:
        self._repository = repository

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_service_requests(self) -> list[ServiceRequest]:
        """Return all persisted Service Requests in deterministic order.

        The ordering applied by the repository is:
        ``date_requested DESC`` → ``id DESC``.

        Returns:
            A :class:`list` of every persisted :class:`ServiceRequest`.  An
            empty list is returned when no records exist — never ``None``.
        """
        return self._repository.find_all()

    # ------------------------------------------------------------------
    # View by ID
    # ------------------------------------------------------------------

    def view_service_request(self, sr_id: int) -> ServiceRequest | None:
        """Retrieve one Service Request by its persisted identifier.

        Reuses the T09 :meth:`~csms.repositories.service_request_repository
        .ServiceRequestRepository.find_by_id` capability directly.

        Args:
            sr_id: The integer ID of the Service Request to view.

        Returns:
            The :class:`ServiceRequest` when found, or ``None`` when no
            record exists for ``sr_id``.  Does not create a new record.
        """
        return self._repository.find_by_id(sr_id)

    # ------------------------------------------------------------------
    # Search / filter
    # ------------------------------------------------------------------

    def search_service_requests(
        self,
        search_term: str,
        status_filter: str | None = None,
    ) -> list[ServiceRequest]:
        """Search Service Requests by text and/or filter by status.

        Processing steps:

        1. **Trim** the ``search_term`` to remove leading/trailing whitespace.
        2. **Blank check** — if the trimmed term is empty, treat the call as
           a full listing (call :meth:`list_service_requests` and optionally
           apply the status filter at the DB level).
        3. **Status validation** — if a non-``None`` ``status_filter`` is
           provided, verify it is one of the four supported values.  An
           unsupported value raises :class:`ValueError` so the caller can
           distinguish it from a normal empty result.
        4. **Delegate** — pass the trimmed term (in lower-case; the
           repository's ``LOWER()`` comparison handles the rest) and the
           validated ``status_filter`` to
           :meth:`~csms.repositories.service_request_repository
           .ServiceRequestRepository.search`.

        Non-blank searching is performed through the persistence layer —
        no ``find_all()`` + in-memory filtering.

        Args:
            search_term:   Raw text entered by the caller.  May include
                           leading/trailing spaces; may be blank.
            status_filter: One of ``"Pending"``, ``"In Progress"``,
                           ``"Completed"``, ``"Cancelled"``; or ``None``
                           to include all statuses.

        Returns:
            A :class:`list` of matching :class:`ServiceRequest` objects in
            the required order.  An empty list when nothing matches.

        Raises:
            ValueError: When ``status_filter`` is a non-empty string that is
                        not one of the four supported status values.
        """
        # Step 1: normalise the search term.
        trimmed = search_term.strip()

        # Step 3: validate the status filter (done before the query).
        if status_filter is not None and status_filter not in VALID_STATUS_FILTERS:
            raise ValueError(
                f"Unsupported status filter: '{status_filter}'. "
                f"Supported values are: {sorted(VALID_STATUS_FILTERS)}"
            )

        # Step 2: blank search → full listing (with optional status filter).
        if not trimmed:
            if status_filter is None:
                return self._repository.find_all()
            # Blank text + status filter: list all matching the status.
            return self._repository.search("", status_filter)

        # Step 4: delegate real search to the persistence layer.
        return self._repository.search(trimmed, status_filter)

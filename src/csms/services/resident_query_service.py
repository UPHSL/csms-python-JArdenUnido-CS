"""Resident query/search service (T05).

This module provides :class:`ResidentQueryService`, the application-level
component that coordinates Resident listing and name-search operations.

Responsibilities (T05 scope only):

* **list_residents** — return all persisted Residents in the required
  deterministic order by delegating to the repository.
* **search_residents** — accept a raw search term, normalise it (trim
  leading/trailing whitespace), decide whether a real search or a full
  listing is required, and delegate to the appropriate repository operation.

What this module intentionally does NOT do:

* It does not filter records in application memory — all filtering is
  performed at the database level through the repository.
* It does not modify any Resident record.
* It does not redefine Resident fields, validation rules, or persistence
  SQL — those belong to T01, T02, and T03 respectively.
* It does not render pages or handle HTTP requests — that belongs to future
  tickets.
"""

from __future__ import annotations

from csms.models.resident import Resident
from csms.repositories.resident_repository import ResidentRepository


class ResidentQueryService:
    """Coordinate Resident listing and name-search operations.

    This service is the single entry point for read/query operations on
    persisted Residents.  It reuses the existing repository (T03 + T05
    extensions) rather than duplicating persistence logic.

    Args:
        repository: A :class:`~csms.repositories.resident_repository.ResidentRepository`
            instance that the service will use to query Resident records.
    """

    def __init__(self, repository: ResidentRepository) -> None:
        self._repository = repository

    def list_residents(self) -> list[Resident]:
        """Return all persisted Residents in deterministic alphabetical order.

        The ordering applied by the repository is:
        last name → first name → id (all ascending, case-insensitive).

        Returns:
            A :class:`list` of every persisted :class:`Resident`.  An empty
            list is returned when no Residents have been registered — this
            is a normal result, not an error.
        """
        return self._repository.find_all()

    def search_residents(self, search_term: str) -> list[Resident]:
        """Search for Residents whose name contains the given term.

        Processing steps:

        1. Trim leading and trailing whitespace from ``search_term``.
        2. If the trimmed term is blank (empty string or whitespace only),
           treat the call as a request to list all Residents and return
           :meth:`list_residents`.
        3. Otherwise, delegate to the repository's case-insensitive
           partial-name search, which checks both first name and last name
           at the database level.

        The actual filtering is performed inside the database query — no
        records are loaded into memory for in-application filtering.

        Args:
            search_term: The raw text entered by a caller.  May contain
                leading/trailing spaces; may be blank.

        Returns:
            A :class:`list` of matching :class:`Resident` objects in the
            required deterministic order.  An empty list is returned when
            nothing matches — this is a normal result, not an error.
        """
        trimmed = search_term.strip()

        if not trimmed:
            return self._repository.find_all()

        return self._repository.search_by_name(trimmed)

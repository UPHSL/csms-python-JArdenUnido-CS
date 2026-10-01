"""Resident deactivation service (T07).

This module provides :class:`ResidentDeactivationService`, the application-level
component that coordinates the soft deactivation of an existing Resident.

Soft deactivation means:

* The Resident record is **kept** in persistence.
* Only the ``status`` field changes from ``'Active'`` to ``'Inactive'``.
* The Resident remains retrievable through T03 and searchable/listable
  through T05 after deactivation.

Responsibilities (T07 scope only):

* Receive the ID of the Resident to deactivate.
* Retrieve the existing Resident using the T03 repository.
* Return a not-found result when the ID does not match any persisted Resident.
* If the Resident is already ``'Inactive'``, return a safe already-inactive
  result without modifying persistence again.
* If the Resident is ``'Active'``, persist ``status = 'Inactive'`` using the
  repository and return a success result.
* Never physically delete the Resident record.
* Never change the Resident's personal or contact information.

What this module intentionally does NOT do:

* It does not implement reactivation (Inactive → Active).
* It does not implement a generic status toggle.
* It does not modify ``first_name``, ``last_name``, ``address``,
  ``contact_number``, or ``email``.
* It does not generate a new Resident ID.
* It does not use registration (T04) or general information update (T06).
* It does not re-run T02 personal-information validation (the Resident
  already exists in persistence; the question is only about status).
* It does not render pages or handle HTTP requests.
"""

from __future__ import annotations

from dataclasses import dataclass

from csms.models.resident import Resident
from csms.repositories.resident_repository import ResidentRepository


@dataclass
class DeactivationResult:
    """The outcome of a Resident deactivation attempt.

    Exactly one of the three semantic states below applies:

    * **Newly deactivated** (Active → Inactive):
      ``success=True``, ``already_inactive=False``, ``not_found=False``,
      ``resident`` carries the persisted Resident with ``status='Inactive'``.

    * **Already inactive** (Inactive, no change made):
      ``success=True``, ``already_inactive=True``, ``not_found=False``,
      ``resident`` carries the existing Inactive Resident.

    * **Resident not found**:
      ``success=False``, ``already_inactive=False``, ``not_found=True``,
      ``resident=None``.

    Attributes:
        success:          ``True`` when the Resident was found and is now
                          (or already was) Inactive.
        resident:         The :class:`Resident` carrying ``status='Inactive'``
                          for success outcomes; ``None`` for not-found.
        already_inactive: ``True`` when the Resident was already Inactive
                          and no persistence change was needed.
        not_found:        ``True`` when the supplied ID does not exist.
    """

    success: bool
    resident: Resident | None = None
    already_inactive: bool = False
    not_found: bool = False


class ResidentDeactivationService:
    """Coordinate the soft deactivation of an existing Resident.

    This service reuses the T03 repository for both lookup and the
    status-change persistence operation.  It does not call the T04
    registration service or the T06 update service.

    Args:
        repository: A :class:`~csms.repositories.resident_repository.ResidentRepository`
            used for Resident lookup and deactivation.
    """

    def __init__(self, repository: ResidentRepository) -> None:
        self._repository = repository

    def deactivate(self, resident_id: int) -> DeactivationResult:
        """Attempt to deactivate the Resident identified by ``resident_id``.

        The operation runs in this order:

        1. **Lookup** — retrieve the existing Resident by ``resident_id``.
        2. **Not-found guard** — if no Resident exists, return
           :class:`DeactivationResult` with ``not_found=True``.  Nothing is
           created or deleted.
        3. **Already-inactive check** — if the Resident's current status is
           already ``'Inactive'``, return :class:`DeactivationResult` with
           ``already_inactive=True`` and ``success=True``.  Persistence is
           not touched again.  This makes repeated deactivation idempotent.
        4. **Deactivate** — call :meth:`~csms.repositories.resident_repository
           .ResidentRepository.deactivate_by_id` to write
           ``status = 'Inactive'`` to the database.
        5. **Re-fetch** — retrieve the updated Resident from persistence to
           confirm the change and return the final persisted state.
        6. **Return** — return :class:`DeactivationResult` with
           ``success=True`` and the updated Resident.

        Args:
            resident_id: The persisted integer ID of the Resident to
                         deactivate.

        Returns:
            A :class:`DeactivationResult` that clearly distinguishes newly
            deactivated, already-inactive, and not-found outcomes.
        """
        # Step 1 & 2: lookup and not-found guard.
        existing = self._repository.find_by_id(resident_id)
        if existing is None:
            return DeactivationResult(success=False, not_found=True)

        # Step 3: already-inactive check (idempotent).
        if existing.status == "Inactive":
            return DeactivationResult(
                success=True,
                resident=existing,
                already_inactive=True,
                not_found=False,
            )

        # Step 4 & 5: persist the status change and re-fetch.
        self._repository.deactivate_by_id(resident_id)
        updated = self._repository.find_by_id(resident_id)

        # Step 6: return success with the persisted Resident.
        return DeactivationResult(
            success=True,
            resident=updated,
            already_inactive=False,
            not_found=False,
        )

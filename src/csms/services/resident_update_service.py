"""Resident update service (T06).

This module provides :class:`ResidentUpdateService`, the application-level
component that coordinates updating the permitted information of an existing
persisted Resident.

Responsibilities (T06 scope only):

* Accept a target Resident ID and the proposed new values for the editable
  fields (first name, last name, address, contact number, email).
* Look up the existing Resident through the T03 repository.
* Return a not-found result when no Resident with the given ID exists.
* Preserve the Resident's existing ID (identity) and status (unchanged by
  T06 — that belongs to T07).
* Validate the proposed information using the T02 validator.
* Return a validation-failure result — without touching persistence — when
  the proposed information is invalid.
* Persist the permitted field changes through the T03 repository.
* Return a success result carrying the updated, persisted Resident.

What this module intentionally does NOT do:

* It does not redefine Resident fields — that is T01's responsibility.
* It does not rewrite validation rules — that is T02's responsibility.
* It does not write SQL — that is T03's responsibility.
* It does not create new Residents — that is T04's responsibility.
* It does not change Resident status — that belongs to T07.
* It does not render pages or handle HTTP — that belongs to future tickets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from csms.models.resident import Resident
from csms.repositories.resident_repository import ResidentRepository
from csms.utils.validators import validate_resident


@dataclass
class UpdateResult:
    """The outcome of a Resident update attempt.

    Exactly one of the three state combinations below will be true for any
    given result, making the outcome unambiguous for the caller:

    * **Success:**
      ``success=True``, ``resident`` is set, ``errors`` is empty,
      ``not_found=False``.

    * **Validation failure:**
      ``success=False``, ``resident=None``, ``errors`` contains messages,
      ``not_found=False``.

    * **Resident not found:**
      ``success=False``, ``resident=None``, ``errors`` is empty,
      ``not_found=True``.

    Attributes:
        success:   ``True`` when the Resident was found, validated, and
                   persisted successfully.
        resident:  The updated :class:`Resident` (with the same ``id`` as
                   before) when ``success`` is ``True``, otherwise ``None``.
        errors:    Human-readable validation-failure messages, populated only
                   when a validation failure caused the update to be rejected.
        not_found: ``True`` when no Resident with the requested ID exists in
                   persistence.
    """

    success: bool
    resident: Resident | None = None
    errors: list[str] = field(default_factory=list)
    not_found: bool = False


class ResidentUpdateService:
    """Coordinate the update of an existing Resident's permitted information.

    This service is the single entry point for T06 update operations.  It
    reuses the repository (T03), the validator (T02), and the Resident model
    (T01) without duplicating any of their responsibilities.

    Args:
        repository: A :class:`~csms.repositories.resident_repository.ResidentRepository`
            instance used for both lookup and persistence of the update.
    """

    def __init__(self, repository: ResidentRepository) -> None:
        self._repository = repository

    def update(
        self,
        resident_id: int,
        first_name: str,
        last_name: str,
        address: str,
        contact_number: str,
        email: str,
    ) -> UpdateResult:
        """Attempt to update the permitted information of an existing Resident.

        The operation runs in this order:

        1. **Lookup** — retrieve the existing Resident by ``resident_id``
           using the T03 repository.
        2. **Not-found guard** — if no Resident exists for that ID, return an
           :class:`UpdateResult` with ``not_found=True`` immediately.  No new
           Resident is created.
        3. **Preserve identity and status** — build the candidate Resident
           from the proposed editable values while keeping the original
           ``id`` and ``status`` unchanged.
        4. **Validate** — call :func:`~csms.utils.validators.validate_resident`
           (T02) on the candidate.  The existing status is used, so the T02
           status rule is satisfied without the caller needing to supply it.
        5. **Reject** — if validation fails, return an :class:`UpdateResult`
           with ``success=False`` and the validation errors.  Persistence is
           never touched.
        6. **Persist** — call the repository's ``update()`` method (T06
           extension of T03) which executes a targeted ``UPDATE … WHERE id=?``
           affecting only the requested Resident.
        7. **Return** — return an :class:`UpdateResult` with ``success=True``
           and the updated Resident (same ``id``, same ``status``, new field
           values).

        Args:
            resident_id:    The persisted ID of the Resident to update.
            first_name:     Proposed new first name.
            last_name:      Proposed new last name.
            address:        Proposed new address.
            contact_number: Proposed new contact number (text, format
                            ``09XXXXXXXXX``).
            email:          Proposed new email address.

        Returns:
            An :class:`UpdateResult` that clearly distinguishes success,
            validation failure, and Resident-not-found outcomes.
        """
        # Step 1 & 2: lookup and not-found guard.
        existing = self._repository.find_by_id(resident_id)
        if existing is None:
            return UpdateResult(success=False, not_found=True)

        # Step 3: build the candidate preserving id and status.
        candidate = Resident(
            id=existing.id,
            first_name=first_name,
            last_name=last_name,
            address=address,
            contact_number=contact_number,
            email=email,
            status=existing.status,   # T06 must NOT change status
        )

        # Step 4 & 5: validate before touching persistence.
        validation = validate_resident(candidate)
        if not validation.is_valid:
            return UpdateResult(
                success=False,
                resident=None,
                errors=validation.errors,
                not_found=False,
            )

        # Step 6 & 7: persist and return.
        updated = self._repository.update(candidate)
        return UpdateResult(
            success=True,
            resident=updated,
            errors=[],
            not_found=False,
        )

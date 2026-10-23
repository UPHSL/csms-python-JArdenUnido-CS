"""Resident registration service (T04).

This module provides :class:`ResidentRegistrationService`, the application-level
component that coordinates Resident registration.

Responsibilities (T04 scope only):

* Accept a :class:`~csms.models.resident.Resident` for registration.
* Delegate validation to the T02 validator
  (:func:`~csms.utils.validators.validate_resident`).
* Stop immediately and report the validation errors when the Resident is
  invalid — the persistence layer is never called in this case.
* Delegate persistence to the T03 repository
  (:class:`~csms.repositories.resident_repository.ResidentRepository`) when
  the Resident is valid.
* Return a :class:`RegistrationResult` that clearly distinguishes a
  successful registration from a failed one.

What this module intentionally does NOT do:

* It does not redefine Resident fields — that is T01's responsibility.
* It does not rewrite validation rules — that is T02's responsibility.
* It does not write SQL or generate IDs — that is T03's responsibility.
* It does not render pages or handle HTTP requests — that belongs to future
  tickets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from csms.models.resident import Resident
from csms.repositories.resident_repository import ResidentRepository
from csms.utils.validators import validate_resident


@dataclass
class RegistrationResult:
    """The outcome of a Resident registration attempt.

    Attributes:
        success:  ``True`` when the Resident passed validation and was
            persisted successfully; ``False`` otherwise.
        resident: The persisted :class:`Resident` (with its assigned ``id``)
            when ``success`` is ``True``, or ``None`` when registration
            failed.
        errors:   A list of human-readable validation-failure messages.
            Empty when ``success`` is ``True``.  Each entry describes one
            specific problem with the Resident information, for example
            ``"First name is required."`` so that callers can identify which
            field failed.
    """

    success: bool
    resident: Resident | None = None
    errors: list[str] = field(default_factory=list)


class ResidentRegistrationService:
    """Coordinate the registration of a new Resident.

    This service is the single entry point for the registration operation.
    It reuses the existing validator (T02) and repository (T03) rather than
    duplicating their responsibilities.

    Args:
        repository: A :class:`~csms.repositories.resident_repository.ResidentRepository`
            instance that the service will use to persist valid Residents.
            The same repository — and therefore the same database — is used
            for the lifetime of this service instance.
    """

    def __init__(self, repository: ResidentRepository) -> None:
        self._repository = repository

    def register(self, resident: Resident) -> RegistrationResult:
        """Attempt to register a Resident.

        The operation runs in the following order:

        1. **Validate** — call :func:`~csms.utils.validators.validate_resident`
           on the Resident.  The T02 validation rules are applied without
           being duplicated here.
        2. **Reject** — if validation fails, return a
           :class:`RegistrationResult` with ``success=False`` and the
           validation errors populated.  The repository is *never* called in
           this case so no invalid data can reach the database.
        3. **Persist** — if validation passes, call
           :meth:`~csms.repositories.resident_repository.ResidentRepository.save`,
           which INSERTs the Resident and assigns its database-generated
           ``id``.
        4. **Return** — return a :class:`RegistrationResult` with
           ``success=True`` and the now-persisted Resident (``resident.id``
           is set).

        Args:
            resident: The :class:`Resident` to register.  Its ``id`` should
                be ``None`` before this call; the persistence layer assigns
                the identifier.

        Returns:
            A :class:`RegistrationResult` describing whether registration
            succeeded and, if not, what validation errors prevented it.
        """
        validation = validate_resident(resident)

        if not validation.is_valid:
            return RegistrationResult(
                success=False,
                resident=None,
                errors=validation.errors,
            )

        self._repository.save(resident)

        return RegistrationResult(
            success=True,
            resident=resident,
            errors=[],
        )

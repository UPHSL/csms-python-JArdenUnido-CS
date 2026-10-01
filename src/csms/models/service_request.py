"""Service Request domain model (T08).

This module defines :class:`ServiceRequest`, the domain object that
represents a request for a community service associated with a Resident.

T08 scope — this module is responsible for **representation only**:

* What information a Service Request contains.
* The default status of a newly created Service Request.

T08 intentionally does NOT include:

* Validation of field values — that belongs to T09.
* Verification that the ``resident_id`` refers to an existing Resident
  — that also belongs to T09.
* Persistence, repositories, or database interaction — that belongs to a
  future persistence ticket.
* Status transitions (Pending → In Progress → Completed/Cancelled) — those
  belong to later workflow tickets.
* Controllers, routes, or any UI concern.
"""

import datetime
from dataclasses import dataclass


@dataclass
class ServiceRequest:
    """Represent a community-service request submitted on behalf of a Resident.

    A :class:`ServiceRequest` records who made the request (``resident_id``),
    what was requested (``service_type`` and ``description``), when it was
    made (``date_requested``), and its current lifecycle stage (``status``).

    The association with a Resident is stored through ``resident_id``.  The
    Service Request does not duplicate the Resident's name, address, or other
    personal information — those values belong to the :class:`~csms.models.resident.Resident`
    domain object.

    Attributes:
        resident_id:    The integer ID of the Resident who owns this request.
                        T08 stores this reference; it does not verify that a
                        Resident with this ID actually exists (that check is
                        introduced in T09).
        service_type:   The category or type of community service requested.
                        Examples: ``"Barangay Clearance"``,
                        ``"Certificate Request"``, ``"Community Assistance"``.
                        T08 does not restrict which values are allowed.
        description:    Additional details about the request.
        date_requested: The date the request was made, represented as a
                        :class:`datetime.date`.  The caller supplies this
                        value; T08 does not automatically capture the current
                        system date.
        status:         The current lifecycle status.  Defaults to
                        ``"Pending"`` for every newly created Service Request
                        so the caller does not have to supply it explicitly.
        id:             The unique persisted identifier of this Service
                        Request.  Before persistence is established (T09+),
                        a new Service Request has ``id = None``.  The domain
                        model never generates an ID itself — that is the
                        responsibility of the persistence layer.
    """

    resident_id: int
    service_type: str
    description: str
    date_requested: datetime.date
    status: str = "Pending"
    id: int | None = None

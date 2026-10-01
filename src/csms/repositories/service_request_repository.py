"""Service Request persistence repository (T09).

This module provides :class:`ServiceRequestRepository`, responsible for
storing and retrieving :class:`~csms.models.service_request.ServiceRequest`
objects in the SQLite database.

Responsibilities (T09 scope):

* **save** — INSERT a new Service Request row and write the database-generated
  ``id`` back onto the object.  The ``date_requested`` field is stored as an
  ISO-8601 text string (``YYYY-MM-DD``) and retrieved as a
  :class:`datetime.date`.
* **find_by_id** — SELECT a Service Request row by its primary key and
  reconstruct a :class:`ServiceRequest` instance, or return ``None``.

What this repository intentionally does NOT do:

* It does not validate Service Request information — that is T09's
  :mod:`~csms.utils.service_request_validators` responsibility.
* It does not check Resident existence or status — that is the submission
  service's responsibility.
* It does not implement search, listing, update, or status transitions —
  those belong to future tickets.
* Resident personal information is not stored here; only ``resident_id``.
"""

import datetime

from csms.database import get_connection, init_db
from csms.models.service_request import ServiceRequest


class ServiceRequestRepository:
    """Store and retrieve Service Request records in the SQLite database.

    Each method opens its own connection and closes it immediately after
    the operation completes so that separate instances pointing at the same
    database file can both access persisted data.

    Args:
        database_path: Filesystem path to the SQLite database file.  The
            schema (including the ``service_requests`` table) is created
            automatically on first use via :func:`~csms.database.init_db`.
    """

    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        init_db(database_path)

    def save(self, service_request: ServiceRequest) -> ServiceRequest:
        """Persist a new Service Request and assign its database-generated id.

        ``date_requested`` is stored as an ISO-8601 string (``YYYY-MM-DD``)
        which is SQLite's recommended date representation.  It is converted
        back to :class:`datetime.date` when retrieved by :meth:`find_by_id`.

        Args:
            service_request: The :class:`ServiceRequest` to persist.
                ``service_request.id`` must be ``None`` before this call.

        Returns:
            The same :class:`ServiceRequest` object with ``id`` now set to the
            value assigned by the database.
        """
        connection = get_connection(self._database_path)
        try:
            cursor = connection.execute(
                """
                INSERT INTO service_requests
                    (resident_id, service_type, description,
                     date_requested, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    service_request.resident_id,
                    service_request.service_type,
                    service_request.description,
                    service_request.date_requested.isoformat(),
                    service_request.status,
                ),
            )
            connection.commit()
            service_request.id = cursor.lastrowid
        finally:
            connection.close()

        return service_request

    def find_by_id(self, sr_id: int) -> ServiceRequest | None:
        """Retrieve a Service Request by its primary-key identifier.

        Args:
            sr_id: The integer identifier previously assigned by :meth:`save`.

        Returns:
            A :class:`ServiceRequest` reconstructed from the stored row, or
            ``None`` when no record with ``sr_id`` exists.
        """
        connection = get_connection(self._database_path)
        try:
            cursor = connection.execute(
                "SELECT id, resident_id, service_type, description, "
                "date_requested, status "
                "FROM service_requests WHERE id = ?",
                (sr_id,),
            )
            row = cursor.fetchone()
        finally:
            connection.close()

        if row is None:
            return None

        return ServiceRequest(
            id=row["id"],
            resident_id=row["resident_id"],
            service_type=row["service_type"],
            description=row["description"],
            date_requested=datetime.date.fromisoformat(row["date_requested"]),
            status=row["status"],
        )

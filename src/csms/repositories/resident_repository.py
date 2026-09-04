"""Resident persistence repository (T03).

This module provides :class:`ResidentRepository`, the single component
responsible for storing and retrieving :class:`~csms.models.resident.Resident`
objects from the SQLite database.

Responsibilities of this class (T03 scope only):

* **save** – INSERT a new Resident row and write the database-generated
  identifier back onto the Resident object.
* **find_by_id** – SELECT a Resident row by its primary key and reconstruct
  a :class:`Resident` instance, or return ``None`` when no record exists.

What this class intentionally does NOT do:

* It does not validate Resident information – that is T02's responsibility
  (:mod:`csms.utils.validators`).
* It does not implement search, listing, update, deletion, or any other
  operation beyond the two methods above – those belong to future tickets.
"""

from csms.database import get_connection, init_db
from csms.models.resident import Resident


class ResidentRepository:
    """Store and retrieve Resident records in the SQLite database.

    Each instance opens its own SQLite connection when needed and closes it
    immediately after the operation completes.  This means two separate
    :class:`ResidentRepository` instances pointed at the **same database
    file** can both access the same persisted data, which satisfies the
    requirement that persistence works across repository instances (Test 7).

    Args:
        database_path: Filesystem path to the SQLite database file.  The
            schema is created automatically on first use via
            :func:`~csms.database.init_db`.
    """

    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        init_db(database_path)

    def save(self, resident: Resident) -> Resident:
        """Persist a new Resident and assign its database-generated identifier.

        The SQLite ``AUTOINCREMENT`` column generates the ``id`` value so that
        identifiers are never hard-coded by the caller.  After a successful
        INSERT the ``resident.id`` attribute is updated in-place and the same
        object is returned.

        Args:
            resident: The :class:`Resident` to persist.  ``resident.id``
                should be ``None`` before calling this method.

        Returns:
            The same :class:`Resident` object with ``id`` now set to the
            value assigned by the database.
        """
        connection = get_connection(self._database_path)
        try:
            cursor = connection.execute(
                """
                INSERT INTO residents
                    (first_name, last_name, address, contact_number, email, status)
                VALUES
                    (?, ?, ?, ?, ?, ?)
                """,
                (
                    resident.first_name,
                    resident.last_name,
                    resident.address,
                    resident.contact_number,
                    resident.email,
                    resident.status,
                ),
            )
            connection.commit()
            resident.id = cursor.lastrowid
        finally:
            connection.close()

        return resident

    def find_by_id(self, resident_id: int) -> Resident | None:
        """Retrieve a Resident by its primary-key identifier.

        Args:
            resident_id: The integer identifier previously assigned by
                :meth:`save`.

        Returns:
            A :class:`Resident` reconstructed from the stored row, or
            ``None`` when no record with ``resident_id`` exists.  The method
            never raises an exception for a missing record.
        """
        connection = get_connection(self._database_path)
        try:
            cursor = connection.execute(
                "SELECT id, first_name, last_name, address, contact_number, email, status "
                "FROM residents WHERE id = ?",
                (resident_id,),
            )
            row = cursor.fetchone()
        finally:
            connection.close()

        if row is None:
            return None

        return Resident(
            id=row["id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            address=row["address"],
            contact_number=row["contact_number"],
            email=row["email"],
            status=row["status"],
        )

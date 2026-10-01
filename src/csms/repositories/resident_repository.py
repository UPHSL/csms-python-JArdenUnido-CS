"""Resident persistence repository (T03 + T05).

This module provides :class:`ResidentRepository`, the single component
responsible for storing and retrieving :class:`~csms.models.resident.Resident`
objects from the SQLite database.

Responsibilities:

* **save** – INSERT a new Resident row and write the database-generated
  identifier back onto the Resident object.  (T03)
* **find_by_id** – SELECT a Resident row by its primary key and reconstruct
  a :class:`Resident` instance, or return ``None`` when no record exists.  (T03)
* **find_all** – SELECT all Resident rows ordered deterministically by
  last name, first name, and id.  Returns an empty list when no records
  exist.  (T05)
* **search_by_name** – SELECT Resident rows whose first name or last name
  contains the given search term, using a case-insensitive partial match
  performed entirely inside the database query.  Returns an empty list when
  nothing matches.  (T05)

What this class intentionally does NOT do:

* It does not validate Resident information – that is T02's responsibility
  (:mod:`csms.utils.validators`).
* It does not implement update, deletion, or other operations – those belong
  to future tickets.
* The search is performed through parameterised SQL; raw search text is never
  concatenated into a query string.
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

    def find_all(self) -> list[Resident]:
        """Retrieve every persisted Resident in deterministic alphabetical order.

        The ordering is:
        1. ``last_name`` ascending (case-insensitive)
        2. ``first_name`` ascending (case-insensitive)
        3. ``id`` ascending (tie-breaker)

        Returns:
            A :class:`list` of :class:`Resident` objects.  An empty list is
            returned when no records exist — ``None`` is never returned.
        """
        connection = get_connection(self._database_path)
        try:
            cursor = connection.execute(
                "SELECT id, first_name, last_name, address, contact_number, email, status "
                "FROM residents "
                "ORDER BY LOWER(last_name) ASC, LOWER(first_name) ASC, id ASC"
            )
            rows = cursor.fetchall()
        finally:
            connection.close()

        return [
            Resident(
                id=row["id"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                address=row["address"],
                contact_number=row["contact_number"],
                email=row["email"],
                status=row["status"],
            )
            for row in rows
        ]

    def search_by_name(self, term: str) -> list[Resident]:
        """Search for Residents whose first or last name contains ``term``.

        The search is performed entirely inside the database using a
        parameterised ``LIKE`` query — no records are loaded into memory
        for in-application filtering.  The comparison is case-insensitive
        because both the stored values and the search term are lowercased
        via SQLite's ``LOWER()`` function before matching.

        A Resident matches when ``term`` appears anywhere within either
        ``first_name`` or ``last_name`` (partial-match / contains search).

        Each matching Resident appears exactly once even if the term matches
        both the first name and the last name, because ``OR`` in a single
        ``WHERE`` clause naturally deduplicates rows.

        Results are ordered by the same deterministic rule as
        :meth:`find_all` (last name → first name → id, all ascending).

        The raw ``term`` value is never concatenated into the SQL string.
        It is passed as a query parameter after being wrapped in ``%``
        wildcards, which is the correct parameterised approach.

        Args:
            term: The (already-trimmed) search text.  Must not be blank;
                callers are responsible for treating a blank term as a
                request for :meth:`find_all` instead.

        Returns:
            A :class:`list` of matching :class:`Resident` objects in the
            required order.  An empty list is returned when nothing matches.
        """
        pattern = f"%{term.lower()}%"
        connection = get_connection(self._database_path)
        try:
            cursor = connection.execute(
                "SELECT id, first_name, last_name, address, contact_number, email, status "
                "FROM residents "
                "WHERE LOWER(first_name) LIKE ? OR LOWER(last_name) LIKE ? "
                "ORDER BY LOWER(last_name) ASC, LOWER(first_name) ASC, id ASC",
                (pattern, pattern),
            )
            rows = cursor.fetchall()
        finally:
            connection.close()

        return [
            Resident(
                id=row["id"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                address=row["address"],
                contact_number=row["contact_number"],
                email=row["email"],
                status=row["status"],
            )
            for row in rows
        ]

    def update(self, resident: Resident) -> Resident:
        """Persist permitted field changes to an existing Resident record.

        Only the editable fields are written:
        ``first_name``, ``last_name``, ``address``, ``contact_number``,
        ``email``.

        The following fields are intentionally never touched by this method:

        * ``id``   – the Resident's identity; must not change.
        * ``status`` – managed separately by T07.

        The UPDATE targets exactly the Resident identified by ``resident.id``
        so no other Resident row is affected.

        Args:
            resident: The :class:`Resident` carrying the new values.  Its
                ``id`` must refer to an existing row.

        Returns:
            The same :class:`Resident` object, which now represents the
            persisted state.
        """
        connection = get_connection(self._database_path)
        try:
            connection.execute(
                """
                UPDATE residents
                SET first_name      = ?,
                    last_name       = ?,
                    address         = ?,
                    contact_number  = ?,
                    email           = ?
                WHERE id = ?
                """,
                (
                    resident.first_name,
                    resident.last_name,
                    resident.address,
                    resident.contact_number,
                    resident.email,
                    resident.id,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        return resident

    def deactivate_by_id(self, resident_id: int) -> None:
        """Set the status of the target Resident to ``'Inactive'``.

        This is a soft-deactivation operation — the Resident record is
        kept in persistence; only the ``status`` column is changed.

        The UPDATE targets exactly the Resident identified by
        ``resident_id``; no other Resident row is affected.  The method
        uses a fixed ``'Inactive'`` value so the caller cannot accidentally
        supply an arbitrary status string (T07 is specifically an
        Active-to-Inactive transition).

        The caller is responsible for verifying that the Resident exists and
        checking its current status before calling this method.

        Args:
            resident_id: The persisted ID of the Resident to deactivate.
        """
        connection = get_connection(self._database_path)
        try:
            connection.execute(
                "UPDATE residents SET status = ? WHERE id = ?",
                ("Inactive", resident_id),
            )
            connection.commit()
        finally:
            connection.close()

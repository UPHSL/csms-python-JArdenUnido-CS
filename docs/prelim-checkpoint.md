# Preliminary Checkpoint — T03: Establish Resident Persistence

## Developer Information

- **Name:** Jem Arden D. Unido
- **GitHub Username:** JArdenUnido-CS
- **Primary Technology Stack:** Python with Flask
- **T03 Branch:** `feature/t03-resident-persistence`

---

## My T03 Implementation

Resident data is stored in a **SQLite database file** (`csms.db`) using
Python's built-in `sqlite3` module, which requires no additional dependencies
beyond what is already declared in `pyproject.toml`. The component that
handles persistence is `ResidentRepository` in
`src/csms/repositories/resident_repository.py`. When a Resident is saved, the
repository opens a connection to the database, executes an `INSERT` statement
that supplies all field values except `id`, and then reads back the row
identifier that SQLite assigned through its `AUTOINCREMENT` mechanism; that
value is written back onto the `resident.id` attribute before the connection is
closed, so the caller immediately has the assigned identifier. A Resident is
retrieved by passing its integer `id` to `find_by_id`, which runs a `SELECT`
query and reconstructs a `Resident` dataclass instance from the returned row;
if no row exists for that `id`, the method returns `None` without raising an
exception so callers can handle missing records safely. The `contact_number`
column is declared as `TEXT` in the schema so the leading zero of a Philippine
mobile number (e.g. `09171234567`) is never converted to an integer and lost.

---

## Files I Changed

| File | Role in T03 |
|---|---|
| `src/csms/models/resident.py` | **Resident domain model (T01) — minimal update.** The `id` field was changed from a required `int` to an optional `int \| None = None`. This allows a Resident to be created without an id before it is saved, which is the correct representation of an unsaved record. All existing T01 tests still pass because they supply `id` as a keyword argument. |
| `src/csms/database.py` | **New — database initialisation and connection factory.** `init_db(database_path)` creates the `residents` table with `CREATE TABLE IF NOT EXISTS` (idempotent). `get_connection(database_path)` opens and returns a `sqlite3.Connection` with `row_factory = sqlite3.Row` so rows can be accessed by column name. |
| `src/csms/repositories/resident_repository.py` | **New — persistence component.** `ResidentRepository` implements `save(resident)` (INSERT + id assignment) and `find_by_id(resident_id)` (SELECT returning `Resident` or `None`). Each method opens and closes its own connection so that separate instances pointing at the same file can both see persisted data. |
| `src/csms/config.py` | **Updated — added `DATABASE_PATH` configuration.** `BaseConfig` exposes a `DATABASE_PATH` that defaults to `csms.db` in the project root. `TestingConfig` overrides it with a real temporary file (not `:memory:`) so that Test 7 — which creates two independent repository instances — can share the same on-disk database. |
| `tests/test_resident_persistence.py` | **New — T03 automated test suite.** Contains eight tests covering: saving, id assignment, retrieval, full field preservation, Active-status preservation, missing-resident handling, cross-instance persistence, and leading-zero preservation for contact numbers. |

---

## Problem I Encountered

**Problem:** After making `id` optional (`int | None = None`) in the Resident
dataclass, Python raised a `TypeError` during the test run:

```
TypeError: non-default argument 'first_name' follows default argument
```

**Cause:** Python dataclasses require that fields with default values come
*after* fields without defaults. The original T01 model placed `id` first
(no default), followed by `first_name`, `last_name`, etc. (no defaults), and
`status` last (default `"Active"`). When `id` was given the default `None`,
it became a "default argument" that now preceded the non-default fields
`first_name`, `last_name`, `address`, `contact_number`, and `email`, which is
illegal.

**Resolution:** The field order was rearranged so that all required fields
come first and both defaulted fields (`status` and `id`) come last:

```python
@dataclass
class Resident:
    first_name: str
    last_name: str
    address: str
    contact_number: str
    email: str
    status: str = "Active"
    id: int | None = None
```

Because all existing tests supply every argument as a keyword argument (e.g.
`Resident(id=1, first_name="Juan", ...)`), the reordering does not break any
existing test.

---

## My Student-Designed Test

**Test name:** `test_contact_number_leading_zero_is_preserved`

**What it verifies:** After a Resident is saved and retrieved, the
`contact_number` field is still the string `"09171234567"` — the leading zero
is present and the value is a `str`, not an integer.

**Why I chose this scenario:** The T03 requirements explicitly state that
`09171234567` must *not* become `9171234567` after persistence. SQLite silently
converts values in columns declared as `INTEGER` or `NUMERIC` into numbers,
which would drop the leading zero. A dedicated test makes the TEXT-column
contract explicit and immediately catches any future accidental schema change.

---

## Tools and References Used

- **Kiro AI (Kiro IDE)** — assisted with implementation planning, code generation,
  and commit workflow for T03.
- **Python `sqlite3` documentation** — standard library reference for
  connection, cursor, `lastrowid`, `row_factory`, and `AUTOINCREMENT`.
- **Flask configuration documentation** — for understanding how to wire
  `DATABASE_PATH` into `app.config` for use by the repository.
- **pytest documentation** — for `tmp_path` fixture used in the persistence
  test suite.

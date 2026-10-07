# Midterm Checkpoint — T10: Manage Service Request Status

## Developer Information

- **Name:** Jem Arden D. Unido
- **GitHub Username:** JArdenUnido-CS
- **Primary Technology Stack:** Python with Flask
- **T10 Branch:** `feature/t10-service-request-status`

---

## My T10 Implementation

The `ServiceRequestStatusService` in `src/csms/services/service_request_status_service.py`
manages the Service Request status workflow.  When `change_status(sr_id, requested_status)`
is called, the service first uses `ServiceRequestRepository.find_by_id()` (the T09
repository) to retrieve the existing Service Request from SQLite persistence — this is
how the current status is determined.  The requested status is then checked against a
`frozenset` of four supported values (`Pending`, `In Progress`, `Completed`, `Cancelled`),
and if it is not recognised the call returns immediately with `unsupported_status=True`
without touching the database.  Valid and invalid transitions are enforced through a
`ALLOWED_TRANSITIONS` dictionary that maps each current status to a `frozenset` of the
statuses it may move to; if the requested status is not in that set — including
same-status requests, since a status is never in its own allowed-next set — the call
returns with `invalid_transition=True` and persistence is left unchanged.  For a valid
transition, the service calls `ServiceRequestRepository.update_status(sr_id, new_status)`,
which executes a targeted `UPDATE service_requests SET status = ? WHERE id = ?` with
parameterised arguments so only the intended row and column are affected.  After the
successful update, `find_by_id()` is called again to retrieve the authoritative persisted
state, which is returned inside a `StatusResult(success=True, service_request=...)`.

---

## My Transition Rules

| Current Status | Allowed Next Statuses      |
|----------------|---------------------------|
| Pending        | In Progress, Cancelled    |
| In Progress    | Completed, Cancelled      |
| Completed      | (none — terminal)         |
| Cancelled      | (none — terminal)         |

**Why Pending cannot become Completed directly:**
A Service Request must pass through active processing (`In Progress`) before it
can be marked `Completed`. Skipping this step would bypass the operational tracking
of whether work was actually started, which is the purpose of the `In Progress` state.

**Why Completed is terminal:**
`Completed` represents a successfully fulfilled request. There is no business reason to
reopen or re-process a finished request; doing so would corrupt the audit trail of
completed work.

**Why Cancelled is terminal:**
`Cancelled` represents a definitively withdrawn or rejected request. Reopening a
cancelled request could lead to duplicated or contradictory records. Reactivation would
require a separate business process outside T10 scope.

**How same-status requests are handled:**
A status value is never placed in its own allowed-next `frozenset`. Therefore
`Pending → Pending`, `In Progress → In Progress`, etc. all fail the transition check
with `invalid_transition=True`, leaving persistence unchanged.

---

## Files I Changed

**File:** `src/csms/repositories/service_request_repository.py`
**Purpose:** Extended the T09 repository by appending an `update_status(sr_id, new_status)`
method. This method executes `UPDATE service_requests SET status = ? WHERE id = ?` with
parameterised arguments, targeting only the requested row and only the `status` column.
All other columns are untouched.

**File:** `src/csms/services/service_request_status_service.py`
**Purpose:** New file. Contains `SUPPORTED_STATUSES`, `ALLOWED_TRANSITIONS`, the
`StatusResult` dataclass (four outcome fields), and `ServiceRequestStatusService` with
its `change_status()` method. This is the only component responsible for enforcing the
T10 business transition rules.

**File:** `tests/test_service_request_status.py`
**Purpose:** New file. Contains all 14 T10 automated tests (13 required + 1
student-designed). Uses the T09 submission workflow to set up real persisted Service
Requests in a fresh SQLite database for each test.

**File:** `docs/midterm-checkpoint.md`
**Purpose:** This document. Required Midterm Examination checkpoint.

---

## Problem I Encountered

**Problem:** While writing Test 10 (`test_nonexistent_service_request_is_handled_safely`),
I wanted to confirm that no Service Request record was created as a side-effect of the
failed status operation. My first assertion was `sr_repo.find_all_ids() == []`, calling
a method `find_all_ids()` that does not exist on `ServiceRequestRepository`.

**Cause:** I wrote the assertion based on what seemed like a useful query method without
checking that the method actually existed on the T09 repository. Python would have raised
`AttributeError` at test-collection time, which would have caused the entire test file to
fail to load — not just the one test.

**How I resolved it:** I caught the error by static review before running pytest.
Since `find_by_id()` already exists and returns `None` for a missing record, I replaced
the assertion with `sr_repo.find_by_id(1) is None`, which verifies the same thing
(no record with id=1 was created) using only existing API surface. This kept the test
correct and the repository clean.

---

## My Student-Designed Test

**Test Name:** `test_sequential_valid_transitions_work_correctly`

**What the Test Verifies:**
A Service Request can progress through its complete valid lifecycle in sequential
order — `Pending → In Progress → Completed` — with each intermediate state confirmed
in persistence before the next transition is attempted. After reaching `Completed`, every
possible outgoing transition is also verified to be rejected, confirming the terminal
state holds after sequential use.

**Why I Added This Test:**
The thirteen required tests each verify a single-step transition in isolation. This test
confirms that the transition table works correctly when transitions are applied
*sequentially on the same persisted record* — a realistic workflow scenario that could
expose bugs if the service accidentally cached an in-memory status rather than
re-reading the current status from the database before each decision. It also documents
the intended full lifecycle in a single readable test.

---

## Tools and References Used

- **Kiro AI (Kiro IDE)** — assisted with planning, implementation, and commit workflow for T10.
- **Python `sqlite3` documentation** — for the parameterised `UPDATE` pattern.
- **Python `dataclasses` documentation** — for `StatusResult` field design.
- **pytest documentation** — for fixture composition and parametric patterns.

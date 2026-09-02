# Scheduling Module

## Purpose

Guarantees that a technician has no overlapping active assignments, including under simultaneous requests across multiple API instances.

## Validation

- Both start and end are supplied together.
- End is strictly later than start.
- Start cannot be in the past when an assignment/reschedule request is accepted.
- Assigned user is an active Technician in the actor's organisation.
- Cancelled work orders do not block time; other scheduled operational statuses do.
- Intervals are half-open and overlap when `new_start < existing_end AND new_end > existing_start`.

## Transaction

1. Open `transaction.atomic()`.
2. Organisation-scope and lock the technician's `OrganisationUser` row with `select_for_update()`.
3. Reload the target work order within the organisation.
4. Query overlapping assignments, excluding the target during edits.
5. On conflict, abort with HTTP 409 and `SCHEDULE_CONFLICT`.
6. Save assignment and audit entry.
7. Register notification/realtime effects with `transaction.on_commit()`.

Locking a stable technician row serializes scheduling decisions for that technician in PostgreSQL and remains correct with multiple API containers. Different technicians can be scheduled concurrently.

The generic work-order serializers expose scheduling fields as read-only. `POST /api/v1/work-orders/{id}/assign` is the only HTTP mutation path and supports both first assignment and rescheduling/reassignment while the work order remains assignable.

## Tests

- Boundary and overlap examples.
- Wrong organisation/role.
- Two real concurrent PostgreSQL transactions competing for the same technician: exactly one conflicting assignment succeeds.
- No notification is queued on rollback.

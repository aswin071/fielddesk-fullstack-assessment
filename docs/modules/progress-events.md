# Progress Events Module

## Purpose

Accepts untrusted technician progress updates exactly once and preserves the accepted request as immutable history.

## API

- `POST /api/v1/progress-events`

Request fields are `eventId`, `workOrderId`, `type`, `occurredAt` and type-specific `payload`.

## Rules

- Actor must be an active Technician assigned to the referenced work order in the same organisation.
- Allowlisted event types have dedicated payload serializers; unknown fields/types are rejected.
- Timestamp must be timezone-aware and within the configured acceptable clock window.
- Original accepted type, timestamp and payload are stored without later mutation.
- Unique `(organisation, event_id)` is the database idempotency boundary.

## Transaction

Inside one PostgreSQL transaction, acquire a transaction-scoped advisory lock derived from `(organisation, eventId)`, check for an accepted duplicate, lock the assigned work order, validate/apply the state transition, insert the event and write its audit entry. Any failure rolls everything back. Realtime publication happens only after commit.

For a duplicate `eventId` submitted by the same technician, return the stored outcome if the canonical request matches. Reusing the same ID with different content returns `409 IDEMPOTENCY_KEY_REUSED`. Another actor receives `404`, avoiding disclosure. The PostgreSQL advisory lock serialises duplicate requests before the unique constraint is reached, including requests handled by different API containers.

## Implemented contract

- Supported types are `status_changed` and `note_added`.
- Technician status updates are limited to `in_progress`, `blocked` and `completed`, then checked against the work-order state machine.
- Event IDs accept 1-100 allowlisted characters and are unique per organisation.
- Events may be at most five minutes in the future and 30 days old by default.
- Both the accepted original JSON and canonical payload/hash are retained.
- Persisted event instances reject normal update and delete operations.

## Tests

Valid/invalid payloads, assignment authorization, tenant isolation, duplicate sequential and concurrent requests, conflicting reuse, rollback and immutable records.

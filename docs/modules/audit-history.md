# Audit History Module

## Purpose

Maintains immutable, organisation-scoped evidence of material user and system actions.

## Recorded actions

Work-order creation and edits, assignment/schedule/status changes, attachment addition/removal, user role/status changes, progress-event acceptance and notification outcomes.

Each entry records organisation, actor or system identity, action, target type/ID, UTC timestamp, correlation ID, relevant before/after JSON and safe metadata.

## API

- `GET /api/v1/work-orders/{id}/activity`
- Organisation-wide audit listing is intentionally not exposed; the assessment workflow uses work-order activity.

## Rules

- Audit entries are written inside the business transaction.
- No normal create/update/delete API is exposed.
- Sensitive values, credentials, raw tokens and file contents are never captured.
- Activity queries are organisation-scoped and ordered deterministically.
- System notification outcomes use a null actor plus explicit system metadata.

## Implementation

`AuditEntry` is organisation-owned and immutable. It stores an optional actor, action, polymorphic target type/UUID, optional related work order, correlation ID, before/after JSON and safe metadata. The related-work-order column gives activity reads an indexed tenant-safe path without parsing polymorphic metadata.

Domain services call the shared recorder explicitly inside their existing PostgreSQL transaction. Signals are not used. Recorded actions are:

- `work_order.created`, `work_order.updated` and `work_order.assigned`;
- `progress_event.accepted`;
- `attachment.added` and `attachment.deleted`;
- `user.created` and `user.updated` for role/profile/status changes;
- classified `notification.*` outcomes for every worker attempt.

Snapshots are converted with Django's JSON encoder and are deliberately constructed from allowlisted domain fields. Passwords, tokens, file contents, storage keys and provider diagnostics are excluded. Notification entries have a null actor and `system: celery-worker` metadata.

The activity API uses current work-order visibility: Owners and Dispatchers can read work in their organisation, while Technicians can read only currently assigned work. Cross-organisation or unauthorized work-order IDs return `404`. Results use deterministic newest-first ordering and bounded pagination.

## Tests

Required actions generate one correct entry, rollbacks leave none, records cannot be edited, and another organisation cannot read them.

# API Standards

## Base and representation

All endpoints use `/api/v1/`. JSON field names use `camelCase` at the boundary and Python code uses `snake_case`. Timestamps use ISO-8601 UTC. UUIDs are strings.

## Success responses

Single resource:

```json
{"data": {}, "meta": {"correlationId": "uuid"}}
```

Paginated collection:

```json
{
  "data": [],
  "meta": {"page": 1, "pageSize": 25, "total": 0, "correlationId": "uuid"}
}
```

## Error responses

```json
{
  "error": {
    "code": "SCHEDULE_CONFLICT",
    "message": "The technician is unavailable during this period.",
    "fields": {"assignedTechnicianId": ["Conflicts with an existing assignment."]},
    "correlationId": "uuid"
  }
}
```

Standard status usage:

- `400` malformed input
- `401` missing/invalid authentication
- `403` authenticated but role is forbidden
- `404` absent or outside the caller's organisation scope
- `409` scheduling/state/idempotency conflict requiring client action
- `413` file too large or organisation quota exceeded
- `429` throttled
- `500` unexpected server error with no internal detail

## Collection behavior

- Search: `search`
- Filters: `status`, `priority`, `technicianId`, `scheduledFrom`, `scheduledTo`
- Sorting: `ordering=createdAt` or `ordering=-scheduledStart`; only allowlisted fields
- Pagination: `page` and `pageSize`, with configured maximum

List, dashboard and export share the same organisation-scoped filter selector to prevent authorization drift.

## Mutation conventions

- `POST` creates and returns `201`.
- `PATCH` performs validated partial updates.
- Progress events use their request `eventId` as an idempotency key.
- Conflicting scheduling returns stable `SCHEDULE_CONFLICT` code.
- State transitions are validated by services rather than accepting arbitrary status assignments.

## Correlation and logging

The API accepts a valid `X-Correlation-ID` or generates one. It returns the value in response headers and bodies and includes it in structured logs, audit entries and asynchronous job metadata.

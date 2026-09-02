# Work Orders Module

## Purpose

Owns work-order lifecycle, retrieval, filtering, dashboard summaries and validated state transitions.

## Fields

Reference number, title, description, priority, status, technician, scheduled interval, site name, organisation, creator and timestamps. Attachments and activity are related resources.

## Permissions

- Owner/Dispatcher: create, list, retrieve, edit, assign, schedule and update status.
- Technician: list/retrieve only assigned work and update it only through progress events.
- All access is organisation-scoped before role/object checks.

## API

- `GET/POST /api/v1/work-orders`
- `GET/PATCH /api/v1/work-orders/{id}`
- `POST /api/v1/work-orders/{id}/assign`
- `GET /api/v1/work-orders/{id}/activity`
- `GET /api/v1/dashboard/summary`

## Rules

- Reference numbers are unique per organisation and generated server-side.
- Title, priority, status and scheduling fields are centrally validated.
- Assignment calls the scheduling service; it cannot bypass overlap checks.
- Allowed state transitions are explicit. Completed/cancelled orders cannot be casually returned to active states.
- List/search/filter/sort/pagination use one selector shared with reporting.
- Mutations write audit entries and publish realtime events after commit.

## Delivery sequence

Phase 6 delivers the model, organisation/role-scoped CRUD, list behavior, state validation and dashboard counts. Assignment and scheduling fields are read-only in generic serializers. Phase 7 supplies the dedicated assignment endpoint and PostgreSQL concurrency service. Mutations now write audit entries transactionally and emit realtime hints only after commit.

## Tests

CRUD permissions, validation, transitions, tenant isolation, search/filter/sort/pagination, activity and dashboard counts.

# System Context and Architecture

## Goals

FieldDesk is a review-friendly multi-tenant application for scheduling and tracking field work. Correct organisation isolation, transactional consistency and observable behavior are higher priorities than architectural novelty.

## Runtime components

```text
Browser (React)
    | HTTPS REST + authenticated SSE
    v
Django ASGI API
    |-- PostgreSQL: authoritative application state and locks
    |-- Redis: Celery broker and SSE fan-out
    |-- protected local media volume: assessment attachments
    `-- Celery worker: notification delivery
```

All components are started by Docker Compose. API and worker use the same Django domain code; `worker/` contains worker-specific container/configuration material, not a second business implementation.

## Backend layout

```text
backend/
|-- config/                 # settings, URLs, ASGI, Celery
|-- api/v1/                 # versioned URL composition
|-- common/                 # base models, errors, logging, tenancy
|-- organisations/
|-- authentication/
|-- users/
|-- workorders/
|-- scheduling/
|-- progress_events/
|-- attachments/
|-- audit/
|-- notifications/
|-- realtime/
`-- reporting/
```

Each domain app follows the KBN module shape while separating responsibilities more clearly:

```text
models.py       persistent state and database constraints
serializers.py  request/response validation
services.py     transactional business operations
selectors.py    organisation-scoped read queries
permissions.py  role and object authorization
views.py        HTTP orchestration only
tasks.py        asynchronous entry points where applicable
tests/          externally observable module behavior
SPEC.md         link or copy of the authoritative module specification
```

## Dependency rules

- Views call serializers, selectors and services; they do not implement transactions directly.
- Services own multi-model writes and publish post-commit events.
- Selectors always require an organisation or authenticated OrganisationUser.
- Cross-domain behavior uses explicit service calls, not implicit signals. Signals are reserved for framework-level concerns.
- Celery tasks receive IDs, reload current database state and are idempotent.
- Audit creation occurs inside the same transaction as the business change.

## Scaling

- API containers are stateless and horizontally scalable.
- PostgreSQL transactions/advisory or row locks coordinate scheduling across API instances.
- Redis distributes queue work and real-time events.
- Local attachments are replaced by private object storage in production through Django's storage interface.
- SSE instances consume organisation channels; clients reconnect using an event cursor when possible and otherwise refetch current state.

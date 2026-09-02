# Operations and Testing Module

## Local operation

Docker Compose starts frontend, API, worker, PostgreSQL and Redis. A documented command applies migrations and seeds two organisations with Owner, Dispatcher and Technician users. `.env.example` contains placeholders only.

## Health

- `/health/live` confirms the process event loop is responsive.
- `/health/ready` checks required PostgreSQL and Redis connectivity with short timeouts.
- Health endpoints expose no secrets or internal configuration.

API and worker handle termination signals, stop accepting new work and allow bounded graceful completion. Container health checks and dependency readiness are declared in Compose.

## Observability

JSON structured logs include timestamp, level, service, correlation ID, actor/organisation identifiers where safe, event and outcome. Request middleware propagates/generates correlation IDs. Secrets, tokens, passwords, attachment content and unsafe payloads are excluded.

## Test strategy

- Unit tests for pure validation and state-transition functions.
- API integration tests for authentication, roles, isolation and response contracts.
- PostgreSQL transaction tests for overlap and idempotency races.
- Celery eager/integration tests that verify database-visible behavior and provider outcomes.
- Realtime integration tests with two organisations.
- Attachment and streaming-export tests.
- Frontend component/integration test for the principal Dispatcher workflow.

Tests requiring constraints, locks or concurrent transactions use real PostgreSQL, not SQLite. CI runs backend lint/type checks/tests, frontend lint/type checks/tests and production builds.

## Deployment, backup and recovery

Production uses managed PostgreSQL/Redis, private object storage, TLS termination, secret management, multiple stateless API/worker replicas, centralized logs/metrics and database/object lifecycle backups. Recovery documentation specifies restore testing and reconciles attachment metadata with storage. Redis is not authoritative business storage.

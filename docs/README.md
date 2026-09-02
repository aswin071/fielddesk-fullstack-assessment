# FieldDesk Software Design Documentation

This directory is the source of truth for FieldDesk design decisions. Implementation must conform to these specifications or update the relevant document with the reason for divergence.

## System specifications

- [Requirements decisions](./00-requirements-decisions.md)
- [System context and architecture](./01-architecture.md)
- [Security and organisation isolation](./02-security.md)
- [Database model](./03-data-model.md)
- [API standards](./04-api-standards.md)
- [Requirements traceability](./05-requirements-traceability.md)
- [Deployment and operations](./06-deployment-operations.md)

## Module specifications

- [Organisations](./modules/organisations.md)
- [Authentication](./modules/authentication.md)
- [Users and roles](./modules/users-and-roles.md)
- [Work orders](./modules/work-orders.md)
- [Scheduling](./modules/scheduling.md)
- [Progress events](./modules/progress-events.md)
- [Attachments](./modules/attachments.md)
- [Audit history](./modules/audit-history.md)
- [Notifications](./modules/notifications.md)
- [Real-time updates](./modules/realtime.md)
- [Reporting](./modules/reporting.md)
- [Frontend](./modules/frontend.md)
- [Operations and testing](./modules/operations-and-testing.md)

## Architectural lineage

FieldDesk retains the useful KBN patterns: a Django/DRF modular monolith, domain-oriented Django apps, versioned APIs, shared abstract models, PostgreSQL, Redis/Celery, model history, role permissions and external-storage abstraction.

FieldDesk deliberately strengthens KBN's weaker areas: deny-by-default authorization, explicit organisation ownership, UUID public identifiers, database-enforced concurrency, immutable idempotent events, protected attachments, transaction-safe side effects, structured errors and comprehensive tests.

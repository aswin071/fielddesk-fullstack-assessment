# Background Notifications Module

## Purpose

Notifies technicians asynchronously when work is assigned and records reliable delivery outcomes.

## Design

Every successful assignment increments a server-owned work-order assignment revision. The scheduling transaction creates or identifies one `NotificationDelivery` for `(work order, assignment revision)` and registers enqueueing with `transaction.on_commit()`. A broker failure is logged while the durable queued delivery remains recoverable; it never rolls back an assignment that already committed.

The Celery task locks and reloads the delivery, exits successfully if already delivered/permanently failed, records an immutable attempt and calls the configured provider. The row lock spans the mock provider call so competing workers cannot invoke the provider simultaneously for one delivery. A production provider receives the stable `provider_idempotency_key`, protecting ambiguous retries if a worker dies after the external provider accepts a request.

Provider outcomes:

- success: mark delivered and stop;
- temporary failure: commit the attempt and retry with exponential backoff up to the configured limit;
- permanent failure: record final failure and never retry.

The mock provider modes are `success`, `temporary_failure`, `temporary_then_success` and `permanent_failure`. Retry count, base delay and simulated temporary-failure count are environment configured. It does not require a third-party account.

## Idempotency

Database uniqueness on `(work_order, assignment_revision)` prevents duplicate delivery records. The task locks/rechecks current state before provider invocation. Terminal tasks return the stored status without adding another attempt. This coordination uses PostgreSQL and therefore remains safe with multiple API and worker containers.

## Durable state

`NotificationDelivery` records queued/retrying/delivered/permanently-failed state, attempt count, sanitized last diagnostic and terminal timestamps. `NotificationAttempt` records attempt number, classified outcome, diagnostic and provider reference and cannot be updated or deleted normally.

Assignment and notification-outcome audit entries are recorded inside their corresponding database transactions. A production deployment should also run a periodic recovery task that re-enqueues stale queued/retrying deliveries after broker outages.

## Tests

Success, temporary retry then success, retry exhaustion, permanent failure, duplicate task delivery, no enqueue before commit and recorded audit/log outcomes.

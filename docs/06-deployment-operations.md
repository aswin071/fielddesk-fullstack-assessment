# Deployment and Operations

## Reviewer startup

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec api python manage.py seed_fielddesk --reset-passwords
docker compose ps
```

Open `http://localhost:5173`. The idempotent seed creates two organisations, every role and three representative work orders per organisation. Re-running it restores documented account roles, activation and passwords without duplicating records.

API startup applies migrations before Uvicorn accepts traffic. PostgreSQL and Redis health checks gate API startup; API health gates frontend startup. The worker runs independently and drops root privileges in Compose.

## Production topology

- TLS load balancer in front of multiple stateless ASGI API replicas.
- Static frontend deployed through a CDN or immutable web container.
- Managed PostgreSQL with multi-zone durability, point-in-time recovery and connection pooling.
- Managed Redis for Celery and ephemeral realtime fan-out; Redis is not authoritative storage.
- Multiple Celery workers with bounded concurrency and graceful termination.
- Private S3-compatible attachment storage with encryption, versioning and lifecycle cleanup.
- Central logs, metrics, alerts and managed secrets.

Set `DJANGO_SETTINGS_MODULE=config.settings.production`. Production fails closed without an explicit secret, allowed hosts and CORS origins. Terminate TLS at the trusted proxy and preserve `X-Forwarded-Proto`. Never expose PostgreSQL, Redis, Uvicorn or object storage publicly.

## Deployment sequence

1. Build immutable API/worker and frontend images from a reviewed commit.
2. Run backend and frontend lint/tests/build in CI with PostgreSQL and Redis.
3. Scan/sign images and publish them to the deployment registry.
4. Confirm a recoverable database checkpoint for high-risk migrations.
5. Run `python manage.py migrate --noinput` as one release job.
6. Roll API replicas gradually; readiness removes unavailable replicas.
7. Roll workers with termination grace longer than expected provider calls.
8. Publish the frontend and smoke-test all three roles.
9. Monitor errors, latency, queue depth and database health before completion.

Use expand/migrate/contract sequencing when mixed application versions may run. Destructive migrations require a separate reviewed release and tested restore point.

## Monitoring and alerts

Collect JSON logs from API and worker. Preserve correlation IDs and add deployment version, service and environment at log ingestion.

Monitor:

- request rate, p50/p95/p99 latency and 4xx/5xx rate by route;
- readiness failures, process restarts and active SSE connections;
- PostgreSQL connections, lock waits, slow queries, capacity and replication lag;
- Redis connectivity, memory, evictions and queue errors;
- Celery queue age/depth, retries, permanent failures and runtime;
- attachment quota/cleanup failures and authentication throttling;
- repeated authorization failures and scheduling conflicts.

Page on sustained 5xx/readiness failure, database availability/replication risk, oldest Celery job above SLA, backup failure or storage capacity thresholds. Provider permanent failures are operational workflow alerts, not worker crashes.

## Backup and recovery

Business truth is PostgreSQL plus private attachment objects. Redis can be rebuilt.

- Enable encrypted snapshots and continuous PostgreSQL WAL/PITR retention.
- Enable bucket versioning with retention aligned to database backups.
- Store backup encryption keys separately from application credentials.
- Test restoration quarterly in an isolated environment.
- Suggested assessment targets are RPO 15 minutes and RTO 4 hours; production owners must approve real targets.

Recovery procedure:

1. Freeze writes or route traffic to maintenance mode.
2. Restore PostgreSQL to the chosen consistent timestamp.
3. Restore the corresponding object-storage version window.
4. Apply only migrations included in the restored application release.
5. Reconcile active attachment metadata against object keys; quarantine orphans.
6. Start Redis empty and re-enqueue stale queued/retrying deliveries.
7. Validate both organisations independently, including cross-tenant negative tests.
8. Resume workers, APIs and then client traffic while monitoring errors.

Audit and progress records remain part of database backups. Backup administrators and database superusers are privileged trust roles and require external access auditing.

## Scaling and failure behavior

Scheduling uses PostgreSQL technician-row locks and progress idempotency uses PostgreSQL advisory locks. Attachment quotas lock organisation rows. Notification workers lock delivery rows and pass provider idempotency keys. Redis Pub/Sub is best-effort; reconnecting clients refetch REST state.

Broker or realtime publication failure never rolls back committed business data. Production should periodically re-enqueue stale notification deliveries. Local attachment storage is assessment-only; multiple API replicas require shared private object storage.

## Security checklist

- Rotate development credentials and use a managed secret store.
- Use production settings, HTTPS-only cookies, HSTS and strict origin allowlists.
- Restrict database/Redis/bucket networks and use least-privilege identities.
- Run containers with read-only roots/non-root identities where supported.
- Align upload, request, proxy and provider timeouts/body limits.
- Retain security/audit logs without tokens or request bodies.
- Patch images/dependencies regularly and rerun the full test matrix.

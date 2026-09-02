# Technical notes

## Candidate

- Name: Aswin K
- GitHub username: `aswin071`
- Final commit SHA: 148e42b76dce318f84fbc3259c9e82d20ef14827
- Screen-recording link: [FieldDesk demonstration](https://drive.google.com/file/d/1cGYLFGTlDG8oCBWiA_ZzA04c0smeo7So/view?usp=sharing) (Google Drive)

## Local setup

Docker Desktop with Docker Compose is required. From the repository root, run:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api python manage.py seed_fielddesk --reset-passwords
docker compose ps
Invoke-RestMethod http://localhost:8000/health/ready
```

Open `http://localhost:5173`. The API is available at `http://localhost:8000/api/v1/`. To stop the stack, run `docker compose down`.

## Sample accounts

The idempotent seed creates two isolated organisations with the following assessment-only accounts. All accounts use the password `FieldDeskDemo!2026`.

| Organisation | Role | Email |
| --- | --- | --- |
| Northstar Maintenance | Owner | `owner@northstar.test` |
| Northstar Maintenance | Dispatcher | `dispatcher@northstar.test` |
| Northstar Maintenance | Technician | `technician@northstar.test` |
| Harborview Services | Owner | `owner@harborview.test` |
| Harborview Services | Dispatcher | `dispatcher@harborview.test` |
| Harborview Services | Technician | `technician@harborview.test` |

These credentials and the values in `.env.example` are development fixtures and must not be used in production.

## Verification results

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `docker compose exec api pytest -q` | 98 passed |
| Frontend tests | `docker compose exec frontend npm run test` | 1 test passed |
| Integration tests | Included in the PostgreSQL-backed backend suite and frontend workflow test | Scheduling concurrency, idempotency, tenant isolation and Dispatcher workflow passed |
| Lint | `docker compose exec api ruff check .` and `docker compose exec frontend npm run lint` | Passed with no errors |
| Build | `docker compose exec frontend npm run build` | TypeScript and Vite production build passed |

Additional checks used were `docker compose exec api python manage.py makemigrations --check --dry-run`, `docker compose exec api python manage.py check`, `pip check`, `npm audit --omit=dev` and live readiness checks.

## Architecture

- React, TypeScript and Vite provide the responsive ERP frontend.
- Django and Django REST Framework provide the modular API.
- PostgreSQL is the permanent source of truth and provides transactional coordination.
- Redis provides Celery brokering and organisation-scoped realtime fan-out.
- Celery processes assignment notifications independently of API requests.
- Docker Compose starts the frontend, API, worker, PostgreSQL and Redis services.

React Router manages frontend routes and TanStack Query manages API state, caching and refetching. The Django backend is separated into authentication, organisations, users, work orders, scheduling, progress events, attachments, audit, notifications, realtime and reporting modules.

## Database design

Organisation-owned models use UUID primary keys, timestamps and an explicit organisation foreign key. The principal models are User, Organisation, OrganisationUser, WorkOrder, ProgressEvent, Attachment, AuditEntry, NotificationDelivery and NotificationAttempt. OrganisationUser holds a person's role and active status within an organisation. WorkOrder holds the job, creator, assigned Technician, schedule, priority and status.

Database constraints enforce unique work-order references per organisation, paired and valid schedule windows, unique progress event IDs per organisation, and one notification delivery per assignment revision. Indexes cover common organisation, status, priority, Technician, schedule and timestamp queries. Schema changes are managed through committed Django migrations, which the API startup process applies automatically.

## Authentication, roles and organisation isolation

SimpleJWT issues a short-lived access token and a rotating refresh token after email and password authentication. The frontend holds the access token in memory, while the refresh token is stored in an HttpOnly, SameSite cookie. Logout blacklists the refresh token and clears the cookie.

The roles are Owner, Dispatcher and Technician. The backend derives both role and organisation from the authenticated OrganisationUser and never trusts client-provided authority fields. All organisation-owned queries are scoped before object lookup. Owners and Dispatchers see their organisation's work orders, while Technicians see only work assigned to them. Cross-organisation and unauthorized object lookups return `404` to avoid revealing whether the object exists.

## Transactions, idempotency and concurrency

- Business changes and their audit entries commit atomically.
- Scheduling locks the work order and stable Technician OrganisationUser row using PostgreSQL `select_for_update()`.
- Overlaps are checked inside the locked transaction and return `409 SCHEDULE_CONFLICT`.
- Progress requests use a PostgreSQL transaction-level advisory lock derived from organisation and event ID.
- A unique `(organisation, event_id)` constraint is the persistent idempotency boundary.
- Exact event retries return the stored result; altered reuse returns `409 IDEMPOTENCY_KEY_REUSED`.
- Realtime and background side effects are registered only after successful commits.

This database-backed coordination remains correct when multiple API containers process requests concurrently.

## Background jobs

Each successful assignment increments an assignment revision and creates one durable NotificationDelivery for that work order and revision. Celery enqueueing happens through `transaction.on_commit()`, so a rolled-back assignment cannot produce a notification. The worker locks and rechecks the delivery before calling the provider, and terminal deliveries are returned without creating another attempt.

Temporary failures are recorded and retried with exponential backoff up to the configured limit. Permanent failures and exhausted retries are recorded without further delivery attempts. A stable provider idempotency key protects retries where the external outcome is uncertain. The assessment uses a configurable mock provider so success, temporary failure and permanent failure can be demonstrated without third-party credentials.

## Real-time updates

The frontend opens an authenticated Server-Sent Events stream using `fetch`, allowing the JWT to stay in the Authorization header instead of the URL. The backend derives the Redis channel only from the authenticated organisation. Events contain minimal allowlisted change information and are published after the relevant transaction commits.

The frontend treats events as invalidation hints and asks TanStack Query to refetch authoritative REST data. Redis Pub/Sub has no replay history, so reconnecting clients receive `sync_required` and perform a full refetch. Redis failure is logged but does not roll back an already committed business operation.

## File security and storage limits

- Only genuine JPEG, PNG and PDF content is accepted.
- The backend checks magic bytes, extension, declared content type, size and empty content.
- Clean display names are separated from private UUID-based storage keys.
- Downloads pass through current organisation and work-order authorization.
- Technicians can access attachments only for currently assigned work.
- PostgreSQL organisation-row locks make quota updates safe under concurrent uploads.
- Attachment metadata, checksum and audit history are stored without exposing file bodies or storage keys.

Development uses Django's local storage abstraction. Production should use a private S3-compatible bucket with public access disabled and short-lived authorized downloads.

## Security considerations

The main threats considered were cross-organisation data leakage, role escalation, credential and token exposure, schedule races, duplicate offline events, unsafe uploads, quota races, spreadsheet injection and sensitive logging. Controls include deny-by-default API authentication, server-derived organisation and role context, scoped querysets, generic login failures, throttling, password hashing, refresh rotation and blacklisting, secure production cookies and headers, database locks and constraints, upload signature validation, CSV formula neutralisation, allowlisted audit snapshots, correlation IDs and sensitive-log redaction.

## Production deployment and operations

I would publish versioned API, frontend and worker images to a trusted registry and deploy them behind HTTPS. PostgreSQL and Redis should be managed private services. Migrations should run as a controlled deployment job before new API containers receive traffic. API and worker containers can scale independently because coordination is stored in PostgreSQL.

Attachments should move to private object storage, while JSON application logs should be collected centrally. Monitoring should cover readiness, HTTP errors, authentication failures, database and Redis health, Celery queue depth, notification failure rate and storage usage. PostgreSQL should use encrypted automated backups and point-in-time recovery, with regular restoration tests. The documented planning assumption is a 15-minute recovery point and four-hour recovery time, subject to the selected hosting provider.

## Assumptions and trade-offs

- One user belongs to one organisation in this assessment, although OrganisationUser can be extended for multiple organisations.
- Roles are fixed rather than user-defined permission bundles.
- SSE was chosen over WebSockets because the required updates are one-way and SSE is simpler to operate.
- Redis Pub/Sub is lightweight but does not replay events, so clients refetch after reconnecting.
- The notification provider is deterministic and mocked rather than connected to email or SMS.
- Development uses local private file storage; production requires shared object storage.
- Work orders are retained for operational history instead of exposing a destructive delete workflow.

## Known limitations or incomplete requirements

No requirement-defined feature is intentionally incomplete. Real notification-provider credentials, production object storage, CI/CD pipelines and hosting infrastructure are environment-specific and are not included in this local assessment implementation. The mock provider does not send an actual email or SMS, and local attachment storage must be replaced before horizontally scaling the API in production.

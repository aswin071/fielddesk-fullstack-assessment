# Requirements Decisions

Status: Accepted for initial implementation. Decisions marked "assumption" may be revised without changing the assessment requirements.

## Vocabulary

- **Organisation**: a maintenance company and the top-level security boundary.
- **OrganisationUser**: a user's account, role and status within one organisation. This replaces the less clear term "membership".
- **Owner**: manages organisation settings and users and has full organisation visibility.
- **Dispatcher**: FieldDesk's operational equivalent of KBN's Supervisor; creates, schedules, assigns and updates work orders.
- **Technician**: sees only work orders assigned to them and submits progress.

## Accepted decisions

1. Use React with TypeScript and Vite for the frontend.
2. Use Django, Django REST Framework and SimpleJWT for the API.
3. Use PostgreSQL as the sole source of truth; use Redis for Celery and real-time fan-out.
4. Use Celery as the independently runnable worker.
5. Use Server-Sent Events (SSE) for one-way dashboard updates. It is simpler than WebSockets for this requirement and supports browser reconnection.
6. Use UUID primary keys and separate human-readable work-order reference numbers.
7. A user belongs to exactly one organisation in the assessment implementation. `OrganisationUser` still makes the relationship explicit and can later support multiple organisations.
8. Authentication uses email and password. Access tokens are short-lived; rotating refresh tokens are stored in secure HttpOnly cookies. Logout blacklists the refresh token.
9. Work-order statuses are `draft`, `scheduled`, `in_progress`, `blocked`, `completed`, and `cancelled`.
10. Priorities are `low`, `medium`, `high`, and `urgent`.
11. Scheduled intervals are half-open: `[start, end)`. Therefore, 10:00-12:00 and 12:00-14:00 do not overlap.
12. All timestamps are stored in UTC and returned as ISO-8601 UTC timestamps.
13. Owners and Dispatchers can create, edit, assign and schedule work orders. Technicians can change operational status only through the progress-event API.
14. Owners and Dispatchers can view all work orders in their organisation. Technicians can view only assigned work orders.
15. Owners and Dispatchers can export work orders. Technicians cannot export.
16. Owners manage users, roles and organisation settings. Roles are fixed system roles for the assessment, not user-defined permission bundles.
17. Attachments support JPEG, PNG and PDF. Initial defaults: 10 MiB per file and 100 MiB per organisation, configurable by environment/settings.
18. Normal API deletion is soft deletion where appropriate. Immutable audit records and accepted progress events cannot be updated or deleted through normal APIs.

## Security invariants

- The authenticated `OrganisationUser` is the only source of organisation and role authority.
- Client-supplied organisation or role values are ignored or rejected.
- Every organisation-owned lookup includes the authenticated organisation.
- Cross-organisation access returns `404` to avoid confirming object existence.
- Authorization is enforced in the backend even when the frontend hides an action.
- Side effects are published only after a successful database commit.

## Items that remain configurable

- Branding and exact visual styling.
- Default page size and maximum export size.
- Token lifetimes, storage quotas and upload limits.
- Mock notification provider outcome selection in non-production environments.

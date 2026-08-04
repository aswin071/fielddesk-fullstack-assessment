# Assessment brief

## Scenario

FieldDesk is a fictional multi-tenant platform used by maintenance companies to schedule and track field-service work.

Each organisation has its own users, technicians, work orders, attachments and activity history. Information belonging to one organisation must never be accessible by another organisation.

Build a functional full-stack application using the required stack. The application should be straightforward for a reviewer to start, test and understand.

## 1. Authentication, roles and organisation isolation

Provide seed data for two separate organisations. Each organisation should have users representing these roles:

- **Owner:** manages users and organisation settings.
- **Dispatcher:** creates, schedules, assigns and updates work orders.
- **Technician:** views assigned work and submits progress updates.

Implement:

- Secure login and logout
- Secure password storage
- Authenticated API requests
- Backend-enforced role permissions
- Organisation scope derived from the authenticated identity
- Protection against cross-organisation access when IDs, URLs or request payloads are changed manually

The frontend must not be treated as a security boundary. Organisation or role values supplied by the client must not be trusted as authority.

## 2. Work-order management

A work order contains:

- Reference number
- Title and description
- Priority
- Status
- Assigned technician
- Scheduled start and end time
- Site name
- Attachments
- Organisation and creator
- Created and updated timestamps

Authorised users should be able to:

- Create and edit work orders
- Assign a technician
- Update status
- Search, filter, sort and paginate the work-order list
- View an individual work order and its activity history
- View summary counts on a dashboard

Apply the role restrictions described above consistently across the API and interface.

## 3. Scheduling and concurrent requests

A technician cannot be assigned to overlapping work orders.

The implementation must remain correct if two dispatchers attempt conflicting assignments at approximately the same time.

Requirements:

- Validate scheduling windows.
- Prevent overlapping assignments under concurrency.
- Use appropriate database constraints, locking and/or transaction boundaries.
- Return a meaningful conflict response.
- Include an automated concurrency test.
- Explain why the chosen approach remains safe when more than one API instance is running.

A frontend-only availability check or an in-memory lock is not sufficient.

## 4. Progress-event API

Technicians can submit progress events for assigned work orders.

Example request:

```json
{
  "eventId": "evt-10001",
  "workOrderId": "work-order-id",
  "type": "status_changed",
  "occurredAt": "2026-08-04T10:30:00Z",
  "payload": {
    "status": "in_progress",
    "note": "Work started"
  }
}
```

Requirements:

- Treat the complete request as untrusted input.
- Validate the event type, timestamp and payload.
- Verify that the authenticated user may act on the referenced work order.
- Preserve the original accepted event as an immutable audit record.
- Process each `eventId` only once.
- Handle simultaneous duplicate submissions safely.
- Apply the work-order update atomically.
- Avoid partial database changes when processing fails.
- Return clear and consistent API responses.

Document the idempotency mechanism and transaction boundary.

## 5. Attachments and storage limits

Allow authorised users to attach image or PDF files to work orders.

Requirements:

- Validate file type and size on the backend.
- Generate safe storage identifiers and do not trust the original filename.
- Prevent unauthorised attachment access.
- Track storage usage per organisation.
- Enforce a configurable organisation storage limit.
- Do not expose local filesystem paths through the API.
- Explain how local storage would be replaced by object storage in production.

Local file storage is acceptable for the assessment.

## 6. Background processing

When a work order is assigned, enqueue a job that simulates notifying the technician through an external provider.

The worker must:

- Run independently from the API.
- Retry temporary failures with backoff.
- Avoid producing duplicate notifications.
- Distinguish temporary failures from permanent failures.
- Record attempts and final outcomes.
- Stop retrying permanently invalid jobs.
- Produce useful diagnostic logs.

No third-party account is required. Provide a controllable mock provider that can simulate success, temporary failure and permanent failure.

## 7. Real-time updates

The dashboard should receive work-order changes without a full-page refresh. Use WebSockets or Server-Sent Events.

Requirements:

- Authenticate the real-time connection.
- Enforce organisation isolation.
- Avoid sending one organisation's events to another.
- Handle client reconnection.
- Document behaviour when real-time delivery is temporarily unavailable.

## 8. Audit history

Record relevant user and system actions, including:

- Work-order creation
- Assignment changes
- Status changes
- Attachment addition
- User-role changes
- Notification outcomes

Audit entries should identify the organisation, actor, action, target, timestamp and relevant before-and-after information. Audit history must not be editable through the normal API.

## 9. Frontend

Provide:

- Login screen
- Dashboard
- Work-order list with search, filters, sorting and pagination
- Create and edit forms
- Work-order details and activity history
- Technician assignment and scheduling
- Attachment upload
- Clear loading, empty, validation, conflict and error states
- A responsive layout suitable for desktop and mobile browsers

The frontend must communicate with persisted application data through the backend API. Visual polish is welcome, but correctness and usability are more important.

## 10. Reporting

Provide an organisation-scoped CSV export of filtered work-order data.

Requirements:

- Apply the same authorisation rules as the list API.
- Exclude other organisations' records.
- Prevent spreadsheet-formula injection.
- Avoid loading unnecessary data into memory for a large export.
- Include an automated test for organisation isolation.

## 11. API and operational quality

Include:

- Centralised input validation
- A consistent API error format
- Request correlation IDs
- Structured logging
- Health and readiness endpoints
- Graceful shutdown
- Environment-based configuration
- Database migrations and seed data
- Rate limiting for authentication and event submission
- Appropriate database indexes
- No secrets in source control

## 12. Automated testing

Include meaningful tests covering at least:

- Successful and failed authentication
- Role restrictions
- Cross-organisation access attempts
- Cross-organisation real-time isolation
- Work-order validation
- Concurrent scheduling conflicts
- Duplicate and concurrent event submission
- Transaction rollback
- Attachment type, size, quota and access control
- Worker retries and duplicate delivery
- Organisation-scoped CSV export
- One important frontend workflow

Tests should demonstrate externally visible behaviour rather than only verifying that mocked functions were called. Use a real PostgreSQL instance for tests where database behaviour, constraints or concurrency are material.

## 13. Local operation and documentation

The complete application should run locally using documented commands.

Provide:

- `docker-compose.yml`
- `.env.example` containing no real secrets
- PostgreSQL migrations
- Seed data for two organisations and all three roles
- Sample login credentials
- Startup, test, lint and build commands
- Architecture and folder-structure explanation
- Database model
- Authentication, authorisation and tenant-isolation approach
- Transaction, idempotency and concurrency decisions
- Queue retry and failure behaviour
- Scaling considerations
- Deployment and monitoring approach
- Backup and recovery considerations
- Assumptions, limitations and incomplete areas

## Expected repository structure

You may adjust the structure if your framework has a strong convention, but keep responsibilities clear.

```text
.
|-- frontend/
|-- backend/
|-- worker/
|-- database/
|   `-- migrations/
|-- tests/
|-- candidate-submission/
|   |-- AI_USAGE.md
|   `-- TECHNICAL_NOTES.md
|-- .env.example
|-- docker-compose.yml
`-- README.md
```

## Completion

Aim for a coherent, working implementation. If any requirement is incomplete, state it clearly in the technical notes and explain what remains. Undisclosed gaps are viewed less favourably than transparent, well-reasoned limitations.

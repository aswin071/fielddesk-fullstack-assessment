# Security and Organisation Isolation

## Trust boundaries

Request bodies, path IDs, query parameters, filenames, MIME declarations, JWT claims presented by clients and progress-event payloads are untrusted. Authority is resolved from validated authentication and current database state.

## Authentication

- Passwords use Django's password hashing framework and configured validators.
- JWT access tokens authenticate API and SSE requests.
- Refresh tokens rotate and are blacklisted after rotation/logout.
- Login and progress-event endpoints are throttled by both identity and source address.
- Authentication errors do not disclose whether an email exists.
- Inactive OrganisationUsers cannot authenticate or refresh sessions.

## Authorisation

DRF defaults to `IsAuthenticated`. Public endpoints are explicitly marked. Role permissions are composed with OR semantics where appropriate.

Every request resolves:

```text
authenticated User -> active OrganisationUser -> Organisation + Role
```

Every organisation-owned query includes `organisation=actor.organisation`. Object IDs are never fetched globally and checked afterward.

## Tenant-safe write pattern

1. Resolve the active OrganisationUser from the authenticated user.
2. Load the target through an organisation-scoped selector.
3. Reject client organisation/role authority fields.
4. Validate role and object relationship.
5. Execute the service in a transaction.
6. Write an audit entry in the same transaction.
7. Publish queue/realtime effects through `transaction.on_commit`.

## Attachments

- Validate configured size, extension and detected content type.
- Generate a random storage key; retain the sanitized original name only as metadata.
- Serve downloads through an authenticated, organisation-scoped endpoint.
- Never return local paths or publicly addressable unprotected media URLs.

## Additional controls

- Strict CORS allowlist; credentials are never combined with wildcard origins.
- Environment-only secrets and committed `.env.example` placeholders.
- Security headers and HTTPS assumptions documented for deployment.
- Correlation IDs in responses and structured logs.
- Safe error responses exclude tracebacks and internal exception messages.
- CSV cells beginning with formula-control characters are escaped.
- Audit and progress-event records have no normal update/delete endpoints.

## Required isolation tests

For every read, write, attachment, export and real-time channel, tests use two organisations and attempt access with valid credentials from the wrong organisation. Changing IDs or request values must never cross the boundary.

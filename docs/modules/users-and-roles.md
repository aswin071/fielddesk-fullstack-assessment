# Users and Roles Module

## Purpose

Manages an organisation's users through the explicit `OrganisationUser` relationship.

## Permission matrix

| Action | Owner | Dispatcher | Technician |
|---|---:|---:|---:|
| List/view organisation users | Yes | Technician list for assignment | No |
| Create user | Yes | No | No |
| Change role/status | Yes | No | No |
| Edit own basic profile | Yes | Yes | Yes |

## API

- `GET/POST /api/v1/users`
- `GET/PATCH /api/v1/users/{id}`
- `GET/PATCH /api/v1/profile`
- `GET /api/v1/technicians` — assignment-safe subset

## Rules

- Owner cannot create a user in another organisation.
- Role and organisation are set by the service, not blindly saved from a serializer.
- Deactivating an assigned technician does not rewrite history; new assignments are forbidden.
- Role/status changes create immutable audit entries with before/after values.
- The final active Owner cannot demote or deactivate themselves.

## Tests

Role restrictions, last-owner protection, cross-organisation IDs, payload injection and audit creation.

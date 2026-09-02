# Organisations Module

## Purpose

Defines the top-level tenant boundary, organisation settings and storage quota state.

## Rules

- Organisation is never selected from client authority fields.
- An authenticated request obtains its organisation through the active `OrganisationUser`.
- Owner may read/update safe organisation settings. Other roles may read only display-safe organisation information needed by the UI.
- Slug and quota changes are owner/admin-controlled and validated.
- Organisation deletion/deactivation is not exposed in the assessment API.

## API

- `GET /api/v1/organisation`
- `PATCH /api/v1/organisation` — Owner only

## Acceptance criteria

- Users cannot retrieve or update another organisation by changing an ID.
- Organisation and storage fields cannot be reassigned through payload injection.
- Quota counters never become negative and remain correct during concurrent uploads.

# Frontend Module

## Purpose

Provides a responsive React/TypeScript interface backed entirely by persisted API data.

## Routes

- `/login`
- `/dashboard`
- `/work-orders`
- `/work-orders/new`
- `/work-orders/:id`
- `/work-orders/:id/edit`
- `/users` and `/organisation` for Owner

## Architecture

- React Router for routes.
- TanStack Query for server state, invalidation and retry policy.
- Controlled, labelled HTML forms provide immediate browser validation; backend serializers remain the authoritative validation boundary.
- A typed API client normalizes standard errors, automatically refreshes access tokens through the HttpOnly refresh cookie and supports authenticated file downloads.
- Authentication context keeps the access token in memory only. Reload restoration uses refresh-cookie rotation; logout reloads and clears all cached tenant data.
- An authenticated streaming-fetch SSE client invalidates TanStack Query data. Disconnects retry automatically and `sync_required` causes authoritative REST refetches.

## UX requirements

Dashboard counts, work-order search/filter/sort/pagination, creation/editing, assignment/scheduling, attachment upload and activity history. Every screen includes accessible loading, empty, validation, forbidden, conflict and unexpected-error states. A 409 scheduling conflict remains visible with actionable scheduling guidance.

Role-based navigation improves usability but never substitutes for API authorization. Layout supports desktop and mobile browsers with keyboard navigation, labels, focus management and sufficient contrast.

## Implemented ERP experience

- Persistent desktop sidebar, compact top bar, role/organisation identity and mobile navigation drawer.
- Operational dashboard with KPI cards, recent work and status distribution.
- Dense work-order table with search, filters, ordering, pagination and CSV export.
- Create/edit forms and a detailed work-order workspace.
- Dispatcher/Owner assignment scheduling with visible HTTP 409 conflict guidance.
- Technician progress submission with optional notes.
- Protected attachment upload/download/removal and immutable activity timeline.
- Owner people/role/status administration and organisation/storage settings.
- Loading, empty, error and disabled/pending states throughout.

Routes and actions are hidden when irrelevant to a role, while every API still independently enforces authorization. Technician report/create/edit/scheduling controls and Owner administration routes are not rendered for unauthorized roles.

## Tests

The automated frontend workflow performs refresh-session bootstrap, signs in as a Dispatcher through the typed API client, loads persisted dashboard metrics and verifies role-appropriate work-order actions. Backend integration tests separately cover create/schedule conflicts and all security boundaries. Lint, Vitest and the TypeScript/Vite production build run both locally and inside the frontend container.

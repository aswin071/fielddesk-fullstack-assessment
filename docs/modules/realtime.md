# Real-time Updates Module

## Purpose

Updates dashboards after committed work-order changes without a full-page refresh.

## Transport

Use authenticated Server-Sent Events at `GET /api/v1/realtime/events`. The connection authenticates with the normal JWT `Authorization` header, resolves the active OrganisationUser and subscribes only to a server-generated organisation channel. The frontend uses a streaming `fetch` client because native browser `EventSource` cannot set this header safely; access tokens are never placed in query strings.

Events contain an allowlisted event type, target UUID, Redis-generated per-organisation cursor, timestamp and minimal change metadata. They do not trust a client-supplied organisation channel. Redis messages are filtered into this safe envelope before delivery.

## Delivery behavior

- Business services publish only through `transaction.on_commit()`.
- Redis fan-out distributes events across API instances.
- The authenticated frontend streaming client reconnects after disconnects.
- Redis Pub/Sub intentionally has no replay log. A reconnect with `Last-Event-ID` receives `sync_required`, causing the frontend to refetch current list/detail/dashboard state; SSE is an invalidation hint, not the source of truth.
- Temporary realtime unavailability does not block committed writes.
- Heartbeats keep proxies from treating an idle connection as abandoned. Connections rotate after a configured maximum lifetime so JWT and current organisation access are revalidated.

Published mutation hints cover work-order creation/editing, assignment, technician progress, attachment addition/deletion and notification outcomes. Notification queueing and realtime publication are separate post-commit callbacks.

Each organisation has a distinct Redis channel derived exclusively from authenticated database identity. PostgreSQL remains authoritative; Redis channel contents never grant access. Multiple API containers may subscribe and publish without in-process coordination.

## Tests

Authenticated connection, rejected unauthenticated connection, cross-organisation isolation, post-commit-only emission, reconnect/refetch behavior and safe payloads.

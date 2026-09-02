# Attachments Module

## Purpose

Stores authorised work-order images/PDFs while enforcing access controls and organisation quotas.

## API

- `POST /api/v1/work-orders/{id}/attachments`
- `GET /api/v1/work-orders/{id}/attachments`
- `GET /api/v1/work-orders/{id}/attachments/{attachmentId}`
- `DELETE /api/v1/work-orders/{id}/attachments/{attachmentId}` where policy permits

## Upload flow

1. Organisation-scope the work order and authorize the actor.
2. Stream to a disk-spillable bounded temporary upload; validate actual magic bytes, declared type, extension, non-empty content and configured size against JPEG/PNG/PDF allowlists.
3. Generate an opaque UUID storage key and checksum; never use the original filename as a path.
4. In a transaction, lock Organisation, verify remaining quota, create metadata, increment usage and write the immutable audit entry.
5. Finalize storage safely; compensate/clean temporary data if persistence fails.
6. Publish realtime activity after commit.

## Access

Downloads go through Django authorization and organisation/object checks. The API returns metadata/content responses, never filesystem paths. Production uses the same interface with a private object-storage bucket and short-lived signed delivery after authorization.

Owners and Dispatchers can access attachments on their organisation's visible work orders. A Technician can list, upload and download only on their currently assigned work orders. Only Owners and Dispatchers can delete. Cross-organisation and unauthorized assignment lookups return `404`.

Local files are accessed only through Django's storage abstraction and protected API endpoint. For production, configure a private S3-compatible storage backend for `default_storage`; retain opaque keys, disable public bucket access and replace streamed delivery with a short-lived signed URL created only after the same database authorization checks. Object-storage lifecycle rules can remove abandoned keys, while durable cleanup jobs handle transient deletion failures.

Quota accounting serializes on the PostgreSQL Organisation row. This keeps the limit correct across concurrent uploads and horizontally scaled API containers. Deletion soft-deletes metadata, restores quota under the same lock and removes the stored object after commit.

## Tests

Type spoofing, oversized/empty file, path-like filename, quota boundary/concurrency, unauthorized access, cross-organisation IDs, storage cleanup and quota restoration.

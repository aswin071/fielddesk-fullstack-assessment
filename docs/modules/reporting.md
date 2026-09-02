# Reporting Module

## Purpose

Exports filtered work orders as an organisation-safe CSV without excessive memory usage or spreadsheet execution risks.

## API

- `GET /api/v1/reports/work-orders.csv`

Owner and Dispatcher only. It accepts the same allowlisted filters and ordering as the work-order list and invokes the same organisation-scoped selector.

## Safety and performance

- Never accepts organisation authority from request parameters.
- Uses a streaming HTTP response and queryset iteration rather than building the entire file in memory.
- Selects only required columns and uses `select_related` where appropriate.
- Prefixes cells whose first non-whitespace character is `=`, `+`, `-` or `@` with a single quote.
- Uses a fixed header/schema and safe CSV quoting.
- Logs correlation and completion metadata without report contents.

## Implemented schema

The fixed columns are reference number, title, description, priority, status, technician name/email, scheduled start/end, site name, creator email and created/updated timestamps. Timestamps are emitted as ISO-8601 UTC values.

The endpoint validates query parameters with `WorkOrderFilterSerializer` and passes the result to `filtered_work_orders`, exactly like the list API. Organisation is always taken from the authenticated Owner or Dispatcher. A supplied organisation-like query parameter has no authority and cannot alter the queryset.

Rows use `values_list(...).iterator(chunk_size=...)`, so Django/psycopg fetch database results in configured chunks and the HTTP response yields one CSV row at a time. Attachments, audit payloads and other unrelated relationships are not loaded. A count query enforces the configured maximum before response headers are sent; oversized exports return `413 EXPORT_TOO_LARGE` rather than silently truncating.

All cells are rendered as strings and checked after leading whitespace. Values beginning with `=`, `+`, `-` or `@` receive a leading apostrophe before Python's CSV writer performs standards-compliant quoting. This covers direct and whitespace-prefixed spreadsheet formulas while preserving commas, quotes and newlines as data.

Responses use `text/csv`, attachment disposition, `nosniff` and private/no-store caching. Completion logs contain correlation ID and row count but never report contents.

## Tests

Filtered equivalence with list API, role restriction, two-organisation isolation, formula injection, CSV escaping and streaming behavior.

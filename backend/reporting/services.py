import csv
import logging

from django.conf import settings

logger = logging.getLogger("fielddesk.reporting")
CSV_HEADER = (
    "Reference Number",
    "Title",
    "Description",
    "Priority",
    "Status",
    "Technician Name",
    "Technician Email",
    "Scheduled Start",
    "Scheduled End",
    "Site Name",
    "Creator Email",
    "Created At",
    "Updated At",
)
EXPORT_FIELDS = (
    "reference_number",
    "title",
    "description",
    "priority",
    "status",
    "assigned_technician__user__first_name",
    "assigned_technician__user__last_name",
    "assigned_technician__user__email",
    "scheduled_start",
    "scheduled_end",
    "site_name",
    "creator__user__email",
    "created_at",
    "updated_at",
)
FORMULA_PREFIXES = {"=", "+", "-", "@"}


class CsvEcho:
    def write(self, value):
        return value


def safe_csv_cell(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        rendered = value.isoformat().replace("+00:00", "Z")
    else:
        rendered = str(value)
    first_non_whitespace = rendered.lstrip()[:1]
    if first_non_whitespace in FORMULA_PREFIXES:
        return f"'{rendered}"
    return rendered


def work_order_csv_rows(queryset, *, correlation_id):
    writer = csv.writer(CsvEcho())
    row_count = 0
    yield writer.writerow(CSV_HEADER)
    rows = queryset.values_list(*EXPORT_FIELDS).iterator(
        chunk_size=settings.REPORT_EXPORT_CHUNK_SIZE
    )
    try:
        for row in rows:
            (
                reference,
                title,
                description,
                priority,
                status,
                technician_first_name,
                technician_last_name,
                technician_email,
                scheduled_start,
                scheduled_end,
                site_name,
                creator_email,
                created_at,
                updated_at,
            ) = row
            technician_name = " ".join(
                part for part in (technician_first_name, technician_last_name) if part
            )
            yield writer.writerow(
                safe_csv_cell(value)
                for value in (
                    reference,
                    title,
                    description,
                    priority,
                    status,
                    technician_name,
                    technician_email,
                    scheduled_start,
                    scheduled_end,
                    site_name,
                    creator_email,
                    created_at,
                    updated_at,
                )
            )
            row_count += 1
    finally:
        logger.info(
            "work_order_export_finished",
            extra={
                "event": "work_order_export_finished",
                "correlationId": correlation_id,
                "rowCount": row_count,
            },
        )

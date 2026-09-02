import json

from django.core.serializers.json import DjangoJSONEncoder

from audit.models import AuditEntry
from common.context import get_correlation_id


def json_safe(value):
    return json.loads(json.dumps(value or {}, cls=DjangoJSONEncoder))


def record_audit(
    *,
    organisation,
    action,
    target_type,
    target_id,
    actor=None,
    related_work_order=None,
    before=None,
    after=None,
    metadata=None,
):
    entry = AuditEntry(
        organisation=organisation,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        related_work_order=related_work_order,
        correlation_id=get_correlation_id() or "",
        before=json_safe(before),
        after=json_safe(after),
        metadata=json_safe(metadata),
    )
    entry.full_clean()
    entry.save()
    return entry

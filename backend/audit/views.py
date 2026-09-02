from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from audit.models import AuditEntry
from audit.serializers import AuditEntrySerializer
from common.actor import resolve_actor
from common.pagination import FieldDeskPageNumberPagination
from workorders.selectors import visible_work_orders


class WorkOrderActivityView(APIView):
    def get(self, request, work_order_id):
        actor = resolve_actor(request)
        work_order = get_object_or_404(visible_work_orders(actor), pk=work_order_id)
        entries = (
            AuditEntry.objects.for_organisation(actor.organisation)
            .filter(related_work_order=work_order)
            .select_related("actor__user")
        )
        paginator = FieldDeskPageNumberPagination()
        page = paginator.paginate_queryset(entries, request, view=self)
        return paginator.get_paginated_response(AuditEntrySerializer(page, many=True).data)

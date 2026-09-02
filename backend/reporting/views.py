from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework.views import APIView

from common.actor import resolve_actor
from common.context import get_correlation_id
from common.exceptions import ExportTooLargeError
from common.permissions import IsOwnerOrDispatcher
from reporting.services import work_order_csv_rows
from workorders.selectors import filtered_work_orders
from workorders.serializers import WorkOrderFilterSerializer


class WorkOrderCsvExportView(APIView):
    permission_classes = [IsOwnerOrDispatcher]

    def get(self, request):
        actor = resolve_actor(request)
        filters = WorkOrderFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        queryset = filtered_work_orders(actor, filters.validated_data)
        if queryset.count() > settings.REPORT_EXPORT_MAX_ROWS:
            raise ExportTooLargeError()

        response = StreamingHttpResponse(
            work_order_csv_rows(queryset, correlation_id=get_correlation_id()),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = 'attachment; filename="fielddesk-work-orders.csv"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response

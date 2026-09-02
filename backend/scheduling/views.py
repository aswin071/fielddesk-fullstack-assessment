from rest_framework.views import APIView

from common.actor import resolve_actor
from common.permissions import IsOwnerOrDispatcher
from common.responses import success_response
from scheduling.serializers import WorkOrderAssignmentSerializer
from scheduling.services import assign_work_order
from workorders.selectors import visible_work_orders
from workorders.serializers import WorkOrderSerializer


class WorkOrderAssignmentView(APIView):
    permission_classes = [IsOwnerOrDispatcher]

    def post(self, request, work_order_id):
        actor = resolve_actor(request)
        serializer = WorkOrderAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work_order = assign_work_order(
            actor=actor,
            work_order_id=work_order_id,
            **serializer.validated_data,
        )
        work_order = visible_work_orders(actor).get(pk=work_order.pk)
        return success_response(WorkOrderSerializer(work_order).data)


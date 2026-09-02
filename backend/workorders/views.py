from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from common.actor import resolve_actor
from common.pagination import FieldDeskPageNumberPagination
from common.permissions import IsOwnerOrDispatcher
from common.responses import success_response
from workorders.models import WorkOrderPriority, WorkOrderStatus
from workorders.selectors import filtered_work_orders, visible_work_orders
from workorders.serializers import (
    WorkOrderCreateSerializer,
    WorkOrderFilterSerializer,
    WorkOrderSerializer,
    WorkOrderUpdateSerializer,
)
from workorders.services import create_work_order, update_work_order


class WorkOrderListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsOwnerOrDispatcher()]
        return super().get_permissions()

    def get(self, request):
        actor = resolve_actor(request)
        filters = WorkOrderFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        queryset = filtered_work_orders(actor, filters.validated_data)
        paginator = FieldDeskPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(WorkOrderSerializer(page, many=True).data)

    def post(self, request):
        actor = resolve_actor(request)
        serializer = WorkOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work_order = create_work_order(actor=actor, validated_data=serializer.validated_data)
        work_order = visible_work_orders(actor).get(pk=work_order.pk)
        return success_response(
            WorkOrderSerializer(work_order).data,
            status_code=status.HTTP_201_CREATED,
        )


class WorkOrderDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsOwnerOrDispatcher()]
        return super().get_permissions()

    def get_object(self, actor, work_order_id):
        return get_object_or_404(visible_work_orders(actor), pk=work_order_id)

    def get(self, request, work_order_id):
        actor = resolve_actor(request)
        return success_response(WorkOrderSerializer(self.get_object(actor, work_order_id)).data)

    def patch(self, request, work_order_id):
        actor = resolve_actor(request)
        work_order = self.get_object(actor, work_order_id)
        serializer = WorkOrderUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = update_work_order(
            actor=actor,
            work_order=work_order,
            validated_data=serializer.validated_data,
        )
        updated = visible_work_orders(actor).get(pk=updated.pk)
        return success_response(WorkOrderSerializer(updated).data)


class DashboardSummaryView(APIView):
    def get(self, request):
        actor = resolve_actor(request)
        queryset = visible_work_orders(actor)
        aggregate = queryset.aggregate(
            total=Count("id"),
            assigned=Count("id", filter=Q(assigned_technician__isnull=False)),
            unassigned=Count("id", filter=Q(assigned_technician__isnull=True)),
            **{
                f"status_{choice.value}": Count("id", filter=Q(status=choice.value))
                for choice in WorkOrderStatus
            },
            **{
                f"priority_{choice.value}": Count("id", filter=Q(priority=choice.value))
                for choice in WorkOrderPriority
            },
        )
        return success_response(
            {
                "total": aggregate["total"],
                "assigned": aggregate["assigned"],
                "unassigned": aggregate["unassigned"],
                "byStatus": {
                    choice.value: aggregate[f"status_{choice.value}"]
                    for choice in WorkOrderStatus
                },
                "byPriority": {
                    choice.value: aggregate[f"priority_{choice.value}"]
                    for choice in WorkOrderPriority
                },
            }
        )


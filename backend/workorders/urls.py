from django.urls import path

from workorders.views import DashboardSummaryView, WorkOrderDetailView, WorkOrderListCreateView

urlpatterns = [
    path("work-orders", WorkOrderListCreateView.as_view(), name="work-order-list"),
    path(
        "work-orders/<uuid:work_order_id>",
        WorkOrderDetailView.as_view(),
        name="work-order-detail",
    ),
    path("dashboard/summary", DashboardSummaryView.as_view(), name="dashboard-summary"),
]


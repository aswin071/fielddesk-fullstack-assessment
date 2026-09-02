from django.urls import path

from audit.views import WorkOrderActivityView

urlpatterns = [
    path(
        "work-orders/<uuid:work_order_id>/activity",
        WorkOrderActivityView.as_view(),
        name="work-order-activity",
    ),
]

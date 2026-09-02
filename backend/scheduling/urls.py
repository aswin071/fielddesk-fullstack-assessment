from django.urls import path

from scheduling.views import WorkOrderAssignmentView

urlpatterns = [
    path(
        "work-orders/<uuid:work_order_id>/assign",
        WorkOrderAssignmentView.as_view(),
        name="work-order-assign",
    )
]


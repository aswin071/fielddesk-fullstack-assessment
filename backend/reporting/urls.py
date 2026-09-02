from django.urls import path

from reporting.views import WorkOrderCsvExportView

urlpatterns = [
    path(
        "reports/work-orders.csv",
        WorkOrderCsvExportView.as_view(),
        name="work-order-csv-export",
    ),
]

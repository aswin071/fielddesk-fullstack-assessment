from django.urls import path

from attachments.views import AttachmentCollectionView, AttachmentDetailView

urlpatterns = [
    path(
        "work-orders/<uuid:work_order_id>/attachments",
        AttachmentCollectionView.as_view(),
        name="attachment-collection",
    ),
    path(
        "work-orders/<uuid:work_order_id>/attachments/<uuid:attachment_id>",
        AttachmentDetailView.as_view(),
        name="attachment-detail",
    ),
]

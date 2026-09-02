from django.urls import path

from progress_events.views import ProgressEventCreateView

urlpatterns = [
    path("progress-events", ProgressEventCreateView.as_view(), name="progress-event-create")
]


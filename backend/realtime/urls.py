from django.urls import path

from realtime.views import RealtimeEventView

urlpatterns = [
    path("realtime/events", RealtimeEventView.as_view(), name="realtime-events"),
]

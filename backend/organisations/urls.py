from django.urls import path

from organisations.views import OrganisationView

urlpatterns = [path("", OrganisationView.as_view(), name="organisation-detail")]


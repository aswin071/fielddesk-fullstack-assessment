from django.urls import path

from users.views import OrganisationUserDetailView, OrganisationUserListCreateView

urlpatterns = [
    path("", OrganisationUserListCreateView.as_view(), name="organisation-user-list"),
    path("<uuid:user_id>", OrganisationUserDetailView.as_view(), name="organisation-user-detail"),
]


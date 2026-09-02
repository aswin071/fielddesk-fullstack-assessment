import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.tests.test_authentication import PASSWORD, create_account
from organisations.models import Organisation, OrganisationUser, OrganisationUserRole


def authenticated_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.mark.django_db
def test_dispatcher_lists_only_technicians_in_own_organisation():
    alpha = Organisation.objects.create(name="Alpha", slug="alpha")
    beta = Organisation.objects.create(name="Beta", slug="beta")
    dispatcher, _ = create_account(
        alpha, "dispatcher@alpha.test", OrganisationUserRole.DISPATCHER
    )
    create_account(alpha, "technician@alpha.test", OrganisationUserRole.TECHNICIAN)
    create_account(beta, "technician@beta.test", OrganisationUserRole.TECHNICIAN)

    response = authenticated_client(dispatcher).get("/api/v1/users/")

    assert response.status_code == 200
    assert [item["email"] for item in response.data["data"]] == ["technician@alpha.test"]


@pytest.mark.django_db
def test_dispatcher_cannot_create_users():
    organisation = Organisation.objects.create(name="Alpha", slug="alpha")
    dispatcher, _ = create_account(
        organisation, "dispatcher@alpha.test", OrganisationUserRole.DISPATCHER
    )

    response = authenticated_client(dispatcher).post(
        "/api/v1/users/",
        {
            "email": "new@alpha.test",
            "firstName": "New",
            "password": PASSWORD,
            "role": OrganisationUserRole.TECHNICIAN,
        },
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_owner_cannot_update_another_organisations_user():
    alpha = Organisation.objects.create(name="Alpha", slug="alpha")
    beta = Organisation.objects.create(name="Beta", slug="beta")
    owner, _ = create_account(alpha, "owner@alpha.test")
    _, beta_technician = create_account(
        beta, "technician@beta.test", OrganisationUserRole.TECHNICIAN
    )

    response = authenticated_client(owner).patch(
        f"/api/v1/users/{beta_technician.id}",
        {"isActive": False},
        format="json",
    )

    assert response.status_code == 404
    beta_technician.refresh_from_db()
    assert beta_technician.is_active is True


@pytest.mark.django_db
def test_client_organisation_value_cannot_change_creation_scope():
    alpha = Organisation.objects.create(name="Alpha", slug="alpha")
    beta = Organisation.objects.create(name="Beta", slug="beta")
    owner, _ = create_account(alpha, "owner@alpha.test")

    response = authenticated_client(owner).post(
        "/api/v1/users/",
        {
            "email": "technician@alpha.test",
            "firstName": "Tech",
            "password": PASSWORD,
            "role": OrganisationUserRole.TECHNICIAN,
            "organisation": str(beta.id),
        },
        format="json",
    )

    assert response.status_code == 201
    created = OrganisationUser.objects.get(id=response.data["data"]["id"])
    assert created.organisation == alpha


@pytest.mark.django_db
def test_final_active_owner_cannot_be_demoted():
    organisation = Organisation.objects.create(name="Alpha", slug="alpha")
    owner, organisation_owner = create_account(organisation, "owner@alpha.test")

    response = authenticated_client(owner).patch(
        f"/api/v1/users/{organisation_owner.id}",
        {"role": OrganisationUserRole.DISPATCHER},
        format="json",
    )

    assert response.status_code == 400
    organisation_owner.refresh_from_db()
    assert organisation_owner.role == OrganisationUserRole.OWNER

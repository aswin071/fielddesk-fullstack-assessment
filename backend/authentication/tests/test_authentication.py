import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from organisations.models import Organisation, OrganisationUser, OrganisationUserRole
from users.models import User

PASSWORD = "StrongDemo!2026"


@pytest.fixture
def organisations(db):
    return (
        Organisation.objects.create(name="Alpha Services", slug="alpha"),
        Organisation.objects.create(name="Beta Services", slug="beta"),
    )


def create_account(organisation, email, role=OrganisationUserRole.OWNER, password=PASSWORD):
    user = User.objects.create_user(
        email=email,
        password=password,
        first_name="Test",
        last_name="User",
    )
    organisation_user = OrganisationUser.objects.create(
        organisation=organisation,
        user=user,
        role=role,
    )
    return user, organisation_user


def bearer_client(access_token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client


@pytest.mark.django_db
def test_login_returns_access_token_and_secure_refresh_cookie(organisations, settings):
    settings.JWT_REFRESH_COOKIE_SECURE = False
    user, _ = create_account(organisations[0], "owner@alpha.test")

    response = APIClient().post(
        "/api/v1/auth/login",
        {"email": "OWNER@ALPHA.TEST", "password": PASSWORD},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["accessToken"]
    assert response.data["data"]["organisation"]["id"] == str(organisations[0].id)
    cookie = response.cookies[settings.JWT_REFRESH_COOKIE_NAME]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Strict"
    assert user.password != PASSWORD
    assert user.check_password(PASSWORD)


@pytest.mark.django_db
def test_failed_login_is_generic_for_unknown_email_and_wrong_password(organisations):
    create_account(organisations[0], "owner@alpha.test")
    client = APIClient()

    unknown = client.post(
        "/api/v1/auth/login",
        {"email": "unknown@example.test", "password": "WrongPassword!"},
        format="json",
    )
    wrong = client.post(
        "/api/v1/auth/login",
        {"email": "owner@alpha.test", "password": "WrongPassword!"},
        format="json",
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.data["error"]["message"] == wrong.data["error"]["message"]


@pytest.mark.django_db
def test_me_derives_role_and_organisation_from_authenticated_user(organisations, settings):
    settings.JWT_REFRESH_COOKIE_SECURE = False
    create_account(organisations[0], "dispatcher@alpha.test", OrganisationUserRole.DISPATCHER)
    login = APIClient().post(
        "/api/v1/auth/login",
        {"email": "dispatcher@alpha.test", "password": PASSWORD},
        format="json",
    )
    client = bearer_client(login.data["data"]["accessToken"])

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.data["data"]["role"] == OrganisationUserRole.DISPATCHER
    assert response.data["data"]["organisation"]["slug"] == "alpha"


@pytest.mark.django_db
def test_refresh_rotates_cookie_and_logout_blacklists_session(organisations, settings):
    settings.JWT_REFRESH_COOKIE_SECURE = False
    create_account(organisations[0], "owner@alpha.test")
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login",
        {"email": "owner@alpha.test", "password": PASSWORD},
        format="json",
    )
    original_refresh = login.cookies[settings.JWT_REFRESH_COOKIE_NAME].value
    client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = original_refresh

    refreshed = client.post("/api/v1/auth/refresh", {}, format="json")

    assert refreshed.status_code == 200
    rotated_refresh = refreshed.cookies[settings.JWT_REFRESH_COOKIE_NAME].value
    assert rotated_refresh != original_refresh

    authenticated = bearer_client(refreshed.data["data"]["accessToken"])
    authenticated.cookies[settings.JWT_REFRESH_COOKIE_NAME] = rotated_refresh
    logout = authenticated.post("/api/v1/auth/logout", {}, format="json")
    assert logout.status_code == 200

    client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = rotated_refresh
    rejected = client.post("/api/v1/auth/refresh", {}, format="json")
    assert rejected.status_code == 401


@pytest.mark.django_db
def test_seed_command_creates_two_organisations_and_all_roles():
    call_command("seed_fielddesk")

    assert Organisation.objects.count() == 2
    for organisation in Organisation.objects.all():
        assert set(
            OrganisationUser.objects.for_organisation(organisation).values_list("role", flat=True)
        ) == {
            OrganisationUserRole.OWNER,
            OrganisationUserRole.DISPATCHER,
            OrganisationUserRole.TECHNICIAN,
        }


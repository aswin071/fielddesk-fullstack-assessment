from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.tests.test_authentication import create_account
from organisations.models import Organisation, OrganisationUserRole
from workorders.models import WorkOrderStatus
from workorders.tests.test_work_orders import create_order


def authenticated_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def scheduling_accounts(db):
    alpha = Organisation.objects.create(name="Alpha", slug="alpha")
    beta = Organisation.objects.create(name="Beta", slug="beta")
    alpha_owner, alpha_owner_role = create_account(alpha, "owner@alpha.test")
    alpha_dispatcher, alpha_dispatcher_role = create_account(
        alpha, "dispatcher@alpha.test", OrganisationUserRole.DISPATCHER
    )
    alpha_technician, alpha_technician_role = create_account(
        alpha, "technician@alpha.test", OrganisationUserRole.TECHNICIAN
    )
    beta_owner, beta_owner_role = create_account(beta, "owner@beta.test")
    return {
        "alpha": alpha,
        "beta": beta,
        "alpha_owner": alpha_owner,
        "alpha_owner_role": alpha_owner_role,
        "alpha_dispatcher": alpha_dispatcher,
        "alpha_dispatcher_role": alpha_dispatcher_role,
        "alpha_technician": alpha_technician,
        "alpha_technician_role": alpha_technician_role,
        "beta_owner": beta_owner,
        "beta_owner_role": beta_owner_role,
    }


def assignment_payload(technician_id, start, end):
    return {
        "technicianId": str(technician_id),
        "scheduledStart": start.isoformat(),
        "scheduledEnd": end.isoformat(),
    }


@pytest.mark.django_db
def test_dispatcher_assigns_technician_and_activates_schedule(scheduling_accounts):
    accounts = scheduling_accounts
    work_order = create_order(accounts["alpha"], accounts["alpha_owner_role"])
    start = timezone.now() + timedelta(days=1)

    response = authenticated_client(accounts["alpha_dispatcher"]).post(
        f"/api/v1/work-orders/{work_order.id}/assign",
        assignment_payload(accounts["alpha_technician_role"].id, start, start + timedelta(hours=2)),
        format="json",
    )

    assert response.status_code == 200
    work_order.refresh_from_db()
    assert work_order.assigned_technician == accounts["alpha_technician_role"]
    assert work_order.status == WorkOrderStatus.SCHEDULED
    assert response.data["data"]["assignedTechnician"]["id"] == str(
        accounts["alpha_technician_role"].id
    )


@pytest.mark.django_db
def test_overlapping_assignment_returns_meaningful_conflict(scheduling_accounts):
    accounts = scheduling_accounts
    start = timezone.now() + timedelta(days=1)
    create_order(
        accounts["alpha"],
        accounts["alpha_owner_role"],
        assigned_technician=accounts["alpha_technician_role"],
        scheduled_start=start,
        scheduled_end=start + timedelta(hours=2),
        status=WorkOrderStatus.SCHEDULED,
    )
    second = create_order(accounts["alpha"], accounts["alpha_owner_role"])

    response = authenticated_client(accounts["alpha_dispatcher"]).post(
        f"/api/v1/work-orders/{second.id}/assign",
        assignment_payload(
            accounts["alpha_technician_role"].id,
            start + timedelta(hours=1),
            start + timedelta(hours=3),
        ),
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "SCHEDULE_CONFLICT"
    second.refresh_from_db()
    assert second.assigned_technician is None
    assert second.status == WorkOrderStatus.DRAFT


@pytest.mark.django_db
def test_adjacent_half_open_windows_are_allowed(scheduling_accounts):
    accounts = scheduling_accounts
    start = timezone.now() + timedelta(days=1)
    boundary = start + timedelta(hours=2)
    create_order(
        accounts["alpha"],
        accounts["alpha_owner_role"],
        assigned_technician=accounts["alpha_technician_role"],
        scheduled_start=start,
        scheduled_end=boundary,
        status=WorkOrderStatus.SCHEDULED,
    )
    second = create_order(accounts["alpha"], accounts["alpha_owner_role"])

    response = authenticated_client(accounts["alpha_owner"]).post(
        f"/api/v1/work-orders/{second.id}/assign",
        assignment_payload(
            accounts["alpha_technician_role"].id,
            boundary,
            boundary + timedelta(hours=2),
        ),
        format="json",
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_rescheduling_excludes_the_current_work_order(scheduling_accounts):
    accounts = scheduling_accounts
    start = timezone.now() + timedelta(days=1)
    work_order = create_order(
        accounts["alpha"],
        accounts["alpha_owner_role"],
        assigned_technician=accounts["alpha_technician_role"],
        scheduled_start=start,
        scheduled_end=start + timedelta(hours=1),
        status=WorkOrderStatus.SCHEDULED,
    )

    response = authenticated_client(accounts["alpha_dispatcher"]).post(
        f"/api/v1/work-orders/{work_order.id}/assign",
        assignment_payload(
            accounts["alpha_technician_role"].id,
            start + timedelta(hours=1),
            start + timedelta(hours=2),
        ),
        format="json",
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_cross_organisation_or_non_technician_assignment_is_hidden(scheduling_accounts):
    accounts = scheduling_accounts
    beta_technician, beta_technician_role = create_account(
        accounts["beta"], "technician@beta.test", OrganisationUserRole.TECHNICIAN
    )
    del beta_technician
    work_order = create_order(accounts["alpha"], accounts["alpha_owner_role"])
    start = timezone.now() + timedelta(days=1)
    client = authenticated_client(accounts["alpha_dispatcher"])

    wrong_organisation = client.post(
        f"/api/v1/work-orders/{work_order.id}/assign",
        assignment_payload(beta_technician_role.id, start, start + timedelta(hours=1)),
        format="json",
    )
    wrong_role = client.post(
        f"/api/v1/work-orders/{work_order.id}/assign",
        assignment_payload(
            accounts["alpha_owner_role"].id, start, start + timedelta(hours=1)
        ),
        format="json",
    )

    assert wrong_organisation.status_code == wrong_role.status_code == 404


@pytest.mark.django_db
def test_technician_cannot_assign_and_invalid_window_is_rejected(scheduling_accounts):
    accounts = scheduling_accounts
    work_order = create_order(accounts["alpha"], accounts["alpha_owner_role"])
    start = timezone.now() + timedelta(days=1)
    payload = assignment_payload(
        accounts["alpha_technician_role"].id,
        start,
        start - timedelta(minutes=1),
    )

    forbidden = authenticated_client(accounts["alpha_technician"]).post(
        f"/api/v1/work-orders/{work_order.id}/assign", payload, format="json"
    )
    invalid = authenticated_client(accounts["alpha_dispatcher"]).post(
        f"/api/v1/work-orders/{work_order.id}/assign", payload, format="json"
    )

    assert forbidden.status_code == 403
    assert invalid.status_code == 400
    assert "scheduledEnd" in invalid.data["error"]["fields"]


@pytest.mark.django_db
def test_past_schedule_is_rejected(scheduling_accounts):
    accounts = scheduling_accounts
    work_order = create_order(accounts["alpha"], accounts["alpha_owner_role"])
    start = timezone.now() - timedelta(hours=2)

    response = authenticated_client(accounts["alpha_dispatcher"]).post(
        f"/api/v1/work-orders/{work_order.id}/assign",
        assignment_payload(
            accounts["alpha_technician_role"].id,
            start,
            start + timedelta(hours=1),
        ),
        format="json",
    )

    assert response.status_code == 400
    assert "scheduledStart" in response.data["error"]["fields"]


@pytest.mark.django_db(transaction=True)
def test_concurrent_conflicting_api_assignments_allow_exactly_one(scheduling_accounts):
    accounts = scheduling_accounts
    first = create_order(accounts["alpha"], accounts["alpha_owner_role"])
    second = create_order(accounts["alpha"], accounts["alpha_owner_role"])
    start = timezone.now() + timedelta(days=1)
    payload = assignment_payload(
        accounts["alpha_technician_role"].id,
        start,
        start + timedelta(hours=2),
    )
    access_token = str(RefreshToken.for_user(accounts["alpha_dispatcher"]).access_token)
    barrier = Barrier(2)

    def submit(work_order_id):
        close_old_connections()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        barrier.wait(timeout=5)
        response = client.post(
            f"/api/v1/work-orders/{work_order_id}/assign",
            payload,
            format="json",
        )
        result = (response.status_code, response.data)
        close_old_connections()
        return result

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, (first.id, second.id)))

    statuses = sorted(status for status, _ in results)
    assert statuses == [200, 409]
    conflict_data = next(data for status, data in results if status == 409)
    assert conflict_data["error"]["code"] == "SCHEDULE_CONFLICT"

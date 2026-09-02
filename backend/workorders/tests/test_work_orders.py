import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.tests.test_authentication import create_account
from organisations.models import Organisation, OrganisationUserRole
from workorders.models import WorkOrder, WorkOrderPriority, WorkOrderStatus


def authenticated_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def work_order_accounts(db):
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


def create_order(organisation, creator, **overrides):
    number = WorkOrder.all_objects.filter(organisation=organisation).count() + 1
    defaults = {
        "organisation": organisation,
        "creator": creator,
        "reference_number": f"WO-TEST-{number:04d}",
        "title": f"Test order {number}",
        "description": "Routine maintenance",
        "priority": WorkOrderPriority.MEDIUM,
        "status": WorkOrderStatus.DRAFT,
        "site_name": "Main site",
    }
    defaults.update(overrides)
    return WorkOrder.objects.create(**defaults)


@pytest.mark.django_db
def test_owner_creates_work_order_with_server_authority(work_order_accounts):
    accounts = work_order_accounts
    response = authenticated_client(accounts["alpha_owner"]).post(
        "/api/v1/work-orders",
        {
            "title": "Repair cooling unit",
            "description": "Unit is not cooling",
            "priority": WorkOrderPriority.HIGH,
            "siteName": "Tower A",
            "organisation": str(accounts["beta"].id),
            "creatorId": str(accounts["beta_owner_role"].id),
            "assignedTechnicianId": str(accounts["alpha_technician_role"].id),
        },
        format="json",
    )

    assert response.status_code == 201
    work_order = WorkOrder.objects.get(id=response.data["data"]["id"])
    assert work_order.organisation == accounts["alpha"]
    assert work_order.creator == accounts["alpha_owner_role"]
    assert work_order.assigned_technician is None
    assert work_order.reference_number.startswith("WO-")
    assert response.data["data"]["referenceNumber"] == work_order.reference_number


@pytest.mark.django_db
def test_dispatcher_can_create_but_technician_cannot(work_order_accounts):
    payload = {"title": "Inspect pump", "siteName": "Plant room"}

    dispatcher_response = authenticated_client(work_order_accounts["alpha_dispatcher"]).post(
        "/api/v1/work-orders", payload, format="json"
    )
    technician_response = authenticated_client(work_order_accounts["alpha_technician"]).post(
        "/api/v1/work-orders", payload, format="json"
    )

    assert dispatcher_response.status_code == 201
    assert technician_response.status_code == 403


@pytest.mark.django_db
def test_list_never_exposes_another_organisation(work_order_accounts):
    accounts = work_order_accounts
    alpha_order = create_order(accounts["alpha"], accounts["alpha_owner_role"])
    create_order(accounts["beta"], accounts["beta_owner_role"])

    response = authenticated_client(accounts["alpha_owner"]).get("/api/v1/work-orders")

    assert response.status_code == 200
    assert [item["id"] for item in response.data["data"]] == [str(alpha_order.id)]
    assert response.data["meta"]["total"] == 1


@pytest.mark.django_db
def test_technician_sees_only_assigned_work(work_order_accounts):
    accounts = work_order_accounts
    assigned = create_order(
        accounts["alpha"],
        accounts["alpha_owner_role"],
        assigned_technician=accounts["alpha_technician_role"],
    )
    create_order(accounts["alpha"], accounts["alpha_owner_role"])

    response = authenticated_client(accounts["alpha_technician"]).get("/api/v1/work-orders")

    assert response.status_code == 200
    assert [item["id"] for item in response.data["data"]] == [str(assigned.id)]


@pytest.mark.django_db
def test_cross_organisation_detail_and_update_return_not_found(work_order_accounts):
    accounts = work_order_accounts
    beta_order = create_order(accounts["beta"], accounts["beta_owner_role"])
    client = authenticated_client(accounts["alpha_owner"])

    detail = client.get(f"/api/v1/work-orders/{beta_order.id}")
    update = client.patch(
        f"/api/v1/work-orders/{beta_order.id}", {"title": "Tampered"}, format="json"
    )

    assert detail.status_code == update.status_code == 404
    beta_order.refresh_from_db()
    assert beta_order.title != "Tampered"


@pytest.mark.django_db
def test_search_filter_sort_and_pagination(work_order_accounts):
    accounts = work_order_accounts
    create_order(
        accounts["alpha"],
        accounts["alpha_owner_role"],
        title="Boiler inspection",
        priority=WorkOrderPriority.HIGH,
    )
    create_order(
        accounts["alpha"],
        accounts["alpha_owner_role"],
        title="Replace lamp",
        priority=WorkOrderPriority.LOW,
    )

    response = authenticated_client(accounts["alpha_dispatcher"]).get(
        "/api/v1/work-orders",
        {"search": "boiler", "priority": "high", "ordering": "referenceNumber", "pageSize": 1},
    )

    assert response.status_code == 200
    assert response.data["meta"]["total"] == 1
    assert response.data["meta"]["pageSize"] == 1
    assert response.data["data"][0]["title"] == "Boiler inspection"


@pytest.mark.django_db
def test_invalid_status_transition_rolls_back(work_order_accounts):
    accounts = work_order_accounts
    work_order = create_order(accounts["alpha"], accounts["alpha_owner_role"])

    response = authenticated_client(accounts["alpha_dispatcher"]).patch(
        f"/api/v1/work-orders/{work_order.id}",
        {"status": WorkOrderStatus.COMPLETED, "title": "Should not persist"},
        format="json",
    )

    assert response.status_code == 400
    work_order.refresh_from_db()
    assert work_order.status == WorkOrderStatus.DRAFT
    assert work_order.title != "Should not persist"


@pytest.mark.django_db
def test_dashboard_is_organisation_and_role_scoped(work_order_accounts):
    accounts = work_order_accounts
    create_order(
        accounts["alpha"],
        accounts["alpha_owner_role"],
        priority=WorkOrderPriority.HIGH,
        assigned_technician=accounts["alpha_technician_role"],
    )
    create_order(accounts["alpha"], accounts["alpha_owner_role"])
    create_order(accounts["beta"], accounts["beta_owner_role"])

    owner_summary = authenticated_client(accounts["alpha_owner"]).get(
        "/api/v1/dashboard/summary"
    )
    technician_summary = authenticated_client(accounts["alpha_technician"]).get(
        "/api/v1/dashboard/summary"
    )

    assert owner_summary.status_code == technician_summary.status_code == 200
    assert owner_summary.data["data"]["total"] == 2
    assert owner_summary.data["data"]["assigned"] == 1
    assert owner_summary.data["data"]["unassigned"] == 1
    assert technician_summary.data["data"]["total"] == 1

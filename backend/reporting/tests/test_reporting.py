import csv
import io
from datetime import timedelta

import pytest
from django.db.models.query import QuerySet
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.tests.test_authentication import create_account
from organisations.models import Organisation, OrganisationUserRole
from reporting.services import CSV_HEADER
from workorders.models import WorkOrder, WorkOrderPriority, WorkOrderStatus


def authenticated_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def report_accounts(db):
    alpha = Organisation.objects.create(name="Report Alpha", slug="report-alpha")
    beta = Organisation.objects.create(name="Report Beta", slug="report-beta")
    owner, owner_role = create_account(alpha, "owner-report@alpha.test")
    dispatcher, dispatcher_role = create_account(
        alpha, "dispatcher-report@alpha.test", OrganisationUserRole.DISPATCHER
    )
    technician, technician_role = create_account(
        alpha, "technician-report@alpha.test", OrganisationUserRole.TECHNICIAN
    )
    beta_owner, beta_owner_role = create_account(beta, "owner-report@beta.test")
    return locals()


def create_order(organisation, creator, reference, **overrides):
    values = {
        "organisation": organisation,
        "creator": creator,
        "reference_number": reference,
        "title": f"Order {reference}",
        "description": "Routine service",
        "priority": WorkOrderPriority.MEDIUM,
        "status": WorkOrderStatus.DRAFT,
        "site_name": "Main site",
    }
    values.update(overrides)
    return WorkOrder.objects.create(**values)


def csv_rows(response):
    content = b"".join(response.streaming_content).decode()
    return list(csv.reader(io.StringIO(content)))


@pytest.mark.django_db
def test_export_is_organisation_scoped_even_with_tampered_query(report_accounts):
    accounts = report_accounts
    create_order(accounts["alpha"], accounts["owner_role"], "WO-ALPHA-1")
    create_order(accounts["beta"], accounts["beta_owner_role"], "WO-BETA-SECRET")

    response = authenticated_client(accounts["owner"]).get(
        "/api/v1/reports/work-orders.csv",
        {"organisation": str(accounts["beta"].id)},
    )
    rows = csv_rows(response)

    assert response.status_code == 200
    assert response.streaming is True
    assert rows[0] == list(CSV_HEADER)
    assert [row[0] for row in rows[1:]] == ["WO-ALPHA-1"]
    assert "WO-BETA-SECRET" not in str(rows)


@pytest.mark.django_db
def test_export_filters_match_work_order_list(report_accounts):
    accounts = report_accounts
    create_order(
        accounts["alpha"],
        accounts["owner_role"],
        "WO-HIGH",
        title="Boiler emergency",
        priority=WorkOrderPriority.HIGH,
    )
    create_order(
        accounts["alpha"],
        accounts["owner_role"],
        "WO-LOW",
        title="Routine inspection",
        priority=WorkOrderPriority.LOW,
    )
    client = authenticated_client(accounts["dispatcher"])
    filters = {"search": "boiler", "priority": "high", "ordering": "referenceNumber"}

    work_orders = client.get("/api/v1/work-orders", filters)
    report = client.get("/api/v1/reports/work-orders.csv", filters)

    expected_references = [item["referenceNumber"] for item in work_orders.data["data"]]
    assert [row[0] for row in csv_rows(report)[1:]] == expected_references


@pytest.mark.django_db
def test_technician_cannot_export_reports(report_accounts):
    response = authenticated_client(report_accounts["technician"]).get(
        "/api/v1/reports/work-orders.csv"
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_formula_cells_are_neutralized_and_csv_quoting_is_preserved(report_accounts):
    accounts = report_accounts
    create_order(
        accounts["alpha"],
        accounts["owner_role"],
        "WO-FORMULA",
        title='=HYPERLINK("https://invalid.test","click")',
        description="  +SUM(1,2)\nsecond line",
        site_name="@malicious, site",
    )

    rows = csv_rows(
        authenticated_client(accounts["owner"]).get("/api/v1/reports/work-orders.csv")
    )
    exported = rows[1]

    assert exported[1].startswith("'=")
    assert exported[2].startswith("'  +")
    assert "\nsecond line" in exported[2]
    assert exported[9] == "'@malicious, site"


@pytest.mark.django_db
def test_export_uses_chunked_queryset_iteration(report_accounts, settings, monkeypatch):
    accounts = report_accounts
    for index in range(5):
        create_order(
            accounts["alpha"],
            accounts["owner_role"],
            f"WO-STREAM-{index}",
        )
    settings.REPORT_EXPORT_CHUNK_SIZE = 2
    observed_chunks = []
    original_iterator = QuerySet.iterator

    def observed_iterator(queryset, *args, **kwargs):
        observed_chunks.append(kwargs.get("chunk_size"))
        return original_iterator(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "iterator", observed_iterator)
    response = authenticated_client(accounts["owner"]).get(
        "/api/v1/reports/work-orders.csv"
    )

    assert "Content-Length" not in response
    assert len(csv_rows(response)) == 6
    assert observed_chunks == [2]


@pytest.mark.django_db
def test_export_row_limit_returns_stable_error(report_accounts, settings):
    accounts = report_accounts
    settings.REPORT_EXPORT_MAX_ROWS = 1
    create_order(accounts["alpha"], accounts["owner_role"], "WO-LIMIT-1")
    create_order(accounts["alpha"], accounts["owner_role"], "WO-LIMIT-2")

    response = authenticated_client(accounts["owner"]).get(
        "/api/v1/reports/work-orders.csv"
    )

    assert response.status_code == 413
    assert response.data["error"]["code"] == "EXPORT_TOO_LARGE"


@pytest.mark.django_db
def test_export_formats_utc_schedule_without_loading_attachments(report_accounts):
    accounts = report_accounts
    start = timezone.now() + timedelta(hours=1)
    create_order(
        accounts["alpha"],
        accounts["owner_role"],
        "WO-SCHEDULED",
        assigned_technician=accounts["technician_role"],
        status=WorkOrderStatus.SCHEDULED,
        scheduled_start=start,
        scheduled_end=start + timedelta(hours=1),
    )

    row = csv_rows(
        authenticated_client(accounts["owner"]).get("/api/v1/reports/work-orders.csv")
    )[1]

    assert row[5] == "Test User"
    assert row[6] == "technician-report@alpha.test"
    assert row[7].endswith("Z")
    assert row[8].endswith("Z")

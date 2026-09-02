import pytest
from django.core.management import call_command

from organisations.models import Organisation, OrganisationUser
from workorders.models import WorkOrder, WorkOrderStatus


@pytest.mark.django_db
def test_seed_command_is_idempotent_and_creates_reviewable_tenant_data():
    call_command("seed_fielddesk", "--reset-passwords")
    call_command("seed_fielddesk", "--reset-passwords")

    assert Organisation.objects.count() == 2
    assert OrganisationUser.objects.count() == 6
    assert WorkOrder.objects.count() == 6
    for organisation in Organisation.objects.all():
        orders = WorkOrder.objects.for_organisation(organisation)
        assert orders.count() == 3
        assert set(orders.values_list("status", flat=True)) == {
            WorkOrderStatus.DRAFT,
            WorkOrderStatus.SCHEDULED,
            WorkOrderStatus.IN_PROGRESS,
        }

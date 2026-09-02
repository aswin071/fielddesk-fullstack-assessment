from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from organisations.models import Organisation, OrganisationUser, OrganisationUserRole
from users.models import User
from workorders.models import WorkOrder, WorkOrderPriority, WorkOrderStatus

SEED_PASSWORD = "FieldDeskDemo!2026"
SEED_ORGANISATIONS = (
    (
        "northstar",
        "Northstar Maintenance",
        (
            ("owner@northstar.test", "Nora", "Owner", OrganisationUserRole.OWNER),
            ("dispatcher@northstar.test", "Dylan", "Dispatcher", OrganisationUserRole.DISPATCHER),
            ("technician@northstar.test", "Tina", "Technician", OrganisationUserRole.TECHNICIAN),
        ),
    ),
    (
        "harborview",
        "Harborview Services",
        (
            ("owner@harborview.test", "Owen", "Owner", OrganisationUserRole.OWNER),
            ("dispatcher@harborview.test", "Daisy", "Dispatcher", OrganisationUserRole.DISPATCHER),
            ("technician@harborview.test", "Theo", "Technician", OrganisationUserRole.TECHNICIAN),
        ),
    ),
)


class Command(BaseCommand):
    help = "Create deterministic review data for two isolated FieldDesk organisations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Reset existing seed-user passwords to the documented demo password.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        for slug, name, accounts in SEED_ORGANISATIONS:
            organisation, _ = Organisation.all_objects.update_or_create(
                slug=slug,
                defaults={"name": name, "is_active": True, "deleted_at": None},
            )
            for email, first_name, last_name, role in accounts:
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "first_name": first_name,
                        "last_name": last_name,
                        "is_active": True,
                    },
                )
                changed_fields = []
                if not user.is_active:
                    user.is_active = True
                    changed_fields.append("is_active")
                if created or options["reset_passwords"]:
                    user.set_password(SEED_PASSWORD)
                    changed_fields.append("password")
                if changed_fields:
                    user.save(update_fields=changed_fields)

                OrganisationUser.all_objects.update_or_create(
                    user=user,
                    defaults={
                        "organisation": organisation,
                        "role": role,
                        "is_active": True,
                        "deleted_at": None,
                    },
                )

            organisation_users = {
                membership.role: membership
                for membership in OrganisationUser.objects.for_organisation(
                    organisation
                ).select_related("user")
            }
            dispatcher = organisation_users[OrganisationUserRole.DISPATCHER]
            technician = organisation_users[OrganisationUserRole.TECHNICIAN]
            now = timezone.now()
            demo_orders = (
                {
                    "reference_number": f"DEMO-{slug.upper()}-001",
                    "title": "Inspect main electrical panel",
                    "description": "Complete the quarterly safety inspection and record findings.",
                    "priority": WorkOrderPriority.MEDIUM,
                    "status": WorkOrderStatus.DRAFT,
                    "site_name": "Head office",
                    "assigned_technician": None,
                    "scheduled_start": None,
                    "scheduled_end": None,
                },
                {
                    "reference_number": f"DEMO-{slug.upper()}-002",
                    "title": "Preventive HVAC service",
                    "description": "Service filters, belts and controls before peak operation.",
                    "priority": WorkOrderPriority.HIGH,
                    "status": WorkOrderStatus.SCHEDULED,
                    "site_name": "Operations centre",
                    "assigned_technician": technician,
                    "scheduled_start": now + timedelta(days=1),
                    "scheduled_end": now + timedelta(days=1, hours=2),
                },
                {
                    "reference_number": f"DEMO-{slug.upper()}-003",
                    "title": "Repair loading-bay door",
                    "description": (
                        "Diagnose intermittent closing fault and restore safe operation."
                    ),
                    "priority": WorkOrderPriority.URGENT,
                    "status": WorkOrderStatus.IN_PROGRESS,
                    "site_name": "Distribution warehouse",
                    "assigned_technician": technician,
                    "scheduled_start": now - timedelta(hours=1),
                    "scheduled_end": now + timedelta(hours=2),
                },
            )
            for demo in demo_orders:
                reference_number = demo.pop("reference_number")
                WorkOrder.all_objects.update_or_create(
                    organisation=organisation,
                    reference_number=reference_number,
                    defaults={
                        **demo,
                        "creator": dispatcher,
                        "deleted_at": None,
                    },
                )

        self.stdout.write(self.style.SUCCESS("FieldDesk seed data is ready."))

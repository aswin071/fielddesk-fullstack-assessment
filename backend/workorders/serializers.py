from rest_framework import serializers

from organisations.models import OrganisationUser
from workorders.models import WorkOrder, WorkOrderPriority, WorkOrderStatus
from workorders.selectors import ORDERING_FIELDS


class WorkOrderPersonSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source="user.id", read_only=True)
    fullName = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = OrganisationUser
        fields = ("id", "userId", "fullName", "email", "role")
        read_only_fields = fields


class WorkOrderSerializer(serializers.ModelSerializer):
    referenceNumber = serializers.CharField(source="reference_number", read_only=True)
    siteName = serializers.CharField(source="site_name", read_only=True)
    assignedTechnician = WorkOrderPersonSerializer(
        source="assigned_technician", read_only=True, allow_null=True
    )
    scheduledStart = serializers.DateTimeField(source="scheduled_start", read_only=True)
    scheduledEnd = serializers.DateTimeField(source="scheduled_end", read_only=True)
    creator = WorkOrderPersonSerializer(read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = WorkOrder
        fields = (
            "id",
            "referenceNumber",
            "title",
            "description",
            "priority",
            "status",
            "assignedTechnician",
            "scheduledStart",
            "scheduledEnd",
            "siteName",
            "creator",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = fields


class WorkOrderCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    priority = serializers.ChoiceField(
        choices=WorkOrderPriority.choices,
        default=WorkOrderPriority.MEDIUM,
    )
    siteName = serializers.CharField(source="site_name", max_length=200)


class WorkOrderUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(choices=WorkOrderPriority.choices, required=False)
    status = serializers.ChoiceField(choices=WorkOrderStatus.choices, required=False)
    siteName = serializers.CharField(source="site_name", max_length=200, required=False)


class WorkOrderFilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=200)
    status = serializers.ChoiceField(choices=WorkOrderStatus.choices, required=False)
    priority = serializers.ChoiceField(choices=WorkOrderPriority.choices, required=False)
    technicianId = serializers.UUIDField(required=False)
    scheduledFrom = serializers.DateTimeField(required=False)
    scheduledTo = serializers.DateTimeField(required=False)
    ordering = serializers.ChoiceField(
        choices=tuple(ORDERING_FIELDS) + tuple(f"-{field}" for field in ORDERING_FIELDS),
        required=False,
    )

    def validate(self, attrs):
        start = attrs.get("scheduledFrom")
        end = attrs.get("scheduledTo")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"scheduledTo": ["Must be later than or equal to scheduledFrom."]}
            )
        return attrs


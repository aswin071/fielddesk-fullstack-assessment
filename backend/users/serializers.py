from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from audit.services import record_audit
from organisations.models import OrganisationUser, OrganisationUserRole
from users.models import User


class OrganisationUserSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    firstName = serializers.CharField(source="user.first_name", read_only=True)
    lastName = serializers.CharField(source="user.last_name", read_only=True)
    fullName = serializers.CharField(source="user.get_full_name", read_only=True)
    isActive = serializers.BooleanField(source="is_active", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = OrganisationUser
        fields = (
            "id",
            "userId",
            "email",
            "firstName",
            "lastName",
            "fullName",
            "role",
            "isActive",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = fields


class OrganisationUserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    firstName = serializers.CharField(source="first_name", max_length=150)
    lastName = serializers.CharField(
        source="last_name", max_length=150, required=False, allow_blank=True
    )
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=OrganisationUserRole.choices)

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return normalized

    @transaction.atomic
    def create(self, validated_data):
        actor = self.context["actor"]
        organisation = actor.organisation
        role = validated_data.pop("role")
        user = User.objects.create_user(**validated_data)
        organisation_user = OrganisationUser.objects.create(
            organisation=organisation,
            user=user,
            role=role,
        )
        record_audit(
            organisation=organisation,
            actor=actor.organisation_user,
            action="user.created",
            target_type="OrganisationUser",
            target_id=organisation_user.id,
            after={
                "email": user.email,
                "firstName": user.first_name,
                "lastName": user.last_name,
                "role": organisation_user.role,
                "isActive": organisation_user.is_active,
            },
        )
        return organisation_user


class OrganisationUserUpdateSerializer(serializers.Serializer):
    firstName = serializers.CharField(source="first_name", max_length=150, required=False)
    lastName = serializers.CharField(
        source="last_name", max_length=150, required=False, allow_blank=True
    )
    role = serializers.ChoiceField(choices=OrganisationUserRole.choices, required=False)
    isActive = serializers.BooleanField(source="is_active", required=False)

    @transaction.atomic
    def update(self, instance, validated_data):
        actor = self.context["actor"]
        locked_owners = list(
            OrganisationUser.objects.select_for_update()
            .for_organisation(instance.organisation)
            .filter(role=OrganisationUserRole.OWNER, is_active=True)
            .order_by("pk")
        )
        instance = OrganisationUser.objects.select_for_update().select_related("user").get(
            pk=instance.pk
        )
        before = {
            "firstName": instance.user.first_name,
            "lastName": instance.user.last_name,
            "role": instance.role,
            "isActive": instance.is_active,
        }
        removes_owner = instance.role == OrganisationUserRole.OWNER and (
            validated_data.get("role", instance.role) != OrganisationUserRole.OWNER
            or validated_data.get("is_active", instance.is_active) is False
        )
        if removes_owner and not any(owner.pk != instance.pk for owner in locked_owners):
            raise serializers.ValidationError(
                {"role": ["The organisation must retain at least one active Owner."]}
            )
        user_fields = []
        for field in ("first_name", "last_name"):
            if field in validated_data:
                setattr(instance.user, field, validated_data.pop(field))
                user_fields.append(field)
        if user_fields:
            instance.user.save(update_fields=user_fields)
        for field in ("role", "is_active"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()
        after = {
            "firstName": instance.user.first_name,
            "lastName": instance.user.last_name,
            "role": instance.role,
            "isActive": instance.is_active,
        }
        record_audit(
            organisation=instance.organisation,
            actor=actor.organisation_user,
            action="user.updated",
            target_type="OrganisationUser",
            target_id=instance.id,
            before=before,
            after=after,
            metadata={
                "changedFields": [key for key in after if before.get(key) != after.get(key)]
            },
        )
        return instance

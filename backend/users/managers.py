from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    @staticmethod
    def normalize_email_address(email: str) -> str:
        normalized = BaseUserManager.normalize_email(email).strip().lower()
        if not normalized:
            raise ValueError("An email address is required")
        return normalized

    def create_user(self, email, password=None, **extra_fields):
        email = self.normalize_email_address(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean(exclude=("password",))
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("A superuser must have is_staff=True and is_superuser=True")
        return self.create_user(email, password, **extra_fields)


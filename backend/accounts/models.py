import secrets

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, display_name, password=None, **extra):
        if not email:
            raise ValueError("Email is required.")
        if not display_name:
            raise ValueError("Display name is required.")
        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, display_name=display_name, **extra)
        user.set_password(password)
        user.save(using=self._db)
        self.ensure_marketplace_connections(user)
        return user

    def ensure_marketplace_connections(self, user):
        existing = set(
            MarketplaceConnection.objects.using(self._db)
            .filter(user=user)
            .values_list("marketplace", flat=True)
        )
        missing = [
            MarketplaceConnection(user=user, marketplace=marketplace)
            for marketplace in MarketplaceConnection.Marketplace.values
            if marketplace not in existing
        ]
        if missing:
            MarketplaceConnection.objects.using(self._db).bulk_create(missing)

    def create_superuser(self, email, display_name, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, display_name, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    browser_profile_id = models.CharField(max_length=255, blank=True)
    browser_profile_status = models.CharField(max_length=16, default="pending")
    browser_profile_error = models.TextField(blank=True)
    stripe_provision_error = models.TextField(blank=True)
    vinted_password = models.TextField(blank=True)
    depop_password = models.TextField(blank=True)
    ebay_password = models.TextField(blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    _MARKETPLACE_PASSWORD_FIELDS = {
        "vinted": "vinted_password",
        "depop": "depop_password",
        "ebay": "ebay_password",
    }

    def set_marketplace_password(self, marketplace, password):
        """Store ``password`` as ciphertext. The caller saves the user."""
        from accounts.secrets import encrypt_password

        field = self._marketplace_password_field(marketplace)
        setattr(self, field, encrypt_password(password))

    def marketplace_password(self, marketplace):
        """Return the decrypted marketplace password, or "" when none is stored."""
        from accounts.secrets import decrypt_password

        field = self._marketplace_password_field(marketplace)
        return decrypt_password(getattr(self, field))

    def _marketplace_password_field(self, marketplace):
        try:
            return self._MARKETPLACE_PASSWORD_FIELDS[marketplace]
        except KeyError as exc:
            raise ValueError(f"Unknown marketplace {marketplace!r}.") from exc

    def __str__(self):
        return self.email


class ApiToken(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="api_token",
    )
    key = models.CharField(max_length=64, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"API token for {self.user}"


class MarketplaceConnection(models.Model):
    class Marketplace(models.TextChoices):
        VINTED = "vinted", "Vinted"
        DEPOP = "depop", "Depop"
        EBAY = "ebay", "eBay"

    class Status(models.TextChoices):
        NOT_CONNECTED = "not_connected", "Not connected"
        CONNECTED = "connected", "Connected"
        NEEDS_LOGIN = "needs_login", "Needs login"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="marketplace_connections",
    )
    marketplace = models.CharField(max_length=16, choices=Marketplace.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.NOT_CONNECTED,
    )
    external_username = models.CharField(max_length=255, blank=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "marketplace"],
                name="unique_user_marketplace_connection",
            )
        ]

    def __str__(self):
        return f"{self.marketplace} for {self.user}"

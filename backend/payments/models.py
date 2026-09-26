import secrets

from django.conf import settings
from django.db import models


class ApiToken(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
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


class Seller(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="seller",
    )
    stripe_account_id = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    contact_email = models.EmailField()
    transfers_status = models.CharField(max_length=32, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name


class MarketplaceSale(models.Model):
    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    seller = models.ForeignKey(
        Seller, on_delete=models.PROTECT, related_name="sales"
    )
    listing = models.ForeignKey(
        "listings.Listing",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sales",
    )
    marketplace = models.CharField(max_length=64)
    external_sale_id = models.CharField(max_length=255)
    amount_minor = models.PositiveIntegerField(
        help_text="Seller proceeds for this sale, in minor currency units."
    )
    currency = models.CharField(max_length=3, default="gbp")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.COMPLETED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seller", "marketplace", "external_sale_id"],
                name="unique_seller_marketplace_sale",
            )
        ]

    def __str__(self):
        return f"{self.marketplace}:{self.external_sale_id}"


class FundAuthorization(models.Model):
    """Seller consent to move one sale's amount out of the platform balance."""

    sale = models.OneToOneField(
        MarketplaceSale, on_delete=models.PROTECT, related_name="authorization"
    )
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    statement = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Authorization {self.pk} for {self.sale}"


class BalanceTransfer(models.Model):
    sale = models.OneToOneField(
        MarketplaceSale, on_delete=models.PROTECT, related_name="transfer"
    )
    stripe_transfer_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, default="pending")
    failure_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.stripe_transfer_id or f"Transfer for {self.sale_id}"


class ProcessedStripeEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

"""Buyer threads Steve reads and answers."""

from django.conf import settings
from django.db import models


class BuyerThread(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        NEEDS_SELLER = "needs_seller", "Needs seller"
        CLOSED = "closed", "Closed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buyer_threads",
    )
    marketplace = models.CharField(max_length=16)
    external_thread_id = models.CharField(max_length=255)
    item = models.ForeignKey(
        "listings.Item",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="buyer_threads",
    )
    buyer_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "marketplace", "external_thread_id"],
                name="unique_buyer_thread",
            )
        ]

    def __str__(self):
        return f"{self.marketplace}:{self.external_thread_id}"


class BuyerMessage(models.Model):
    class Direction(models.TextChoices):
        BUYER = "buyer", "Buyer"
        SELLER = "seller", "Seller"

    thread = models.ForeignKey(
        BuyerThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    direction = models.CharField(max_length=16, choices=Direction.choices)
    body = models.TextField()
    offer_minor = models.PositiveIntegerField(null=True, blank=True)
    external_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "external_id"],
                name="unique_buyer_message",
            )
        ]

    def __str__(self):
        return f"{self.direction} on {self.thread_id}"

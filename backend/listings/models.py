from django.conf import settings
from django.db import models
from django.utils import timezone


class Item(models.Model):
    class Department(models.TextChoices):
        WOMEN = "women", "Women"
        MEN = "men", "Men"
        KIDS = "kids", "Kids"
        UNISEX = "unisex", "Unisex"

    class Category(models.TextChoices):
        TOPS = "tops", "Tops"
        BOTTOMS = "bottoms", "Bottoms"
        DRESSES = "dresses", "Dresses"
        OUTERWEAR = "outerwear", "Outerwear"
        SHOES = "shoes", "Shoes"
        BAGS = "bags", "Bags"
        ACCESSORIES = "accessories", "Accessories"
        ACTIVEWEAR = "activewear", "Activewear"
        OTHER = "other", "Other"

    class SizeSystem(models.TextChoices):
        UK = "uk", "UK"
        EU = "eu", "EU"
        US = "us", "US"
        ALPHA = "alpha", "Alpha"
        WAIST = "waist", "Waist"
        ONE_SIZE = "one_size", "One size"

    class Condition(models.TextChoices):
        NEW_WITH_TAGS = "new_with_tags", "New with tags"
        NEW_WITHOUT_TAGS = "new_without_tags", "New without tags"
        VERY_GOOD = "very_good", "Very good"
        GOOD = "good", "Good"
        SATISFACTORY = "satisfactory", "Satisfactory"

    class PackageSize(models.TextChoices):
        SMALL = "small", "Small"
        MEDIUM = "medium", "Medium"
        LARGE = "large", "Large"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        LISTED = "listed", "Listed"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"
        ARCHIVED = "archived", "Archived"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="items",
    )
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    department = models.CharField(
        max_length=32, choices=Department.choices, blank=True
    )
    category = models.CharField(max_length=32, choices=Category.choices, blank=True)
    garment_type = models.CharField(max_length=64, blank=True)
    brand = models.CharField(max_length=255, blank=True)
    colour = models.CharField(max_length=64, blank=True)
    colour_secondary = models.CharField(max_length=64, blank=True)
    size_label = models.CharField(max_length=64, blank=True)
    size_system = models.CharField(
        max_length=32, choices=SizeSystem.choices, blank=True
    )
    condition = models.CharField(
        max_length=32, choices=Condition.choices, blank=True
    )
    material = models.CharField(max_length=255, blank=True)
    flaws = models.TextField(blank=True)
    chest_cm = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True
    )
    waist_cm = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True
    )
    length_cm = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True
    )
    inseam_cm = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True
    )
    package_size = models.CharField(
        max_length=16, choices=PackageSize.choices, blank=True
    )
    cost_minor = models.PositiveIntegerField(null=True, blank=True)
    price_minor = models.PositiveIntegerField(null=True, blank=True)
    min_offer_minor = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="gbp")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    source = models.CharField(max_length=255, blank=True)
    acquired_on = models.DateField(null=True, blank=True)
    storage_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f"Item {self.pk}"


class ItemPhoto(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="listings/%Y/%m/")
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "position"],
                name="unique_item_photo_position",
            )
        ]

    def __str__(self):
        return f"Photo {self.position} for {self.item}"


class Listing(models.Model):
    class Marketplace(models.TextChoices):
        VINTED = "vinted", "Vinted"
        DEPOP = "depop", "Depop"
        EBAY = "ebay", "eBay"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHING = "publishing", "Publishing"
        LIVE = "live", "Live"
        PAUSED = "paused", "Paused"
        SOLD = "sold", "Sold"
        ENDED = "ended", "Ended"
        FAILED = "failed", "Failed"

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="listings")
    marketplace = models.CharField(max_length=16, choices=Marketplace.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    external_id = models.CharField(max_length=255, blank=True)
    external_url = models.URLField(max_length=500, blank=True)
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    price_minor = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="gbp")
    category_ref = models.CharField(max_length=255, blank=True)
    shipping_price_minor = models.PositiveIntegerField(null=True, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    listed_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "marketplace"],
                name="unique_item_marketplace",
            )
        ]

    def __str__(self):
        return f"{self.marketplace} listing for {self.item}"

    def mark_sold(self):
        """Close this channel and withdraw the other open offers for the garment."""
        now = timezone.now()
        self.status = self.Status.SOLD
        self.ended_at = now
        self.save(update_fields=["status", "ended_at"])
        self.item.listings.filter(
            status__in=(
                self.Status.PUBLISHING,
                self.Status.LIVE,
                self.Status.PAUSED,
            )
        ).update(status=self.Status.ENDED, ended_at=now)
        item = self.item
        item.status = Item.Status.SOLD
        item.save(update_fields=["status", "updated_at"])

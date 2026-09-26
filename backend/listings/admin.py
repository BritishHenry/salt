from django.contrib import admin

from listings.models import Comparable, Item, ItemPhoto, Listing, PriceQuote


class ItemPhotoInline(admin.TabularInline):
    model = ItemPhoto
    extra = 0


class ListingInline(admin.TabularInline):
    model = Listing
    extra = 0


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "price_minor", "currency")
    list_filter = ("status", "department", "category")
    search_fields = ("title", "brand", "user__email")
    inlines = [ItemPhotoInline, ListingInline]


@admin.register(ItemPhoto)
class ItemPhotoAdmin(admin.ModelAdmin):
    list_display = ("item", "position")


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("item", "marketplace", "status", "price_minor", "currency")
    list_filter = ("marketplace", "status")
    search_fields = ("title", "external_id", "item__title")


class ComparableInline(admin.TabularInline):
    model = Comparable
    extra = 0


@admin.register(PriceQuote)
class PriceQuoteAdmin(admin.ModelAdmin):
    list_display = ("item", "status", "price_minor", "currency", "created_at")
    list_filter = ("status",)
    search_fields = ("item__title", "item__brand", "rationale", "error")
    inlines = [ComparableInline]

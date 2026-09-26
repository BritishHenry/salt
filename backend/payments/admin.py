from django.contrib import admin

from payments.models import (
    ApiToken,
    BalanceTransfer,
    FundAuthorization,
    MarketplaceSale,
    Seller,
)


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    readonly_fields = ("key", "created_at")
    search_fields = ("user__username",)


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "contact_email", "transfers_status", "stripe_account_id")
    search_fields = ("display_name", "contact_email", "stripe_account_id")


@admin.register(MarketplaceSale)
class MarketplaceSaleAdmin(admin.ModelAdmin):
    list_display = (
        "marketplace",
        "external_sale_id",
        "amount_minor",
        "currency",
        "seller",
        "listing",
        "status",
    )
    list_filter = ("status", "marketplace")


@admin.register(FundAuthorization)
class FundAuthorizationAdmin(admin.ModelAdmin):
    list_display = ("sale", "authorized_by", "created_at")
    readonly_fields = ("statement", "created_at")


@admin.register(BalanceTransfer)
class BalanceTransferAdmin(admin.ModelAdmin):
    list_display = ("sale", "stripe_transfer_id", "status")

from django.urls import path

from listings import views

urlpatterns = [
    path("items/", views.items, name="listing-items"),
    path("items/<int:item_id>/", views.item_detail, name="listing-item"),
    path("items/<int:item_id>/photos/", views.item_photos, name="listing-item-photos"),
    path(
        "items/<int:item_id>/photos/<int:position>/",
        views.item_photo,
        name="listing-item-photo",
    ),
    path(
        "items/<int:item_id>/listings/",
        views.item_listings,
        name="listing-item-listings",
    ),
    path(
        "items/<int:item_id>/listings/<str:marketplace>/",
        views.item_listing,
        name="listing-item-listing",
    ),
    path(
        "items/<int:item_id>/price/",
        views.price_item_view,
        name="listing-price",
    ),
]

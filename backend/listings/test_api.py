import json
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import ApiToken, User
from listings.models import Item, Listing
from payments.models import MarketplaceSale, Seller


def make_user(name):
    return User.objects.create_user(
        email=f"{name}@example.com",
        display_name=name,
        password="secret",
    )


def make_seller(user, suffix):
    return Seller.objects.create(
        user=user,
        stripe_account_id=f"acct_{suffix}",
        display_name=user.display_name,
        contact_email=user.email,
    )


class WardrobeApiTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.media_override = override_settings(MEDIA_ROOT=self.media.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)

        self.user = make_user("ada")
        self.token = ApiToken.objects.create(user=self.user)
        self.other = make_user("bea")
        self.other_token = ApiToken.objects.create(user=self.other)

    def auth(self, token=None):
        key = self.token.key if token is None else token.key
        return {"HTTP_AUTHORIZATION": f"Bearer {key}"}

    def post_json(self, path, body, token=None):
        return self.client.post(
            path,
            data=json.dumps(body),
            content_type="application/json",
            **self.auth(token),
        )

    def patch_json(self, path, body, token=None):
        return self.client.patch(
            path,
            data=json.dumps(body),
            content_type="application/json",
            **self.auth(token),
        )

    def test_items_require_a_token(self):
        response = self.client.get("/api/listings/items/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "Authentication required.")

    def test_owner_creates_and_lists_an_item(self):
        created = self.post_json(
            "/api/listings/items/",
            {
                "title": "Wool coat",
                "brand": "COS",
                "size_label": "M",
                "condition": "good",
                "category": "outerwear",
                "price_minor": 7500,
                "currency": "GBP",
                "chest_cm": 96.5,
                "acquired_on": "2026-03-01",
            },
        )
        self.assertEqual(created.status_code, 201)
        body = created.json()
        self.assertEqual(body["title"], "Wool coat")
        self.assertEqual(body["brand"], "COS")
        self.assertEqual(body["size_label"], "M")
        self.assertEqual(body["condition"], "good")
        self.assertEqual(body["category"], "outerwear")
        self.assertEqual(body["price_minor"], 7500)
        self.assertEqual(body["currency"], "gbp")
        self.assertEqual(body["chest_cm"], 96.5)
        self.assertEqual(body["acquired_on"], "2026-03-01")
        self.assertEqual(body["status"], "draft")
        self.assertEqual(body["photos"], [])
        self.assertEqual(body["listings"], [])

        listed = self.client.get("/api/listings/items/", **self.auth())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.json()["items"]], [body["id"]])

        detail = self.client.get(f"/api/listings/items/{body['id']}/", **self.auth())
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["title"], "Wool coat")

    def test_list_hides_another_users_items(self):
        own = self.post_json("/api/listings/items/", {"title": "Mine"})
        self.post_json("/api/listings/items/", {"title": "Theirs"}, token=self.other_token)
        listed = self.client.get("/api/listings/items/", **self.auth())
        titles = [item["title"] for item in listed.json()["items"]]
        self.assertEqual(titles, ["Mine"])
        self.assertEqual(own.status_code, 201)

    def test_other_user_item_is_not_found(self):
        created = self.post_json("/api/listings/items/", {"title": "Mine"})
        item_id = created.json()["id"]
        response = self.client.get(
            f"/api/listings/items/{item_id}/", **self.auth(self.other_token)
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "Item not found.")

        patched = self.patch_json(
            f"/api/listings/items/{item_id}/",
            {"title": "Stolen"},
            token=self.other_token,
        )
        self.assertEqual(patched.status_code, 404)
        self.user.items.get(pk=item_id).refresh_from_db()
        self.assertEqual(Item.objects.get(pk=item_id).title, "Mine")

    def test_invalid_category_is_rejected(self):
        response = self.post_json(
            "/api/listings/items/", {"category": "coat"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("category must be one of:", response.json()["error"])
        self.assertEqual(Item.objects.count(), 0)

    def test_create_does_not_accept_status(self):
        response = self.post_json(
            "/api/listings/items/", {"title": "Coat", "status": "listed"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Item.objects.count(), 0)

    def test_patch_updates_status(self):
        item_id = self.post_json("/api/listings/items/", {"title": "Coat"}).json()["id"]
        response = self.patch_json(
            f"/api/listings/items/{item_id}/", {"status": "ready", "price_minor": 2500}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        self.assertEqual(response.json()["price_minor"], 2500)

        invalid = self.patch_json(
            f"/api/listings/items/{item_id}/", {"status": "published"}
        )
        self.assertEqual(invalid.status_code, 400)

    def test_photo_positions_are_unique_and_deletable(self):
        item_id = self.post_json("/api/listings/items/", {"title": "Coat"}).json()["id"]
        first = self.client.post(
            f"/api/listings/items/{item_id}/photos/",
            data={"image": SimpleUploadedFile("coat.jpg", b"jpeg", content_type="image/jpeg")},
            **self.auth(),
        )
        second = self.client.post(
            f"/api/listings/items/{item_id}/photos/",
            data={"image": SimpleUploadedFile("coat-2.jpg", b"jpeg", content_type="image/jpeg")},
            **self.auth(),
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["position"], 0)
        self.assertEqual(second.json()["position"], 1)
        self.assertIn("/media/", first.json()["url"])
        positions = list(
            Item.objects.get(pk=item_id).photos.order_by("position").values_list(
                "position", flat=True
            )
        )
        self.assertEqual(positions, [0, 1])

        removed = self.client.delete(
            f"/api/listings/items/{item_id}/photos/0/", **self.auth()
        )
        self.assertEqual(removed.status_code, 204)
        self.assertEqual(
            list(Item.objects.get(pk=item_id).photos.values_list("position", flat=True)),
            [1],
        )

        missing = self.client.delete(
            f"/api/listings/items/{item_id}/photos/0/", **self.auth()
        )
        self.assertEqual(missing.status_code, 404)

    def test_other_user_cannot_upload_a_photo(self):
        item_id = self.post_json("/api/listings/items/", {"title": "Coat"}).json()["id"]
        response = self.client.post(
            f"/api/listings/items/{item_id}/photos/",
            data={"image": SimpleUploadedFile("coat.jpg", b"jpeg", content_type="image/jpeg")},
            **self.auth(self.other_token),
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Item.objects.get(pk=item_id).photos.exists())

    def test_listing_create_rejects_unknown_marketplace_and_duplicates(self):
        item_id = self.post_json("/api/listings/items/", {"title": "Coat"}).json()["id"]
        invalid = self.post_json(
            f"/api/listings/items/{item_id}/listings/", {"marketplace": "etsy"}
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("marketplace must be one of:", invalid.json()["error"])

        created = self.post_json(
            f"/api/listings/items/{item_id}/listings/",
            {"marketplace": "vinted", "price_minor": 7500, "attributes": {"size": "M"}},
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["marketplace"], "vinted")
        self.assertEqual(created.json()["status"], "draft")
        self.assertEqual(created.json()["price_minor"], 7500)
        self.assertEqual(created.json()["attributes"], {"size": "M"})

        duplicate = self.post_json(
            f"/api/listings/items/{item_id}/listings/", {"marketplace": "vinted"}
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(Listing.objects.filter(item_id=item_id).count(), 1)

    def test_patch_listing_status_does_not_close_other_channels(self):
        item_id = self.post_json("/api/listings/items/", {"title": "Coat"}).json()["id"]
        self.post_json(
            f"/api/listings/items/{item_id}/listings/", {"marketplace": "vinted"}
        )
        self.post_json(
            f"/api/listings/items/{item_id}/listings/", {"marketplace": "depop"}
        )
        patched = self.patch_json(
            f"/api/listings/items/{item_id}/listings/vinted/",
            {"status": "sold"},
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["status"], "sold")
        depop = Listing.objects.get(item_id=item_id, marketplace="depop")
        self.assertEqual(depop.status, Listing.Status.DRAFT)
        self.assertIsNone(depop.ended_at)
        item = Item.objects.get(pk=item_id)
        self.assertEqual(item.status, Item.Status.DRAFT)

    def test_marketplace_connections_are_read_only_for_the_caller(self):
        response = self.client.get("/api/accounts/marketplaces/", **self.auth())
        self.assertEqual(response.status_code, 200)
        rows = response.json()["marketplaces"]
        self.assertEqual(
            [row["marketplace"] for row in rows], ["depop", "ebay", "vinted"]
        )
        self.assertTrue(all(row["status"] == "not_connected" for row in rows))
        self.assertNotIn("password", response.content.decode())

        anonymous = self.client.get("/api/accounts/marketplaces/")
        self.assertEqual(anonymous.status_code, 401)

    def test_sales_list_returns_only_the_callers_sales(self):
        seller = make_seller(self.user, "ada")
        other_seller = make_seller(self.other, "bea")
        now = timezone.now()
        MarketplaceSale.objects.create(
            seller=seller,
            marketplace="vinted",
            external_sale_id="v-1",
            amount_minor=2000,
            created_at=now,
        )
        MarketplaceSale.objects.create(
            seller=other_seller,
            marketplace="depop",
            external_sale_id="d-1",
            amount_minor=900,
            created_at=now,
        )

        anonymous = self.client.get("/api/stripe/sales/")
        self.assertEqual(anonymous.status_code, 401)

        response = self.client.get("/api/stripe/sales/", **self.auth())
        self.assertEqual(response.status_code, 200)
        sales = response.json()["sales"]
        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0]["marketplace"], "vinted")
        self.assertEqual(sales[0]["external_sale_id"], "v-1")
        self.assertEqual(sales[0]["amount_minor"], 2000)
        self.assertEqual(sales[0]["currency"], "gbp")
        self.assertEqual(sales[0]["status"], "completed")

    def test_sales_list_requires_a_seller(self):
        response = self.client.get("/api/stripe/sales/", **self.auth())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["error"], "Seller has not started Stripe onboarding."
        )

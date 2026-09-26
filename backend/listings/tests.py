from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase

from listings.models import Item, ItemPhoto, Listing
from payments.models import MarketplaceSale, Seller
from payments.services import PaymentError, record_sale

User = get_user_model()


def make_user(username):
    return User.objects.create_user(username=username, password="secret")


def make_seller(user):
    return Seller.objects.create(
        user=user,
        stripe_account_id=f"acct_{user.username}",
        display_name=user.username,
        contact_email=f"{user.username}@example.com",
    )


class ListingConstraintTests(TestCase):
    def test_one_listing_per_marketplace(self):
        user = make_user("seller")
        item = Item.objects.create(user=user, title="Wool coat")
        Listing.objects.create(item=item, marketplace=Listing.Marketplace.VINTED)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Listing.objects.create(
                    item=item, marketplace=Listing.Marketplace.VINTED
                )

    def test_photo_positions_are_unique(self):
        user = make_user("seller")
        item = Item.objects.create(user=user)
        ItemPhoto.objects.create(
            item=item,
            image=SimpleUploadedFile("coat.jpg", b"jpeg", content_type="image/jpeg"),
            position=0,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ItemPhoto.objects.create(
                    item=item,
                    image=SimpleUploadedFile(
                        "coat-2.jpg", b"jpeg", content_type="image/jpeg"
                    ),
                    position=0,
                )


class RecordSaleListingTests(TestCase):
    def test_sale_marks_item_sold_and_ends_other_live_channel(self):
        user = make_user("seller")
        seller = make_seller(user)
        item = Item.objects.create(user=user, title="Wool coat", price_minor=2500)
        vinted = Listing.objects.create(
            item=item,
            marketplace=Listing.Marketplace.VINTED,
            status=Listing.Status.LIVE,
            price_minor=2500,
        )
        depop = Listing.objects.create(
            item=item,
            marketplace=Listing.Marketplace.DEPOP,
            status=Listing.Status.LIVE,
            price_minor=2500,
        )
        ebay = Listing.objects.create(
            item=item,
            marketplace=Listing.Marketplace.EBAY,
            status=Listing.Status.PAUSED,
        )

        sale = record_sale(
            seller=seller,
            marketplace="vinted",
            external_sale_id="v-1",
            amount_minor=2000,
            listing=vinted,
        )

        item.refresh_from_db()
        vinted.refresh_from_db()
        depop.refresh_from_db()
        ebay.refresh_from_db()
        self.assertEqual(sale.listing_id, vinted.pk)
        self.assertEqual(sale.status, MarketplaceSale.Status.COMPLETED)
        self.assertEqual(item.status, Item.Status.SOLD)
        self.assertEqual(vinted.status, Listing.Status.SOLD)
        self.assertIsNotNone(vinted.ended_at)
        self.assertEqual(depop.status, Listing.Status.ENDED)
        self.assertIsNotNone(depop.ended_at)
        self.assertEqual(ebay.status, Listing.Status.ENDED)
        self.assertIsNotNone(ebay.ended_at)

    def test_draft_channel_stays_open_when_another_sells(self):
        user = make_user("seller-draft")
        seller = make_seller(user)
        item = Item.objects.create(user=user)
        vinted = Listing.objects.create(
            item=item,
            marketplace=Listing.Marketplace.VINTED,
            status=Listing.Status.PUBLISHING,
        )
        ebay = Listing.objects.create(
            item=item,
            marketplace=Listing.Marketplace.EBAY,
            status=Listing.Status.DRAFT,
        )

        record_sale(
            seller=seller,
            marketplace="vinted",
            external_sale_id="v-draft",
            amount_minor=2000,
            listing=vinted,
        )

        vinted.refresh_from_db()
        ebay.refresh_from_db()
        self.assertEqual(vinted.status, Listing.Status.SOLD)
        self.assertEqual(ebay.status, Listing.Status.DRAFT)
        self.assertIsNone(ebay.ended_at)

    def test_listing_must_belong_to_the_seller(self):
        seller = make_seller(make_user("seller"))
        other_item = Item.objects.create(user=make_user("other"))
        listing = Listing.objects.create(
            item=other_item, marketplace=Listing.Marketplace.VINTED
        )
        with self.assertRaises(PaymentError):
            record_sale(
                seller=seller,
                marketplace="vinted",
                external_sale_id="v-1",
                amount_minor=2000,
                listing=listing,
            )
        self.assertFalse(MarketplaceSale.objects.exists())

    def test_listing_marketplace_must_match_the_sale(self):
        user = make_user("seller")
        seller = make_seller(user)
        item = Item.objects.create(user=user)
        listing = Listing.objects.create(
            item=item, marketplace=Listing.Marketplace.DEPOP
        )
        with self.assertRaises(PaymentError):
            record_sale(
                seller=seller,
                marketplace="vinted",
                external_sale_id="v-1",
                amount_minor=2000,
                listing=listing,
            )
        item.refresh_from_db()
        self.assertEqual(item.status, Item.Status.DRAFT)

    def test_sale_without_a_listing_stays_completed(self):
        seller = make_seller(make_user("seller"))
        sale = record_sale(
            seller=seller,
            marketplace="ebay",
            external_sale_id="e-1",
            amount_minor=1500,
        )
        self.assertIsNone(sale.listing_id)
        self.assertEqual(sale.status, MarketplaceSale.Status.COMPLETED)

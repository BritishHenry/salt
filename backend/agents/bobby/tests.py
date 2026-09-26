import json
import re
from base64 import b64encode

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from agents.bobby import __doc__ as BOBBY_MODULE_DOC
from agents.bobby.draft import INSTRUCTIONS, LIMITS, MODEL, draft_listings
from agents.bobby.tool import BOBBY_DESCRIPTION
from agents.salt.agent import INSTRUCTIONS as SALT_INSTRUCTIONS
from agents.salt.tools import specialist_tools
from agents.tools import TOOLS, call_tool
from listings.models import Item, ItemPhoto, Listing

User = get_user_model()

CLAIM = re.compile(r"publish|\bpost(?:ed|ing|s)?\b|live listing|going live", re.IGNORECASE)


class FakeGrok:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    @property
    def chat(self):
        return self

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.payload, Exception):
            raise self.payload
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return {"choices": [{"message": {"content": text}}]}


def make_user(name):
    return User.objects.create_user(
        email=f"{name}@example.com",
        display_name=name,
        password="secret",
    )


def make_item(user, **extra):
    fields = {
        "user": user,
        "title": "Navy wool coat",
        "department": Item.Department.WOMEN,
        "category": Item.Category.TOPS,
        "garment_type": "blouse",
        "brand": "COS",
        "colour": "navy",
        "size_label": "12",
        "size_system": Item.SizeSystem.UK,
        "condition": Item.Condition.GOOD,
        "material": "wool",
        "price_minor": 2500,
        "currency": "gbp",
    }
    fields.update(extra)
    return Item.objects.create(**fields)


def add_photo(item, payload=b"jpeg-bytes", name="coat.jpg", position=None):
    if position is None:
        last = item.photos.order_by("-position").values_list("position", flat=True).first()
        position = 0 if last is None else last + 1
    return ItemPhoto.objects.create(
        item=item,
        image=SimpleUploadedFile(name, payload, content_type="image/jpeg"),
        position=position,
    )


def copies(*marketplaces, brand="COS", title=None, description=None):
    rows = []
    for marketplace in marketplaces:
        rows.append(
            {
                "marketplace": marketplace,
                "title": title if title is not None else f"{brand} navy coat",
                "description": description
                if description is not None
                else f"{brand} navy wool coat, size 12, good condition.",
            }
        )
    return {"listings": rows}


def draft(user, item, grok, marketplaces=None):
    arguments = {"action": "draft", "item_id": item.pk}
    if marketplaces is not None:
        arguments["marketplaces"] = marketplaces
    return draft_listings(user, arguments, grok=grok)


class BobbyDraftTests(TestCase):
    def test_another_sellers_item_fails_without_calling_grok(self):
        owner = make_user("owner")
        other = make_user("other")
        item = make_item(owner)
        add_photo(item)
        grok = FakeGrok(AssertionError("Grok was called"))

        result = draft(other, item, grok)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["item_id"], item.pk)
        self.assertIn("someone else", result["message"])
        self.assertEqual(result["listings"], [])
        self.assertEqual(grok.calls, [])
        self.assertEqual(item.listings.count(), 0)

    def test_missing_colour_or_photo_needs_details_without_calling_grok(self):
        user = make_user("ada")
        grok = FakeGrok(AssertionError("Grok was called"))
        colourless = make_item(user, colour="")
        add_photo(colourless)
        photoless = make_item(user)

        missing_colour = draft(user, colourless, grok)
        missing_photo = draft(user, photoless, grok)

        self.assertEqual(missing_colour["status"], "needs_details")
        self.assertIn("colour", missing_colour["message"])
        self.assertEqual(missing_photo["status"], "needs_details")
        self.assertIn("photo", missing_photo["message"])
        self.assertEqual(grok.calls, [])

    def test_confirmed_item_becomes_three_draft_listings(self):
        user = make_user("ada")
        item = make_item(user)
        payloads = [bytes([position]) for position in range(5)]
        for position, payload in enumerate(payloads):
            add_photo(item, payload=payload, name=f"{position}.jpg", position=position)
        grok = FakeGrok(copies("vinted", "depop", "ebay"))

        result = draft(user, item, grok)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(
            [row["marketplace"] for row in result["listings"]],
            ["vinted", "depop", "ebay"],
        )
        self.assertTrue(all(row["status"] == "draft" for row in result["listings"]))
        stored = list(item.listings.order_by("marketplace"))
        self.assertEqual([row.marketplace for row in stored], ["depop", "ebay", "vinted"])
        for listing in stored:
            self.assertEqual(listing.status, Listing.Status.DRAFT)
            self.assertEqual(listing.category_ref, "women/tops/blouse")
            self.assertEqual(
                listing.attributes,
                {
                    "department": "women",
                    "category": "tops",
                    "garment_type": "blouse",
                    "brand": "COS",
                    "colour": "navy",
                    "size_label": "12",
                    "size_system": "uk",
                    "condition": "good",
                    "material": "wool",
                },
            )
            self.assertEqual(listing.price_minor, 2500)
            self.assertEqual(listing.currency, "gbp")
            self.assertEqual(listing.title, "COS navy coat")
        call = grok.calls[0]
        self.assertEqual(call["model"], MODEL)
        self.assertEqual(MODEL, "grok-4.7")
        self.assertEqual(call["messages"][0]["content"], INSTRUCTIONS)
        images = [
            block
            for block in call["messages"][1]["content"]
            if block.get("type") == "image_url"
        ]
        self.assertEqual(len(images), 4)
        sent = json.dumps(images)
        self.assertIn(b64encode(payloads[0]).decode("ascii"), sent)
        self.assertNotIn(b64encode(payloads[4]).decode("ascii"), sent)

    def test_a_missing_price_stays_null(self):
        user = make_user("ada")
        item = make_item(user, price_minor=None)
        add_photo(item)
        grok = FakeGrok(copies("vinted"))

        result = draft(user, item, grok, marketplaces=["vinted"])

        self.assertEqual(result["status"], "ready")
        listing = item.listings.get(marketplace="vinted")
        self.assertIsNone(listing.price_minor)

    def test_existing_draft_is_updated_and_a_live_listing_is_skipped(self):
        user = make_user("ada")
        item = make_item(user)
        add_photo(item)
        Listing.objects.create(
            item=item,
            marketplace=Listing.Marketplace.VINTED,
            status=Listing.Status.LIVE,
            title="Old Vinted",
            description="Leave this.",
        )
        Listing.objects.create(
            item=item,
            marketplace=Listing.Marketplace.DEPOP,
            status=Listing.Status.DRAFT,
            title="Old Depop",
            description="Replace this.",
        )
        grok = FakeGrok(copies("depop", "ebay"))

        result = draft(user, item, grok)

        self.assertEqual(result["status"], "ready")
        self.assertIn("Depop and eBay", result["message"])
        self.assertIn("Vinted listing is already live", result["message"])
        vinted = item.listings.get(marketplace="vinted")
        depop = item.listings.get(marketplace="depop")
        ebay = item.listings.get(marketplace="ebay")
        self.assertEqual(vinted.title, "Old Vinted")
        self.assertEqual(vinted.status, Listing.Status.LIVE)
        self.assertEqual(depop.title, "COS navy coat")
        self.assertEqual(depop.status, Listing.Status.DRAFT)
        self.assertEqual(ebay.title, "COS navy coat")
        self.assertEqual(ebay.status, Listing.Status.DRAFT)
        asked = json.loads(grok.calls[0]["messages"][1]["content"][0]["text"].split("\n", 1)[1])
        self.assertEqual(
            [row["marketplace"] for row in asked["marketplaces"]],
            ["depop", "ebay"],
        )
        self.assertEqual(
            [row["marketplace"] for row in result["listings"]],
            ["vinted", "depop", "ebay"],
        )
        self.assertEqual(result["listings"][0]["title"], "Old Vinted")

    def test_over_long_title_or_missing_brand_does_not_save(self):
        user = make_user("ada")
        item = make_item(user)
        add_photo(item)
        Listing.objects.create(
            item=item,
            marketplace=Listing.Marketplace.VINTED,
            status=Listing.Status.DRAFT,
            title="Keep me",
            description="Keep this.",
        )
        too_long = FakeGrok(
            copies(
                "vinted",
                title="C" * (LIMITS["vinted"]["title"] + 1),
                description="COS navy coat.",
            )
        )
        missing_brand = FakeGrok(
            copies("vinted", title="Navy wool coat", description="Size 12, good condition.")
        )

        long_result = draft(user, item, too_long, marketplaces=["vinted"])
        item.listings.get(marketplace="vinted").refresh_from_db()
        brand_result = draft(user, item, missing_brand, marketplaces=["vinted"])

        self.assertEqual(long_result["status"], "failed")
        self.assertIn("100 characters", long_result["message"])
        self.assertEqual(brand_result["status"], "failed")
        self.assertIn("COS", brand_result["message"])
        listing = item.listings.get(marketplace="vinted")
        self.assertEqual(listing.title, "Keep me")
        self.assertEqual(listing.description, "Keep this.")
        self.assertEqual(item.listings.count(), 1)

    def test_call_tool_returns_bobbys_result_shape(self):
        user = make_user("ada")
        item = make_item(user, colour="")
        bobby = specialist_tools()[1]

        result = call_tool("bobby", user, {"action": "draft", "item_id": item.pk})

        self.assertIs(bobby, TOOLS["bobby"].schema)
        self.assertEqual(bobby["name"], "bobby")
        self.assertEqual(bobby["description"], BOBBY_DESCRIPTION)
        self.assertEqual(
            set(bobby["parameters"]["properties"]),
            {"action", "item_id", "marketplaces"},
        )
        self.assertEqual(
            set(result),
            {"status", "item_id", "message", "listings"},
        )
        self.assertEqual(result["status"], "needs_details")
        self.assertEqual(result["item_id"], item.pk)
        self.assertEqual(result["listings"], [])

    def test_bobby_copy_does_not_claim_to_publish(self):
        bullet = next(
            line
            for line in SALT_INSTRUCTIONS.splitlines()
            if line.strip().startswith("- Bobby")
        )
        for text in (BOBBY_MODULE_DOC, INSTRUCTIONS, BOBBY_DESCRIPTION, bullet):
            self.assertIsNone(CLAIM.search(text), text)

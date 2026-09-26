"""Maggie publishes drafts and takes the other copies down. No live browser calls."""

import io
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from accounts.models import MarketplaceConnection
from agents.maggie.sites import SITES
from agents.maggie.publish import PUBLISH_TIMEOUT, SHORT_TIMEOUT
from agents.salt.tools import specialist_tools
from agents.tools import TOOLS, call_tool
from listings.models import Item, ItemPhoto, Listing
from payments.models import Seller
from payments.services import record_sale
from services.browser_use.errors import BrowserUseTimeout

User = get_user_model()

PASSWORD = "s3cret-password"


def jpeg_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "navy").save(buffer, format="JPEG")
    return buffer.getvalue()


class FakeBrowser:
    def __init__(self, output=None, outputs=None, wait_error=None, create_error=None):
        self.outputs = list(outputs) if outputs is not None else [output]
        self.wait_error = wait_error
        self.create_error = create_error
        self.runs = []
        self.uploads = []
        self.cancelled = []
        self.released = []
        self.wait_kwargs = {}

    def create_workspace(self, name=None):
        return SimpleNamespace(id="ws_1")

    def upload_workspace_files(self, workspace_id, files):
        self.uploads.append({"workspace_id": workspace_id, "files": files})
        return tuple(SimpleNamespace(id=f"file_{index}") for index, _file in enumerate(files))

    def create_run(self, task, **kwargs):
        if self.create_error:
            raise self.create_error
        self.runs.append({"task": task, **kwargs})
        return SimpleNamespace(id=f"run_{len(self.runs)}", session_id="sess_1")

    def wait(self, run_id, **kwargs):
        self.wait_kwargs = kwargs
        if self.wait_error is not None:
            raise self.wait_error
        output = self.outputs.pop(0)
        return SimpleNamespace(status="completed", output=output)

    def cancel(self, run_id):
        self.cancelled.append(run_id)

    def release(self, session_id):
        self.released.append(session_id)


def make_user(name):
    user = User.objects.create_user(
        email=f"{name}@example.com",
        display_name=name,
        password="secret",
    )
    user.browser_profile_id = "prof_1"
    user.browser_profile_status = "ready"
    user.save(update_fields=["browser_profile_id", "browser_profile_status"])
    return user


def connect(user, *marketplaces):
    for marketplace in marketplaces:
        row = user.marketplace_connections.get(marketplace=marketplace)
        row.status = MarketplaceConnection.Status.CONNECTED
        row.save(update_fields=["status"])


def make_item(user, **extra):
    fields = {
        "user": user,
        "title": "Navy wool coat",
        "department": Item.Department.WOMEN,
        "category": Item.Category.TOPS,
        "garment_type": "coat",
        "brand": "COS",
        "colour": "navy",
        "size_label": "12",
        "size_system": Item.SizeSystem.UK,
        "condition": Item.Condition.GOOD,
        "price_minor": 2500,
        "currency": "gbp",
    }
    fields.update(extra)
    return Item.objects.create(**fields)


def add_photo(item):
    return ItemPhoto.objects.create(
        item=item,
        image=SimpleUploadedFile("coat.jpg", jpeg_bytes(), content_type="image/jpeg"),
        position=0,
    )


def make_listing(item, marketplace, **extra):
    fields = {
        "item": item,
        "marketplace": marketplace,
        "status": Listing.Status.DRAFT,
        "title": "COS navy coat",
        "description": "Wool coat, UK 12.",
        "price_minor": 2500,
        "currency": "gbp",
        "category_ref": "women/outerwear/coat",
        "attributes": {"brand": "COS", "condition": "good", "size_label": "12"},
    }
    fields.update(extra)
    return Listing.objects.create(**fields)


def make_seller(user):
    return Seller.objects.create(
        user=user,
        stripe_account_id=f"acct_{user.pk}",
        display_name=user.display_name,
        contact_email=user.email,
    )


class MaggieSchemaTests(TestCase):
    def test_salt_sends_the_callable_maggie_schema(self):
        maggie = next(tool for tool in specialist_tools() if tool["name"] == "maggie")
        self.assertIs(maggie, TOOLS["maggie"].schema)
        self.assertEqual(
            set(maggie["parameters"]["properties"]),
            {"action", "item_id", "marketplaces"},
        )
        self.assertEqual(
            SITES["vinted"].sell_url, "https://www.vinted.co.uk/items/new"
        )
        self.assertEqual(SITES["depop"].sell_url, "https://www.depop.com/products/create/")
        self.assertEqual(SITES["ebay"].sell_url, "https://www.ebay.co.uk/sl/sell")


class MaggiePublishTests(TestCase):
    def setUp(self):
        self.user = make_user("ada")
        self.item = make_item(self.user)
        add_photo(self.item)
        self.listing = make_listing(self.item, Listing.Marketplace.VINTED)

    def test_another_sellers_item_is_not_opened(self):
        other = make_user("bea")
        with patch("agents.maggie.publish.BrowserUseClient") as browser_cls:
            result = call_tool(
                "maggie",
                other,
                {"action": "publish", "item_id": self.item.pk},
            )
        browser_cls.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertIn("not found", result["message"])

    def test_a_missing_price_does_not_open_a_browser(self):
        self.listing.price_minor = None
        self.listing.save(update_fields=["price_minor"])
        with patch("agents.maggie.publish.BrowserUseClient") as browser_cls:
            result = call_tool(
                "maggie",
                self.user,
                {"action": "publish", "item_id": self.item.pk},
            )
        browser_cls.assert_not_called()
        self.assertEqual(result["status"], "needs_details")
        self.assertIn("price", result["message"])

    def test_a_live_listing_is_not_published_again(self):
        self.listing.status = Listing.Status.LIVE
        self.listing.external_url = "https://www.vinted.co.uk/items/9"
        self.listing.save(update_fields=["status", "external_url"])
        connect(self.user, "vinted")
        with patch("agents.maggie.publish.BrowserUseClient") as browser_cls:
            result = call_tool(
                "maggie",
                self.user,
                {"action": "publish", "item_id": self.item.pk, "marketplaces": ["vinted"]},
            )
        browser_cls.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertIn("already live", result["message"])

    def test_a_disconnected_marketplace_needs_login(self):
        with patch("agents.maggie.publish.BrowserUseClient") as browser_cls:
            result = call_tool(
                "maggie",
                self.user,
                {"action": "publish", "item_id": self.item.pk},
            )
        browser_cls.assert_not_called()
        self.assertEqual(result["status"], "needs_login")
        self.assertIn("not signed in", result["message"])
        self.assertEqual(
            self.user.marketplace_connections.get(marketplace="vinted").status,
            MarketplaceConnection.Status.NOT_CONNECTED,
        )

    def test_publish_stores_the_live_listing(self):
        connect(self.user, "vinted")
        browser = FakeBrowser(
            {
                "logged_in": True,
                "external_id": "v-99",
                "external_url": "https://www.vinted.co.uk/items/99",
                "detail": "",
            }
        )
        with patch("agents.maggie.publish.BrowserUseClient", return_value=browser):
            result = call_tool(
                "maggie",
                self.user,
                {
                    "action": "publish",
                    "item_id": self.item.pk,
                    "password": PASSWORD,
                },
            )
        self.listing.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(self.listing.status, Listing.Status.LIVE)
        self.assertEqual(self.listing.external_id, "v-99")
        self.assertEqual(self.listing.external_url, "https://www.vinted.co.uk/items/99")
        self.assertEqual(self.listing.sync_error, "")
        self.assertIsNotNone(self.listing.listed_at)
        self.assertEqual(self.item.status, Item.Status.LISTED)
        run = browser.runs[0]
        self.assertEqual(run["profile_id"], "prof_1")
        self.assertEqual(run["proxy_country_code"], "gb")
        self.assertIs(run["record"], False)
        self.assertEqual(run["workspace_id"], "ws_1")
        self.assertEqual(run["attached_file_ids"], ["file_0"])
        self.assertEqual(browser.wait_kwargs["timeout"], PUBLISH_TIMEOUT)
        self.assertIn("https://www.vinted.co.uk/items/new", run["task"])
        self.assertNotIn(PASSWORD, run["task"])
        self.assertNotIn(PASSWORD, json.dumps(result))
        self.assertNotIn("secret_bindings", run)
        self.assertEqual(browser.released, ["sess_1"])
        self.assertEqual(len(browser.uploads), 1)

    def test_a_timeout_fails_the_listing_and_stops_the_browser(self):
        connect(self.user, "vinted")
        browser = FakeBrowser(wait_error=BrowserUseTimeout("run_1", session_id="sess_1"))
        with patch("agents.maggie.publish.BrowserUseClient", return_value=browser):
            result = call_tool(
                "maggie", self.user, {"action": "publish", "item_id": self.item.pk}
            )
        self.listing.refresh_from_db()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.listing.status, Listing.Status.FAILED)
        self.assertIn("too long", self.listing.sync_error)
        self.assertEqual(browser.cancelled, ["run_1"])
        self.assertEqual(browser.released, ["sess_1"])

    def test_a_browser_crash_is_a_failed_result(self):
        connect(self.user, "vinted")
        browser = FakeBrowser(create_error=RuntimeError(f"leaked {PASSWORD}"))
        with patch("agents.maggie.publish.BrowserUseClient", return_value=browser):
            result = call_tool(
                "maggie",
                self.user,
                {"action": "publish", "item_id": self.item.pk, "password": PASSWORD},
            )
        self.listing.refresh_from_db()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.listing.status, Listing.Status.FAILED)
        self.assertNotIn(PASSWORD, json.dumps(result))
        self.assertNotIn("leaked", result["message"])
        self.assertEqual(browser.released, [])

    def test_a_logged_out_browser_needs_login(self):
        connect(self.user, "vinted")
        browser = FakeBrowser(
            {
                "logged_in": False,
                "external_id": "",
                "external_url": "",
                "detail": PASSWORD,
            }
        )
        with patch("agents.maggie.publish.BrowserUseClient", return_value=browser):
            result = call_tool(
                "maggie",
                self.user,
                {"action": "publish", "item_id": self.item.pk, "password": PASSWORD},
            )
        self.listing.refresh_from_db()
        row = self.user.marketplace_connections.get(marketplace="vinted")
        self.assertEqual(result["status"], "needs_login")
        self.assertEqual(row.status, MarketplaceConnection.Status.NEEDS_LOGIN)
        self.assertEqual(self.listing.status, Listing.Status.FAILED)
        self.assertNotIn(PASSWORD, json.dumps(result))
        self.assertNotIn(PASSWORD, row.error)


class MaggieSyncTests(TestCase):
    def setUp(self):
        self.user = make_user("ada")
        connect(self.user, "vinted", "depop")
        self.item = make_item(self.user)
        add_photo(self.item)
        self.vinted = make_listing(
            self.item,
            Listing.Marketplace.VINTED,
            status=Listing.Status.LIVE,
            external_id="v-1",
            external_url="https://www.vinted.co.uk/items/1",
        )
        self.depop = make_listing(
            self.item,
            Listing.Marketplace.DEPOP,
            status=Listing.Status.LIVE,
            external_id="d-1",
            external_url="https://www.depop.com/products/coat-1/",
        )

    def test_a_sold_listing_removes_the_other_live_url(self):
        browser = FakeBrowser(
            outputs=[
                {
                    "logged_in": True,
                    "state": "sold",
                    "external_id": "v-1",
                    "external_url": "https://www.vinted.co.uk/items/1",
                    "detail": "",
                },
                {"logged_in": True, "removed": True, "detail": ""},
            ]
        )
        with patch("agents.maggie.publish.BrowserUseClient", return_value=browser):
            result = call_tool(
                "maggie",
                self.user,
                {"action": "status", "item_id": self.item.pk, "marketplaces": ["vinted"]},
            )
        self.item.refresh_from_db()
        self.vinted.refresh_from_db()
        self.depop.refresh_from_db()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(self.item.status, Item.Status.SOLD)
        self.assertEqual(self.vinted.status, Listing.Status.SOLD)
        self.assertEqual(self.depop.status, Listing.Status.ENDED)
        self.assertEqual(self.depop.sync_error, "")
        self.assertEqual(len(browser.runs), 2)
        self.assertIn(self.depop.external_url, browser.runs[1]["task"])
        self.assertEqual(browser.wait_kwargs["timeout"], SHORT_TIMEOUT)
        self.assertEqual(browser.uploads, [])

    def test_a_failed_removal_leaves_the_listing_live(self):
        browser = FakeBrowser({"logged_in": True, "removed": False, "detail": ""})
        with patch("agents.maggie.publish.BrowserUseClient", return_value=browser):
            result = call_tool(
                "maggie",
                self.user,
                {"action": "delist", "item_id": self.item.pk, "marketplaces": ["depop"]},
            )
        self.depop.refresh_from_db()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.depop.status, Listing.Status.LIVE)
        self.assertIn("could not be removed", self.depop.sync_error)

    def test_record_sale_removes_the_other_copy_after_commit(self):
        seller = make_seller(self.user)
        browser = FakeBrowser({"logged_in": True, "removed": True, "detail": ""})
        with patch("agents.maggie.publish.BrowserUseClient", return_value=browser):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                record_sale(
                    seller=seller,
                    marketplace="vinted",
                    external_sale_id="sale-1",
                    amount_minor=2000,
                    listing=self.vinted,
                )
        self.vinted.refresh_from_db()
        self.depop.refresh_from_db()
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(self.vinted.status, Listing.Status.SOLD)
        self.assertEqual(self.depop.status, Listing.Status.ENDED)
        self.assertEqual(self.depop.sync_error, "")
        self.assertEqual(len(browser.runs), 1)
        self.assertIn(self.depop.external_url, browser.runs[0]["task"])
        self.assertNotIn(self.vinted.external_url, browser.runs[0]["task"])

"""Steve answers buyers through Browser Use, and only when the policy allows a send."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import MarketplaceConnection
from agents.steve.models import BuyerMessage, BuyerThread
from agents.steve.tool import STEVE_DESCRIPTION
from agents.salt.tools import specialist_tools
from agents.tools import TOOLS, call_tool
from listings.models import Item, Listing
from services.browser_use.models import Run

User = get_user_model()


class ScriptedBrowser:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.runs = []
        self.released = []

    def create_run(self, task, **options):
        self.runs.append({"task": task, **options})
        return Run(id="run_1", status="running", session_id="sess_1", task=task)

    def wait(self, run_id, **kwargs):
        output = self.outputs.pop(0)
        return Run(id=run_id, status="completed", session_id="sess_1", output=output)

    def cancel(self, run_id):
        return None

    def release(self, session_id):
        self.released.append(session_id)


class FakeGrok:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def ask_for_json_object(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return self.payload


def make_user(name):
    user = User.objects.create_user(
        email=f"{name}@example.com",
        display_name=name,
        password="secret",
    )
    user.browser_profile_id = "prof_1"
    user.browser_profile_status = "ready"
    user.save(update_fields=["browser_profile_id", "browser_profile_status"])
    row = user.marketplace_connections.get(marketplace="vinted")
    row.status = MarketplaceConnection.Status.CONNECTED
    row.save(update_fields=["status"])
    return user


def item_with_listing(user, *, floor=2000):
    item = Item.objects.create(
        user=user,
        title="Wool coat",
        description="Navy wool.",
        brand="COS",
        size_label="M",
        condition="good",
        flaws="Small mark on the cuff.",
        colour="navy",
        chest_cm=Decimal("96.0"),
        length_cm=Decimal("80.5"),
        price_minor=2500,
        min_offer_minor=floor,
    )
    Listing.objects.create(
        item=item,
        marketplace=Listing.Marketplace.VINTED,
        status=Listing.Status.LIVE,
        external_url="https://www.vinted.co.uk/items/1",
        title="Wool coat",
        description="Navy wool.",
        price_minor=2500,
    )
    return item


class SteveToolTests(TestCase):
    def test_schema_is_the_one_salt_sends(self):
        steve = TOOLS["steve"].schema
        self.assertIs(steve, specialist_tools()[4])
        self.assertEqual(steve["description"], STEVE_DESCRIPTION)
        self.assertIn("confirmed", steve["parameters"]["properties"])

    def test_check_stores_a_new_buyer_message_on_the_item(self):
        user = make_user("seller")
        item = item_with_listing(user)
        browser = ScriptedBrowser(
            [
                {
                    "logged_in": True,
                    "threads": [
                        {
                            "external_thread_id": "t1",
                            "buyer_name": "Bea",
                            "item_url": "https://www.vinted.co.uk/items/1",
                            "messages": [
                                {
                                    "external_id": "m1",
                                    "direction": "buyer",
                                    "body": "Is the mark on the cuff still there?",
                                }
                            ],
                        }
                    ],
                }
            ]
        )

        result = call_tool("steve", user, {"action": "check"}, browser=browser)

        thread = BuyerThread.objects.get(user=user, external_thread_id="t1")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(thread.item_id, item.pk)
        self.assertEqual(thread.buyer_name, "Bea")
        self.assertEqual(thread.messages.get().body, "Is the mark on the cuff still there?")
        self.assertEqual(browser.runs[0]["profile_id"], "prof_1")
        self.assertEqual(browser.runs[0]["proxy_country_code"], "gb")
        self.assertIs(browser.runs[0]["record"], False)
        self.assertNotIn("secret_bindings", browser.runs[0])
        self.assertIn("https://www.vinted.co.uk/inbox", browser.runs[0]["task"])
        self.assertNotIn("s3cret", browser.runs[0]["task"])
        self.assertEqual(browser.released, ["sess_1"])

    def test_reply_sends_the_draft_and_includes_measurements(self):
        user = make_user("seller")
        item = item_with_listing(user)
        thread = BuyerThread.objects.create(
            user=user,
            marketplace="vinted",
            external_thread_id="t1",
            item=item,
            buyer_name="Bea",
        )
        BuyerMessage.objects.create(
            thread=thread,
            direction=BuyerMessage.Direction.BUYER,
            body="What is the chest measurement?",
            external_id="m1",
        )
        browser = ScriptedBrowser([{"logged_in": True, "sent": True, "detail": "Sent."}])
        grok = FakeGrok(
            {
                "decision": "reply",
                "text": "The chest is 96 cm.",
                "reason": "The measurement is on the item.",
            }
        )

        result = call_tool(
            "steve",
            user,
            {"action": "reply", "thread_id": thread.pk, "password": "s3cret-pass"},
            grok=grok,
            browser=browser,
        )

        self.assertEqual(result["status"], "ready")
        self.assertIn("96 cm", result["message"])
        self.assertNotIn("s3cret-pass", result["message"])
        self.assertIn("96.0", grok.prompts[0])
        self.assertIn("80.5", grok.prompts[0])
        self.assertEqual(len(browser.runs), 1)
        self.assertIn("The chest is 96 cm.", browser.runs[0]["task"])
        self.assertNotIn("s3cret-pass", browser.runs[0]["task"])
        self.assertNotIn("secret_bindings", browser.runs[0])
        self.assertEqual(browser.runs[0]["profile_id"], "prof_1")
        self.assertEqual(browser.released, ["sess_1"])
        stored = BuyerMessage.objects.get(thread=thread, direction="seller")
        self.assertEqual(stored.body, "The chest is 96 cm.")

    def test_reply_escalates_when_the_answer_is_not_on_the_item(self):
        user = make_user("seller")
        item = item_with_listing(user)
        thread = BuyerThread.objects.create(
            user=user,
            marketplace="vinted",
            external_thread_id="t1",
            item=item,
            buyer_name="Bea",
        )
        BuyerMessage.objects.create(
            thread=thread,
            direction=BuyerMessage.Direction.BUYER,
            body="Can you post it to me and I'll pay by bank transfer?",
            external_id="m1",
        )
        browser = ScriptedBrowser([])
        grok = FakeGrok(
            {
                "decision": "escalate",
                "text": "",
                "reason": "The buyer wants to pay off Vinted.",
            }
        )

        result = call_tool(
            "steve",
            user,
            {"action": "reply", "thread_id": thread.pk},
            grok=grok,
            browser=browser,
        )

        thread.refresh_from_db()
        self.assertEqual(result["status"], "escalate")
        self.assertIn("off Vinted", result["message"])
        self.assertEqual(thread.status, BuyerThread.Status.NEEDS_SELLER)
        self.assertEqual(browser.runs, [])

    def test_offer_below_the_floor_does_not_message_the_buyer(self):
        user = make_user("seller")
        item = item_with_listing(user, floor=2000)
        thread = BuyerThread.objects.create(
            user=user,
            marketplace="vinted",
            external_thread_id="t1",
            item=item,
        )
        browser = ScriptedBrowser([])

        result = call_tool(
            "steve",
            user,
            {"action": "offer", "thread_id": thread.pk, "amount_minor": 1500},
            browser=browser,
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["counter_minor"], 2000)
        self.assertIn("2000", result["message"])
        self.assertEqual(browser.runs, [])
        self.assertEqual(BuyerMessage.objects.filter(direction="seller").count(), 0)

    def test_offer_at_the_floor_waits_for_the_seller(self):
        user = make_user("seller")
        item = item_with_listing(user, floor=2000)
        thread = BuyerThread.objects.create(
            user=user,
            marketplace="vinted",
            external_thread_id="t1",
            item=item,
        )
        browser = ScriptedBrowser([])

        result = call_tool(
            "steve",
            user,
            {"action": "offer", "thread_id": thread.pk, "amount_minor": 2000},
            browser=browser,
        )

        self.assertEqual(result["status"], "needs_confirmation")
        self.assertEqual(browser.runs, [])

    def test_confirmed_offer_is_sent(self):
        user = make_user("seller")
        item = item_with_listing(user, floor=2000)
        thread = BuyerThread.objects.create(
            user=user,
            marketplace="vinted",
            external_thread_id="t1",
            item=item,
            buyer_name="Bea",
        )
        browser = ScriptedBrowser([{"logged_in": True, "sent": True, "detail": "Sent."}])

        result = call_tool(
            "steve",
            user,
            {
                "action": "offer",
                "thread_id": thread.pk,
                "amount_minor": 2200,
                "confirmed": True,
            },
            browser=browser,
        )

        thread.refresh_from_db()
        self.assertEqual(result["status"], "ready")
        self.assertIn("£22.00", result["message"])
        self.assertEqual(thread.status, BuyerThread.Status.CLOSED)
        self.assertEqual(BuyerMessage.objects.filter(direction="seller").count(), 1)
        self.assertIn("£22.00", browser.runs[0]["task"])
        self.assertNotIn("secret_bindings", browser.runs[0])
        self.assertEqual(browser.released, ["sess_1"])

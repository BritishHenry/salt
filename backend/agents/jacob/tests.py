from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from accounts.models import ApiToken
from agents.jacob.pricing import PricingError, price_item
from agents.jacob.search import (
    COMP_OUTPUT_SCHEMA,
    MAX_COMPS,
    MAX_COST_USD,
    SEARCH_TIMEOUT_SECONDS,
    comps_from_output,
    marketplace_searches,
    search_query,
    task_for,
)
from listings.models import Comparable, Item, PriceQuote
from services.browser_use.errors import BrowserUseTimeout

VINTED_URL = "https://www.vinted.co.uk/items/1"
DEPOP_URL = "https://www.depop.com/products/1"
EBAY_URL = "https://www.ebay.co.uk/itm/1"


def make_user(name, **extra):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        email=f"{name}@example.com",
        display_name=name,
        password="secret",
        **extra,
    )


def coat(**extra):
    fields = {
        "title": "Navy wool coat",
        "brand": "COS",
        "garment_type": "wool coat",
        "colour": "navy",
        "size_label": "12",
        "condition": Item.Condition.GOOD,
    }
    fields.update(extra)
    return fields


def listing(url, price, **extra):
    row = {
        "title": "Wool coat",
        "price_pence": price,
        "currency": "gbp",
        "condition": "good",
        "size": "12",
        "url": url,
        "sold": False,
    }
    row.update(extra)
    return row


def judgment(url, similarity="high", reason="Same coat and size."):
    return {"url": url, "similarity": similarity, "reason": reason}


class FakeBrowser:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def run(self, task, **options):
        marketplace = _marketplace_of(task)
        self.calls.append({"task": task, "marketplace": marketplace, **options})
        result = self.results[marketplace]
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(output={"comps": result})


class FakeGrok:
    def __init__(self, decision):
        self.decision = decision
        self.prompts = []
        self.kwargs = []

    def ask_for_json_object(self, prompt, **kwargs):
        self.prompts.append(prompt)
        self.kwargs.append(kwargs)
        if isinstance(self.decision, Exception):
            raise self.decision
        return self.decision


def _marketplace_of(task):
    if "vinted.co.uk" in task:
        return "vinted"
    if "depop.com" in task:
        return "depop"
    if "ebay.co.uk" in task:
        return "ebay"
    raise AssertionError(task)


class SearchQueryTests(SimpleTestCase):
    def test_query_and_uk_search_urls_come_from_the_item(self):
        item = Item(
            brand="COS",
            garment_type="wool coat",
            category=Item.Category.OUTERWEAR,
            colour="navy",
            size_label="12",
            title="Ignored title",
        )
        query = search_query(item)
        self.assertEqual(query, "COS wool coat navy 12")
        searches = {search.marketplace: search for search in marketplace_searches(query)}
        encoded = "COS+wool+coat+navy+12"
        self.assertEqual(
            searches["vinted"].urls,
            (f"https://www.vinted.co.uk/catalog?search_text={encoded}",),
        )
        self.assertEqual(
            searches["depop"].urls,
            (f"https://www.depop.com/search/?q={encoded}",),
        )
        self.assertEqual(
            searches["ebay"].urls,
            (
                f"https://www.ebay.co.uk/sch/i.html?_nkw={encoded}&LH_PrefLoc=1",
                "https://www.ebay.co.uk/sch/i.html?_nkw="
                f"{encoded}&LH_Sold=1&LH_Complete=1&LH_PrefLoc=1",
            ),
        )
        ebay_task = task_for(searches["ebay"])
        self.assertIn(searches["ebay"].urls[0], ebay_task)
        self.assertIn(searches["ebay"].urls[1], ebay_task)

    def test_category_label_is_used_when_the_garment_type_is_blank(self):
        item = Item(
            brand="Arket",
            category=Item.Category.OUTERWEAR,
            colour="navy",
            size_label="10",
        )
        self.assertEqual(search_query(item), "Arket Outerwear navy 10")

    def test_title_is_used_when_the_item_has_no_other_search_words(self):
        self.assertEqual(search_query(Item(title="Navy coat")), "Navy coat")


class CompFilterTests(SimpleTestCase):
    def test_drops_non_gbp_and_non_positive_prices_and_caps_each_marketplace(self):
        valid = [
            listing(f"https://www.vinted.co.uk/items/{index}", 1000 + index)
            for index in range(1, MAX_COMPS + 2)
        ]
        rows = [
            listing("https://www.vinted.co.uk/items/usd", 500, currency="usd"),
            listing("https://www.vinted.co.uk/items/zero", 0),
            listing("https://www.vinted.co.uk/items/blank", 800, currency=""),
            *valid,
        ]
        kept = comps_from_output({"comps": rows}, "vinted")
        self.assertEqual(len(kept), MAX_COMPS)
        self.assertEqual([comp["price_minor"] for comp in kept], list(range(1001, 1009)))
        self.assertTrue(all(comp["currency"] == "gbp" for comp in kept))
        self.assertNotIn(
            "https://www.vinted.co.uk/items/9",
            [comp["url"] for comp in kept],
        )


class PriceItemTests(TestCase):
    def setUp(self):
        self.user = make_user("seller")
        self.user.browser_profile_id = "prof_seller"
        self.user.browser_profile_status = "ready"
        self.user.save(
            update_fields=["browser_profile_id", "browser_profile_status"]
        )

    def test_one_marketplace_failing_still_prices_from_the_others(self):
        item = Item.objects.create(user=self.user, **coat())
        browser = FakeBrowser(
            {
                "vinted": BrowserUseTimeout("run-vinted"),
                "depop": [listing(DEPOP_URL, 2000)],
                "ebay": [listing(EBAY_URL, 2600, sold=True)],
            }
        )
        grok = FakeGrok(
            {
                "price_pence": 2200,
                "rationale": "Between the Depop ask and the eBay sale.",
                "comps": [
                    judgment(DEPOP_URL),
                    judgment(EBAY_URL, reason="Sold in the same size."),
                ],
            }
        )
        quote = price_item(item, browser=browser, grok=grok)
        item.refresh_from_db()
        self.assertEqual(quote.status, PriceQuote.Status.READY)
        self.assertEqual(quote.price_minor, 2200)
        self.assertEqual(item.price_minor, 2200)
        self.assertEqual(
            set(quote.comps.values_list("marketplace", flat=True)),
            {"depop", "ebay"},
        )
        self.assertEqual(len(browser.calls), 3)
        for call in browser.calls:
            self.assertEqual(call["profile_id"], "prof_seller")
            self.assertEqual(call["proxy_country_code"], "gb")
            self.assertEqual(call["timeout"], SEARCH_TIMEOUT_SECONDS)
            self.assertEqual(call["max_cost_usd"], MAX_COST_USD)
            self.assertEqual(call["output_schema"], COMP_OUTPUT_SCHEMA)
        self.assertIn("unknown", grok.prompts[0])

    def test_all_marketplaces_failing_leaves_the_item_price_empty(self):
        self.user.browser_profile_status = "pending"
        self.user.save(update_fields=["browser_profile_status"])
        item = Item.objects.create(user=self.user, **coat())
        browser = FakeBrowser(
            {
                "vinted": BrowserUseTimeout("run-vinted"),
                "depop": BrowserUseTimeout("run-depop"),
                "ebay": BrowserUseTimeout("run-ebay"),
            }
        )
        grok = FakeGrok({})
        quote = price_item(item, browser=browser, grok=grok)
        item.refresh_from_db()
        self.assertEqual(quote.status, PriceQuote.Status.FAILED)
        self.assertIsNone(quote.price_minor)
        self.assertIsNone(item.price_minor)
        self.assertFalse(quote.comps.exists())
        self.assertEqual(grok.prompts, [])
        self.assertIn("vinted", quote.error)
        self.assertTrue(all(call["profile_id"] is None for call in browser.calls))

    def test_in_range_price_fills_an_empty_item_price(self):
        item = Item.objects.create(user=self.user, **coat(condition="", size_label=""))
        browser = FakeBrowser(
            {
                "vinted": [listing(VINTED_URL, 1800)],
                "depop": [listing(DEPOP_URL, 2200)],
                "ebay": [listing(EBAY_URL, 2000)],
            }
        )
        grok = FakeGrok(
            {
                "price_pence": 2000,
                "rationale": "The middle of the close comps.",
                "comps": [
                    judgment(VINTED_URL),
                    judgment(DEPOP_URL, similarity="medium"),
                    judgment(EBAY_URL, similarity="low", reason="Different size."),
                ],
            }
        )
        quote = price_item(item, browser=browser, grok=grok)
        item.refresh_from_db()
        self.assertEqual(quote.status, PriceQuote.Status.READY)
        self.assertEqual(quote.price_minor, 2000)
        self.assertEqual(item.price_minor, 2000)
        stored = {comp.url: comp for comp in quote.comps.all()}
        self.assertEqual(stored[EBAY_URL].similarity, Comparable.Similarity.LOW)
        self.assertEqual(stored[VINTED_URL].similarity, Comparable.Similarity.HIGH)
        self.assertIn('"condition": "unknown"', grok.prompts[0])
        self.assertIn('"size": "unknown"', grok.prompts[0])

    def test_an_existing_item_price_is_kept(self):
        item = Item.objects.create(user=self.user, **coat(price_minor=4200))
        browser = FakeBrowser(
            {
                "vinted": [listing(VINTED_URL, 1800)],
                "depop": [listing(DEPOP_URL, 2200)],
                "ebay": [],
            }
        )
        grok = FakeGrok(
            {
                "price_pence": 2000,
                "rationale": "Close comps sit lower.",
                "comps": [judgment(VINTED_URL), judgment(DEPOP_URL)],
            }
        )
        quote = price_item(item, browser=browser, grok=grok)
        item.refresh_from_db()
        self.assertEqual(quote.price_minor, 2000)
        self.assertEqual(item.price_minor, 4200)

    def test_a_price_outside_the_close_comps_is_rejected(self):
        item = Item.objects.create(user=self.user, **coat())
        browser = FakeBrowser(
            {
                "vinted": [listing(VINTED_URL, 1800)],
                "depop": [listing(DEPOP_URL, 2200)],
                "ebay": [],
            }
        )
        grok = FakeGrok(
            {
                "price_pence": 9000,
                "rationale": "Too high.",
                "comps": [judgment(VINTED_URL), judgment(DEPOP_URL)],
            }
        )
        quote = price_item(item, browser=browser, grok=grok)
        item.refresh_from_db()
        self.assertEqual(quote.status, PriceQuote.Status.FAILED)
        self.assertIsNone(quote.price_minor)
        self.assertIsNone(item.price_minor)
        self.assertIn("outside", quote.error)
        self.assertEqual(quote.comps.count(), 2)

    def test_low_comps_do_not_set_a_price(self):
        item = Item.objects.create(user=self.user, **coat())
        browser = FakeBrowser(
            {
                "vinted": [listing(VINTED_URL, 1800)],
                "depop": [],
                "ebay": [],
            }
        )
        grok = FakeGrok(
            {
                "price_pence": 1800,
                "rationale": "Only a loose match.",
                "comps": [judgment(VINTED_URL, similarity="low")],
            }
        )
        quote = price_item(item, browser=browser, grok=grok)
        item.refresh_from_db()
        self.assertEqual(quote.status, PriceQuote.Status.FAILED)
        self.assertIsNone(item.price_minor)
        self.assertEqual(quote.comps.get().similarity, Comparable.Similarity.LOW)

    def test_a_blank_item_is_refused_before_any_browser_run(self):
        item = Item.objects.create(
            user=self.user, colour="navy", size_label="12", condition=Item.Condition.GOOD
        )
        browser = FakeBrowser({})
        grok = FakeGrok({})
        with self.assertRaises(PricingError):
            price_item(item, browser=browser, grok=grok)
        self.assertEqual(browser.calls, [])
        self.assertEqual(grok.prompts, [])
        self.assertEqual(PriceQuote.objects.count(), 0)


class PriceApiTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.item = Item.objects.create(user=self.owner, **coat())
        self.token = ApiToken.objects.create(user=self.owner)
        self.browser = FakeBrowser(
            {
                "vinted": [listing(VINTED_URL, 1800)],
                "depop": [listing(DEPOP_URL, 2200)],
                "ebay": [listing(EBAY_URL, 2000)],
            }
        )
        self.grok = FakeGrok(
            {
                "price_pence": 2000,
                "rationale": "Middle of the comps.",
                "comps": [
                    judgment(VINTED_URL),
                    judgment(DEPOP_URL),
                    judgment(EBAY_URL),
                ],
            }
        )
        patch(
            "agents.jacob.search.BrowserUseClient", return_value=self.browser
        ).start()
        patch(
            "agents.jacob.pricing.GrokClient.from_environment",
            return_value=self.grok,
        ).start()
        self.addCleanup(patch.stopall)

    def test_owner_receives_the_quote(self):
        response = self.client.post(
            f"/api/listings/items/{self.item.pk}/price/",
            HTTP_AUTHORIZATION=f"Bearer {self.token.key}",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["quote"]["status"], "ready")
        self.assertEqual(body["quote"]["price_minor"], 2000)
        self.assertEqual(len(body["quote"]["comps"]), 3)
        self.assertEqual(body["item"]["price_minor"], 2000)
        self.item.refresh_from_db()
        self.assertEqual(self.item.price_minor, 2000)

    def test_authentication_is_required(self):
        response = self.client.post(f"/api/listings/items/{self.item.pk}/price/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(PriceQuote.objects.count(), 0)

    def test_another_users_item_is_hidden(self):
        other = make_user("other")
        token = ApiToken.objects.create(user=other)
        response = self.client.post(
            f"/api/listings/items/{self.item.pk}/price/",
            HTTP_AUTHORIZATION=f"Bearer {token.key}",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(PriceQuote.objects.count(), 0)
        self.assertEqual(self.browser.calls, [])


class JacobToolTests(TestCase):
    def test_price_action_returns_the_quote_salt_can_say(self):
        from agents.jacob.tool import JACOB_DESCRIPTION
        from agents.salt.tools import specialist_tools
        from agents.tools import TOOLS, call_tool

        user = make_user("pricer")
        item = Item.objects.create(
            user=user,
            title="Navy wool coat",
            brand="COS",
            garment_type="coat",
            price_minor=None,
        )
        quote = PriceQuote(
            item=item,
            status=PriceQuote.Status.READY,
            price_minor=2400,
            currency="gbp",
            rationale="Close to sold coats in the same size.",
        )

        with patch("agents.jacob.tool.price_item", return_value=quote) as price:
            result = call_tool("jacob", user, {"action": "price", "item_id": item.pk})

        price.assert_called_once()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["item_id"], item.pk)
        self.assertEqual(result["price_minor"], 2400)
        self.assertEqual(result["currency"], "gbp")
        self.assertIn("£24.00", result["message"])
        jacob = TOOLS["jacob"].schema
        self.assertIs(jacob, specialist_tools()[2])
        self.assertEqual(jacob["description"], JACOB_DESCRIPTION)
        self.assertEqual(set(jacob["parameters"]["properties"]), {"action", "item_id"})

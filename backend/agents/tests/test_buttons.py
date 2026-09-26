import base64
import io
import json
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from PIL import Image

from agents.buttons.errors import ButtonsError
from agents.buttons.photos import fetch_image
from agents.buttons.schema import FIELD_ORDER
from agents.salt.dispatch import TOOLS, DispatchError, dispatch
from listings.models import Item
from services.grok.constants import DEFAULT_TEXT_MODEL

User = get_user_model()
MEDIA = tempfile.mkdtemp(prefix="salt-buttons-")


def make_user(name):
    return User.objects.create_user(
        email=f"{name}@example.com",
        display_name=name,
        password="secret",
    )


def jpeg_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), (12, 80, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


def found(value, confidence="high", evidence="visible"):
    return {"value": value, "confidence": confidence, "evidence": evidence}


def reading(**overrides):
    payload = {field: None for field in FIELD_ORDER}
    payload.update(overrides)
    return payload


def ready_reading():
    return reading(
        category=found("tops"),
        brand=found("Nike"),
        colour=found("white"),
        size_label=found("UK 10"),
        size_system=found("uk"),
        condition=found("good"),
    )


class FakeChat:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads.pop(0)
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}


class FakeFiles:
    def __init__(self, data):
        self.data = data

    def download_file_bytes(self, file_id, **kwargs):
        return self.data


class FakeGrok:
    def __init__(self, payloads, data=None):
        if isinstance(payloads, dict):
            payloads = [payloads]
        self.chat = FakeChat(payloads)
        self.files = FakeFiles(jpeg_bytes() if data is None else data)


def call(user, grok, **arguments):
    return dispatch("buttons", arguments, user, grok=grok)


@override_settings(MEDIA_ROOT=MEDIA)
class ButtonsToolTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def test_tool_is_registered_for_salt(self):
        self.assertEqual([tool["function"]["name"] for tool in TOOLS], ["buttons"])

    def test_read_photo_stores_a_draft_and_leaves_columns_blank(self):
        user = make_user("seller")
        grok = FakeGrok(ready_reading())

        result = call(
            user,
            grok,
            action="read_photo",
            image_file_id="file_1",
            user_id=999999,
        )

        item = Item.objects.get(pk=result["item_id"])
        self.assertEqual(item.user_id, user.pk)
        self.assertEqual(item.status, Item.Status.DRAFT)
        self.assertEqual(item.source, "buttons")
        self.assertEqual(item.photos.count(), 1)
        self.assertEqual(item.photos.get().position, 0)
        for field in (
            "title",
            "brand",
            "category",
            "colour",
            "size_label",
            "size_system",
            "condition",
        ):
            self.assertEqual(getattr(item, field), "")
        self.assertEqual(item.proposals["brand"]["value"], "Nike")
        self.assertEqual(result["status"], "needs_confirmation")
        chat_call = grok.chat.calls[0]
        self.assertEqual(chat_call["model"], DEFAULT_TEXT_MODEL)
        self.assertEqual(chat_call["response_format"]["type"], "json_schema")
        self.assertEqual(
            chat_call["messages"][1]["content"][1]["image_url"]["file_id"],
            "file_1",
        )

    def test_second_photo_fills_unconfirmed_fields_only(self):
        user = make_user("seller")
        grok = FakeGrok(
            [
                reading(brand=found("Nike"), category=found("tops")),
                reading(brand=found("Adidas"), colour=found("red")),
            ]
        )
        created = call(user, grok, action="read_photo", image_file_id="file_1")
        call(
            user,
            grok,
            action="confirm_field",
            item_id=created["item_id"],
            field="brand",
        )

        call(user, grok, action="add_photo", item_id=created["item_id"], image_file_id="file_2")

        item = Item.objects.get(pk=created["item_id"])
        self.assertEqual(item.brand, "Nike")
        self.assertEqual(item.colour, "")
        self.assertNotIn("brand", item.proposals)
        self.assertEqual(item.proposals["colour"]["value"], "red")
        self.assertEqual(item.proposals["category"]["value"], "tops")
        self.assertEqual(item.photos.count(), 2)
        self.assertEqual(list(item.photos.values_list("position", flat=True)), [0, 1])

    def test_confirm_field_and_apply_answer_mark_fields_confirmed(self):
        user = make_user("seller")
        grok = FakeGrok(reading(category=found("tops"), brand=found("Nike")))
        created = call(user, grok, action="read_photo", image_file_id="file_1")

        confirmed = call(
            user,
            grok,
            action="confirm_field",
            item_id=created["item_id"],
            field="category",
        )
        answered = call(
            user,
            grok,
            action="apply_answer",
            item_id=created["item_id"],
            field="brand",
            value="unbranded",
        )

        item = Item.objects.get(pk=created["item_id"])
        self.assertEqual(item.category, "tops")
        self.assertEqual(item.brand, "")
        self.assertEqual(confirmed["confirmed"]["category"], "tops")
        self.assertEqual(answered["confirmed"]["brand"], "unbranded")
        self.assertNotIn("category", item.proposals)
        self.assertNotIn("brand", item.proposals)
        self.assertIn("category", item.confirmed_fields)
        self.assertIn("brand", item.confirmed_fields)
        self.assertNotIn("brand", answered["missing_required"])

    def test_missing_required_fields_yield_one_question(self):
        user = make_user("seller")
        grok = FakeGrok(reading())

        result = call(user, grok, action="read_photo", image_file_id="file_1")

        self.assertEqual(result["status"], "needs_details")
        self.assertEqual(
            result["missing_required"],
            ["category", "brand", "colour", "size_label", "size_system", "condition"],
        )
        self.assertEqual(
            set(result["next_question"]),
            {"field", "prompt", "choices", "asks_for_photo"},
        )
        self.assertEqual(result["next_question"]["field"], "category")
        self.assertFalse(result["next_question"]["asks_for_photo"])
        self.assertIn(
            {"value": "tops", "label": "Tops"},
            result["next_question"]["choices"],
        )

    def test_low_confidence_brand_asks_for_a_label_photo(self):
        user = make_user("seller")
        grok = FakeGrok(
            reading(
                category=found("tops"),
                brand=found("Nke", confidence="low", evidence="blurry label"),
            )
        )

        result = call(user, grok, action="read_photo", image_file_id="file_1")

        question = result["next_question"]
        self.assertEqual(question["field"], "brand")
        self.assertTrue(question["asks_for_photo"])
        self.assertIsNone(question["choices"])
        self.assertIn("label", question["prompt"].lower())
        self.assertIn("label", result["summary"].lower())

    def test_confirm_item_is_ready_when_required_details_are_accepted(self):
        user = make_user("seller")
        grok = FakeGrok(ready_reading())
        created = call(user, grok, action="read_photo", image_file_id="file_1")

        result = call(user, grok, action="confirm_item", item_id=created["item_id"])

        item = Item.objects.get(pk=created["item_id"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["missing_required"], [])
        self.assertIsNone(result["next_question"])
        self.assertEqual(result["proposed"], [])
        self.assertEqual(item.status, Item.Status.DRAFT)
        self.assertEqual(item.brand, "Nike")
        self.assertEqual(item.category, "tops")
        self.assertEqual(item.colour, "white")
        self.assertEqual(item.size_label, "UK 10")
        self.assertEqual(item.size_system, "uk")
        self.assertEqual(item.condition, "good")
        self.assertEqual(item.proposals, {})

    def test_deny_item_archives_the_draft(self):
        user = make_user("seller")
        grok = FakeGrok(reading(brand=found("Nike")))
        created = call(user, grok, action="read_photo", image_file_id="file_1")

        result = call(user, grok, action="deny_item", item_id=created["item_id"])

        item = Item.objects.get(pk=created["item_id"])
        self.assertEqual(result["status"], "archived")
        self.assertIsNone(result["next_question"])
        self.assertEqual(item.status, Item.Status.ARCHIVED)
        self.assertEqual(item.proposals, {})

    def test_dispatch_refuses_another_users_item_and_unknown_tools(self):
        owner = make_user("owner")
        other = make_user("other")
        grok = FakeGrok(reading(brand=found("Nike")))
        created = call(owner, grok, action="read_photo", image_file_id="file_1")

        with self.assertRaises(ButtonsError) as refused:
            call(other, grok, action="deny_item", item_id=created["item_id"])
        self.assertIn("someone else", str(refused.exception))
        self.assertEqual(
            Item.objects.get(pk=created["item_id"]).status,
            Item.Status.DRAFT,
        )
        with self.assertRaises(DispatchError):
            dispatch("willow", {}, owner, grok=grok)

    def test_unrecognised_choice_does_not_save_an_item(self):
        user = make_user("seller")
        grok = FakeGrok(reading(category=found("hat")))

        with self.assertRaises(ButtonsError):
            call(user, grok, action="read_photo", image_file_id="file_1")

        self.assertEqual(Item.objects.count(), 0)

    def test_data_image_and_private_url(self):
        encoded = base64.b64encode(jpeg_bytes()).decode("ascii")
        data = fetch_image(f"data:image/jpeg;base64,{encoded}")
        self.assertTrue(data.startswith(b"\xff\xd8"))
        with self.assertRaises(ButtonsError):
            fetch_image("https://127.0.0.1/coat.jpg")

"""Read buyer messages and answer from the item the seller already confirmed."""

import json

from django.db import transaction

from accounts.models import MarketplaceConnection
from agents.steve.models import BuyerMessage, BuyerThread
from agents.steve.sites import SITES
from listings.models import Listing
from services.browser_use import BrowserUseClient
from services.browser_use.errors import BrowserUseTimeout
from services.grok import GrokClient

CHECK_TIMEOUT = 180

INBOX_SCHEMA = {
    "type": "object",
    "properties": {
        "logged_in": {"type": "boolean"},
        "threads": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "external_thread_id": {"type": "string"},
                    "buyer_name": {"type": "string"},
                    "item_url": {"type": "string"},
                    "messages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "external_id": {"type": "string"},
                                "direction": {"type": "string", "enum": ["buyer", "seller"]},
                                "body": {"type": "string"},
                                "offer_pence": {"type": "integer"},
                            },
                            "required": ["external_id", "direction", "body"],
                        },
                    },
                },
                "required": ["external_thread_id", "messages"],
            },
        },
    },
    "required": ["logged_in", "threads"],
}

SEND_SCHEMA = {
    "type": "object",
    "properties": {
        "logged_in": {"type": "boolean"},
        "sent": {"type": "boolean"},
        "detail": {"type": "string"},
    },
    "required": ["logged_in", "sent"],
}

REPLY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {"type": "string", "enum": ["reply", "escalate"]},
        "text": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["decision", "text", "reason"],
}

REPLY_INSTRUCTIONS = (
    "You answer a buyer about one second-hand garment. "
    "Use only the item facts in the message, including measurements when they are present. "
    "If the buyer asks for a fact that is not there, or asks to pay or ship off the marketplace, "
    "set decision to escalate and leave text empty. "
    "Do not invent a measurement, flaw, price, or discount. "
    "A reply is one short message the seller could send."
)

_ACTIONS = frozenset({"check", "reply", "offer"})


def run_steve(user, arguments, *, grok=None, browser=None):
    """Check an inbox, reply from item facts, or handle an offer."""
    if not isinstance(arguments, dict):
        return _failed("Tool arguments must be an object.")
    action = arguments.get("action")
    if action not in _ACTIONS:
        return _failed("action must be check, reply, or offer.")
    client = browser if browser is not None else BrowserUseClient()
    if action == "check":
        return _check(user, arguments, client)
    if action == "reply":
        return _reply(user, arguments, client, grok)
    return _offer(user, arguments, client)


def _check(user, arguments, client):
    try:
        slugs = _marketplaces(arguments.get("marketplaces", None))
    except ValueError as exc:
        return _failed(str(exc))
    if slugs is None:
        slugs = [
            row.marketplace
            for row in user.marketplace_connections.filter(
                status=MarketplaceConnection.Status.CONNECTED
            )
        ]
    if not slugs:
        return _result("needs_login", "Ask Willow to connect a marketplace first.", [])
    found = []
    statuses = []
    for slug in slugs:
        site = SITES.get(slug)
        if site is None:
            return _failed("marketplace must be vinted, depop, or ebay.")
        gate = _session_gate(user, site)
        if gate is not None:
            statuses.append(gate[0])
            found.append({"marketplace": slug, "message": gate[1]})
            continue
        outcome = _browse(
            client,
            task=_inbox_task(site),
            profile_id=user.browser_profile_id,
            output_schema=INBOX_SCHEMA,
        )
        if outcome.get("kind") != "done":
            statuses.append("failed")
            found.append({"marketplace": slug, "message": _outage(site, outcome)})
            continue
        output = outcome.get("output")
        if not isinstance(output, dict) or output.get("logged_in") is not True:
            if isinstance(output, dict) and output.get("logged_in") is False:
                _mark_needs_login(user, site)
                statuses.append("needs_login")
                found.append(
                    {"marketplace": slug, "message": f"Ask Willow to connect {site.label} again."}
                )
            else:
                statuses.append("failed")
                found.append(
                    {
                        "marketplace": slug,
                        "message": f"{site.label} did not report the inbox. Ask the seller to try again.",
                    }
                )
            continue
        new_rows = _store_threads(user, site, output.get("threads"))
        statuses.append("ready")
        found.extend(new_rows)
    status = _overall(statuses)
    if not found:
        message = "No new buyer messages."
    else:
        message = " ".join(row["message"] for row in found if row.get("message"))
    return _result(status, message or "No new buyer messages.", found)


def _reply(user, arguments, client, grok):
    thread = _thread(user, arguments.get("thread_id"))
    if isinstance(thread, dict):
        return thread
    if thread.item_id is None:
        return _escalate(thread, "I don't know which item this conversation is about.")
    latest = (
        thread.messages.filter(direction=BuyerMessage.Direction.BUYER)
        .order_by("-created_at", "-pk")
        .first()
    )
    if latest is None:
        return _escalate(thread, "There is no buyer message to answer.")
    facts = _facts(thread.item)
    try:
        decision = _ask(grok, facts, latest.body)
    except Exception:
        return _failed("That reply could not be written. Ask the seller to try again.", thread)
    if decision.get("decision") != "reply" or not _text(decision.get("text")):
        reason = _text(decision.get("reason")) or "That needs the seller."
        return _escalate(thread, reason)
    text = _text(decision["text"])
    sent = _send(client, user, thread, text)
    if sent["status"] != "ready":
        return sent
    _store_seller_message(thread, text, external_id=f"salt-reply-{latest.pk}")
    return _result("ready", text, [_thread_row(thread, text)])


def _offer(user, arguments, client):
    thread = _thread(user, arguments.get("thread_id"))
    if isinstance(thread, dict):
        return thread
    amount = arguments.get("amount_minor")
    if type(amount) is not int or amount < 1:
        return _failed("amount_minor must be a positive integer.", thread)
    if thread.item_id is None:
        return _escalate(thread, "I don't know which item this offer is for.")
    floor = thread.item.min_offer_minor
    if floor is None:
        return _needs_seller(
            thread,
            "No minimum offer is set. Ask the seller before accepting.",
            amount,
        )
    if amount < floor:
        return _result(
            "ready",
            f"That offer is below the minimum of {floor} pence. Suggest {floor} pence instead.",
            [_thread_row(thread, f"Counter at {floor} pence.")],
            counter_minor=floor,
        )
    if arguments.get("confirmed") is not True:
        return _needs_seller(
            thread,
            f"The offer of {amount} pence is at or above the minimum. Ask the seller before accepting.",
            amount,
        )
    text = f"Yes, I'll accept £{amount // 100}.{amount % 100:02d}."
    sent = _send(client, user, thread, text)
    if sent["status"] != "ready":
        return sent
    _store_seller_message(thread, text, external_id=f"salt-offer-{thread.pk}-{amount}", offer_minor=amount)
    thread.status = BuyerThread.Status.CLOSED
    thread.save(update_fields=["status", "updated_at"])
    return _result("ready", text, [_thread_row(thread, text)])


def _send(client, user, thread, text):
    site = SITES.get(thread.marketplace)
    if site is None:
        return _failed("That marketplace is not supported.", thread)
    gate = _session_gate(user, site)
    if gate is not None:
        return _result(gate[0], gate[1], [_thread_row(thread, gate[1])])
    outcome = _browse(
        client,
        task=_send_task(site, thread, text),
        profile_id=user.browser_profile_id,
        output_schema=SEND_SCHEMA,
    )
    if outcome.get("kind") != "done":
        return _result("failed", _outage(site, outcome), [_thread_row(thread, _outage(site, outcome))])
    output = outcome.get("output")
    if not isinstance(output, dict) or output.get("logged_in") is not True:
        if isinstance(output, dict) and output.get("logged_in") is False:
            _mark_needs_login(user, site)
            return _result(
                "needs_login",
                f"Ask Willow to connect {site.label} again.",
                [_thread_row(thread, f"Ask Willow to connect {site.label} again.")],
            )
        message = f"{site.label} did not send the message. Ask the seller to try again."
        return _result("failed", message, [_thread_row(thread, message)])
    if output.get("sent") is not True:
        message = _text(output.get("detail")) or f"{site.label} did not send the message."
        return _result("failed", message, [_thread_row(thread, message)])
    return _result("ready", text, [])


def _send_task(site, thread, text):
    return (
        f"Open {site.inbox_url}. The seller is already signed in. "
        f"Find the conversation {thread.external_thread_id} with {thread.buyer_name or 'the buyer'}. "
        f"Send exactly this message and nothing else: {text} "
        "Do not type a password. Do not accept a payment off the site. "
        "Report whether the message was sent."
    )


def _inbox_task(site):
    return (
        f"Open {site.inbox_url}. Do not type a password and do not send a message. "
        f"List each {site.label} conversation, its id, the buyer name, the item URL, "
        "and the messages with their ids, whether the buyer or the seller wrote them, "
        "the text, and any offer in pence."
    )


def _store_threads(user, site, threads):
    rows = []
    if not isinstance(threads, list):
        return rows
    for raw in threads:
        if not isinstance(raw, dict):
            continue
        external_id = _text(raw.get("external_thread_id"))
        if not external_id:
            continue
        item = _item_for_url(user, site.slug, raw.get("item_url"))
        thread, _created = BuyerThread.objects.get_or_create(
            user=user,
            marketplace=site.slug,
            external_thread_id=external_id,
            defaults={
                "buyer_name": _text(raw.get("buyer_name"))[:255],
                "item": item,
            },
        )
        if item is not None and thread.item_id is None:
            thread.item = item
            thread.save(update_fields=["item", "updated_at"])
        new_messages = _store_messages(thread, raw.get("messages"))
        if new_messages:
            rows.append(
                _thread_row(
                    thread,
                    new_messages[-1].body,
                    new=True,
                )
            )
    return rows


def _store_messages(thread, messages):
    stored = []
    if not isinstance(messages, list):
        return stored
    for raw in messages:
        if not isinstance(raw, dict):
            continue
        external_id = _text(raw.get("external_id"))
        body = _text(raw.get("body"))
        direction = raw.get("direction")
        if not external_id or not body or direction not in {"buyer", "seller"}:
            continue
        offer = raw.get("offer_pence")
        if type(offer) is not int or offer < 1:
            offer = None
        with transaction.atomic():
            row, created = BuyerMessage.objects.get_or_create(
                thread=thread,
                external_id=external_id[:255],
                defaults={
                    "direction": direction,
                    "body": body,
                    "offer_minor": offer,
                },
            )
        if created and direction == "buyer":
            stored.append(row)
    return stored


def _store_seller_message(thread, text, *, external_id, offer_minor=None):
    BuyerMessage.objects.get_or_create(
        thread=thread,
        external_id=external_id[:255],
        defaults={
            "direction": BuyerMessage.Direction.SELLER,
            "body": text,
            "offer_minor": offer_minor,
        },
    )


def _item_for_url(user, marketplace, url):
    cleaned = _text(url)
    if not cleaned:
        return None
    listing = (
        Listing.objects.filter(
            item__user=user,
            marketplace=marketplace,
            external_url=cleaned,
        )
        .select_related("item")
        .first()
    )
    if listing is None:
        return None
    return listing.item


def _ask(grok, facts, question):
    client = grok if grok is not None else GrokClient.from_environment()
    raw = client.ask_for_json_object(
        json.dumps({"item": facts, "buyer_message": question}),
        instructions=REPLY_INSTRUCTIONS,
        schema=REPLY_SCHEMA,
        schema_name="buyer_reply",
    )
    if not isinstance(raw, dict):
        return {"decision": "escalate", "text": "", "reason": "No reply was written."}
    return raw


def _facts(item):
    return {
        "title": item.title,
        "description": item.description,
        "brand": item.brand,
        "size": item.size_label,
        "condition": item.condition,
        "flaws": item.flaws,
        "colour": item.colour,
        "chest_cm": _measure(item.chest_cm),
        "waist_cm": _measure(item.waist_cm),
        "length_cm": _measure(item.length_cm),
        "inseam_cm": _measure(item.inseam_cm),
        "price_minor": item.price_minor,
        "currency": item.currency,
    }


def _measure(value):
    if value is None:
        return None
    return str(value)


def _thread(user, thread_id):
    if type(thread_id) is not int or thread_id < 1:
        return _failed("thread_id must be an integer.")
    try:
        return BuyerThread.objects.select_related("item").get(pk=thread_id, user=user)
    except BuyerThread.DoesNotExist:
        return _failed("That conversation was not found.")


def _session_gate(user, site):
    if user.browser_profile_status != "ready" or not user.browser_profile_id:
        return ("failed", user.browser_profile_error or "The browser profile is not ready.")
    try:
        connection = user.marketplace_connections.get(marketplace=site.slug)
    except MarketplaceConnection.DoesNotExist:
        return ("needs_login", f"Ask Willow to connect {site.label} first.")
    if connection.status != MarketplaceConnection.Status.CONNECTED:
        return ("needs_login", f"Ask Willow to connect {site.label} first.")
    return None


def _mark_needs_login(user, site):
    try:
        connection = user.marketplace_connections.get(marketplace=site.slug)
    except MarketplaceConnection.DoesNotExist:
        return
    connection.status = MarketplaceConnection.Status.NEEDS_LOGIN
    connection.error = f"{site.label} needs the seller to sign in again."
    connection.save(update_fields=["status", "error"])


def _browse(client, *, task, profile_id, output_schema):
    created = None
    outcome = {"kind": "crashed"}
    try:
        created = client.create_run(
            task,
            profile_id=profile_id,
            proxy_country_code="gb",
            record=False,
            output_schema=output_schema,
        )
        try:
            finished = client.wait(
                created.id,
                timeout=CHECK_TIMEOUT,
                raise_on_error=False,
                session_id=created.session_id,
            )
        except BrowserUseTimeout:
            try:
                client.cancel(created.id)
            except Exception:
                pass
            outcome = {"kind": "timeout"}
        else:
            if getattr(finished, "status", None) != "completed":
                outcome = {"kind": "crashed"}
            else:
                outcome = {"kind": "done", "output": getattr(finished, "output", None)}
    except Exception:
        outcome = {"kind": "crashed"}
    if created is not None and getattr(created, "session_id", None):
        try:
            client.release(created.session_id)
        except Exception:
            outcome = {"kind": "crashed"}
    return outcome


def _escalate(thread, reason):
    thread.status = BuyerThread.Status.NEEDS_SELLER
    thread.save(update_fields=["status", "updated_at"])
    return _result("escalate", reason, [_thread_row(thread, reason)])


def _needs_seller(thread, message, amount):
    thread.status = BuyerThread.Status.NEEDS_SELLER
    thread.save(update_fields=["status", "updated_at"])
    return _result(
        "needs_confirmation",
        message,
        [_thread_row(thread, message)],
        amount_minor=amount,
    )


def _thread_row(thread, message, *, new=False):
    return {
        "thread_id": thread.pk,
        "marketplace": thread.marketplace,
        "buyer_name": thread.buyer_name,
        "item_id": thread.item_id,
        "message": message,
        "new": new,
    }


def _marketplaces(value):
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise ValueError("marketplaces must be a list of vinted, depop, or ebay.")
    slugs = []
    for slug in value:
        if slug not in SITES or slug in slugs:
            raise ValueError("marketplaces must be vinted, depop, or ebay.")
        slugs.append(slug)
    return slugs


def _overall(statuses):
    if any(status == "failed" for status in statuses):
        return "failed"
    if any(status == "needs_login" for status in statuses):
        return "needs_login"
    if not statuses:
        return "ready"
    return "ready"


def _outage(site, outcome):
    if outcome.get("kind") == "timeout":
        return f"{site.label} took too long to answer. Ask the seller to try again."
    return f"{site.label} could not be reached. Ask the seller to try again."


def _text(value):
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def _result(status, message, threads, **extra):
    payload = {
        "status": status,
        "message": message,
        "threads": threads,
    }
    payload.update(extra)
    return payload


def _failed(message, thread=None):
    threads = [] if thread is None else [_thread_row(thread, message)]
    return _result("failed", message, threads)

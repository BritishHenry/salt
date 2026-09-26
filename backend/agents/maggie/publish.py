"""Publish, check, update, and remove marketplace listings on Willow's session.

Runs are sequential on the seller's browser profile. A sale recorded in
payments calls delist_after_sale after commit, so the browser work stays
outside that transaction.
"""

import json
import mimetypes
import os

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import MarketplaceConnection
from agents.maggie.sites import MARKETPLACES, SITES
from listings.models import Item, Listing
from services.browser_use import BrowserUseClient
from services.browser_use.errors import BrowserUseTimeout

MAX_PHOTOS = 4
PUBLISH_TIMEOUT = 300
SHORT_TIMEOUT = 180

_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
_PUBLISHABLE = frozenset({Listing.Status.DRAFT, Listing.Status.FAILED})
_OPEN = frozenset(
    {Listing.Status.LIVE, Listing.Status.PAUSED, Listing.Status.PUBLISHING}
)
_ATTRIBUTE_KEYS = (
    "department",
    "category",
    "garment_type",
    "brand",
    "colour",
    "colour_secondary",
    "size_label",
    "size_system",
    "condition",
    "material",
    "flaws",
)

_COPY_SCHEMA = {
    "type": "object",
    "properties": {
        "logged_in": {"type": "boolean"},
        "external_id": {"type": "string"},
        "external_url": {"type": "string"},
        "detail": {"type": "string"},
    },
    "required": ["logged_in", "external_id", "external_url"],
}
_STATUS_SCHEMA = {
    "type": "object",
    "properties": {
        "logged_in": {"type": "boolean"},
        "state": {
            "type": "string",
            "enum": ["live", "paused", "sold", "ended", "missing"],
        },
        "external_id": {"type": "string"},
        "external_url": {"type": "string"},
        "detail": {"type": "string"},
    },
    "required": ["logged_in", "state"],
}
_DELIST_SCHEMA = {
    "type": "object",
    "properties": {
        "logged_in": {"type": "boolean"},
        "removed": {"type": "boolean"},
        "detail": {"type": "string"},
    },
    "required": ["logged_in", "removed"],
}
_STATES = frozenset({"live", "paused", "sold", "ended", "missing"})


class _PhotoError(Exception):
    pass


def run(user, arguments, *, client=None):
    """Run publish, status, update, or delist for one of the seller's items."""
    if not isinstance(arguments, dict):
        return _failed(None, "Tool arguments must be an object.")
    item_id = _item_id(arguments.get("item_id"))
    action = arguments.get("action")
    if action not in {"publish", "status", "update", "delist"}:
        return _failed(item_id, "action must be publish, status, update, or delist.")
    if item_id is None:
        return _failed(None, "item_id must be an integer.")
    try:
        marketplaces = _marketplaces(arguments.get("marketplaces", None))
    except ValueError as exc:
        return _failed(item_id, str(exc))
    try:
        item = Item.objects.prefetch_related("photos", "listings").get(
            pk=item_id, user=user
        )
    except Item.DoesNotExist:
        return _failed(item_id, "That item was not found.")
    secrets = _secrets(user, arguments)
    if action == "publish":
        payload = _publish(user, item, marketplaces, client, secrets)
    elif action == "status":
        payload = _status(user, item, marketplaces, client, secrets)
    elif action == "update":
        payload = _update(user, item, marketplaces, client, secrets)
    else:
        payload = _delist(user, item, marketplaces, client, secrets)
    return _scrub(payload, secrets)


def delist_after_sale(user_id, targets):
    """Remove copies that were live when a sale was recorded.

    ``targets`` is a tuple of ``(listing_id, previous_status)``. Failures put
    that status back and store sync_error. They do not raise.
    """
    try:
        user = get_user_model().objects.get(pk=user_id)
    except get_user_model().DoesNotExist:
        return
    browser = None
    secrets = _secrets(user, {})
    for listing_id, previous in targets:
        try:
            listing = Listing.objects.select_related("item").get(
                pk=listing_id, item__user_id=user.pk
            )
        except Listing.DoesNotExist:
            continue
        if not listing.external_url:
            continue
        try:
            if browser is None:
                problem = _profile_problem(user)
                if problem:
                    _restore(listing, previous, problem)
                    continue
                browser = BrowserUseClient()
            _remove_one(
                user, listing, browser, secrets, restore_status=previous
            )
        except Exception:
            _restore(
                listing,
                previous,
                "That listing could not be removed. Ask the seller to try again.",
            )


def _publish(user, item, marketplaces, client, secrets):
    if item.status == Item.Status.SOLD:
        return _failed(item.pk, "This item is already sold.")
    listings = _by_marketplace(item)
    selected = marketplaces or [
        name
        for name in MARKETPLACES
        if name in listings and listings[name].status in _PUBLISHABLE
    ]
    if not selected:
        return _failed(item.pk, "There is no draft listing to publish.")
    blocked = {}
    runnable = []
    for name in selected:
        listing = listings.get(name)
        problem = _publish_block(user, item, listing, name)
        if problem is None:
            runnable.append(listing)
        else:
            blocked[name] = problem
    if not runnable:
        return _finish(item.pk, selected, blocked)
    problem = _profile_problem(user)
    if problem:
        for listing in runnable:
            blocked[listing.marketplace] = _view(listing.marketplace, "failed", problem)
        return _finish(item.pk, selected, blocked)
    browser = _browser(client)
    try:
        workspace_id, file_ids = _attach(browser, item)
    except _PhotoError:
        message = "A photo on this item is empty."
        for listing in runnable:
            blocked[listing.marketplace] = _view(listing.marketplace, "failed", message)
        return _finish(item.pk, selected, blocked)
    except Exception:
        message = "The photos could not be uploaded. Ask the seller to try again."
        for listing in runnable:
            blocked[listing.marketplace] = _view(listing.marketplace, "failed", message)
        return _finish(item.pk, selected, blocked)
    for listing in runnable:
        blocked[listing.marketplace] = _publish_one(
            user, listing, browser, secrets, workspace_id, file_ids
        )
    return _finish(item.pk, selected, blocked)


def _status(user, item, marketplaces, client, secrets):
    listings = _by_marketplace(item)
    selected = marketplaces or [
        name
        for name in MARKETPLACES
        if name in listings and _live_with_url(listings[name])
    ]
    if not selected:
        return _failed(item.pk, "There is no live listing to check.")
    blocked = {}
    runnable = []
    for name in selected:
        listing = listings.get(name)
        if listing is None or not _live_with_url(listing):
            blocked[name] = _view(
                name, "failed", f"There is no live {SITES[name].label} listing to check."
            )
        else:
            connection = _connection(user, name)
            if not _is_connected(connection):
                blocked[name] = _view(name, "needs_login", _login_message(SITES[name].label), listing.external_url)
            else:
                runnable.append(listing)
    if not runnable:
        return _finish(item.pk, selected, blocked)
    problem = _profile_problem(user)
    if problem:
        for listing in runnable:
            blocked[listing.marketplace] = _view(
                listing.marketplace, "failed", problem, listing.external_url
            )
        return _finish(item.pk, selected, blocked)
    browser = _browser(client)
    handled = set()
    extra = []
    for listing in runnable:
        if listing.pk in handled:
            continue
        handled.add(listing.pk)
        view, siblings = _status_one(user, listing, browser, secrets)
        blocked[listing.marketplace] = view
        for sibling_pk, sibling_view in siblings:
            handled.add(sibling_pk)
            name = sibling_view["marketplace"]
            if name in selected:
                blocked[name] = sibling_view
            else:
                extra.append(sibling_view)
    payload = _finish(item.pk, selected, blocked)
    if extra:
        payload["listings"].extend(extra)
        payload["status"] = _overall(payload["listings"])
        payload["message"] = _summary(payload["listings"])
    return payload


def _update(user, item, marketplaces, client, secrets):
    listings = _by_marketplace(item)
    selected = marketplaces or [
        name
        for name in MARKETPLACES
        if name in listings and _live_with_url(listings[name])
    ]
    if not selected:
        return _failed(item.pk, "There is no live listing to update.")
    blocked = {}
    runnable = []
    for name in selected:
        listing = listings.get(name)
        if listing is None or not _live_with_url(listing):
            blocked[name] = _view(
                name, "failed", f"There is no live {SITES[name].label} listing to update."
            )
            continue
        connection = _connection(user, name)
        if not _is_connected(connection):
            blocked[name] = _view(
                name, "needs_login", _login_message(SITES[name].label), listing.external_url
            )
            continue
        runnable.append(listing)
    if not runnable:
        return _finish(item.pk, selected, blocked)
    problem = _profile_problem(user)
    if problem:
        for listing in runnable:
            blocked[listing.marketplace] = _view(
                listing.marketplace, "failed", problem, listing.external_url
            )
        return _finish(item.pk, selected, blocked)
    browser = _browser(client)
    workspace_id = None
    file_ids = None
    if item.photos.exists():
        try:
            workspace_id, file_ids = _attach(browser, item)
        except _PhotoError:
            message = "A photo on this item is empty."
            for listing in runnable:
                blocked[listing.marketplace] = _view(
                    listing.marketplace, "failed", message, listing.external_url
                )
            return _finish(item.pk, selected, blocked)
        except Exception:
            message = "The photos could not be uploaded. Ask the seller to try again."
            for listing in runnable:
                blocked[listing.marketplace] = _view(
                    listing.marketplace, "failed", message, listing.external_url
                )
            return _finish(item.pk, selected, blocked)
    for listing in runnable:
        blocked[listing.marketplace] = _update_one(
            user, listing, browser, secrets, workspace_id, file_ids
        )
    return _finish(item.pk, selected, blocked)


def _delist(user, item, marketplaces, client, secrets):
    listings = _by_marketplace(item)
    names = marketplaces or list(MARKETPLACES)
    selected = []
    for name in names:
        listing = listings.get(name)
        if listing is not None and _removable(listing):
            selected.append(name)
    if not selected:
        return _result(item.pk, "ready", "Nothing else is listed.", [])
    blocked = {}
    runnable = []
    for name in selected:
        listing = listings[name]
        connection = _connection(user, name)
        if not _is_connected(connection):
            blocked[name] = _view(
                name, "needs_login", _login_message(SITES[name].label), listing.external_url
            )
        else:
            runnable.append(listing)
    if not runnable:
        return _finish(item.pk, selected, blocked)
    problem = _profile_problem(user)
    if problem:
        for listing in runnable:
            blocked[listing.marketplace] = _view(
                listing.marketplace, "failed", problem, listing.external_url
            )
        return _finish(item.pk, selected, blocked)
    browser = _browser(client)
    for listing in runnable:
        blocked[listing.marketplace] = _remove_one(user, listing, browser, secrets)
    return _finish(item.pk, selected, blocked)


def _publish_one(user, listing, browser, secrets, workspace_id, file_ids):
    site = SITES[listing.marketplace]
    listing.status = Listing.Status.PUBLISHING
    listing.sync_error = ""
    listing.save(update_fields=["status", "sync_error"])
    try:
        kind, output = _browse(
            browser,
            task=_redact(_publish_task(listing), secrets),
            profile_id=user.browser_profile_id,
            schema=_COPY_SCHEMA,
            timeout=PUBLISH_TIMEOUT,
            workspace_id=workspace_id,
            file_ids=file_ids,
        )
    except Exception:
        return _fail_listing(listing, f"{site.label} could not be reached. Ask the seller to try again.")
    if kind == "timeout":
        return _fail_listing(listing, f"{site.label} took too long. Ask the seller to try again.")
    if kind == "crashed":
        return _fail_listing(listing, f"{site.label} could not be reached. Ask the seller to try again.")
    parsed = _parse_copy(output)
    if parsed == "logged_out":
        _mark_needs_login(_connection(user, listing.marketplace), _login_message(site.label))
        return _fail_listing(listing, _login_message(site.label), outcome="needs_login")
    if parsed is None:
        return _fail_listing(listing, f"{site.label} did not return a listing URL.")
    external_id, url = parsed
    now = timezone.now()
    listing.status = Listing.Status.LIVE
    listing.external_id = external_id
    listing.external_url = url
    listing.listed_at = now
    listing.last_synced_at = now
    listing.sync_error = ""
    listing.save(
        update_fields=[
            "status",
            "external_id",
            "external_url",
            "listed_at",
            "last_synced_at",
            "sync_error",
        ]
    )
    _mark_item_listed(listing.item)
    return _view(listing.marketplace, "ready", f"{site.label} is live.", url)


def _update_one(user, listing, browser, secrets, workspace_id, file_ids):
    site = SITES[listing.marketplace]
    kind, output = _browse(
        browser,
        task=_redact(_update_task(listing), secrets),
        profile_id=user.browser_profile_id,
        schema=_COPY_SCHEMA,
        timeout=PUBLISH_TIMEOUT,
        workspace_id=workspace_id,
        file_ids=file_ids,
    )
    if kind == "timeout":
        return _keep_live(listing, f"{site.label} took too long. Ask the seller to try again.")
    if kind == "crashed":
        return _keep_live(listing, f"{site.label} could not be reached. Ask the seller to try again.")
    parsed = _parse_copy(output)
    if parsed == "logged_out":
        _mark_needs_login(_connection(user, listing.marketplace), _login_message(site.label))
        return _keep_live(listing, _login_message(site.label), outcome="needs_login")
    if parsed is None:
        return _keep_live(listing, f"{site.label} did not confirm the update.")
    external_id, url = parsed
    now = timezone.now()
    listing.external_id = external_id or listing.external_id
    listing.external_url = url
    listing.last_synced_at = now
    listing.sync_error = ""
    listing.save(
        update_fields=["external_id", "external_url", "last_synced_at", "sync_error"]
    )
    return _view(listing.marketplace, "ready", f"{site.label} was updated.", listing.external_url)


def _status_one(user, listing, browser, secrets):
    site = SITES[listing.marketplace]
    kind, output = _browse(
        browser,
        task=_redact(_status_task(listing), secrets),
        profile_id=user.browser_profile_id,
        schema=_STATUS_SCHEMA,
        timeout=SHORT_TIMEOUT,
    )
    if kind == "timeout":
        message = f"{site.label} took too long. Ask the seller to try again."
        return _keep_live(listing, message), []
    if kind == "crashed":
        message = f"{site.label} could not be reached. Ask the seller to try again."
        return _keep_live(listing, message), []
    if not isinstance(output, dict) or output.get("logged_in") is not True:
        if isinstance(output, dict) and output.get("logged_in") is False:
            _mark_needs_login(_connection(user, listing.marketplace), _login_message(site.label))
            return _keep_live(listing, _login_message(site.label), outcome="needs_login"), []
        return _keep_live(listing, f"{site.label} did not report a status."), []
    state = output.get("state")
    if state not in _STATES:
        return _keep_live(listing, f"{site.label} did not report a status."), []
    if state == "sold":
        siblings = _delist_siblings(user, listing, browser, secrets)
        listing.refresh_from_db()
        return (
            _view(listing.marketplace, "ready", f"{site.label} is sold.", listing.external_url),
            siblings,
        )
    if state in {"ended", "missing"}:
        _finish_removed(listing)
        word = "ended" if state == "ended" else "no longer listed"
        return _view(listing.marketplace, "ready", f"{site.label} is {word}.", listing.external_url), []
    if state == "paused":
        listing.status = Listing.Status.PAUSED
        listing.last_synced_at = timezone.now()
        listing.sync_error = ""
        listing.save(update_fields=["status", "last_synced_at", "sync_error"])
        return _view(listing.marketplace, "ready", f"{site.label} is paused.", listing.external_url), []
    url = _http_url(output.get("external_url")) or listing.external_url
    external_id = _external_id(output.get("external_id")) or listing.external_id
    listing.status = Listing.Status.LIVE
    listing.external_url = url
    listing.external_id = external_id
    listing.last_synced_at = timezone.now()
    listing.sync_error = ""
    listing.save(
        update_fields=["status", "external_url", "external_id", "last_synced_at", "sync_error"]
    )
    return _view(listing.marketplace, "ready", f"{site.label} is still live.", url), []


def _delist_siblings(user, sold_listing, browser, secrets):
    siblings = []
    for row in sold_listing.item.listings.all():
        if row.pk == sold_listing.pk:
            continue
        if _removable(row):
            siblings.append((row, row.status))
    sold_listing.mark_sold()
    views = []
    for row, previous in siblings:
        row.refresh_from_db()
        view = _remove_one(user, row, browser, secrets, restore_status=previous)
        views.append((row.pk, view))
    return views


def _remove_one(user, listing, browser, secrets, restore_status=None):
    site = SITES[listing.marketplace]
    connection = _connection(user, listing.marketplace)
    if not _is_connected(connection):
        message = _login_message(site.label)
        if restore_status is not None:
            _restore(listing, restore_status, message)
        return _view(listing.marketplace, "needs_login", message, listing.external_url)
    kind, output = _browse(
        browser,
        task=_redact(_delist_task(listing), secrets),
        profile_id=user.browser_profile_id,
        schema=_DELIST_SCHEMA,
        timeout=SHORT_TIMEOUT,
    )
    if kind == "timeout":
        message = f"{site.label} took too long. Ask the seller to try again."
        return _delist_failed(listing, message, restore_status)
    if kind == "crashed":
        message = f"{site.label} could not be reached. Ask the seller to try again."
        return _delist_failed(listing, message, restore_status)
    if not isinstance(output, dict) or not isinstance(output.get("logged_in"), bool):
        return _delist_failed(listing, f"{site.label} did not confirm the removal.", restore_status)
    if output.get("logged_in") is False:
        message = _login_message(site.label)
        _mark_needs_login(connection, message)
        if restore_status is not None:
            _restore(listing, restore_status, message)
        else:
            _note_error(listing, message)
        return _view(listing.marketplace, "needs_login", message, listing.external_url)
    if output.get("removed") is not True:
        return _delist_failed(listing, f"{site.label} could not be removed.", restore_status)
    _finish_removed(listing)
    return _view(listing.marketplace, "ready", f"{site.label} was removed.", listing.external_url)


def _publish_block(user, item, listing, marketplace):
    label = SITES[marketplace].label
    if listing is None:
        return _view(marketplace, "needs_details", f"There is no {label} draft to publish.")
    if listing.status not in _PUBLISHABLE:
        return _view(
            marketplace,
            "failed",
            f"The {label} listing is already {listing.status}.",
        )
    missing = _missing_copy(item, listing)
    if missing:
        return _view(
            marketplace,
            "needs_details",
            f"The {label} listing needs {missing}.",
        )
    connection = _connection(user, marketplace)
    if not _is_connected(connection):
        return _view(marketplace, "needs_login", _login_message(label))
    return None


def _missing_copy(item, listing):
    missing = []
    if not (listing.title or "").strip():
        missing.append("a title")
    if not (listing.description or "").strip():
        missing.append("a description")
    if listing.price_minor is None:
        missing.append("a price")
    if not item.photos.exists():
        missing.append("at least one photo")
    if not missing:
        return ""
    if len(missing) == 1:
        return missing[0]
    return ", ".join(missing[:-1]) + " and " + missing[-1]


def _attach(browser, item):
    files = _photo_files(item)
    workspace = browser.create_workspace(name=f"item-{item.pk}"[:100])
    uploads = browser.upload_workspace_files(workspace.id, files)
    return workspace.id, [upload.id for upload in uploads]


def _photo_files(item):
    files = []
    for photo in item.photos.order_by("position")[:MAX_PHOTOS]:
        base = os.path.basename(photo.image.name or "") or f"photo-{photo.position}.jpg"
        base = base.replace("\\", "-").replace("/", "-").replace(" ", "-")
        name = f"{photo.position}-{base}"[:255]
        mime, _encoding = mimetypes.guess_type(base)
        if mime not in _IMAGE_TYPES:
            mime = "image/jpeg"
        with photo.image.open("rb") as handle:
            data = handle.read()
        if not data:
            raise _PhotoError()
        files.append({"name": name, "data": data, "content_type": mime})
    if not files:
        raise _PhotoError()
    return files


def _browse(browser, *, task, profile_id, schema, timeout, workspace_id=None, file_ids=None):
    created = None
    kind = None
    output = None
    try:
        created = browser.create_run(
            task,
            profile_id=profile_id,
            proxy_country_code="gb",
            record=False,
            output_schema=schema,
            workspace_id=workspace_id,
            attached_file_ids=file_ids,
        )
        try:
            finished = browser.wait(
                created.id,
                timeout=timeout,
                raise_on_error=False,
                session_id=created.session_id,
            )
        except BrowserUseTimeout:
            _cancel(browser, created.id)
            kind = "timeout"
        else:
            if getattr(finished, "status", None) != "completed":
                kind = "crashed"
            else:
                output = getattr(finished, "output", None)
    except Exception:
        kind = "crashed"
    finally:
        if created is not None and getattr(created, "session_id", None):
            try:
                browser.release(created.session_id)
            except Exception:
                if kind is None and output is None:
                    kind = "crashed"
    return kind, output


def _publish_task(listing):
    site = SITES[listing.marketplace]
    facts = json.dumps(_facts(listing), ensure_ascii=False)
    return (
        f"Open {site.sell_url}. You are already signed in. Do not type a password. "
        "Create one listing and publish it. Use the attached photos. "
        "Pick the closest category, condition, size, and shipping the site offers "
        f"from these facts: {facts}. "
        "If the site asks for a login, stop. "
        "Report whether you are logged in, the new listing id, and its public https URL."
    )


def _update_task(listing):
    site = SITES[listing.marketplace]
    facts = json.dumps(_facts(listing), ensure_ascii=False)
    return (
        f"Open {listing.external_url}. You are already signed in. Do not type a password. "
        f"Update this {site.label} listing to match these facts: {facts}. "
        "Use the attached photos if the site lets you replace the pictures. "
        "Do not create a second listing. If the site asks for a login, stop. "
        "Report whether you are logged in, the listing id, and its public https URL."
    )


def _status_task(listing):
    return (
        f"Open {listing.external_url}. Do not type a password and do not change the listing. "
        "Report whether you are logged in and whether the listing is live, paused, sold, ended, or missing."
    )


def _delist_task(listing):
    label = SITES[listing.marketplace].label
    return (
        f"Open {listing.external_url}. You are already signed in. Do not type a password. "
        f"Remove or end this {label} listing. Do not create a new listing. "
        "If the site asks for a login, stop. "
        "Report whether you are logged in and whether the listing was removed."
    )


def _facts(listing):
    item = listing.item
    facts = {}
    if (listing.title or "").strip():
        facts["title"] = listing.title.strip()
    if (listing.description or "").strip():
        facts["description"] = listing.description.strip()
    if (listing.category_ref or "").strip():
        facts["category_ref"] = listing.category_ref.strip()
    price = _price_label(listing)
    if price:
        facts["price"] = price
    attributes = listing.attributes if isinstance(listing.attributes, dict) else {}
    for key in _ATTRIBUTE_KEYS:
        value = attributes.get(key)
        if not isinstance(value, str) or not value.strip():
            value = getattr(item, key, "")
        if isinstance(value, str) and value.strip():
            facts[key] = value.strip()
    if item.package_size:
        facts["package_size"] = item.package_size
    return facts


def _price_label(listing):
    if listing.price_minor is None:
        return ""
    major = listing.price_minor // 100
    minor = listing.price_minor % 100
    return f"{major}.{minor:02d} {(listing.currency or 'gbp').upper()}"


def _parse_copy(output):
    if not isinstance(output, dict) or not isinstance(output.get("logged_in"), bool):
        return None
    if output.get("logged_in") is False:
        return "logged_out"
    url = _http_url(output.get("external_url"))
    if not url:
        return None
    return _external_id(output.get("external_id")), url


def _http_url(value):
    if not isinstance(value, str):
        return ""
    url = value.strip()
    if len(url) > 500 or not url.startswith("https://"):
        return ""
    return url


def _external_id(value):
    if not isinstance(value, str):
        return ""
    return value.strip()[:255]


def _fail_listing(listing, message, outcome="failed"):
    now = timezone.now()
    listing.status = Listing.Status.FAILED
    listing.sync_error = message
    listing.last_synced_at = now
    listing.save(update_fields=["status", "sync_error", "last_synced_at"])
    return _view(listing.marketplace, outcome, message)


def _keep_live(listing, message, outcome="failed"):
    _note_error(listing, message)
    return _view(listing.marketplace, outcome, message, listing.external_url)


def _note_error(listing, message):
    listing.sync_error = message
    listing.last_synced_at = timezone.now()
    listing.save(update_fields=["sync_error", "last_synced_at"])


def _delist_failed(listing, message, restore_status):
    if restore_status is not None:
        _restore(listing, restore_status, message)
    else:
        _note_error(listing, message)
    return _view(listing.marketplace, "failed", message, listing.external_url)


def _finish_removed(listing):
    now = timezone.now()
    listing.status = Listing.Status.ENDED
    if listing.ended_at is None:
        listing.ended_at = now
    listing.last_synced_at = now
    listing.sync_error = ""
    listing.save(update_fields=["status", "ended_at", "last_synced_at", "sync_error"])


def _restore(listing, status, message):
    listing.status = status
    if status not in (Listing.Status.SOLD, Listing.Status.ENDED):
        listing.ended_at = None
    listing.sync_error = message
    listing.last_synced_at = timezone.now()
    listing.save(update_fields=["status", "ended_at", "sync_error", "last_synced_at"])


def _mark_item_listed(item):
    if item.status in (Item.Status.DRAFT, Item.Status.READY):
        item.status = Item.Status.LISTED
        item.save(update_fields=["status", "updated_at"])


def _mark_needs_login(connection, message):
    if connection is None:
        return
    connection.status = MarketplaceConnection.Status.NEEDS_LOGIN
    connection.error = message
    connection.last_checked_at = timezone.now()
    connection.save(update_fields=["status", "error", "last_checked_at"])


def _live_with_url(listing):
    return listing.status == Listing.Status.LIVE and bool(listing.external_url)


def _removable(listing):
    if not listing.external_url:
        return False
    return listing.status in _OPEN


def _connection(user, marketplace):
    try:
        return user.marketplace_connections.get(marketplace=marketplace)
    except MarketplaceConnection.DoesNotExist:
        return None


def _is_connected(connection):
    return (
        connection is not None
        and connection.status == MarketplaceConnection.Status.CONNECTED
    )


def _profile_problem(user):
    if user.browser_profile_status == "ready" and user.browser_profile_id:
        return None
    return user.browser_profile_error or "The browser profile is not ready."


def _browser(client):
    if client is not None:
        return client
    return BrowserUseClient()


def _by_marketplace(item):
    return {listing.marketplace: listing for listing in item.listings.all()}


def _finish(item_id, order, views):
    listings = [views[name] for name in order if name in views]
    status = _overall(listings)
    return _result(item_id, status, _summary(listings), listings)


def _overall(listings):
    statuses = [row["status"] for row in listings]
    if any(status == "failed" for status in statuses):
        return "failed"
    if any(status == "needs_login" for status in statuses):
        return "needs_login"
    if any(status == "needs_details" for status in statuses):
        return "needs_details"
    if listings and all(status == "ready" for status in statuses):
        return "ready"
    return "failed"


def _summary(listings):
    messages = [row["message"] for row in listings if row.get("message")]
    if not messages:
        return "That tool could not finish. Ask the seller to try again."
    if len(messages) == 1:
        return messages[0]
    return " ".join(messages)


def _cancel(client, run_id):
    try:
        client.cancel(run_id)
    except Exception:
        return


def _item_id(value):
    if type(value) is not int or value < 1:
        return None
    return value


def _marketplaces(value):
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise ValueError("marketplaces must be vinted, depop, or ebay.")
    cleaned = []
    for item in value:
        if item not in SITES or item in cleaned:
            raise ValueError("marketplaces must be vinted, depop, or ebay.")
        cleaned.append(item)
    return cleaned


def _login_message(label):
    return (
        f"{label} is not signed in. Ask the seller for their password, "
        "then call willow with action connect."
    )


def _secrets(user, arguments):
    found = []
    if isinstance(arguments, dict):
        password = arguments.get("password")
        if isinstance(password, str) and len(password) >= 4:
            found.append(password)
    for marketplace in MARKETPLACES:
        try:
            stored = user.marketplace_password(marketplace)
        except ValueError:
            continue
        if isinstance(stored, str) and len(stored) >= 4:
            found.append(stored)
    return tuple(found)


def _redact(value, secrets):
    text = " ".join((value or "").split())
    for secret in secrets:
        if secret in text:
            text = text.replace(secret, "")
    return " ".join(text.split())


def _scrub(payload, secrets):
    payload["message"] = _redact(payload.get("message"), secrets)
    for row in payload.get("listings") or []:
        row["message"] = _redact(row.get("message"), secrets)
    return payload


def _view(marketplace, status, message, external_url=""):
    return {
        "marketplace": marketplace,
        "status": status,
        "external_url": external_url or "",
        "message": message,
    }


def _result(item_id, status, message, listings):
    return {
        "status": status,
        "item_id": item_id,
        "message": message,
        "listings": listings,
    }


def _failed(item_id, message):
    return _result(item_id, "failed", message, [])

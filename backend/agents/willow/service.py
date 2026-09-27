"""Sign a seller into a marketplace, or check the session already on their profile.

A password the seller just typed is encrypted on their account, then decrypted
into one Browser Use secret locked to that marketplace's hosts. The plaintext
is never written onto the connection row. Cookies stay on the seller's browser
profile after the browser stops.
"""

from django.utils import timezone

from accounts.models import MarketplaceConnection
from accounts.secrets import marketplace_login_secret
from accounts.services import AccountError
from agents.willow.sites import SITES
from services.browser_use import BrowserUseClient
from services.browser_use.errors import BrowserUseTimeout

RUN_TIMEOUT = 180

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "logged_in": {"type": "boolean"},
        "username": {"type": "string"},
        "blocked_by": {
            "type": "string",
            "enum": ["none", "password", "two_factor", "captcha", "unknown"],
        },
        "detail": {"type": "string"},
    },
    "required": ["logged_in", "blocked_by"],
}

_BLOCKED = frozenset(OUTPUT_SCHEMA["properties"]["blocked_by"]["enum"])


def connect_marketplace(user, marketplace, password, *, client=None):
    """Sign in with a password, or reuse the encrypted one already stored."""
    site = SITES[marketplace]
    connection = _connection(user, site)
    if connection is None:
        return _missing(site)
    supplied = password.strip() if isinstance(password, str) else ""
    if not supplied and not _has_stored_password(user, site.slug):
        message = (
            f"Ask the seller for their {site.label} password, then call willow "
            "again with action connect and that password."
        )
        return _save(connection, status="needs_login", message=message, checked=False)
    problem = _profile_problem(user)
    if problem:
        return _save(connection, status="failed", message=problem, checked=False, password=supplied)
    try:
        secret = _bind_login_secret(user, site, supplied)
    except ValueError:
        message = (
            f"The {site.label} password could not be saved. Ask the seller to try again."
        )
        return _save(connection, status="failed", message=message, checked=False, password=supplied)
    except AccountError:
        message = (
            f"Ask the seller for their {site.label} password, then call willow "
            "again with action connect and that password."
        )
        return _save(connection, status="needs_login", message=message, checked=False, password=supplied)
    return _browse(
        connection,
        site,
        task=_login_task(site, user.email, secret.value),
        profile_id=user.browser_profile_id,
        secret=secret,
        password=secret.value,
        client=client,
    )


def check_session(user, marketplace, *, client=None):
    """Open the marketplace and report whether the saved cookies still work."""
    site = SITES[marketplace]
    connection = _connection(user, site)
    if connection is None:
        return _missing(site)
    problem = _profile_problem(user)
    if problem:
        return _save(connection, status="failed", message=problem, checked=False)
    return _browse(
        connection,
        site,
        task=_check_task(site),
        profile_id=user.browser_profile_id,
        secret=None,
        password="",
        client=client,
    )


def _connection(user, site):
    try:
        return user.marketplace_connections.get(marketplace=site.slug)
    except MarketplaceConnection.DoesNotExist:
        return None


def _missing(site):
    return _result(
        site.slug,
        "failed",
        "",
        f"No {site.label} connection is open for this seller.",
    )


def _profile_problem(user):
    if user.browser_profile_status == "ready" and user.browser_profile_id:
        return None
    return user.browser_profile_error or "The browser profile is not ready."


def _has_stored_password(user, marketplace):
    field = user._marketplace_password_field(marketplace)
    return bool(getattr(user, field))


def _clear_stored_password(user, marketplace):
    field = user._marketplace_password_field(marketplace)
    if not getattr(user, field):
        return
    setattr(user, field, "")
    user.save(update_fields=[field])


def _bind_login_secret(user, site, supplied):
    """Encrypt a new password, then return the domain-locked secret."""
    if supplied:
        user.set_marketplace_password(site.slug, supplied)
        user.save(update_fields=[user._marketplace_password_field(site.slug)])
    return marketplace_login_secret(user, site.slug, site.allowed_hosts)


def _login_task(site, email, password):
    if password and email and password in email:
        identity = "Use the email already filled in on the page."
    elif email:
        identity = f"If an email or username field is empty, type {email}."
    else:
        identity = "Use the email already filled in on the page."
    return (
        f"Open {site.login_url}. Reach the email login. {identity} "
        f"Type the secret aliased {site.secret_alias} into the password field and submit. "
        "Do not read the secret back or include it in the result. "
        "If the site asks for a verification code or shows a captcha, stop. "
        "Report whether the account is logged in and the shop or account name."
    )


def _check_task(site):
    return (
        f"Open {site.login_url}. Do not type a password and do not submit a login form. "
        "Report whether a seller is already signed in and the shop or account name."
    )


def _browse(connection, site, *, task, profile_id, secret, password, client):
    browser = client if client is not None else BrowserUseClient()
    created = None
    kind = None
    output = None
    try:
        created = browser.create_run(
            task,
            profile_id=profile_id,
            proxy_country_code="gb",
            record=False,
            output_schema=OUTPUT_SCHEMA,
            secret_bindings=None if secret is None else [secret],
        )
        try:
            finished = browser.wait(
                created.id,
                timeout=RUN_TIMEOUT,
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
        if created is not None and created.session_id:
            try:
                browser.release(created.session_id)
            except Exception:
                if kind is None:
                    kind = "crashed"
                    output = None
    if kind == "timeout":
        message = f"{site.label} took too long to answer. Ask the seller to try again."
        return _save(connection, status="failed", message=message, checked=True, password=password)
    if kind == "crashed":
        message = f"{site.label} could not be reached. Ask the seller to try again."
        return _save(
            connection,
            status="failed",
            message=message,
            checked=created is not None,
            password=password,
        )
    status, username, message = _interpret(site, output)
    if (
        secret is not None
        and status == "needs_login"
        and isinstance(output, dict)
        and output.get("blocked_by") == "password"
    ):
        _clear_stored_password(connection.user, site.slug)
    return _save(
        connection,
        status=status,
        message=message,
        username=username,
        checked=True,
        password=password,
    )


def _interpret(site, output):
    if not isinstance(output, dict):
        return (
            "failed",
            "",
            f"{site.label} did not report a login result. Ask the seller to try again.",
        )
    logged_in = output.get("logged_in")
    blocked = output.get("blocked_by")
    if not isinstance(logged_in, bool) or blocked not in _BLOCKED:
        return (
            "failed",
            "",
            f"{site.label} did not report a login result. Ask the seller to try again.",
        )
    username = output.get("username")
    username = username.strip() if isinstance(username, str) else ""
    if logged_in:
        if username:
            message = f"{site.label} is connected as {username}."
        else:
            message = f"{site.label} is connected."
        return "connected", username, message
    return "needs_login", username, _blocked_message(site, blocked)


def _blocked_message(site, blocked):
    if blocked == "password":
        return f"{site.label} rejected the password. Ask the seller to try again."
    if blocked == "two_factor":
        return f"{site.label} asked for a verification code. Ask the seller to try again later."
    if blocked == "captcha":
        return f"{site.label} showed a captcha. Ask the seller to try again later."
    return (
        f"{site.label} is not signed in. Ask the seller for their password, "
        "then call willow again with action connect."
    )


def _cancel(client, run_id):
    try:
        client.cancel(run_id)
    except Exception:
        return


def _save(connection, *, status, message, username="", checked, password=""):
    message = _redact(message, password)
    connection.status = status
    connection.error = "" if status == "connected" else message
    if username and status == "connected":
        connection.external_username = _redact(username, password)
    fields = ["status", "error", "external_username"]
    if checked or status == "connected":
        now = timezone.now()
        connection.last_checked_at = now
        fields.append("last_checked_at")
        if status == "connected":
            connection.connected_at = now
            fields.append("connected_at")
    connection.save(update_fields=fields)
    return _result(
        connection.marketplace,
        connection.status,
        connection.external_username,
        message,
    )


def _redact(value, password):
    text = " ".join((value or "").split())
    if isinstance(password, str) and len(password) >= 4 and password in text:
        text = " ".join(text.replace(password, "").split())
    return text


def _result(marketplace, status, external_username, message):
    return {
        "marketplace": marketplace,
        "status": status,
        "external_username": external_username or "",
        "message": message,
    }

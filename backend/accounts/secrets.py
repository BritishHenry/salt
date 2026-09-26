import os

from cryptography.fernet import Fernet, InvalidToken

from services.browser_use.models import Secret


LOGIN_DOMAINS = {
    "vinted": "vinted.co.uk",
    "depop": "depop.com",
    "ebay": "ebay.co.uk",
}


def encrypt_password(value):
    """Return a Fernet token for ``value``. A blank password stays blank."""
    if not value:
        return ""
    if not isinstance(value, str):
        raise ValueError("password must be a string")
    return _fernet().encrypt(value.encode()).decode()


def decrypt_password(token):
    """Return the password stored in ``token``. A blank token stays blank."""
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("marketplace password could not be decrypted") from exc


def marketplace_login_secret(user, marketplace):
    """Decrypt one marketplace password into a single-run Browser Use secret.

    The secret can be typed only on that marketplace's domain. The caller
    attaches it to a new run that uses this user's browser profile.
    """
    from accounts.services import AccountError

    password = user.marketplace_password(marketplace)
    if not password:
        raise AccountError(f"No {marketplace} password is stored.")
    return Secret.inline(
        f"{marketplace}_password",
        password,
        [LOGIN_DOMAINS[marketplace]],
    )


def _fernet():
    key = os.environ.get("MARKETPLACE_SECRET_KEY", "").strip()
    if not key:
        raise ValueError("MARKETPLACE_SECRET_KEY is missing.")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise ValueError("MARKETPLACE_SECRET_KEY is not a valid Fernet key.") from exc

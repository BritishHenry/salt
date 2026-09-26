"""Realtime voice sessions, ephemeral browser secrets, and SIP call control.

Browser clients should use an ephemeral client secret from
create_ephemeral_realtime_client_secret. Do not put the main API key in a page.
"""

from __future__ import annotations

from services.grok.constants import DEFAULT_REALTIME_MODEL, REALTIME_MODELS
from services.grok.errors import GrokApiError, GrokUsageError
from services.grok.resources.base import Resource
from services.grok.safety import (
    optional_choice,
    optional_dict,
    optional_int,
    optional_text,
    require_https_url,
    require_resource_id,
    require_text,
    without_none,
)


class EphemeralClientSecret:
    """A short-lived realtime credential. Printing this object hides the token."""

    def __init__(self, value, expires_at):
        self.value = value
        self.expires_at = expires_at

    def __repr__(self):
        return f"EphemeralClientSecret(expires_at={self.expires_at!r}, value='***')"

    @property
    def authorization_header_value(self):
        return f"Bearer {self.value}"


class RealtimeResource(Resource):
    def create_ephemeral_realtime_client_secret(
        self,
        *,
        expires_after_seconds=600,
        model=None,
        reasoning_effort=None,
        timeout_seconds=None,
    ):
        """POST /v1/realtime/client_secrets.

        The returned token can authorize a browser websocket. It expires in at
        most one hour. Treat .value as a credential.
        """
        body = {
            "expires_after": {
                "seconds": optional_int(
                    expires_after_seconds, "expires_after_seconds", minimum=1, maximum=3600
                )
            }
        }
        session = {}
        if model is not None:
            session["model"] = optional_choice(model, "model", REALTIME_MODELS)
        if reasoning_effort is not None:
            if reasoning_effort not in {"high", "none"}:
                raise GrokUsageError("reasoning_effort must be 'high' or 'none'.")
            session["reasoning"] = {"effort": reasoning_effort}
        if session:
            body["session"] = session
        payload = self._json(
            "POST",
            "/v1/realtime/client_secrets",
            body=body,
            timeout_seconds=timeout_seconds,
        )
        value = payload.get("value")
        expires_at = payload.get("expires_at")
        if not isinstance(value, str) or not value:
            raise GrokApiError("The realtime client secret response did not include a token.")
        return EphemeralClientSecret(value, expires_at)

    def realtime_websocket_connection(
        self,
        *,
        model=DEFAULT_REALTIME_MODEL,
        reasoning_effort="high",
        call_id=None,
    ):
        """Connection details for wss://api.x.ai/v1/realtime.

        Pass call_id only when attaching to an inbound SIP call. Ephemeral
        client secrets cannot be used for those sessions; use the API key headers
        returned here. The key is not placed in the URL.
        """
        if reasoning_effort not in {"high", "none"}:
            raise GrokUsageError("reasoning_effort must be 'high' or 'none'.")
        query = {"reasoning.effort": reasoning_effort}
        if call_id is not None:
            query["call_id"] = require_resource_id(call_id, "call_id")
        else:
            query["model"] = optional_choice(model, "model", REALTIME_MODELS)
        return self._http.websocket_connection("/v1/realtime", query)

    def refer_realtime_phone_call(self, call_id, target_uri, *, timeout_seconds=None):
        """POST /v1/realtime/calls/{call_id}/refer.

        target_uri is tel:+E.164 or sip:user@host.
        """
        if not isinstance(target_uri, str) or any(character in target_uri for character in "\r\n "):
            raise GrokUsageError("target_uri must be a tel:+ or sip: URI without spaces.")
        if not (target_uri.startswith("tel:+") or target_uri.startswith("sip:")):
            raise GrokUsageError("target_uri must start with tel:+ or sip:.")
        return self._json(
            "POST",
            f"/v1/realtime/calls/{require_resource_id(call_id, 'call_id')}/refer",
            body={"target_uri": target_uri},
            timeout_seconds=timeout_seconds,
        )

    def hang_up_realtime_phone_call(self, call_id, *, timeout_seconds=None):
        """POST /v1/realtime/calls/{call_id}/hangup."""
        return self._json(
            "POST",
            f"/v1/realtime/calls/{require_resource_id(call_id, 'call_id')}/hangup",
            timeout_seconds=timeout_seconds,
        )

    def create_phone_number(
        self,
        *,
        origin,
        name,
        agent_id=None,
        area_code=None,
        phone_number=None,
        sip_authentication=None,
        webhook=None,
        timeout_seconds=None,
    ):
        """POST /v2/phone-numbers.

        origin is xai_provisioned or byo_trunk. agent_id and webhook are mutually
        exclusive. A webhook signing secret in the response is shown only once.
        """
        if origin not in {"xai_provisioned", "byo_trunk"}:
            raise GrokUsageError("origin must be 'xai_provisioned' or 'byo_trunk'.")
        if agent_id is not None and webhook is not None:
            raise GrokUsageError("Set agent_id or webhook, not both.")
        if origin == "byo_trunk" and not phone_number:
            raise GrokUsageError("byo_trunk numbers require phone_number in E.164 format.")
        if origin == "xai_provisioned" and phone_number is not None:
            raise GrokUsageError("phone_number is only for byo_trunk origins.")
        body = without_none(
            {
                "origin": origin,
                "name": require_text(name, "name", max_length=200),
                "agent_id": optional_text(agent_id, "agent_id", max_length=200)
                if agent_id is not None
                else None,
                "area_code": _area_code(area_code),
                "phone_number": _e164(phone_number),
                "sip_auth": _sip_auth(sip_authentication),
                "webhook": _webhook(webhook),
            }
        )
        return self._json("POST", "/v2/phone-numbers", body=body, timeout_seconds=timeout_seconds)


def _area_code(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 3 or not value.isdigit():
        raise GrokUsageError("area_code must be three digits.")
    return value


def _e164(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value.startswith("+") or not value[1:].isdigit():
        raise GrokUsageError("phone_number must be E.164, such as +18005550199.")
    if len(value) < 8 or len(value) > 16:
        raise GrokUsageError("phone_number is not a usable E.164 number.")
    return value


def _sip_auth(value):
    if value is None:
        return None
    payload = optional_dict(value, "sip_authentication")
    allowed = {"auth_username", "auth_password", "allowed_addresses"}
    unknown = set(payload) - allowed
    if unknown:
        raise GrokUsageError("sip_authentication only accepts auth_username, auth_password, and allowed_addresses.")
    username = payload.get("auth_username")
    password = payload.get("auth_password")
    if (username is None) != (password is None):
        raise GrokUsageError("auth_username and auth_password must be provided together.")
    cleaned = {}
    if username is not None:
        cleaned["auth_username"] = require_text(username, "auth_username", max_length=200)
        cleaned["auth_password"] = require_text(password, "auth_password", max_length=200)
    addresses = payload.get("allowed_addresses")
    if addresses is not None:
        if not isinstance(addresses, list) or not addresses:
            raise GrokUsageError("allowed_addresses must be a list of CIDR ranges.")
        cleaned["allowed_addresses"] = [
            require_text(item, "allowed_addresses", max_length=64) for item in addresses
        ]
    return cleaned or None


def _webhook(value):
    if value is None:
        return None
    payload = optional_dict(value, "webhook")
    url = payload.get("url")
    if not url:
        raise GrokUsageError("webhook.url is required.")
    cleaned = {
        "url": require_https_url(url, "webhook.url"),
    }
    if payload.get("name") is not None:
        cleaned["name"] = optional_text(payload["name"], "webhook.name", max_length=200)
    if payload.get("auth_url") is not None:
        cleaned["auth_url"] = require_https_url(payload["auth_url"], "webhook.auth_url")
    if payload.get("auth_token") is not None:
        cleaned["auth_token"] = require_text(payload["auth_token"], "webhook.auth_token", max_length=4096)
    return cleaned

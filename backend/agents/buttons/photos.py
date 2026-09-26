"""Load the photo bytes Buttons stores on the draft item."""

import base64
import http.client
import ipaddress
import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse

from services.grok.safety import require_https_or_data_url, require_https_url

from agents.buttons.errors import ButtonsError

MAX_IMAGE_BYTES = 10 * 1024 * 1024


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ButtonsError("The image URL must not redirect.")


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, *, pinned_address, **kwargs):
        self._pinned_address = pinned_address
        super().__init__(host, **kwargs)

    def connect(self):
        sock = socket.create_connection(
            (self._pinned_address, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, pinned_address):
        self._pinned_address = pinned_address
        super().__init__()

    def https_open(self, req):
        def connection_factory(host, **kwargs):
            kwargs.setdefault("context", self._context)
            return _PinnedHTTPSConnection(host, pinned_address=self._pinned_address, **kwargs)

        return self.do_open(connection_factory, req)


def load_photo_bytes(grok, *, image_url=None, image_file_id=None):
    if image_file_id is not None:
        try:
            data = grok.files.download_file_bytes(image_file_id)
        except Exception as exc:
            raise ButtonsError("I couldn't download that photo.") from exc
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise ButtonsError("The image file was empty.")
        return bytes(data)
    return fetch_image(image_url)


def fetch_image(url):
    if isinstance(url, str) and url.startswith("data:"):
        require_https_or_data_url(url, allowed_data_prefix="data:image/", name="image_url")
        return _decode_data_image(url)
    require_https_url(url, "image_url")
    parsed = urlparse(url)
    pinned_address = _assert_public_host(parsed.hostname)
    opener = urllib.request.build_opener(
        _RefuseRedirect,
        _PinnedHTTPSHandler(pinned_address),
    )
    request = urllib.request.Request(url, headers={"User-Agent": "salt-buttons/1.0"})
    try:
        with opener.open(request, timeout=20) as response:
            data = response.read(MAX_IMAGE_BYTES + 1)
    except ButtonsError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ButtonsError("I couldn't download that photo.") from exc
    if len(data) > MAX_IMAGE_BYTES:
        raise ButtonsError("That photo is too large.")
    if not data:
        raise ButtonsError("That photo was empty.")
    return data


def _decode_data_image(url):
    header, separator, encoded = url.partition(",")
    if not separator or not header.startswith("data:image/") or ";base64" not in header:
        raise ButtonsError("image_url data URLs must be base64 images.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ButtonsError("image_url data URLs must be base64 images.") from exc
    if not data:
        raise ButtonsError("That photo was empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ButtonsError("That photo is too large.")
    return data


def _assert_public_host(hostname):
    if not hostname:
        raise ButtonsError("The image URL must be a public https address.")
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    addresses = [literal] if literal is not None else _resolve(hostname)
    for address in addresses:
        if _blocked(address):
            raise ButtonsError("The image URL must be a public https address.")
    return str(addresses[0])


def _resolve(hostname):
    try:
        infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ButtonsError("I couldn't download that photo.") from exc
    addresses = []
    for info in infos:
        try:
            addresses.append(ipaddress.ip_address(info[4][0]))
        except ValueError as exc:
            raise ButtonsError("I couldn't download that photo.") from exc
    if not addresses:
        raise ButtonsError("I couldn't download that photo.")
    return addresses


def _blocked(address):
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )

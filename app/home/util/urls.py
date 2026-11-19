import ipaddress
import socket
from typing import List, Optional
from urllib.parse import urlparse

import httpcore
import httpx

NON_PUBLIC_MESSAGE = "URL resolves to a non-public address."


def _resolve(host: str, port: int) -> List[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)]


def _has_non_public(addresses: List[str]) -> bool:
    return any(not ipaddress.ip_address(address).is_global for address in addresses)


def remote_url_error(url: str) -> Optional[str]:
    """
    SSRF guard for URLs the server fetches on a user's behalf. Returns an
    error message, or None when the URL is safe to fetch: http(s) only, and
    every address the host resolves to must be public — otherwise any user
    with a token could make the server probe internal services.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return "Missing/Invalid URL"
    if parsed.scheme not in ("http", "https"):
        return "Only http(s) URLs are allowed."
    if not parsed.hostname:
        return "Missing/Invalid URL"
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = _resolve(parsed.hostname, port)
    except (socket.gaierror, ValueError):
        return f"Could not resolve host: {parsed.hostname}"
    if not addresses:
        return "Could not resolve host."
    if _has_non_public(addresses):
        return NON_PUBLIC_MESSAGE
    return None


class _PublicOnlyBackend(httpcore.SyncBackend):
    """
    Re-vets the host at connect time and dials the vetted IP, so DNS that
    changes between remote_url_error and the request (rebinding) can't
    steer the connection to an internal address.
    """

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        try:
            addresses = _resolve(host, port)
        except (socket.gaierror, ValueError) as error:
            raise httpcore.ConnectError(f"Could not resolve host: {host}") from error
        if not addresses or _has_non_public(addresses):
            raise httpcore.ConnectError(NON_PUBLIC_MESSAGE)
        error = None
        for address in dict.fromkeys(addresses):
            try:
                return super().connect_tcp(address, port, timeout, local_address, socket_options)
            except httpcore.ConnectError as exc:
                error = exc
        raise error


class PublicOnlyTransport(httpx.HTTPTransport):
    """httpx transport that only connects to public addresses; TLS still verifies the original hostname."""

    def __init__(self) -> None:
        super().__init__()
        self._pool = httpcore.ConnectionPool(
            ssl_context=httpx.create_ssl_context(), network_backend=_PublicOnlyBackend()
        )


def public_post(url: str, **kwargs) -> httpx.Response:
    with httpx.Client(transport=PublicOnlyTransport()) as client:
        return client.post(url, **kwargs)

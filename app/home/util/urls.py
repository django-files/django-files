import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse


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
        addr_info = socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, ValueError):
        return f"Could not resolve host: {parsed.hostname}"
    if not addr_info:
        return "Could not resolve host."
    for info in addr_info:
        if not ipaddress.ip_address(info[4][0]).is_global:
            return "URL resolves to a non-public address."
    return None

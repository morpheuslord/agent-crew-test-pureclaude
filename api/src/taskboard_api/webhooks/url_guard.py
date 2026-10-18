"""Server-side request forgery protection for user-supplied webhook URLs."""

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

MAX_URL_LENGTH = 2048
IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str, int], list[str]]


class UnsafeWebhookUrlError(ValueError):
    """The URL is malformed or points somewhere the API must not send requests."""


@dataclass(frozen=True, slots=True)
class WebhookTarget:
    """A validated URL plus the address the request must be sent to."""

    url: SplitResult
    host: str
    port: int
    address: str


def validate_webhook_url(url: str, *, allow_http: bool) -> str:
    """Check the URL's shape. Called when the URL is stored and again before each delivery."""
    if len(url) > MAX_URL_LENGTH:
        msg = "webhook URL is too long"
        raise UnsafeWebhookUrlError(msg)
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        msg = "webhook URL is not a valid URL"
        raise UnsafeWebhookUrlError(msg) from exc
    allowed_schemes = {"https", "http"} if allow_http else {"https"}
    if parts.scheme not in allowed_schemes:
        msg = "webhook URL must use https"
        raise UnsafeWebhookUrlError(msg)
    if not parts.hostname:
        msg = "webhook URL must include a host name"
        raise UnsafeWebhookUrlError(msg)
    if parts.username is not None or parts.password is not None:
        msg = "webhook URL must not contain credentials"
        raise UnsafeWebhookUrlError(msg)
    if port == 0:
        msg = "webhook URL has an invalid port"
        raise UnsafeWebhookUrlError(msg)
    return parts._replace(fragment="").geturl()


def system_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [str(info[4][0]) for info in infos]


def is_public_address(address: IpAddress) -> bool:
    """True only for globally routable unicast addresses."""
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return is_public_address(address.ipv4_mapped)
    return address.is_global and not address.is_multicast


def resolve_target(
    url: str,
    *,
    allow_http: bool,
    allow_private: bool,
    resolver: Resolver = system_resolver,
) -> WebhookTarget:
    """Validate ``url`` and resolve it to one vetted address.

    Every address the name resolves to must be acceptable; mixing a public and a private record
    is rejected. The caller connects to the returned address, so a second DNS lookup (rebinding)
    can not redirect the request.
    """
    parts = urlsplit(validate_webhook_url(url, allow_http=allow_http))
    host = parts.hostname or ""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        candidates = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            candidates = [ipaddress.ip_address(addr.split("%")[0]) for addr in resolver(host, port)]
        except (OSError, ValueError) as exc:
            msg = "webhook host could not be resolved"
            raise UnsafeWebhookUrlError(msg) from exc
    if not candidates:
        msg = "webhook host could not be resolved"
        raise UnsafeWebhookUrlError(msg)
    if not allow_private and not all(is_public_address(addr) for addr in candidates):
        msg = "webhook host resolves to a private or reserved address"
        raise UnsafeWebhookUrlError(msg)
    return WebhookTarget(url=parts, host=host, port=port, address=str(candidates[0]))

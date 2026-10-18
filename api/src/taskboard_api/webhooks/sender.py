"""Signed HTTP delivery of one webhook request."""

import ipaddress
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from taskboard_api.security.tokens import sign
from taskboard_api.webhooks.url_guard import Resolver, resolve_target, system_resolver


@dataclass(frozen=True, slots=True)
class WebhookDelivery:
    url: str
    secret: str = field(repr=False)
    event: str
    payload: dict[str, Any]


class WebhookDeliveryError(Exception):
    """The receiver could not be reached or did not answer with 2xx."""


class WebhookSender(Protocol):
    def send(self, delivery: WebhookDelivery) -> None: ...


class HttpWebhookSender:
    """POSTs JSON to the vetted address of the webhook host.

    Redirects are not followed, proxies from the environment are ignored, and the response body
    is never read beyond the status line.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float,
        allow_http: bool,
        allow_private: bool,
        resolver: Resolver = system_resolver,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._allow_http = allow_http
        self._allow_private = allow_private
        self._resolver = resolver
        self._transport = transport

    def send(self, delivery: WebhookDelivery) -> None:
        target = resolve_target(
            delivery.url,
            allow_http=self._allow_http,
            allow_private=self._allow_private,
            resolver=self._resolver,
        )
        body = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True).encode()
        address = target.address
        if isinstance(ipaddress.ip_address(address), ipaddress.IPv6Address):
            address = f"[{address}]"
        pinned_url = target.url._replace(netloc=f"{address}:{target.port}").geturl()
        default_port = 443 if target.url.scheme == "https" else 80
        host_header = target.host if target.port == default_port else f"{target.host}:{target.port}"
        headers = {
            "Host": host_header,
            "Content-Type": "application/json",
            "User-Agent": "Taskboard-Webhook/1",
            "X-Taskboard-Event": delivery.event,
            "X-Taskboard-Delivery": uuid.uuid4().hex,
            "X-Taskboard-Signature": f"sha256={sign(delivery.secret, body)}",
        }
        extensions = {"sni_hostname": target.host} if target.url.scheme == "https" else {}
        with httpx.Client(
            timeout=self._timeout,
            follow_redirects=False,
            trust_env=False,
            transport=self._transport,
        ) as client:
            request = client.build_request(
                "POST", pinned_url, content=body, headers=headers, extensions=extensions
            )
            try:
                response = client.send(request)
            except httpx.HTTPError as exc:
                raise WebhookDeliveryError(type(exc).__name__) from exc
            response.close()
        if not response.is_success:
            msg = f"receiver answered {response.status_code}"
            raise WebhookDeliveryError(msg)

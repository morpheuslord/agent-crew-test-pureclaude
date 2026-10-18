import json
from collections.abc import Callable

import httpx
import pytest

from taskboard_api.security.tokens import sign
from taskboard_api.webhooks.notifier import ThreadPoolWebhookNotifier
from taskboard_api.webhooks.sender import HttpWebhookSender, WebhookDelivery, WebhookDeliveryError
from taskboard_api.webhooks.url_guard import (
    UnsafeWebhookUrlError,
    resolve_target,
    validate_webhook_url,
)

PUBLIC = "93.184.215.14"


def resolver(*addresses: str) -> Callable[[str, int], list[str]]:
    return lambda host, port: list(addresses)


def delivery(url: str = "https://hooks.example.com/in?x=1") -> WebhookDelivery:
    return WebhookDelivery(url=url, secret="s3cret", event="task.status_changed", payload={"a": 1})


def test_validate_strips_fragment_and_allows_http_only_when_enabled() -> None:
    assert (
        validate_webhook_url("https://h.example/p#frag", allow_http=False) == "https://h.example/p"
    )
    with pytest.raises(UnsafeWebhookUrlError):
        validate_webhook_url("http://h.example/p", allow_http=False)
    assert validate_webhook_url("http://h.example/p", allow_http=True)
    with pytest.raises(UnsafeWebhookUrlError):
        validate_webhook_url("https://h.example/" + "a" * 2048, allow_http=False)
    with pytest.raises(UnsafeWebhookUrlError):
        validate_webhook_url("https://h.example:99999/", allow_http=False)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "172.16.3.4",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "::1",
        "fd00::1",
        "fe80::1%eth0",
        "::ffff:127.0.0.1",
        "224.0.0.1",
    ],
)
def test_private_and_reserved_addresses_are_blocked(address: str) -> None:
    with pytest.raises(UnsafeWebhookUrlError):
        resolve_target(
            "https://hooks.example.com/",
            allow_http=False,
            allow_private=False,
            resolver=resolver(address),
        )


def test_ip_literal_urls_are_checked_too() -> None:
    with pytest.raises(UnsafeWebhookUrlError):
        resolve_target(
            "https://169.254.169.254/latest/meta-data", allow_http=False, allow_private=False
        )
    with pytest.raises(UnsafeWebhookUrlError):
        resolve_target("https://[::1]:8443/", allow_http=False, allow_private=False)


def test_any_private_record_rejects_the_whole_name() -> None:
    with pytest.raises(UnsafeWebhookUrlError):
        resolve_target(
            "https://hooks.example.com/",
            allow_http=False,
            allow_private=False,
            resolver=resolver(PUBLIC, "10.0.0.1"),
        )


def test_resolution_failures_are_unsafe() -> None:
    def broken(host: str, port: int) -> list[str]:
        raise OSError("no such host")

    with pytest.raises(UnsafeWebhookUrlError):
        resolve_target(
            "https://nx.example/", allow_http=False, allow_private=False, resolver=broken
        )
    with pytest.raises(UnsafeWebhookUrlError):
        resolve_target(
            "https://nx.example/", allow_http=False, allow_private=False, resolver=resolver()
        )


def test_public_target_and_private_override() -> None:
    target = resolve_target(
        "https://hooks.example.com:8443/p",
        allow_http=False,
        allow_private=False,
        resolver=resolver(PUBLIC),
    )
    assert (target.host, target.port, target.address) == ("hooks.example.com", 8443, PUBLIC)
    local = resolve_target(
        "http://localhost/p", allow_http=True, allow_private=True, resolver=resolver("127.0.0.1")
    )
    assert local.port == 80


def test_sender_pins_address_signs_body_and_keeps_host_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    sender = HttpWebhookSender(
        timeout_seconds=1,
        allow_http=False,
        allow_private=False,
        resolver=resolver(PUBLIC),
        transport=httpx.MockTransport(handler),
    )
    sender.send(delivery())
    [request] = seen
    assert request.url.host == PUBLIC
    assert request.url.path == "/in"
    assert request.url.query == b"x=1"
    assert request.headers["host"] == "hooks.example.com"
    assert request.extensions["sni_hostname"] == "hooks.example.com"
    body = request.content
    assert json.loads(body) == {"a": 1}
    assert request.headers["x-taskboard-signature"] == f"sha256={sign('s3cret', body)}"
    assert request.headers["x-taskboard-event"] == "task.status_changed"


def test_sender_handles_ipv6_and_custom_ports() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    sender = HttpWebhookSender(
        timeout_seconds=1,
        allow_http=True,
        allow_private=False,
        resolver=resolver("2606:2800:220:1:248:1893:25c8:1946"),
        transport=httpx.MockTransport(handler),
    )
    sender.send(delivery("http://hooks.example.com:8080/x"))
    assert seen[0].url.host == "2606:2800:220:1:248:1893:25c8:1946"
    assert seen[0].headers["host"] == "hooks.example.com:8080"
    assert "sni_hostname" not in seen[0].extensions


@pytest.mark.parametrize("status", [301, 302, 400, 500])
def test_sender_treats_redirects_and_errors_as_failures(status: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers={"location": "http://169.254.169.254/"})

    sender = HttpWebhookSender(
        timeout_seconds=1,
        allow_http=False,
        allow_private=False,
        resolver=resolver(PUBLIC),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(WebhookDeliveryError):
        sender.send(delivery())


def test_sender_wraps_transport_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout")

    sender = HttpWebhookSender(
        timeout_seconds=1,
        allow_http=False,
        allow_private=False,
        resolver=resolver(PUBLIC),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(WebhookDeliveryError):
        sender.send(delivery())


class ScriptedSender:
    def __init__(self, *outcomes: Exception | None) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def send(self, delivery: WebhookDelivery) -> None:
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None:
            raise outcome


def _run(sender: ScriptedSender, attempts: int = 3) -> list[float]:
    sleeps: list[float] = []
    notifier = ThreadPoolWebhookNotifier(
        sender, workers=1, max_attempts=attempts, backoff_seconds=0.5, sleep=sleeps.append
    )
    notifier.notify(delivery())
    notifier.close()
    return sleeps


def test_notifier_retries_with_backoff_then_succeeds() -> None:
    sender = ScriptedSender(WebhookDeliveryError("500"), WebhookDeliveryError("500"), None)
    assert _run(sender) == [0.5, 1.0]
    assert sender.calls == 3


def test_notifier_gives_up_after_max_attempts() -> None:
    sender = ScriptedSender(*(WebhookDeliveryError("down") for _ in range(5)))
    assert _run(sender, attempts=2) == [0.5]
    assert sender.calls == 2


def test_notifier_does_not_retry_blocked_urls() -> None:
    sender = ScriptedSender(UnsafeWebhookUrlError("private"))
    assert _run(sender) == []
    assert sender.calls == 1


def test_notifier_drops_deliveries_when_queue_is_full() -> None:
    sender = ScriptedSender()
    notifier = ThreadPoolWebhookNotifier(
        sender, workers=1, max_attempts=1, backoff_seconds=0, max_pending=1, sleep=lambda _: None
    )
    notifier._slots.acquire()
    notifier.notify(delivery())
    notifier._slots.release()
    notifier.close()
    assert sender.calls == 0

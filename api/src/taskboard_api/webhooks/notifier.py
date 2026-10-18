"""Asynchronous, best-effort webhook delivery with a short retry."""

import contextvars
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol
from urllib.parse import urlsplit

from taskboard_api.webhooks.sender import WebhookDelivery, WebhookDeliveryError, WebhookSender
from taskboard_api.webhooks.url_guard import UnsafeWebhookUrlError

logger = logging.getLogger(__name__)


class WebhookNotifier(Protocol):
    def notify(self, delivery: WebhookDelivery) -> None:
        """Schedule a delivery and return immediately."""
        ...

    def close(self) -> None: ...


class ThreadPoolWebhookNotifier:
    """Delivers on a bounded worker pool so the request that triggered it never waits."""

    def __init__(
        self,
        sender: WebhookSender,
        *,
        workers: int,
        max_attempts: int,
        backoff_seconds: float,
        max_pending: int = 1000,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._sender = sender
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="webhook")
        self._max_attempts = max_attempts
        self._backoff = backoff_seconds
        self._sleep = sleep
        self._slots = threading.BoundedSemaphore(max_pending)

    def notify(self, delivery: WebhookDelivery) -> None:
        if not self._slots.acquire(blocking=False):
            logger.warning("webhook dropped: too many pending deliveries")
            return
        context = contextvars.copy_context()  # keeps the request id in the worker's log lines
        future = self._executor.submit(context.run, self._deliver, delivery)
        future.add_done_callback(lambda _: self._slots.release())

    def close(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _deliver(self, delivery: WebhookDelivery) -> None:
        host = urlsplit(delivery.url).hostname
        for attempt in range(1, self._max_attempts + 1):
            try:
                self._sender.send(delivery)
            except UnsafeWebhookUrlError as exc:
                logger.warning("webhook blocked", extra={"webhook_host": host, "reason": str(exc)})
                return
            except WebhookDeliveryError as exc:
                logger.info(
                    "webhook attempt failed",
                    extra={"webhook_host": host, "attempt": attempt, "reason": str(exc)},
                )
                if attempt < self._max_attempts:
                    self._sleep(self._backoff * 2 ** (attempt - 1))
            else:
                logger.info("webhook delivered", extra={"webhook_host": host, "attempt": attempt})
                return
        logger.warning("webhook gave up", extra={"webhook_host": host})

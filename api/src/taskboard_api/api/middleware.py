"""ASGI middleware: request context and access logging, and request body size limits."""

import json
import logging
import time

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from taskboard_api.logging_config import bind_request_id

logger = logging.getLogger("taskboard_api.access")


class RequestContextMiddleware:
    """Binds the request id from ``X-Request-Id`` (or a new one), echoes it, logs each request."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        request_id = bind_request_id(headers.get(b"x-request-id", b"").decode("latin-1") or None)
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                message.setdefault("headers", [])
                message["headers"] = [
                    *message["headers"],
                    (b"x-request-id", request_id.encode()),
                ]
            await send(message)

        try:
            await self._app(scope, receive, send_with_id)
        finally:
            logger.info(
                "request",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),  # never the query string
                    "status": status_holder["status"],
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )


class _BodyTooLargeError(StarletteHTTPException):
    """Raised from ``receive``. An HTTPException so FastAPI's body parsing re-raises it as is
    (other errors become a generic 400) and the error handler answers 413."""

    def __init__(self) -> None:
        super().__init__(status_code=413, detail="the request body is too large")


class BodySizeLimitMiddleware:
    """Rejects request bodies over ``max_bytes`` with 413, whether or not Content-Length is sent.

    Without this, the multipart parser would spool an arbitrarily large upload to disk before the
    service could check its size.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self._app = app
        self._max = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self._max:
            await self._reject(send)
            return
        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max:
                    raise _BodyTooLargeError
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self._app(scope, limited_receive, tracking_send)
        except _BodyTooLargeError:
            if not response_started:
                await self._reject(send)

    async def _reject(self, send: Send) -> None:
        body = json.dumps(
            {
                "error": {
                    "code": "payload_too_large",
                    "message": "the request body is too large",
                    "fields": {},
                }
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

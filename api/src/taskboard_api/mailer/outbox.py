"""Mailer that writes to the outbox table and the log instead of sending."""

import logging

from taskboard_api.models import OutboxMessage
from taskboard_api.repositories.interfaces import OutboxRepository

logger = logging.getLogger(__name__)


class OutboxMailer:
    """Writes emails to the ``outbox`` table (in the caller's transaction) and to the log.

    There is no email provider. ``log_body=False`` keeps message bodies, which can contain reset
    links, out of the log while still recording that a message was written.
    """

    def __init__(self, outbox: OutboxRepository, *, log_body: bool) -> None:
        self._outbox = outbox
        self._log_body = log_body

    def send(self, to: str, subject: str, body: str) -> None:
        self._outbox.add(OutboxMessage(to_address=to, subject=subject, body=body))
        logger.info(
            "email written to outbox",
            extra={
                "email_to": to,
                "email_subject": subject,
                "email_body": body if self._log_body else "[not logged]",
            },
        )

"""Random tokens and their storage hashes."""

import hashlib
import hmac
import secrets

TOKEN_BYTES = 32


def new_token() -> str:
    """A URL-safe token with 256 bits of entropy."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 hex digest. Tokens are high-entropy, so a fast unsalted hash is sufficient."""
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())


def sign(secret: str, payload: bytes) -> str:
    """HMAC-SHA256 of ``payload``, hex encoded."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

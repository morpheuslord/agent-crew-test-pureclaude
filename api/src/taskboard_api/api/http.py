"""HTTP header helpers."""

import re
from urllib.parse import quote

_UNSAFE_ASCII = re.compile(r"[^A-Za-z0-9._ -]")


def content_disposition(filename: str) -> str:
    """An ``attachment`` header that is safe for any filename.

    The quoted ``filename`` is reduced to a conservative ASCII set (no quotes, backslashes, CR or
    LF, so no header injection), and ``filename*`` carries the exact name percent-encoded.
    """
    fallback = _UNSAFE_ASCII.sub("_", filename.encode("ascii", "replace").decode()).strip()
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{fallback or 'download'}\"; filename*=UTF-8''{encoded}"

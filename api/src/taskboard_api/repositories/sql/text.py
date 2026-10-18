"""Helpers for safe text matching."""


def escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input matches literally (used with ``escape='\\\\'``)."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contains_pattern(value: str) -> str:
    """A bound-parameter pattern matching ``value`` anywhere in a column."""
    return f"%{escape_like(value)}%"

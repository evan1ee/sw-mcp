"""Text normalization (spec 3.4.3)."""

import unicodedata


def normalize_text(s: str) -> str:
    """Return ``s`` in Unicode NFC."""
    return unicodedata.normalize("NFC", s)

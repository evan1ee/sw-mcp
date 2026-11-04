"""Pure ULID encoding and the ID shapes of the project store (spec 13.2.1)."""

import re
from typing import Final, Literal

type IdPrefix = Literal["job", "rep", "snap", "drw", "req"]

ID_PREFIXES: Final[tuple[IdPrefix, ...]] = ("job", "rep", "snap", "drw", "req")
_ALPHABET: Final = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford: no I, L, O, U
_ULID_CHARS: Final = 26
_MS_BITS: Final = 48
_RANDOM_BYTES: Final = 10
_RANDOM_BITS: Final = 80
_ULID_PATTERN: Final = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")


def encode_ulid(ms: int, randomness: bytes) -> str:
    """The 26-character ULID for a Unix time in milliseconds and 10 random bytes."""
    if not 0 <= ms < 1 << _MS_BITS:
        raise ValueError("ulid time must fit in 48 bits")
    if len(randomness) != _RANDOM_BYTES:
        raise ValueError("ulid randomness must be 10 bytes")
    value = (ms << _RANDOM_BITS) | int.from_bytes(randomness, "big")
    chars: list[str] = []
    for _ in range(_ULID_CHARS):
        chars.append(_ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def is_id(value: str, prefix: IdPrefix) -> bool:
    """True when ``value`` is ``<prefix>_`` plus a 26-character Crockford ULID."""
    head, sep, tail = value.partition("_")
    return sep == "_" and head == prefix and _ULID_PATTERN.fullmatch(tail) is not None

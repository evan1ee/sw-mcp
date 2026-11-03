"""Derived Resolved Scheme entry IDs (spec 3.4.4)."""

import re
from collections.abc import Mapping, Sequence
from typing import Final

from cad_ir.core.canonical import content_hash
from cad_ir.core.json_types import JsonValue

_SLUG_MAX: Final = 40
_HASH_LENGTHS: Final = (6, 8, 12)
_NON_SLUG: Final = re.compile(r"[^a-z0-9_]")


def _entry_hash(
    kind: str, covers: Sequence[str], measures: Mapping[str, JsonValue] | None, source: str
) -> str:
    """Content hash of ``{kind, covers (sorted), measures (if any), source}``."""
    sorted_covers: list[JsonValue] = list(sorted(covers))
    entry: dict[str, JsonValue] = {"kind": kind, "covers": sorted_covers, "source": source}
    if measures is not None:
        entry["measures"] = dict(measures)
    return content_hash(entry)


def _slug(covers: Sequence[str], measures: Mapping[str, JsonValue] | None) -> str:
    if covers:
        raw = sorted(covers)[0]
    else:
        target = None if measures is None else measures.get("to")
        raw = target if isinstance(target, str) else ""
    return _NON_SLUG.sub("_", raw)[:_SLUG_MAX]


def scheme_entry_id(
    kind: str,
    covers: Sequence[str],
    measures: Mapping[str, JsonValue] | None,
    source: str,
    *,
    taken: Mapping[str, str] | None = None,
) -> str:
    """Return ``ds_<slug>_<hash>``. ``taken`` maps existing IDs to their content hashes.

    The hash grows from 6 to 8 to 12 hex characters when a different entry holds the ID.
    """
    slug = _slug(covers, measures)
    if not slug:
        raise ValueError("a scheme entry needs a non-empty covers[0] or measures.to for its slug")
    entry_hash = _entry_hash(kind, covers, measures, source)
    digest = entry_hash.removeprefix("sha256:")
    existing = taken or {}
    for length in _HASH_LENGTHS:
        candidate = f"ds_{slug}_{digest[:length]}"
        if existing.get(candidate, entry_hash) == entry_hash:
            return candidate
    raise ValueError(f"scheme entry ID collision persists at 12 hex characters: ds_{slug}")

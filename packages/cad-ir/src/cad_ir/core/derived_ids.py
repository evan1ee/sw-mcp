"""Derived Resolved Scheme entry IDs (spec 3.4.4)."""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from cad_ir.core.canonical import canonical_bytes, content_hash
from cad_ir.core.json_types import JsonValue

_SLUG_MAX: Final = 40
_HASH_LENGTHS: Final = (6, 8, 12)
_NON_SLUG: Final = re.compile(r"[^a-z0-9_]")


@dataclass(frozen=True, slots=True)
class SchemeEntry:
    """The part of a Resolved Scheme entry its ID derives from."""

    kind: str
    covers: tuple[str, ...]
    measures: Mapping[str, JsonValue] | None
    source: str


def _canonical_covers(covers: Iterable[str]) -> list[str]:
    """``covers`` as a set: de-duplicated and sorted by canonical serialization."""
    return sorted(set(covers), key=canonical_bytes)


def _entry_hash(
    kind: str, covers: Sequence[str], measures: Mapping[str, JsonValue] | None, source: str
) -> str:
    """Content hash of ``{kind, covers (set), measures (if any), source}``."""
    unique: list[JsonValue] = list(_canonical_covers(covers))
    entry: dict[str, JsonValue] = {"kind": kind, "covers": unique, "source": source}
    if measures is not None:
        entry["measures"] = dict(measures)
    return content_hash(entry)


def _slug(covers: Sequence[str], measures: Mapping[str, JsonValue] | None) -> str:
    if covers:
        raw = _canonical_covers(covers)[0]
    else:
        target = None if measures is None else measures.get("to")
        raw = target if isinstance(target, str) else ""
    slug = _NON_SLUG.sub("_", raw)[:_SLUG_MAX]
    if not slug:
        raise ValueError("a scheme entry needs a non-empty covers[0] or measures.to for its slug")
    return slug


def scheme_entry_ids(
    entries: Iterable[SchemeEntry], previous: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Map each distinct entry's content hash to its ``ds_<slug>_<hex>`` ID.

    ``previous`` maps entry hashes to the IDs of the last resolution; an entry found there keeps
    its ID. Every other entry takes the shortest of 6, 8 or 12 hex characters at which its ID
    differs from every ID already assigned and from the ID of every other new entry. Entries
    that collide grow together, so the result never depends on the order of ``entries``.
    """
    prior = previous or {}
    slugs: dict[str, str] = {}
    for entry in entries:
        entry_hash = _entry_hash(entry.kind, entry.covers, entry.measures, entry.source)
        slugs[entry_hash] = _slug(entry.covers, entry.measures)

    ids = {h: prior[h] for h in slugs if h in prior}
    taken = set(ids.values())
    pending = [h for h in slugs if h not in prior]
    for length in _HASH_LENGTHS:
        groups: defaultdict[str, list[str]] = defaultdict(list)
        for h in pending:
            groups[f"ds_{slugs[h]}_{h.removeprefix('sha256:')[:length]}"].append(h)
        unresolved: list[str] = []
        for candidate, members in groups.items():
            if len(members) == 1 and candidate not in taken:
                ids[members[0]] = candidate
                taken.add(candidate)
            else:
                unresolved.extend(members)
        pending = unresolved
    if pending:
        raise ValueError(
            f"scheme entry ID collision persists at 12 hex characters: {sorted(pending)}"
        )
    return ids


def scheme_entry_id(
    kind: str, covers: Sequence[str], measures: Mapping[str, JsonValue] | None, source: str
) -> str:
    """The ID of one entry on its own (6 hex characters)."""
    entry = SchemeEntry(kind, tuple(covers), measures, source)
    return next(iter(scheme_entry_ids([entry]).values()))

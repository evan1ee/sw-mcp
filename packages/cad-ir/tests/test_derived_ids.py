import itertools
import re

import pytest
from cad_ir.core import derived_ids
from cad_ir.core.derived_ids import SchemeEntry, scheme_entry_id, scheme_entry_ids


def _entry(source: str, cover: str = "a.b") -> SchemeEntry:
    return SchemeEntry("d", (cover,), None, source)


def _hash_of(entry: SchemeEntry) -> str:
    return derived_ids._entry_hash(  # pyright: ignore[reportPrivateUsage]
        entry.kind, entry.covers, entry.measures, entry.source
    )


@pytest.fixture
def forced_hashes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hashes whose first 6 hex characters collide for sources starting with ``c``.

    ``c1`` and ``c2`` share 8 characters too; ``c3`` shares only 6; ``u`` is unique.
    """
    table = {
        "c1": "aaaaaa" + "11" + "0" * 56,
        "c2": "aaaaaa" + "11" + "1" * 56,
        "c3": "aaaaaa" + "33" + "2" * 56,
        "u": "bbbbbb" + "0" * 58,
    }

    def fake(kind: str, covers: object, measures: object, source: str) -> str:
        del kind, covers, measures
        return "sha256:" + table[source]

    monkeypatch.setattr(derived_ids, "_entry_hash", fake)


def test_scheme_entry_id_shape_and_order_independence() -> None:
    a = scheme_entry_id("diameter", ["bore_1.diameter"], None, "model")
    assert re.fullmatch(r"ds_bore_1_diameter_[0-9a-f]{6}", a)
    assert scheme_entry_id("x", ["b.c", "a.b"], None, "s") == scheme_entry_id(
        "x", ["a.b", "b.c"], None, "s"
    )


def test_scheme_entry_id_golden_vector() -> None:
    assert (
        scheme_entry_id("diameter", ["bore_1.diameter"], None, "model")
        == "ds_bore_1_diameter_216901"
    )


def test_scheme_entry_id_depends_on_content() -> None:
    a = scheme_entry_id("d", ["a.b"], None, "s1")
    b = scheme_entry_id("d", ["a.b"], None, "s2")
    c = scheme_entry_id("d", ["a.b"], {"to": "x"}, "s1")
    assert len({a, b, c}) == 3  # noqa: PLR2004


def test_scheme_entry_id_uses_measures_to_and_cuts_slug() -> None:
    i = scheme_entry_id("distance", [], {"to": "Plane.Right" * 10}, "model")
    slug = "_lane__ight_lane__ight_lane__ight_lane__"
    assert len(slug) == 40  # noqa: PLR2004
    assert re.fullmatch(rf"ds_{slug}_[0-9a-f]{{6}}", i)


def test_covers_are_a_set() -> None:
    assert scheme_entry_id("d", ["a.b", "a.b", "c.d"], None, "s") == scheme_entry_id(
        "d", ["c.d", "a.b"], None, "s"
    )


def test_covers_sort_by_canonical_bytes_for_hash_and_slug() -> None:
    one = scheme_entry_id("d", ["z.a", "é.a"], None, "s")
    other = scheme_entry_id("d", ["é.a", "z.a"], None, "s")
    assert one == other
    assert one.startswith("ds_z_a_")


def test_duplicates_map_once() -> None:
    entry = _entry("s")
    ids = scheme_entry_ids([entry, entry, SchemeEntry("d", ("a.b", "a.b"), None, "s")])
    assert len(ids) == 1


def test_needs_slug() -> None:
    with pytest.raises(ValueError, match="slug"):
        scheme_entry_id("d", [], None, "s")
    with pytest.raises(ValueError, match="slug"):
        scheme_entry_id("d", [], {"to": 5}, "s")


def test_colliding_new_entries_grow_together_in_any_order(forced_hashes: None) -> None:
    entries = [_entry("c1"), _entry("c2"), _entry("c3"), _entry("u")]
    results = [scheme_entry_ids(list(p)) for p in itertools.permutations(entries)]
    assert all(r == results[0] for r in results)
    by_source = {e.source: results[0][_hash_of(e)] for e in entries}
    # c1, c2, c3 collide at 6 so all three grow; c1 and c2 still collide at 8 and need 12
    assert by_source["u"] == "ds_a_b_bbbbbb"
    assert by_source["c3"] == "ds_a_b_aaaaaa33"
    assert by_source["c1"] == "ds_a_b_aaaaaa11" + "0000"
    assert by_source["c2"] == "ds_a_b_aaaaaa11" + "1111"
    assert len(set(by_source.values())) == 4  # noqa: PLR2004


def test_previous_keeps_ids_when_the_partner_disappears(forced_hashes: None) -> None:
    c1, c3 = _entry("c1"), _entry("c3")
    first = scheme_entry_ids([c1, c3])
    assert first[_hash_of(c1)] == "ds_a_b_aaaaaa11"
    assert first[_hash_of(c3)] == "ds_a_b_aaaaaa33"
    # c3 gone: a fresh resolution would shrink c1 to 6 characters, but previous pins its ID
    assert scheme_entry_ids([c1], previous=first) == {_hash_of(c1): "ds_a_b_aaaaaa11"}
    assert scheme_entry_ids([c1])[_hash_of(c1)] == "ds_a_b_aaaaaa"


def test_new_entry_avoids_ids_held_through_previous(forced_hashes: None) -> None:
    c1, c3 = _entry("c1"), _entry("c3")
    previous = {_hash_of(c1): "ds_a_b_aaaaaa"}  # held at 6 characters by an older resolution
    ids = scheme_entry_ids([c3, c1], previous=previous)
    assert ids[_hash_of(c1)] == "ds_a_b_aaaaaa"
    assert ids[_hash_of(c3)] == "ds_a_b_aaaaaa33"


def test_collision_at_twelve_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(kind: str, covers: object, measures: object, source: str) -> str:
        del kind, covers, measures
        return "sha256:" + "ab" * 12 + source * 20

    monkeypatch.setattr(derived_ids, "_entry_hash", fake)
    with pytest.raises(ValueError, match="collision"):
        scheme_entry_ids([_entry("0"), _entry("1")])

import re

import pytest
from cad_ir.core.derived_ids import _entry_hash, scheme_entry_id  # pyright: ignore[reportPrivateUsage]


def test_scheme_entry_id_shape_and_order_independence() -> None:
    a = scheme_entry_id("diameter", ["bore_1.diameter"], None, "model")
    assert re.fullmatch(r"ds_bore_1_diameter_[0-9a-f]{6}", a)
    assert scheme_entry_id("x", ["b.c", "a.b"], None, "s") == scheme_entry_id(
        "x", ["a.b", "b.c"], None, "s"
    )


def test_scheme_entry_id_depends_on_content() -> None:
    a = scheme_entry_id("d", ["a.b"], None, "s1")
    b = scheme_entry_id("d", ["a.b"], None, "s2")
    c = scheme_entry_id("d", ["a.b"], {"to": "x"}, "s1")
    assert len({a, b, c}) == len((a, b, c))


def test_scheme_entry_id_uses_measures_to_and_cuts_slug() -> None:
    i = scheme_entry_id("distance", [], {"to": "Plane.Right" * 10}, "model")
    assert re.fullmatch(r"ds_[a-z0-9_]{40}_[0-9a-f]{6}", i)


def test_scheme_entry_id_grows_on_collision() -> None:
    first = scheme_entry_id("d", ["a.b"], None, "s")
    grown = scheme_entry_id("d", ["a.b"], None, "s", taken={first: "sha256:other"})
    assert re.fullmatch(r"ds_a_b_[0-9a-f]{8}", grown)
    assert grown.startswith(first)
    own = _entry_hash("d", ["a.b"], None, "s")
    assert scheme_entry_id("d", ["a.b"], None, "s", taken={first: own}) == first


def test_scheme_entry_id_grows_to_twelve_then_raises() -> None:
    first = scheme_entry_id("d", ["a.b"], None, "s")
    second = scheme_entry_id("d", ["a.b"], None, "s", taken={first: "x"})
    twelve = scheme_entry_id("d", ["a.b"], None, "s", taken={first: "x", second: "x"})
    assert re.fullmatch(r"ds_a_b_[0-9a-f]{12}", twelve)
    with pytest.raises(ValueError, match="collision"):
        scheme_entry_id("d", ["a.b"], None, "s", taken={first: "x", second: "x", twelve: "x"})


def test_scheme_entry_id_needs_slug() -> None:
    with pytest.raises(ValueError, match="slug"):
        scheme_entry_id("d", [], None, "s")
    with pytest.raises(ValueError, match="slug"):
        scheme_entry_id("d", [], {"to": 5}, "s")

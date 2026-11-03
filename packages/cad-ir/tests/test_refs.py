from collections.abc import Callable

import pytest
from cad_ir.core.refs import (
    DatumGeometryRef,
    DocumentRef,
    FeatureRoleRef,
    IntentItemRef,
    ItemRef,
    LocalRef,
    ParamRef,
    ReferenceSyntaxError,
    SolidWorksDimRef,
    StandardGeometryRef,
    StoredGeometryRef,
    parse_document_ref,
    parse_geometry_ref,
    parse_intent_item_ref,
    parse_item_ref,
    parse_local_ref,
    parse_param_ref,
    parse_solidworks_dim_ref,
)


def test_parse_document_ref_roundtrip() -> None:
    r = parse_document_ref("part:bracket@4")
    assert r == DocumentRef("part", "bracket", 4)
    assert str(r) == "part:bracket@4"
    assert parse_document_ref("drawing_intent:BRK-001-DI").revision is None


@pytest.mark.parametrize(
    "s",
    [
        "part:x@0",
        "part:x@01",
        "part:x@",
        "part:x@-1",
        " part:x",
        "PART:x",
        "foo:x",
        "part:",
        "part:x/bore_1",
        "part:x\n",
    ],
)
def test_parse_document_ref_rejects(s: str) -> None:
    with pytest.raises(ReferenceSyntaxError) as e:
        parse_document_ref(s)
    assert e.value.ref == s
    assert e.value.expected == "<module>:<document_id>[@<revision>]"


def test_parse_item_ref() -> None:
    s = "design_intent:BRK-001-DES@2/r1"
    r = parse_item_ref(s)
    assert r == ItemRef(DocumentRef("design_intent", "BRK-001-DES", 2), "r1")
    assert str(r) == s


@pytest.mark.parametrize(
    "s", ["part:x", "part:x/Bore", "part:x@0/r1", "part:x/r1\n", "part:x/r1/r2", "r1"]
)
def test_parse_item_ref_rejects(s: str) -> None:
    with pytest.raises(ReferenceSyntaxError):
        parse_item_ref(s)


def test_parse_local_ref() -> None:
    assert parse_local_ref("bore_dia") == LocalRef("bore_dia")


def test_parse_intent_item_ref() -> None:
    assert parse_intent_item_ref("datum:A") == IntentItemRef("datum", "A")
    assert (
        parse_intent_item_ref("scheme:ds_bore_1_diameter_b41219").id == "ds_bore_1_diameter_b41219"
    )
    assert parse_intent_item_ref("finish:f1") == IntentItemRef("finish", "f1")


@pytest.mark.parametrize(
    "s", ["datum:I", "datum:a", "scheme:A", "tolerance:x", "datum:A\n", "datum:", "gdt:G1"]
)
def test_parse_intent_item_ref_rejects(s: str) -> None:
    with pytest.raises(ReferenceSyntaxError):
        parse_intent_item_ref(s)


def test_parse_param_ref() -> None:
    r = parse_param_ref("bore_1.diameter")
    assert r == ParamRef("bore_1", "diameter")
    assert str(r) == "bore_1.diameter"


@pytest.mark.parametrize("s", ["bore_1", "bore_1.a.b", "Bore.d", "bore_1.d\n", "part:x"])
def test_parse_param_ref_rejects(s: str) -> None:
    with pytest.raises(ReferenceSyntaxError):
        parse_param_ref(s)


def test_parse_geometry_ref_variants() -> None:
    assert parse_geometry_ref("bore_1.cylindrical_face") == FeatureRoleRef(
        "bore_1", "cylindrical_face"
    )
    assert parse_geometry_ref("geo:g7f3a21c0") == StoredGeometryRef("g7f3a21c0")
    assert parse_geometry_ref("plane:right") == StandardGeometryRef("plane:right")
    assert parse_geometry_ref("origin") == StandardGeometryRef("origin")
    assert parse_geometry_ref("datum:A") == DatumGeometryRef("A")


@pytest.mark.parametrize(
    "s", ["plane:left", "bore_1", "bore_1.a.b", "part:x", "datum:I", "geo:G1", "origin\n"]
)
def test_parse_geometry_ref_rejects(s: str) -> None:
    with pytest.raises(ReferenceSyntaxError):
        parse_geometry_ref(s)


def test_parse_solidworks_dim_ref() -> None:
    r = parse_solidworks_dim_ref("swdim:D1@Sketch1")
    assert r == SolidWorksDimRef("D1@Sketch1")
    assert str(r) == "swdim:D1@Sketch1"


@pytest.mark.parametrize("s", ["swdim:", "swdim:a\nb", "swdim:a\x00", "D1@Sketch1", "swdim:a\x7f"])
def test_parse_solidworks_dim_ref_rejects(s: str) -> None:
    with pytest.raises(ReferenceSyntaxError):
        parse_solidworks_dim_ref(s)


def test_parsers_reject_other_kinds() -> None:  # the field type decides (3.4.2)
    for parse, s in [
        (parse_param_ref, "part:x"),
        (parse_local_ref, "bore_1.diameter"),
        (parse_document_ref, "part:x/r1"),
        (parse_solidworks_dim_ref, "swdim:"),
    ]:
        with pytest.raises(ReferenceSyntaxError):
            parse(s)


@pytest.mark.parametrize(
    ("parse", "s"),
    [
        (parse_document_ref, "part:bracket@4"),
        (parse_document_ref, "assembly:a1"),
        (parse_item_ref, "design_intent:BRK-001-DES@2/r1"),
        (parse_item_ref, "part:x/bore_1"),
        (parse_local_ref, "bore_dia"),
        (parse_intent_item_ref, "datum:A"),
        (parse_intent_item_ref, "scheme:ds_bore_1_diameter_b41219"),
        (parse_param_ref, "sketch_bore.x"),
        (parse_geometry_ref, "bore_1.cylindrical_face"),
        (parse_geometry_ref, "geo:g7f3a21c0"),
        (parse_geometry_ref, "plane:front"),
        (parse_geometry_ref, "plane:top"),
        (parse_geometry_ref, "origin"),
        (parse_geometry_ref, "datum:AB"),
        (parse_solidworks_dim_ref, "swdim:D1@Sketch1"),
    ],
)
def test_str_roundtrip(parse: Callable[[str], object], s: str) -> None:
    assert str(parse(s)) == s


@pytest.mark.parametrize(
    "build",
    [
        lambda: DocumentRef("part", "x y", 0),
        lambda: DocumentRef("part", "x", 0),
        lambda: DocumentRef("part", "x", True),
        lambda: DocumentRef("nope", "x"),  # type: ignore[arg-type]  # pyright: ignore
        lambda: ItemRef(DocumentRef("part", "x"), "Bad"),
        lambda: LocalRef("1a"),
        lambda: IntentItemRef("datum", "bore"),
        lambda: IntentItemRef("scheme", "A"),
        lambda: IntentItemRef("other", "a"),  # type: ignore[arg-type]  # pyright: ignore
        lambda: ParamRef("a", "B"),
        lambda: FeatureRoleRef("a.b", "c"),
        lambda: StoredGeometryRef("G1"),
        lambda: StandardGeometryRef("plane:left"),  # type: ignore[arg-type]  # pyright: ignore
        lambda: DatumGeometryRef("I"),
        lambda: SolidWorksDimRef("D1\u0085"),
        lambda: SolidWorksDimRef("a" + chr(0x2028) + "b"),
        lambda: SolidWorksDimRef(""),
    ],
)
def test_reference_values_validate_on_construction(build: Callable[[], object]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        build()


@pytest.mark.parametrize(
    ("parser", "s"),
    [
        (parse_document_ref, "part:bracket@4"),
        (parse_item_ref, "design_intent:BRK-001-DES@2/r1"),
        (parse_local_ref, "bore_dia"),
        (parse_intent_item_ref, "datum:A"),
        (parse_intent_item_ref, "scheme:ds_a_1"),
        (parse_param_ref, "bore_1.diameter"),
        (parse_geometry_ref, "bore_1.cylindrical_face"),
        (parse_geometry_ref, "geo:g7f3a21c0"),
        (parse_geometry_ref, "plane:right"),
        (parse_geometry_ref, "origin"),
        (parse_geometry_ref, "datum:A"),
        (parse_solidworks_dim_ref, "swdim:D1@Sketch1"),
    ],
)
def test_every_parsed_instance_round_trips(parser: Callable[[str], object], s: str) -> None:
    assert str(parser(s)) == s

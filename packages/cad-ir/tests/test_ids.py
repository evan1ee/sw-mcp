import pytest
from cad_ir.core.ids import (
    DATUM_LABEL_PATTERN,
    DOCUMENT_ID_PATTERN,
    ITEM_ID_PATTERN,
    MODULE_KEYS,
    REVISION_PATTERN,
    is_datum_label,
    is_document_id,
    is_item_id,
    is_module_key,
)


@pytest.mark.parametrize("s", ["bore_1", "a", "a" * 64])
def test_item_id_accepts(s: str) -> None:
    assert is_item_id(s)


@pytest.mark.parametrize(
    "s",
    ["Bore_1", "1bore", "a" * 65, "bore-1", "bore_1\n", "", "前视基准面", "Boss-Extrude1"],
)
def test_item_id_rejects_display_names(s: str) -> None:
    assert not is_item_id(s)


@pytest.mark.parametrize("s", ["A", "AB", "Z", "HJ"])
def test_datum_label_accepts(s: str) -> None:
    assert is_datum_label(s)


@pytest.mark.parametrize("s", ["I", "O", "Q", "AI", "a", "ABC", "", "A\n"])
def test_datum_label_rejects(s: str) -> None:
    assert not is_datum_label(s)


@pytest.mark.parametrize("s", ["BRK-001-DI", "x", "a.b_c-d", "0abc", "a" * 128])
def test_document_id_accepts(s: str) -> None:
    assert is_document_id(s)


@pytest.mark.parametrize("s", ["-x", ".x", "a" * 129, "a b", "", "x\n", "é"])
def test_document_id_rejects(s: str) -> None:
    assert not is_document_id(s)


def test_module_keys() -> None:
    assert MODULE_KEYS == (
        "part",
        "assembly",
        "design_intent",
        "drawing_intent",
        "drawing_layout",
        "drawing_template",
    )
    assert is_module_key("part")
    assert is_module_key("drawing_template")
    assert not is_module_key("PART")
    assert not is_module_key("drawing")


def test_pattern_constants() -> None:
    assert ITEM_ID_PATTERN == r"[a-z][a-z0-9_]{0,63}"
    assert DOCUMENT_ID_PATTERN == r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
    assert DATUM_LABEL_PATTERN == r"[A-HJ-NPR-Z]{1,2}"
    assert REVISION_PATTERN == r"[1-9][0-9]*"

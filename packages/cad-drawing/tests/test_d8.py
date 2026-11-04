"""D8: title block filled, per sheet and mapping (spec 11.5.3)."""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from cad_drawing.checks.d8 import MINIMUM_TITLE_FIELDS, TitleBlockMapping, check_d8
from cad_drawing.checks.outcome import RuleFailure
from cad_drawing.checks.snapshot import Sheet

if TYPE_CHECKING:
    from conftest import Builder

TEMPLATE = "Test-A3.slddrt"
FULL: Mapping[str, str] = {
    "part_number": "BR-001",
    "revision": "B",
    "material": "AISI 304",
    "finish": "Anodized",
    "general_tolerance": "ISO 2768-m",
    "scale": "1:1",
    "projection_symbol": "First angle",
    "units": "mm",
}
MAPPINGS = {TEMPLATE: TitleBlockMapping(TEMPLATE)}


def sheet(  # noqa: PLR0913
    b: "Builder",
    fields: Mapping[str, str] | None = FULL,
    *,
    fmt: str | None = TEMPLATE,
    table: Sequence[str] | None = None,
    key: str = "s_0",
    index: int = 0,
) -> Sheet:
    return b.sheet(
        sheet_format=fmt, title_block_fields=fields, revision_table=table, key=key, index=index
    )


def with_fields(**changes: str) -> dict[str, str]:
    return {**FULL, **changes}


def ids(failures: Sequence[RuleFailure]) -> list[tuple[str, str]]:
    return [(f.code, f.items[0].id) for f in failures]


def test_minimum_fields_constant() -> None:
    assert tuple(FULL) == MINIMUM_TITLE_FIELDS


def test_d8_all_filled_passes(b: "Builder") -> None:
    out = check_d8(b.snapshot([sheet(b)]), MAPPINGS)
    assert (out.status, out.failures, out.reasons) == ("pass", (), ())


def test_d8_empty_and_whitespace_fail(b: "Builder") -> None:
    fields = with_fields(material="", finish="  \t ")
    out = check_d8(b.snapshot([sheet(b, fields)]), MAPPINGS)
    assert out.status == "fail"
    assert ids(out.failures) == [
        ("title_field_unfilled", "finish"),
        ("title_field_unfilled", "material"),
    ]
    assert all(f.sheet == "s_0" and f.detail == () for f in out.failures)
    assert (out.failures[0].items[0].kind, out.failures[0].items[0].sheet) == ("title_field", "s_0")


def test_d8_absent_field_fails(b: "Builder") -> None:
    fields = {k: v for k, v in FULL.items() if k != "scale"}
    out = check_d8(b.snapshot([sheet(b, fields)]), MAPPINGS)
    assert out.status == "fail"
    assert ids(out.failures) == [("title_field_unfilled", "scale")]


def test_d8_unresolved_link_fails(b: "Builder") -> None:
    fields = with_fields(part_number='$PRPSHEET:"PartNo"', units='$prp:"u"')
    out = check_d8(b.snapshot([sheet(b, fields)]), MAPPINGS)
    assert ids(out.failures) == [
        ("title_field_unfilled", "part_number"),
        ("title_field_unfilled", "units"),
    ]


def test_d8_minimum_applies_even_if_mapping_omits(b: "Builder") -> None:
    fields = {k: v for k, v in FULL.items() if k != "finish"}
    mapping = {TEMPLATE: TitleBlockMapping(TEMPLATE, required=("part_number",))}
    out = check_d8(b.snapshot([sheet(b, fields)]), mapping)
    assert ids(out.failures) == [("title_field_unfilled", "finish")]


def test_d8_mapping_adds_required(b: "Builder") -> None:
    mapping = {TEMPLATE: TitleBlockMapping(TEMPLATE, required=("drawn_by",))}
    out = check_d8(b.snapshot([sheet(b)]), mapping)
    assert ids(out.failures) == [("title_field_unfilled", "drawn_by")]
    filled = check_d8(b.snapshot([sheet(b, with_fields(drawn_by="EE"))]), mapping)
    assert filled.status == "pass"


def test_d8_no_mapping_not_evaluated(b: "Builder") -> None:
    out = check_d8(b.snapshot([sheet(b)]), {})
    assert (out.status, out.reasons) == ("not_evaluated", ("title_block_mapping_missing",))
    none_format = check_d8(b.snapshot([sheet(b, fmt=None)]), MAPPINGS)
    assert (none_format.status, none_format.reasons) == (
        "not_evaluated",
        ("title_block_mapping_missing",),
    )


def test_d8_absent_fields_not_evaluated(b: "Builder") -> None:
    out = check_d8(b.snapshot([sheet(b, None)]), MAPPINGS)
    assert (out.status, out.reasons) == ("not_evaluated", ("title_block_data_missing",))


def test_d8_no_sheets_not_evaluated(b: "Builder") -> None:
    out = check_d8(b.snapshot([]), MAPPINGS)
    assert (out.status, out.reasons) == ("not_evaluated", ("title_block_data_missing",))


def test_d8_fail_on_one_sheet_wins_over_unmapped_other(b: "Builder") -> None:
    bad = sheet(b, with_fields(material=""))
    other = sheet(b, fmt="Other.slddrt", key="s_1", index=1)
    out = check_d8(b.snapshot([bad, other]), MAPPINGS)
    assert out.status == "fail"
    assert out.reasons == ("title_block_mapping_missing",)
    assert ids(out.failures) == [("title_field_unfilled", "material")]


def revision_mapping() -> dict[str, TitleBlockMapping]:
    return {TEMPLATE: TitleBlockMapping(TEMPLATE, revision_table=True)}


def test_d8_revision_table_latest_matches(b: "Builder") -> None:
    out = check_d8(b.snapshot([sheet(b, table=["A", "  B "])]), revision_mapping())
    assert out.status == "pass"


def test_d8_revision_table_mismatch(b: "Builder") -> None:
    out = check_d8(b.snapshot([sheet(b, table=["A", "C"])]), revision_mapping())
    assert out.status == "fail"
    (failure,) = out.failures
    assert failure.code == "revision_table_mismatch"
    assert failure.detail == (("latest_entry", "C"), ("revision", "B"))
    assert (failure.items[0].kind, failure.items[0].id) == ("title_field", "revision")


def test_d8_case_differs_is_mismatch(b: "Builder") -> None:
    out = check_d8(b.snapshot([sheet(b, table=["b"])]), revision_mapping())
    assert [f.code for f in out.failures] == ["revision_table_mismatch"]


def test_d8_revision_table_required_but_null(b: "Builder") -> None:
    out = check_d8(b.snapshot([sheet(b, table=None)]), revision_mapping())
    assert [f.code for f in out.failures] == ["revision_table_missing"]
    assert out.status == "fail"


def test_d8_revision_table_no_entries(b: "Builder") -> None:
    out = check_d8(b.snapshot([sheet(b, table=[])]), MAPPINGS)
    assert [f.code for f in out.failures] == ["revision_table_missing"]


def test_d8_table_present_though_not_required_is_checked(b: "Builder") -> None:
    out = check_d8(b.snapshot([sheet(b, table=["A"])]), MAPPINGS)
    assert [f.code for f in out.failures] == ["revision_table_mismatch"]


def test_d8_unfilled_revision_gives_no_mismatch(b: "Builder") -> None:
    out = check_d8(b.snapshot([sheet(b, with_fields(revision=" "), table=["A"])]), MAPPINGS)
    assert ids(out.failures) == [("title_field_unfilled", "revision")]


def test_d8_revision_compare_uses_nfc(b: "Builder") -> None:
    composed, decomposed = "é", "é"
    out = check_d8(
        b.snapshot([sheet(b, with_fields(revision=composed), table=[decomposed])]), MAPPINGS
    )
    assert out.failures == ()

"""The reference parsers accept and reject exactly what the common fixtures label."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from cad_ir.core.refs import (
    ReferenceSyntaxError,
    parse_document_ref,
    parse_geometry_ref,
    parse_intent_item_ref,
    parse_item_ref,
    parse_local_ref,
    parse_param_ref,
    parse_solidworks_dim_ref,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "schemas" / "common"

PARSERS: dict[str, Callable[[str], object]] = {
    "DocumentRef": parse_document_ref,
    "ItemRef": parse_item_ref,
    "LocalRef": parse_local_ref,
    "IntentItemRef": parse_intent_item_ref,
    "ParamRef": parse_param_ref,
    "GeometryRef": parse_geometry_ref,
    "SolidWorksDimRef": parse_solidworks_dim_ref,
}


def _cases(kind: str) -> list[object]:
    cases: list[object] = []
    for name in PARSERS:
        values: list[object] = json.loads((FIXTURES / kind / f"{name}.json").read_text("utf-8"))
        cases.extend(pytest.param(name, v, id=f"{name}[{i}]") for i, v in enumerate(values))
    return cases


@pytest.mark.parametrize(("name", "value"), _cases("valid"))
def test_valid_fixture_parses_and_round_trips(name: str, value: str) -> None:
    assert str(PARSERS[name](value)) == value


@pytest.mark.parametrize(("name", "value"), _cases("invalid"))
def test_invalid_fixture_is_a_syntax_error(name: str, value: object) -> None:
    if not isinstance(value, str):
        pytest.skip("not a string: the schema type rejects it, no parser input exists")
    with pytest.raises(ReferenceSyntaxError):
        PARSERS[name](value)

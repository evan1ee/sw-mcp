"""The evaluation set and its checker (no LLM calls)."""

import copy
from typing import Any

import pytest
from cad_application.authoring_eval.cases import CASES
from cad_application.authoring_eval.checker import score, score_all
from cad_application.authoring_eval.references import REFERENCE_ANSWERS

BY_ID = {case.case_id: case for case in CASES}
MIN_CASES = 10


def test_the_set_is_big_enough_and_has_refusals() -> None:
    assert len(CASES) >= MIN_CASES
    assert any(case.facts is None for case in CASES)
    assert len(BY_ID) == len(CASES)


def test_every_case_has_a_reference_answer() -> None:
    assert set(REFERENCE_ANSWERS) == set(BY_ID)


@pytest.mark.parametrize("case_id", sorted(BY_ID))
def test_reference_answer_passes(case_id: str) -> None:
    assert score(BY_ID[case_id], REFERENCE_ANSWERS[case_id]) == []


def test_score_all_reports_a_missing_answer() -> None:
    assert score_all({})["block"] == ["no answer given"]


def test_building_a_part_for_a_refusal_case_fails() -> None:
    assert score(BY_ID["refuse_fillet"], REFERENCE_ANSWERS["block"]) != []


def test_refusing_a_supported_request_fails() -> None:
    assert score(BY_ID["block"], None) == ["refused a request the MVP supports"]


def _copy(case_id: str) -> dict[str, Any]:
    answer = REFERENCE_ANSWERS[case_id]
    assert answer is not None
    return copy.deepcopy(answer)


def test_wrong_depth_fails() -> None:
    answer = _copy("block")
    answer["nodes"]["extrude_base"]["end_condition"]["depth"] = 12
    assert any("size" in p for p in score(BY_ID["block"], answer))


def test_wrong_hole_diameter_fails() -> None:
    answer = _copy("block_centre_hole")
    answer["nodes"]["sketch_holes"]["entities"]["c1"]["diameter"] = 6
    assert any("cylinder" in p for p in score(BY_ID["block_centre_hole"], answer))


def test_invalid_graph_reports_the_validator_issue() -> None:
    answer = _copy("block")
    del answer["nodes"]["sketch_base"]["entities"]["l4"]
    problems = score(BY_ID["block"], answer)
    assert problems
    assert any("closed loop" in p for p in problems)


def test_a_graph_that_does_not_parse_fails() -> None:
    assert score(BY_ID["block"], {"module": "part"})[0].startswith("graph does not parse")

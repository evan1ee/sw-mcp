"""Tests for feature_contracts and evaluate (ADR-064, Task 9b)."""

from typing import Any

from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.part_feature_graph.model import (
    Circle,
    EndCondition,
    Line,
    PartGraph,
    SketchNode,
    SolidNode,
)
from cad_verification.api import (
    evaluate,
    feature_contracts,
)

EVIDENCE_SCHEMA_ID = "https://sw-mcp.invalid/schemas/execution-evidence/v0.json"


def _sample_graph() -> PartGraph:
    return PartGraph(
        id="bracket",
        schema_version="0.1",
        units="mm",
        origin="corner",
        nodes={
            "sketch_base": SketchNode(
                plane="plane:front",
                entities={
                    "l1": Line(start=(0.0, 0.0), end=(100.0, 0.0)),
                    "l2": Line(start=(100.0, 0.0), end=(100.0, 50.0)),
                    "l3": Line(start=(100.0, 50.0), end=(0.0, 50.0)),
                    "l4": Line(start=(0.0, 50.0), end=(0.0, 0.0)),
                },
            ),
            "extrude_base": SolidNode(
                type="extrude",
                profile="sketch_base",
                end_condition=EndCondition(type="blind", depth=10.0),
                dependencies=("sketch_base",),
            ),
            "sketch_hole": SketchNode(
                plane="plane:front",
                entities={
                    "c1": Circle(center=(50.0, 25.0), diameter=10.0),
                },
                dependencies=("extrude_base",),
            ),
            "cut_hole": SolidNode(
                type="cut_extrude",
                profile="sketch_hole",
                end_condition=EndCondition(type="through_all"),
                dependencies=("sketch_hole",),
            ),
        },
    )


def test_feature_contracts_derives_contracts() -> None:
    graph = _sample_graph()
    contracts = feature_contracts(graph)
    expected_nodes = 4
    assert len(contracts) == expected_nodes
    by_node = {c.node: c for c in contracts}

    # sketch_base
    sb = by_node["sketch_base"]
    assert sb.level == "exact"
    assert sb.hash.startswith("sha256:")
    check_names = [chk.name for chk in sb.checks]
    assert check_names == ["status_ok", "not_suppressed", "type_matches", "entity_count"]
    sb_dict = sb.to_dict()
    assert (
        validate_against_schema(sb_dict, f"{EVIDENCE_SCHEMA_ID}#/$defs/VerificationContract") == ()
    )

    # extrude_base
    eb = by_node["extrude_base"]
    assert eb.level == "exact"
    eb_names = [chk.name for chk in eb.checks]
    assert eb_names == ["status_ok", "not_suppressed", "type_matches"]
    eb_dict = eb.to_dict()
    assert (
        validate_against_schema(eb_dict, f"{EVIDENCE_SCHEMA_ID}#/$defs/VerificationContract") == ()
    )


def test_evaluate_none_observation() -> None:
    graph = _sample_graph()
    contract = feature_contracts(graph)[0]
    results = evaluate(contract, None)
    assert len(results) == len(contract.checks)
    for res in results:
        assert res.status == "not_evaluated"
        assert res.reason == "missing_data"
        assert (
            validate_against_schema(
                res.to_dict(), f"{EVIDENCE_SCHEMA_ID}#/$defs/PostconditionResult"
            )
            == ()
        )


def test_evaluate_healthy_observation() -> None:
    graph = _sample_graph()
    contract = feature_contracts(graph)[0]  # sketch_base, 4 entities
    obs: dict[str, Any] = {
        "type": "sketch",
        "error_code": 0,
        "is_warning": False,
        "suppressed": False,
        "entity_count": 4,
    }
    results = evaluate(contract, obs)
    assert all(r.status == "passed" for r in results)
    for res in results:
        assert (
            validate_against_schema(
                res.to_dict(), f"{EVIDENCE_SCHEMA_ID}#/$defs/PostconditionResult"
            )
            == ()
        )


def test_evaluate_warning_status() -> None:
    graph = _sample_graph()
    contract = feature_contracts(graph)[1]  # extrude_base
    obs: dict[str, Any] = {
        "type": "extrude",
        "error_code": 0,
        "is_warning": True,
        "suppressed": False,
    }
    results = evaluate(contract, obs)
    status_ok = next(r for r in results if r.name == "status_ok")
    assert status_ok.status == "warning"
    for res in results:
        assert (
            validate_against_schema(
                res.to_dict(), f"{EVIDENCE_SCHEMA_ID}#/$defs/PostconditionResult"
            )
            == ()
        )


def test_evaluate_error_code_and_suppressed() -> None:
    graph = _sample_graph()
    contract = feature_contracts(graph)[1]
    obs: dict[str, Any] = {
        "type": "extrude",
        "error_code": 2,
        "is_warning": False,
        "suppressed": True,
    }
    results = evaluate(contract, obs)
    status_ok = next(r for r in results if r.name == "status_ok")
    assert status_ok.status == "failed"
    not_supp = next(r for r in results if r.name == "not_suppressed")
    assert not_supp.status == "failed"


def test_evaluate_type_and_entity_count_mismatch() -> None:
    graph = _sample_graph()
    contract = feature_contracts(graph)[0]  # sketch_base
    obs: dict[str, Any] = {
        "type": "wrong_type",
        "error_code": 0,
        "is_warning": False,
        "suppressed": False,
        "entity_count": 2,  # expected 4
    }
    results = evaluate(contract, obs)
    tm = next(r for r in results if r.name == "type_matches")
    assert tm.status == "failed"
    ec = next(r for r in results if r.name == "entity_count")
    assert ec.status == "failed"

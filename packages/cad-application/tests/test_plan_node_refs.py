"""A plan names nodes; the core swaps in the feature ids the add-in returned (ADR-070)."""

from cad_application.jobs.plan_job import resolve_node_refs
from cad_ir.core.json_types import JsonValue

IDS = {"sketch_base": "f10", "extrude_base": "f11"}


def _face(feature: str) -> dict[str, JsonValue]:
    return {"feature": feature, "role": "end_face", "normal": [0.0, 0.0, 1.0]}


def test_a_feature_profile_becomes_its_feature_id() -> None:
    params: dict[str, JsonValue] = {"node_id": "extrude_base", "profile": "sketch_base"}
    assert resolve_node_refs("feature.create", params, IDS)["profile"] == "f10"


def test_a_sketch_face_feature_becomes_the_extrude_feature_id() -> None:
    params: dict[str, JsonValue] = {"node_id": "sketch_hole", "face": _face("extrude_base")}
    face = resolve_node_refs("sketch.create", params, IDS)["face"]
    assert isinstance(face, dict)
    assert face["feature"] == "f11"
    assert face["normal"] == [0.0, 0.0, 1.0]


def test_the_input_is_not_changed() -> None:
    face = _face("extrude_base")
    params: dict[str, JsonValue] = {"face": face}
    resolve_node_refs("sketch.create", params, IDS)
    assert face["feature"] == "extrude_base"


def test_an_unknown_node_is_left_alone() -> None:
    params: dict[str, JsonValue] = {"face": _face("missing")}
    resolved = resolve_node_refs("sketch.create", params, IDS)
    assert resolved["face"] == _face("missing")


def test_other_operations_pass_through() -> None:
    params: dict[str, JsonValue] = {"profile": "sketch_base"}
    assert resolve_node_refs("part.measure", params, IDS) == params


def test_linear_pattern_seeds_and_directions_resolved() -> None:
    ids = {"cut1": "f20", "cut2": "f21", "ref_feat": "f5"}
    params: dict[str, JsonValue] = {
        "node_id": "pat1",
        "type": "linear_pattern",
        "seeds": ["cut1", "cut2", "cut_unknown"],
        "direction_1": {"direction": "ref_feat", "spacing": 10.0, "count": 3},
        "direction_2": {"direction": "plane:right", "spacing": 5.0, "count": 2},
    }
    resolved = resolve_node_refs("feature.create", params, ids)
    assert resolved["seeds"] == ["f20", "f21", "cut_unknown"]
    assert resolved["direction_1"] == {"direction": "f5", "spacing": 10.0, "count": 3}
    assert resolved["direction_2"] == {"direction": "plane:right", "spacing": 5.0, "count": 2}

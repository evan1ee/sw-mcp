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

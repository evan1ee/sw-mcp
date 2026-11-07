"""Compiling a sketch on a cap face into Execution Plan operations (ADR-070)."""

from typing import Any

import pytest
from cad_compiler.api import CompileContext, CompileInput, compile_bundle
from cad_compiler.profile import CapabilityProfile
from cad_ir.bundle.manifest import BundleManifest
from cad_ir.core.refs import parse_document_ref
from cad_ir.generated.ipc import HelloResult, OperationInfo, SolidWorksInfo

HOLE_DEPTH = 4


def _graph(plane: str, base_plane: str = "plane:front") -> dict[str, Any]:
    box = [(-20, -15), (20, -15), (20, 15), (-20, 15)]
    return {
        "module": "part",
        "id": "face_hole",
        "schema_version": "0.1",
        "units": "mm",
        "origin": "built",
        "nodes": {
            "sketch_base": {
                "type": "sketch",
                "plane": base_plane,
                "entities": {
                    f"l{i + 1}": {
                        "type": "line",
                        "start": list(box[i]),
                        "end": list(box[(i + 1) % 4]),
                    }
                    for i in range(4)
                },
            },
            "extrude_base": {
                "type": "extrude",
                "dependencies": ["sketch_base"],
                "profile": "sketch_base",
                "end_condition": {"type": "blind", "depth": 10},
            },
            "sketch_hole": {
                "type": "sketch",
                "plane": plane,
                "dependencies": ["extrude_base"],
                "entities": {"c1": {"type": "circle", "center": [0, 0], "diameter": 5}},
            },
            "cut_hole": {
                "type": "cut_extrude",
                "dependencies": ["sketch_hole", "extrude_base"],
                "profile": "sketch_hole",
                "end_condition": {"type": "blind", "depth": HOLE_DEPTH},
            },
        },
    }


def _compile(raw: dict[str, Any]) -> Any:
    ref = "part:face_hole@1"
    source = CompileInput(
        manifest=BundleManifest("1.0", (parse_document_ref(ref),)),
        documents={ref: raw},
    )
    session = HelloResult(
        protocol="0.1",
        addin_version="0.1.0",
        solidworks=SolidWorksInfo(version="2025", service_pack="sp1", ui_language="en-US"),
        capabilities=(),
        operations=tuple(
            OperationInfo(op=op, schema_version="0.1")
            for op in ("part.create", "sketch.create", "feature.create")
        ),
        licensed_modules=(),
        warnings=(),
    )
    return compile_bundle(
        source, CompileContext("0.1.0", CapabilityProfile.from_session(session), {})
    )


def _ops(result: Any) -> dict[str, Any]:
    assert result.plan is not None, result.diagnostics
    return result.plan["operations"]


def test_end_face_sketch_carries_the_face_and_its_frame() -> None:
    sketch = _ops(_compile(_graph("extrude_base.end_face")))["op_4"]
    assert sketch["op"] == "sketch.create"
    assert "plane" not in sketch["params"]
    assert sketch["params"]["face"] == {
        "feature": "extrude_base",
        "role": "end_face",
        "normal": [0.0, 0.0, 1.0],
        "offset_mm": 10.0,
        "x_axis": [1.0, 0.0, 0.0],
        "y_axis": [0.0, 1.0, 0.0],
    }
    assert sketch["depends_on"] == ["op_3"]


def test_start_face_sketch_has_the_mirrored_frame() -> None:
    face = _ops(_compile(_graph("extrude_base.start_face")))["op_4"]["params"]["face"]
    assert face["normal"] == [0.0, 0.0, -1.0]
    assert face["offset_mm"] == 0.0
    assert face["x_axis"] == [-1.0, 0.0, 0.0]


def test_a_cut_from_a_face_is_marked_so_the_add_in_picks_the_direction() -> None:
    cut = _ops(_compile(_graph("extrude_base.end_face")))["op_5"]
    assert cut["params"]["host"] == "face"


def test_a_cut_from_an_origin_plane_is_not_marked() -> None:
    cut = _ops(_compile(_graph("plane:front")))["op_5"]
    assert "host" not in cut["params"]
    assert "face" not in _ops(_compile(_graph("plane:front")))["op_4"]["params"]


def test_an_unsupported_host_still_fails_to_compile() -> None:
    result = _compile(_graph("geo:abc"))
    assert result.plan is None


@pytest.mark.parametrize(
    ("base_plane", "role", "exp_normal", "exp_offset", "exp_axes"),
    [
        (
            "plane:front",
            "end_face",
            [0.0, 0.0, 1.0],
            10.0,
            ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]),
        ),
        (
            "plane:front",
            "start_face",
            [0.0, 0.0, -1.0],
            0.0,
            ([-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]),
        ),
        (
            "plane:top",
            "end_face",
            [0.0, 1.0, 0.0],
            10.0,
            ([1.0, 0.0, 0.0], [0.0, 0.0, -1.0]),
        ),
        (
            "plane:top",
            "start_face",
            [0.0, -1.0, 0.0],
            0.0,
            ([-1.0, 0.0, 0.0], [0.0, 0.0, -1.0]),
        ),
        (
            "plane:right",
            "end_face",
            [1.0, 0.0, 0.0],
            10.0,
            ([0.0, 0.0, -1.0], [0.0, 1.0, 0.0]),
        ),
        (
            "plane:right",
            "start_face",
            [-1.0, 0.0, 0.0],
            0.0,
            ([0.0, 0.0, 1.0], [0.0, 1.0, 0.0]),
        ),
    ],
)
def test_lowering_all_six_datum_and_cap_combinations(
    base_plane: str,
    role: str,
    exp_normal: list[float],
    exp_offset: float,
    exp_axes: tuple[list[float], list[float]],
) -> None:
    ops = _ops(_compile(_graph(f"extrude_base.{role}", base_plane=base_plane)))
    assert ops["op_4"]["params"]["face"] == {
        "feature": "extrude_base",
        "role": role,
        "normal": exp_normal,
        "offset_mm": exp_offset,
        "x_axis": exp_axes[0],
        "y_axis": exp_axes[1],
    }
    assert ops["op_5"]["params"]["host"] == "face"

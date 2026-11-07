"""Parameterized tests for cap-face coordinate frames and 3D projection across all 6 datum/caps."""

import pytest
from cad_geometry.signatures import cap_face_frame, project_cap_face_point

DEPTH = 10.0


@pytest.mark.parametrize(
    ("plane", "role", "exp_axes", "exp_offset", "exp_pts"),
    [
        (
            "plane:front",
            "end_face",
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            DEPTH,
            ((10.0, 5.0, 10.0), (10.0, 5.0, 6.0)),
        ),
        (
            "plane:front",
            "start_face",
            ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)),
            0.0,
            ((-10.0, 5.0, 0.0), (-10.0, 5.0, 4.0)),
        ),
        (
            "plane:top",
            "end_face",
            ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
            DEPTH,
            ((10.0, 10.0, -5.0), (10.0, 6.0, -5.0)),
        ),
        (
            "plane:top",
            "start_face",
            ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
            0.0,
            ((10.0, 0.0, 5.0), (10.0, 4.0, 5.0)),
        ),
        (
            "plane:right",
            "end_face",
            ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
            DEPTH,
            ((10.0, 5.0, -10.0), (6.0, 5.0, -10.0)),
        ),
        (
            "plane:right",
            "start_face",
            ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)),
            0.0,
            ((0.0, 5.0, 10.0), (4.0, 5.0, 10.0)),
        ),
    ],
)
def test_cap_face_frame_and_projection_across_all_six_combinations(
    plane: str,
    role: str,
    exp_axes: tuple[
        tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]
    ],
    exp_offset: float,
    exp_pts: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> None:
    frame = cap_face_frame(plane, DEPTH, role)
    assert (frame.x_axis, frame.y_axis, frame.normal) == exp_axes
    assert frame.offset_mm == exp_offset
    assert project_cap_face_point(plane, DEPTH, role, (10.0, 5.0)) == exp_pts[0]
    assert project_cap_face_point(plane, DEPTH, role, (10.0, 5.0), into_body_mm=4.0) == exp_pts[1]

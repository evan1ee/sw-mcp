"""Planes and coordinate mappings for standard SOLIDWORKS sketch planes (spec 5.7.4)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlaneAxes:
    """Axes and transform for a standard sketch plane (spec 5.7.4)."""

    plane: str
    x_axis: tuple[float, float, float]
    y_axis: tuple[float, float, float]
    normal: tuple[float, float, float]

    def to_model(self, x: float, y: float, depth: float = 0.0) -> tuple[float, float, float]:
        """Map 2D sketch coordinates (x, y) and depth along normal to model (X, Y, Z)."""
        return (
            x * self.x_axis[0] + y * self.y_axis[0] + depth * self.normal[0],
            x * self.x_axis[1] + y * self.y_axis[1] + depth * self.normal[1],
            x * self.x_axis[2] + y * self.y_axis[2] + depth * self.normal[2],
        )


_PLANES: dict[str, PlaneAxes] = {
    "plane:front": PlaneAxes(
        plane="plane:front",
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 1.0, 0.0),
        normal=(0.0, 0.0, 1.0),
    ),
    "plane:top": PlaneAxes(
        plane="plane:top",
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 0.0, -1.0),
        normal=(0.0, 1.0, 0.0),
    ),
    "plane:right": PlaneAxes(
        plane="plane:right",
        x_axis=(0.0, 0.0, -1.0),
        y_axis=(0.0, 1.0, 0.0),
        normal=(1.0, 0.0, 0.0),
    ),
}


def plane_axes(plane: str) -> PlaneAxes:
    """Return the PlaneAxes mapping for a standard plane role (spec 5.7.4)."""
    try:
        return _PLANES[plane]
    except KeyError:
        raise ValueError(f"unknown or unsupported plane: {plane!r}") from None

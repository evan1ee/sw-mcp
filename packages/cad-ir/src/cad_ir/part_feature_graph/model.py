"""Dataclass models for Part Feature Graph IR (spec 5.7)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

PART_SCHEMA_ID: Final[str] = "https://sw-mcp.invalid/schemas/part-feature-graph/v0.json"


@dataclass(frozen=True, slots=True)
class Line:
    """2D line segment in sketch coordinates (spec 5.7.4, SK-ENT-001..003)."""

    start: tuple[float, float]
    end: tuple[float, float]
    type: str = "line"
    construction: bool = False

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "type": self.type,
            "start": list(self.start),
            "end": list(self.end),
        }
        if self.construction:
            res["construction"] = True
        return res


@dataclass(frozen=True, slots=True)
class Circle:
    """2D circle in sketch coordinates (spec 5.7.4)."""

    center: tuple[float, float]
    diameter: float
    type: str = "circle"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "center": list(self.center),
            "diameter": self.diameter,
        }


@dataclass(frozen=True, slots=True)
class Arc:
    """2D circular arc in sketch coordinates (spec 5.7.4, 22.4.1, ADR-071)."""

    center: tuple[float, float]
    start: tuple[float, float]
    end: tuple[float, float]
    direction: str  # "ccw" | "cw"
    type: str = "arc"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "center": list(self.center),
            "start": list(self.start),
            "end": list(self.end),
            "direction": self.direction,
        }


@dataclass(frozen=True, slots=True)
class CornerRectangle:
    """2D axis-aligned corner rectangle in sketch coordinates (spec 5.7.4, 22.4.1, ADR-072)."""

    corner1: tuple[float, float]
    corner2: tuple[float, float]
    type: str = "corner_rectangle"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "corner1": list(self.corner1),
            "corner2": list(self.corner2),
        }


@dataclass(frozen=True, slots=True)
class CenterRectangle:
    """2D center rectangle in sketch coordinates (spec 5.7.4, 22.4.1, ADR-072)."""

    center: tuple[float, float]
    width: float
    height: float
    type: str = "center_rectangle"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "center": list(self.center),
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True, slots=True)
class StraightSlot:
    """2D straight slot in sketch coordinates (spec 5.7.4, 22.4.1, ADR-073)."""

    start_point: tuple[float, float]
    end_point: tuple[float, float]
    width: float
    type: str = "straight_slot"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "start_point": list(self.start_point),
            "end_point": list(self.end_point),
            "width": self.width,
        }


SketchEntity = Line | Circle | Arc | CornerRectangle | CenterRectangle | StraightSlot


@dataclass(frozen=True, slots=True)
class SketchNode:
    """Sketch feature node (spec 5.7.4)."""

    plane: str
    entities: Mapping[str, SketchEntity]
    dependencies: tuple[str, ...] = ()
    display_name: str | None = None
    realizes: tuple[str, ...] = ()
    type: str = "sketch"

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "type": self.type,
            "plane": self.plane,
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
        }
        if self.dependencies:
            res["dependencies"] = list(self.dependencies)
        if self.display_name is not None:
            res["display_name"] = self.display_name
        if self.realizes:
            res["realizes"] = list(self.realizes)
        return res


@dataclass(frozen=True, slots=True)
class EndCondition:
    """End condition specification for extrudes and cuts (spec 5.7.3)."""

    type: str
    depth: float | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {"type": self.type}
        if self.depth is not None:
            res["depth"] = self.depth
        return res


@dataclass(frozen=True, slots=True)
class SolidNode:
    """Solid feature node (extrude, cut_extrude) (spec 5.7)."""

    type: str
    profile: str
    end_condition: EndCondition
    dependencies: tuple[str, ...] = ()
    display_name: str | None = None
    realizes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "type": self.type,
            "profile": self.profile,
            "end_condition": self.end_condition.to_dict(),
        }
        if self.dependencies:
            res["dependencies"] = list(self.dependencies)
        if self.display_name is not None:
            res["display_name"] = self.display_name
        if self.realizes:
            res["realizes"] = list(self.realizes)
        return res


@dataclass(frozen=True, slots=True)
class LinearPatternDirection:
    """Direction specification for linear patterns (spec 5.7.3, ADR-074)."""

    direction: str
    spacing: float
    count: int
    reverse: bool = False

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "direction": self.direction,
            "spacing": self.spacing,
            "count": self.count,
        }
        if self.reverse:
            res["reverse"] = True
        return res


@dataclass(frozen=True, slots=True)
class LinearPattern:
    """Linear pattern feature node (spec 5.7.3, ADR-074)."""

    seeds: tuple[str, ...]
    direction_1: LinearPatternDirection
    direction_2: LinearPatternDirection | None = None
    dependencies: tuple[str, ...] = ()
    display_name: str | None = None
    realizes: tuple[str, ...] = ()
    type: str = "linear_pattern"

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "type": self.type,
            "seeds": list(self.seeds),
            "direction_1": self.direction_1.to_dict(),
        }
        if self.direction_2 is not None:
            res["direction_2"] = self.direction_2.to_dict()
        if self.dependencies:
            res["dependencies"] = list(self.dependencies)
        if self.display_name is not None:
            res["display_name"] = self.display_name
        if self.realizes:
            res["realizes"] = list(self.realizes)
        return res


@dataclass(frozen=True, slots=True)
class CircularPattern:
    """Circular pattern feature node (spec 5.7.3, ADR-075)."""

    seeds: tuple[str, ...]
    axis: str
    count: int
    spacing: float
    equal_spacing: bool = True
    reverse: bool = False
    dependencies: tuple[str, ...] = ()
    display_name: str | None = None
    realizes: tuple[str, ...] = ()
    type: str = "circular_pattern"

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "type": self.type,
            "seeds": list(self.seeds),
            "axis": self.axis,
            "count": self.count,
            "spacing": self.spacing,
            "equal_spacing": self.equal_spacing,
        }
        if self.reverse:
            res["reverse"] = True
        if self.dependencies:
            res["dependencies"] = list(self.dependencies)
        if self.display_name is not None:
            res["display_name"] = self.display_name
        if self.realizes:
            res["realizes"] = list(self.realizes)
        return res


@dataclass(frozen=True, slots=True)
class Mirror:
    """Mirror feature node (spec 5.7.3, ADR-076)."""

    seeds: tuple[str, ...]
    plane: str
    merge: bool = True
    dependencies: tuple[str, ...] = ()
    display_name: str | None = None
    realizes: tuple[str, ...] = ()
    type: str = "mirror"

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "type": self.type,
            "seeds": list(self.seeds),
            "plane": self.plane,
            "merge": self.merge,
        }
        if self.dependencies:
            res["dependencies"] = list(self.dependencies)
        if self.display_name is not None:
            res["display_name"] = self.display_name
        if self.realizes:
            res["realizes"] = list(self.realizes)
        return res


@dataclass(frozen=True, slots=True)
class Revolve:
    """Revolve boss/base feature node (spec 5.7.3, 22.5.2, ADR-077)."""

    profile: str
    axis: str | None = None
    angle: float = 360.0
    mid_plane: bool = False
    reverse: bool = False
    thin: Mapping[str, Any] | None = None
    merge_result: bool = True
    dependencies: tuple[str, ...] = ()
    display_name: str | None = None
    realizes: tuple[str, ...] = ()
    type: str = "revolve"

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "type": self.type,
            "profile": self.profile,
            "angle": self.angle,
        }
        if self.axis is not None:
            res["axis"] = self.axis
        if self.mid_plane:
            res["mid_plane"] = True
        if self.reverse:
            res["reverse"] = True
        if self.thin is not None:
            res["thin"] = dict(self.thin)
        if not self.merge_result:
            res["merge_result"] = False
        if self.dependencies:
            res["dependencies"] = list(self.dependencies)
        if self.display_name is not None:
            res["display_name"] = self.display_name
        if self.realizes:
            res["realizes"] = list(self.realizes)
        return res


@dataclass(frozen=True, slots=True)
class CutRevolve:
    """Cut revolve feature node (spec 5.7.3, 22.5.2, ADR-077)."""

    profile: str
    axis: str | None = None
    angle: float = 360.0
    mid_plane: bool = False
    reverse: bool = False
    thin: Mapping[str, Any] | None = None
    dependencies: tuple[str, ...] = ()
    display_name: str | None = None
    realizes: tuple[str, ...] = ()
    type: str = "cut_revolve"

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "type": self.type,
            "profile": self.profile,
            "angle": self.angle,
        }
        if self.axis is not None:
            res["axis"] = self.axis
        if self.mid_plane:
            res["mid_plane"] = True
        if self.reverse:
            res["reverse"] = True
        if self.thin is not None:
            res["thin"] = dict(self.thin)
        if self.dependencies:
            res["dependencies"] = list(self.dependencies)
        if self.display_name is not None:
            res["display_name"] = self.display_name
        if self.realizes:
            res["realizes"] = list(self.realizes)
        return res


PartNode = SketchNode | SolidNode | LinearPattern | CircularPattern | Mirror | Revolve | CutRevolve


@dataclass(frozen=True, slots=True)
class PartGraph:
    """Part Feature Graph IR document (spec 5.7)."""

    id: str
    schema_version: str
    units: str
    origin: str
    nodes: Mapping[str, PartNode]
    module: str = "part"

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "id": self.id,
            "schema_version": self.schema_version,
            "units": self.units,
            "origin": self.origin,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
        }

"""Dataclass models for Part Feature Graph IR (spec 5.7)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

PART_SCHEMA_ID: Final[str] = "https://sw-mcp.invalid/schemas/part-feature-graph/v0.json"


@dataclass(frozen=True, slots=True)
class Line:
    """2D line segment in sketch coordinates (spec 5.7.4)."""

    start: tuple[float, float]
    end: tuple[float, float]
    type: str = "line"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "start": list(self.start),
            "end": list(self.end),
        }


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
class SketchNode:
    """Sketch feature node (spec 5.7.4)."""

    plane: str
    entities: Mapping[str, Line | Circle]
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
class PartGraph:
    """Part Feature Graph IR document (spec 5.7)."""

    id: str
    schema_version: str
    units: str
    origin: str
    nodes: Mapping[str, SketchNode | SolidNode]
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

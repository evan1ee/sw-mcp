"""Dataclass models for Drawing Intent IR (spec 11.10)."""

from dataclasses import dataclass, field
from typing import Any, Final

INTENT_SCHEMA_ID: Final[str] = "https://sw-mcp.invalid/schemas/drawing-intent/v0.json"


def _empty_exceptions() -> dict[str, dict[str, Any]]:
    return {}


def _empty_datums() -> dict[str, "DatumFeature"]:
    return {}


def _empty_critical_dims() -> dict[str, "CriticalDimension"]:
    return {}


def _empty_gdt() -> dict[str, "GDTCallout"]:
    return {}


def _empty_overrides() -> dict[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class IntentContext:
    """Context overrides when no Design Intent IR is attached (spec 11.10)."""

    process: str | None = None
    material: str | None = None
    treatment: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {}
        if self.process is not None:
            res["process"] = self.process
        if self.material is not None:
            res["material"] = self.material
        if self.treatment is not None:
            res["treatment"] = self.treatment
        if self.metadata is not None:
            res["metadata"] = self.metadata
        return res


@dataclass(frozen=True, slots=True)
class SurfaceFinish:
    """Surface finish specification (spec 11.10)."""

    general: dict[str, float] | None = None
    exceptions: dict[str, dict[str, Any]] = field(default_factory=_empty_exceptions)

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {}
        if self.general is not None:
            res["general"] = self.general
        if self.exceptions:
            res["exceptions"] = self.exceptions
        return res


@dataclass(frozen=True, slots=True)
class DatumFeature:
    """Datum feature definition (spec 11.10)."""

    ref: str
    applies_to: str  # "surface" or "feature_of_size"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "applies_to": self.applies_to,
        }


@dataclass(frozen=True, slots=True)
class CriticalDimension:
    """Critical dimension definition (spec 11.10)."""

    param: str | None = None
    ref: str | None = None
    tolerance: Any = None
    requirement: str | None = None
    inspect: bool = False

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {}
        if self.param is not None:
            res["param"] = self.param
        if self.ref is not None:
            res["ref"] = self.ref
        if self.tolerance is not None:
            res["tolerance"] = self.tolerance
        if self.requirement is not None:
            res["requirement"] = self.requirement
        if self.inspect:
            res["inspect"] = self.inspect
        return res


@dataclass(frozen=True, slots=True)
class GDTCallout:
    """GD&T callout definition (spec 11.10)."""

    characteristic: str
    tolerance: float
    target: str
    applies_to: str  # "surface" or "feature_of_size"
    datums: tuple[str, ...] = ()
    requirement: str | None = None
    inspect: bool = False

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "characteristic": self.characteristic,
            "tolerance": self.tolerance,
            "target": self.target,
            "applies_to": self.applies_to,
        }
        if self.datums:
            res["datums"] = list(self.datums)
        if self.requirement is not None:
            res["requirement"] = self.requirement
        if self.inspect:
            res["inspect"] = self.inspect
        return res


@dataclass(frozen=True, slots=True)
class DrawingIntent:
    """Root Drawing Intent IR document (spec 11.10)."""

    id: str
    schema_version: str
    units: str
    documents: str
    revision: int | None = None
    design_intent: str | None = None
    configuration: str = "Default"
    general_tolerance: str = "ISO 2768-m"
    context: IntentContext | None = None
    surface_finish: SurfaceFinish | None = None
    datums: dict[str, DatumFeature] = field(default_factory=_empty_datums)
    critical_dimensions: dict[str, CriticalDimension] = field(default_factory=_empty_critical_dims)
    gdt: dict[str, GDTCallout] = field(default_factory=_empty_gdt)
    scheme_overrides: dict[str, Any] = field(default_factory=_empty_overrides)

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "module": "drawing_intent",
            "id": self.id,
            "schema_version": self.schema_version,
            "units": self.units,
            "documents": self.documents,
        }
        if self.revision is not None:
            res["revision"] = self.revision
        if self.design_intent is not None:
            res["design_intent"] = self.design_intent
        if self.configuration != "Default":
            res["configuration"] = self.configuration
        if self.general_tolerance != "ISO 2768-m":
            res["general_tolerance"] = self.general_tolerance
        if self.context is not None:
            res["context"] = self.context.to_dict()
        if self.surface_finish is not None:
            res["surface_finish"] = self.surface_finish.to_dict()
        if self.datums:
            res["datums"] = {k: v.to_dict() for k, v in self.datums.items()}
        if self.critical_dimensions:
            res["critical_dimensions"] = {
                k: v.to_dict() for k, v in self.critical_dimensions.items()
            }
        if self.gdt:
            res["gdt"] = {k: v.to_dict() for k, v in self.gdt.items()}
        if self.scheme_overrides:
            res["scheme_overrides"] = self.scheme_overrides
        return res

"""Dataclass models for Resolved Dimension Scheme (spec 11.10.1)."""

from dataclasses import dataclass, field
from typing import Any, Final

RESOLVED_SCHEME_SCHEMA_ID: Final[str] = "https://sw-mcp.invalid/schemas/resolved-scheme/v0.json"


def _empty_entries() -> dict[str, "SchemeEntry"]:
    return {}


@dataclass(frozen=True, slots=True)
class SchemeEntry:
    """Individual dimension scheme entry (spec 11.10.1)."""

    kind: str
    source: str  # "model_item", "dimxpert", "reference", "authored"
    status: str  # "shown", "hidden", "omitted"
    origin: str  # "authored", "derived"
    covers: tuple[str, ...] = ()
    measures: dict[str, Any] | None = None
    tolerance: Any = None
    reason: str | None = None
    auxiliary: bool = False

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "kind": self.kind,
            "source": self.source,
            "status": self.status,
            "origin": self.origin,
        }
        if self.covers:
            res["covers"] = list(self.covers)
        if self.measures is not None:
            res["measures"] = self.measures
        if self.tolerance is not None:
            res["tolerance"] = self.tolerance
        if self.reason is not None:
            res["reason"] = self.reason
        if self.auxiliary:
            res["auxiliary"] = self.auxiliary
        return res


@dataclass(frozen=True, slots=True)
class ResolvedScheme:
    """Root Resolved Dimension Scheme document (spec 11.10.1)."""

    schema_version: str
    drawing_intent: str
    entries: dict[str, SchemeEntry] = field(default_factory=_empty_entries)
    part_revision: int | None = None
    pipeline_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "schema_version": self.schema_version,
            "drawing_intent": self.drawing_intent,
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
        }
        if self.part_revision is not None:
            res["part_revision"] = self.part_revision
        if self.pipeline_version is not None:
            res["pipeline_version"] = self.pipeline_version
        return res

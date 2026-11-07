"""Feature registry for CAD features (spec 5.3, 5.7)."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


@dataclass(frozen=True, slots=True)
class FeatureTypeInfo:
    """Metadata about a registered CAD feature type (spec 5.3)."""

    name: str
    is_solid: bool
    modes: frozenset[str] = frozenset({"create", "read"})


_REGISTRY: Final[Mapping[str, FeatureTypeInfo]] = MappingProxyType(
    {
        "sketch": FeatureTypeInfo(name="sketch", is_solid=False),
        "extrude": FeatureTypeInfo(name="extrude", is_solid=True),
        "cut_extrude": FeatureTypeInfo(name="cut_extrude", is_solid=True),
        "linear_pattern": FeatureTypeInfo(name="linear_pattern", is_solid=True),
    }
)


def get_feature_info(feature_type: str) -> FeatureTypeInfo | None:
    """Return registered feature type metadata, or None if unknown."""
    return _REGISTRY.get(feature_type)


def is_registered_feature(feature_type: str) -> bool:
    """Check if a feature type is known in the registry."""
    return feature_type in _REGISTRY


def is_solid_feature(feature_type: str) -> bool:
    """Check if a feature type represents a solid CAD body feature."""
    info = _REGISTRY.get(feature_type)
    return info.is_solid if info is not None else False

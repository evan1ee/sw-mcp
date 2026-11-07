"""Backend Capability Profile (spec 6.6)."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Self, cast

from cad_ir.core.canonical import content_hash
from cad_ir.core.json_types import JsonValue
from cad_ir.generated.ipc import HelloResult

DEFAULT_COVERAGE: Final[Mapping[str, str]] = MappingProxyType(
    {
        "sketch": "create",
        "extrude": "create",
        "cut_extrude": "create",
        "linear_pattern": "create",
        "circular_pattern": "create",
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityProfile:
    """Snapshot of what the connected CAD backend and compiler support (spec 6.6)."""

    session: HelloResult
    operations: frozenset[str]
    coverage: Mapping[str, str]
    hash: str

    @classmethod
    def from_session(
        cls,
        session: HelloResult,
        *,
        coverage: Mapping[str, str] = DEFAULT_COVERAGE,
    ) -> Self:
        """Construct a CapabilityProfile from a backend session and compute its content hash."""
        ops = frozenset(op.op for op in session.operations)
        sorted_ops = sorted(session.operations, key=lambda op: op.op)
        canonical_dict: dict[str, Any] = {
            "addin_version": session.addin_version,
            "backend": {
                "service_pack": session.solidworks.service_pack,
                "ui_language": session.solidworks.ui_language,
                "version": session.solidworks.version,
            },
            "capabilities": sorted(session.capabilities),
            "coverage": dict(sorted(coverage.items())),
            "licensed_modules": sorted(session.licensed_modules),
            "operations": [{"op": op.op, "schema_version": op.schema_version} for op in sorted_ops],
            "protocol": session.protocol,
        }
        chash = content_hash(cast(JsonValue, canonical_dict))
        return cls(
            session=session,
            operations=ops,
            coverage=MappingProxyType(dict(coverage)),
            hash=chash,
        )

    def supports_operation(self, op: str) -> bool:
        """Check if an operation is supported by the backend."""
        return op in self.operations

    def supports_feature(self, feature_type: str, mode: str = "create") -> bool:
        """Check if a feature type is supported at the specified mode."""
        return self.coverage.get(feature_type) == mode

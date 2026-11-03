"""Pure geometric drawing checks D1, D2, D3, D7 on a Drawing Geometry Snapshot (spec 11.5)."""

from cad_drawing.checks.failures import CheckFailure, CheckItem
from cad_drawing.checks.runner import GeometryCheckResult, run_geometry_checks
from cad_drawing.checks.snapshot import SNAPSHOT_SCHEMA_ID, Snapshot, parse_snapshot
from cad_drawing.checks.soft_metrics import SoftMetrics
from cad_drawing.checks.thresholds import CheckThresholds

__all__ = [
    "SNAPSHOT_SCHEMA_ID",
    "CheckFailure",
    "CheckItem",
    "CheckThresholds",
    "GeometryCheckResult",
    "Snapshot",
    "SoftMetrics",
    "parse_snapshot",
    "run_geometry_checks",
]

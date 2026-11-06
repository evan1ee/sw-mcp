"""Pure drawing checks D1-D3, D5, D7, D8, D10 and the drawing report (spec 11.5)."""

from cad_drawing.checks.d8 import TitleBlockMapping, check_d8, mapping_from_drawing_template
from cad_drawing.checks.failures import CheckFailure, CheckItem
from cad_drawing.checks.outcome import CheckOutcome, RuleFailure
from cad_drawing.checks.report import REPORT_SCHEMA_ID, DrawingReport, build_report
from cad_drawing.checks.runner import GeometryCheckResult, run_geometry_checks
from cad_drawing.checks.snapshot import SNAPSHOT_SCHEMA_ID, Snapshot, parse_snapshot
from cad_drawing.checks.soft_metrics import SoftMetrics
from cad_drawing.checks.thresholds import CheckThresholds

__all__ = [
    "REPORT_SCHEMA_ID",
    "SNAPSHOT_SCHEMA_ID",
    "CheckFailure",
    "CheckItem",
    "CheckOutcome",
    "CheckThresholds",
    "DrawingReport",
    "GeometryCheckResult",
    "RuleFailure",
    "Snapshot",
    "SoftMetrics",
    "TitleBlockMapping",
    "build_report",
    "check_d8",
    "mapping_from_drawing_template",
    "parse_snapshot",
    "run_geometry_checks",
]

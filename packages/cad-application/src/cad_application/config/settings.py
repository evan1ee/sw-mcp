"""Immutable settings and configuration errors (spec 13.3)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from cad_drawing.checks import CheckThresholds
from cad_ir.core.json_types import JsonValue

type LayerSource = Literal["defaults", "user", "project", "env"]


@dataclass(frozen=True, slots=True)
class Layer:
    """One configuration source: its kind, where it came from, and its nested values."""

    source: LayerSource
    origin: str
    values: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class ConfigError:
    """``CONFIG_INVALID``: names the origin, the dotted key and, for syntax errors, the line."""

    origin: str
    key: str | None
    line: int | None
    message: str
    code: str = "CONFIG_INVALID"


@dataclass(frozen=True, slots=True)
class Settings:
    """Merged settings; every key of 13.3.3 except ``references.high_confidence``."""

    allowed_roots: tuple[str, ...] = ()
    pdm_vault_roots: tuple[str, ...] = ()
    toolsets: tuple[str, ...] = ("core", "drawing")
    idle_shutdown_min: int = 30
    job_retention_days: int = 7
    solidworks_session: str | int = "auto"
    command_timeout_s: int = 120
    read_timeout_s: int = 30
    ui_blocked_s: int = 30
    heartbeat_s: int = 10
    job_timeout_min: int = 10
    relayout_max_iterations: int = 8
    pin_threshold_mm: float = 0.5
    epsilon_mm: float = 0.01
    text_clearance_mm: float = 0.5
    line_clearance_mm: float = 0.25
    edge_clearance_mm: float = 0.25
    font_metric_margin: float = 0.1
    parallel_deg: float = 0.01
    # Relative to the installation; the core service resolves it (a gap noted for 13.3.3).
    standard_dir: str = "standards\\iso"
    snapshot_keep: int = 10
    backup_keep: int = 5
    logging_level: str = "info"
    logging_retention_days: int = 14
    part_template: str = ""
    # Not a configuration key: the core service fills it from the environment (12.5).
    local_app_data: str = ""
    warnings: tuple[str, ...] = ()

    def check_thresholds(self) -> CheckThresholds:
        return CheckThresholds(
            epsilon_mm=self.epsilon_mm,
            text_clearance_mm=self.text_clearance_mm,
            line_clearance_mm=self.line_clearance_mm,
            edge_clearance_mm=self.edge_clearance_mm,
            font_metric_margin=self.font_metric_margin,
            parallel_deg=self.parallel_deg,
        )

"""Check thresholds with the defaults of spec 13.3.3 (``drawing.check.*``)."""

from dataclasses import dataclass

from cad_ir.core import JsonValue


@dataclass(frozen=True, slots=True)
class CheckThresholds:
    """All lengths are sheet millimetres; ``font_metric_margin`` is a fraction of text height."""

    epsilon_mm: float = 0.01
    text_clearance_mm: float = 0.5
    line_clearance_mm: float = 0.25
    edge_clearance_mm: float = 0.25
    font_metric_margin: float = 0.1

    @property
    def arc_chord_error_mm(self) -> float:
        """Chord error of tessellated arcs: half of epsilon, so tessellation cannot hide a touch."""
        return self.epsilon_mm / 2.0

    def to_json(self) -> dict[str, JsonValue]:
        """The values used, keyed as in 13.3.3 without the ``drawing.check.`` prefix."""
        return {
            "epsilon_mm": self.epsilon_mm,
            "text_clearance_mm": self.text_clearance_mm,
            "line_clearance_mm": self.line_clearance_mm,
            "edge_clearance_mm": self.edge_clearance_mm,
            "font_metric_margin": self.font_metric_margin,
            "arc_chord_error_mm": self.arc_chord_error_mm,
        }

"""Drawing Template IR: models, parser, and semantic rules (spec 11.12)."""

from cad_ir.drawing_template.model import (
    PAPER_SIZES_MM,
    DrawingTemplate,
    Margins,
    Rect,
    StaticText,
    TemplateField,
    TitleBlockLine,
)
from cad_ir.drawing_template.parse import parse_drawing_template
from cad_ir.drawing_template.rules import (
    MINIMUM_FIELDS,
    TEMPLATE_SCHEMA_ID,
    semantic_issues,
)

__all__ = [
    "MINIMUM_FIELDS",
    "PAPER_SIZES_MM",
    "TEMPLATE_SCHEMA_ID",
    "DrawingTemplate",
    "Margins",
    "Rect",
    "StaticText",
    "TemplateField",
    "TitleBlockLine",
    "parse_drawing_template",
    "semantic_issues",
]

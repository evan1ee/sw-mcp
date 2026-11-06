"""Parser and validation driver for Drawing Intent IR (spec 11.10)."""

from typing import Any, cast

from cad_ir.core.issues import IssueReport, build_report
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.drawing_intent.model import (
    INTENT_SCHEMA_ID,
    CriticalDimension,
    DatumFeature,
    DrawingIntent,
    GDTCallout,
    IntentContext,
    SurfaceFinish,
)


def parse_drawing_intent(doc: dict[str, Any]) -> DrawingIntent | IssueReport:
    """Validate and parse a Drawing Intent IR document against schemas/drawing-intent/v0.json."""
    issues = list(validate_against_schema(cast(JsonValue, doc), INTENT_SCHEMA_ID))
    if issues:
        return build_report(issues)

    ctx_dict = doc.get("context")
    context = None
    if ctx_dict is not None:
        context = IntentContext(
            process=ctx_dict.get("process"),
            material=ctx_dict.get("material"),
            treatment=ctx_dict.get("treatment"),
            metadata=ctx_dict.get("metadata"),
        )

    sf_dict = doc.get("surface_finish")
    surface_finish = None
    if sf_dict is not None:
        surface_finish = SurfaceFinish(
            general=sf_dict.get("general"),
            exceptions=dict(sf_dict.get("exceptions", {})),
        )

    datums: dict[str, DatumFeature] = {}
    for d_id, d_dict in doc.get("datums", {}).items():
        datums[d_id] = DatumFeature(
            ref=str(d_dict["ref"]),
            applies_to=str(d_dict["applies_to"]),
        )

    critical_dims: dict[str, CriticalDimension] = {}
    for cd_id, cd_dict in doc.get("critical_dimensions", {}).items():
        critical_dims[cd_id] = CriticalDimension(
            param=cd_dict.get("param"),
            ref=cd_dict.get("ref"),
            tolerance=cd_dict.get("tolerance"),
            requirement=cd_dict.get("requirement"),
            inspect=bool(cd_dict.get("inspect", False)),
        )

    gdt: dict[str, GDTCallout] = {}
    for g_id, g_dict in doc.get("gdt", {}).items():
        gdt[g_id] = GDTCallout(
            characteristic=str(g_dict["characteristic"]),
            tolerance=float(g_dict["tolerance"]),
            target=str(g_dict["target"]),
            applies_to=str(g_dict["applies_to"]),
            datums=tuple(str(d) for d in g_dict.get("datums", [])),
            requirement=g_dict.get("requirement"),
            inspect=bool(g_dict.get("inspect", False)),
        )

    return DrawingIntent(
        id=str(doc["id"]),
        schema_version=str(doc["schema_version"]),
        units=str(doc["units"]),
        documents=str(doc["documents"]),
        revision=doc.get("revision"),
        design_intent=doc.get("design_intent"),
        configuration=str(doc.get("configuration", "Default")),
        general_tolerance=str(doc.get("general_tolerance", "ISO 2768-m")),
        context=context,
        surface_finish=surface_finish,
        datums=datums,
        critical_dimensions=critical_dims,
        gdt=gdt,
        scheme_overrides=dict(doc.get("scheme_overrides", {})),
    )

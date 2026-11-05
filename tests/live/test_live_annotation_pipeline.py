"""Live integration verification for drawing annotation pipeline and hard checks D1, D2, D3, D5, D7.

Spec 11.4, 11.5, 11.10, 11.10.1, 6.5.2, ADR-055.
Requires active interactive SOLIDWORKS 2025+ session with sw-mcp add-in loaded.
"""

import contextlib
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import cast

import pytest
from cad_application.drawing.annotation_ops import (
    plan_annotation_insertion_ops,
    plan_dimension_cleanup_ops,
)
from cad_application.drawing.layout_ops import layout_to_create_ops
from cad_drawing.checks.report import DrawingReport, build_report
from cad_drawing.checks.runner import run_geometry_checks
from cad_drawing.checks.snapshot import Snapshot, parse_snapshot
from cad_drawing.view_planning.planner import plan_ortho_views
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.drawing_intent import DrawingIntent
from cad_ir.generated.ipc import Operation, OperationGroup
from cad_protocol.backend import IpcBackend
from core_service.discovery import (
    NamedPipeBackendProvider,
    SessionInfo,
    discover_sessions,
    get_default_session_dir,
)

pytestmark = [
    pytest.mark.skipif(sys.platform != "win32", reason="Windows only"),
    pytest.mark.live,
]

EXPECTED_VIEWS_COUNT = 4
SNAPSHOT_SCHEMA_URI = "https://sw-mcp.invalid/schemas/drawing-geometry-snapshot/v0.json"
REPO_ROOT = Path(__file__).resolve().parents[2]
MINIMAL_TEMPLATE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "schemas" / "drawing-template" / "valid" / "minimal.json"
)
SAMPLE_PRT_PATH = (
    Path(r"C:\Users\Public\Documents\SOLIDWORKS\SOLIDWORKS 2023\CAM Examples")
    / "TBM_SampleParts"
    / "TBM Inch Sample Parts"
    / "adapter plate.sldprt"
)


def _get_live_session() -> SessionInfo:
    sessions = discover_sessions(get_default_session_dir())
    if not sessions:
        pytest.skip(
            "No live SOLIDWORKS session discovered in %LOCALAPPDATA%\\sw-mcp\\sessions. "
            "Requires active SOLIDWORKS interactive session with sw-mcp add-in loaded."
        )
    return sessions[0]


def test_live_annotation_and_dimension_pipeline() -> None:  # noqa: PLR0915
    if not SAMPLE_PRT_PATH.exists():
        pytest.skip(f"Sample part fixture not found: {SAMPLE_PRT_PATH}")

    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = provider.acquire(on_notification=lambda _m, _p: None)

    assert MINIMAL_TEMPLATE_PATH.exists(), f"Fixture missing: {MINIMAL_TEMPLATE_PATH}"
    template_data: JsonValue = json.loads(MINIMAL_TEMPLATE_PATH.read_text(encoding="utf-8"))

    job_prefix = f"job_ann_{uuid.uuid4().hex[:12]}"
    scratch_dir = Path(tempfile.gettempdir()) / "sw-mcp-test-live"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    model_scratch = scratch_dir / f"model_{uuid.uuid4().hex[:6]}.sldprt"
    shutil.copyfile(SAMPLE_PRT_PATH, model_scratch)

    format_path = str(scratch_dir / f"format_{uuid.uuid4().hex[:6]}.slddrt")
    save_target = str(scratch_dir / f"dwg_{uuid.uuid4().hex[:6]}.slddrw")

    created_doc: str | None = None
    try:
        # 1. Generate Sheet Format
        gen_op = Operation(
            operation_id=f"{job_prefix}:fmt",
            op="sheet_format.generate",
            params={
                "template": template_data,
                "destination_path": format_path,
            },
        )
        batch1 = OperationGroup(document="", operations=(gen_op,))
        res1 = backend.apply_ops([batch1])
        assert len(res1.outcomes) == 1
        assert res1.outcomes[0].error is None
        assert Path(format_path).exists()

        # 2. Create Drawing
        create_op = Operation(
            operation_id=f"{job_prefix}:dwg",
            op="drawing.create",
            params={
                "sheet_format_path": format_path,
                "paper_size": "A3",
                "width_mm": 420.0,
                "height_mm": 297.0,
            },
        )
        batch2 = OperationGroup(document="", operations=(create_op,))
        res2 = backend.apply_ops([batch2])
        assert len(res2.outcomes) == 1
        assert res2.outcomes[0].error is None

        res_obj = res2.outcomes[0].result
        assert isinstance(res_obj, dict)
        created_doc = cast(str, res_obj["document"])
        assert created_doc

        # 3. View Planning & View Creation
        planned_layout = plan_ortho_views(
            part_extents=(100.0, 50.0, 30.0),
            sheet_size="A3",
            sheet_width_mm=420.0,
            sheet_height_mm=297.0,
            title_block_box=(230.0, 10.0, 410.0, 75.0),
        )
        view_ops = layout_to_create_ops(
            layout=planned_layout,
            model_path=str(model_scratch),
            job_prefix=f"{job_prefix}:v",
            sheet_name="Sheet1",
        )
        batch3 = OperationGroup(document=created_doc, operations=tuple(view_ops))
        res3 = backend.apply_ops([batch3])
        assert len(res3.outcomes) == EXPECTED_VIEWS_COUNT
        for outcome in res3.outcomes:
            assert outcome.error is None

        # Build view name mapping (e.g. "v_front" -> "Drawing View1")
        view_names: dict[str, str] = {}
        for outcome in res3.outcomes:
            if isinstance(outcome.result, dict):
                vid = str(outcome.result.get("view_id", ""))
                nid = str(outcome.result.get("native_id", ""))
                if vid and nid:
                    view_names[vid] = nid

        # 4. Plan and Dispatch Annotation Insertion Operations
        intent = DrawingIntent(
            id="intent_live_adapter",
            schema_version="0.1",
            units="mm",
            documents=str(model_scratch),
        )
        ann_ops = plan_annotation_insertion_ops(
            layout=planned_layout,
            intent=intent,
            job_prefix=f"{job_prefix}:ann",
            view_names=view_names,
            spacing_mm=10.0,
        )
        batch_ann = OperationGroup(document=created_doc, operations=tuple(ann_ops))
        res_ann = backend.apply_ops([batch_ann])
        assert len(res_ann.outcomes) == len(ann_ops)
        for outcome in res_ann.outcomes:
            assert outcome.error is None, f"Annotation op failed: {outcome.error}"

        # 5. Read back Drawing Geometry Snapshot
        snap_raw = backend.snapshot_drawing(created_doc)
        assert isinstance(snap_raw, dict)
        schema_issues = validate_against_schema(snap_raw, SNAPSHOT_SCHEMA_URI)
        assert len(schema_issues) == 0, f"Snapshot schema validation failed: {schema_issues}"

        # 6. Pure Dimension Scheme Duplicate Cleanup Planning
        cleanup_ops, _resolved_scheme = plan_dimension_cleanup_ops(
            snapshot=snap_raw,
            intent=intent,
            job_prefix=f"{job_prefix}:clean",
        )
        if cleanup_ops:
            batch_clean = OperationGroup(document=created_doc, operations=tuple(cleanup_ops))
            res_clean = backend.apply_ops([batch_clean])
            for outcome in res_clean.outcomes:
                assert outcome.error is None, f"Dimension hide op failed: {outcome.error}"

            # Re-read snapshot after hiding duplicates
            snap_raw = backend.snapshot_drawing(created_doc)
            assert isinstance(snap_raw, dict)

        # 7. Validate Hard Checks: D1, D2, D3, D5, D7
        parsed_snapshot = parse_snapshot(snap_raw)
        assert isinstance(parsed_snapshot, Snapshot), (
            f"parse_snapshot returned issues: {parsed_snapshot}"
        )

        # Geometry checks (D1, D2, D3, D7)
        geo_result = run_geometry_checks(parsed_snapshot)
        assert geo_result.status("D1") == "pass", f"D1 failed: {geo_result.failures}"
        assert geo_result.status("D2") == "pass", f"D2 failed: {geo_result.failures}"
        assert geo_result.status("D3") == "pass", f"D3 failed: {geo_result.failures}"
        assert geo_result.status("D7") == "pass", f"D7 failed: {geo_result.failures}"

        # Full drawing report (includes D5 duplicate dimension verification)
        report = build_report(snap_raw)
        assert isinstance(report, DrawingReport), f"build_report returned issues: {report}"
        d5_outcome = report.outcomes.get("D5")
        assert d5_outcome is not None, "D5 outcome missing from report"
        assert dict(d5_outcome.parts)["duplicates"] == "pass", (
            f"D5 duplicates failed: {d5_outcome.failures}"
        )
        assert len(d5_outcome.failures) == 0, (
            f"D5 duplicate parameter dimensions found: {d5_outcome.failures}"
        )

        # 8. Document Save
        save_op = Operation(
            operation_id=f"{job_prefix}:save",
            op="document.save",
            params={
                "path": created_doc,
                "target_path": save_target,
            },
        )
        batch_save = OperationGroup(document=created_doc, operations=(save_op,))
        res_save = backend.apply_ops([batch_save])
        assert len(res_save.outcomes) == 1
        assert res_save.outcomes[0].error is None
        assert Path(save_target).exists()
        assert Path(save_target).stat().st_size > 0

    finally:
        # Cleanup: Close drawing document in SOLIDWORKS
        if created_doc:
            with contextlib.suppress(Exception):
                close_op = Operation(
                    operation_id=f"{job_prefix}:close",
                    op="document.close",
                    params={},
                )
                backend.apply_ops([OperationGroup(document=created_doc, operations=(close_op,))])
        if isinstance(backend, IpcBackend):
            with contextlib.suppress(Exception):
                backend.close()
        # Cleanup: Remove scratch files
        for p in (format_path, save_target, str(model_scratch)):
            with contextlib.suppress(OSError):
                Path(p).unlink(missing_ok=True)

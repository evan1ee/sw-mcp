"""Live integration verification for sheet format generation and drawing creation.

Spec 11.12, ADR-055, K7.
Requires active interactive SOLIDWORKS 2025+ session with sw-mcp add-in loaded.
"""

import contextlib
import json
import sys
import tempfile
import uuid
from pathlib import Path
from typing import cast

import pytest
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
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

EXPECTED_DIMS_COUNT = 2
SNAPSHOT_SCHEMA_URI = "https://sw-mcp.invalid/schemas/drawing-geometry-snapshot/v0.json"
REPO_ROOT = Path(__file__).resolve().parents[2]
MINIMAL_TEMPLATE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "schemas" / "drawing-template" / "valid" / "minimal.json"
)


def _get_live_session() -> SessionInfo:
    sessions = discover_sessions(get_default_session_dir())
    if not sessions:
        pytest.skip(
            "No live SOLIDWORKS session discovered in %LOCALAPPDATA%\\sw-mcp\\sessions. "
            "Requires active SOLIDWORKS interactive session with sw-mcp add-in loaded."
        )
    return sessions[0]


def test_live_sheet_format_generate_and_drawing_create() -> None:  # noqa: PLR0915
    session = _get_live_session()
    provider = NamedPipeBackendProvider(target_session=str(session.pid))
    backend = provider.acquire(on_notification=lambda _m, _p: None)

    assert MINIMAL_TEMPLATE_PATH.exists(), f"Fixture missing: {MINIMAL_TEMPLATE_PATH}"
    template_data: JsonValue = json.loads(MINIMAL_TEMPLATE_PATH.read_text(encoding="utf-8"))

    job_prefix = f"job_live_{uuid.uuid4().hex[:12]}"
    scratch_dir = Path(tempfile.gettempdir()) / "sw-mcp-test-live"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    format_path = str(scratch_dir / f"test_format_{uuid.uuid4().hex[:6]}.slddrt")

    gen_op = Operation(
        operation_id=f"{job_prefix}:1",
        op="sheet_format.generate",
        params={
            "template": template_data,
            "destination_path": format_path,
        },
    )

    created_doc: str | None = None
    save_target: str | None = None
    try:
        # 1. Generate Sheet Format
        batch1 = OperationGroup(document="", operations=(gen_op,))
        res1 = backend.apply_ops([batch1])
        assert len(res1.outcomes) == 1
        assert res1.outcomes[0].error is None
        assert Path(format_path).exists()
        assert Path(format_path).stat().st_size > 0

        # 2. Create Drawing using generated Sheet Format
        create_op = Operation(
            operation_id=f"{job_prefix}:2",
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

        # Extract created document name
        res_obj = res2.outcomes[0].result
        if isinstance(res_obj, dict):
            doc_val = res_obj.get("document")
            if isinstance(doc_val, str):
                created_doc = doc_val

        assert created_doc is not None

        # 3. Snapshot the newly created drawing
        snapshot = backend.snapshot_drawing(document=created_doc)
        assert snapshot is not None
        assert isinstance(snapshot, dict)

        issues = validate_against_schema(snapshot, SNAPSHOT_SCHEMA_URI)
        assert issues == ()

        # Assert sheet size in snapshot is A3 (420 x 297)
        raw_sheets = snapshot.get("sheets")
        assert isinstance(raw_sheets, dict)
        sheets = cast("dict[str, dict[str, JsonValue]]", raw_sheets)
        assert len(sheets) == 1
        first_sheet = next(iter(sheets.values()))
        assert isinstance(first_sheet, dict)
        raw_size = first_sheet.get("size_mm")
        assert isinstance(raw_size, list)
        size = cast("list[float | int]", raw_size)
        assert len(size) == EXPECTED_DIMS_COUNT
        assert abs(float(size[0]) - 420.0) < 1.0
        assert abs(float(size[1]) - 297.0) < 1.0

        # 4. Save the drawing to disk via document.save
        save_target = str(scratch_dir / f"test_saved_{uuid.uuid4().hex[:6]}.slddrw")
        save_op = Operation(
            operation_id=f"{job_prefix}:3",
            op="document.save",
            params={
                "path": created_doc,
                "target_path": save_target,
            },
        )
        batch3 = OperationGroup(document=created_doc, operations=(save_op,))
        res3 = backend.apply_ops([batch3])
        assert len(res3.outcomes) == 1
        assert res3.outcomes[0].error is None
        assert Path(save_target).exists()
        assert Path(save_target).stat().st_size > 0

    finally:
        # Clean up document in SOLIDWORKS
        if created_doc is not None:
            close_op = Operation(
                operation_id=f"{job_prefix}:4",
                op="document.close",
                params={"path": created_doc, "save": False},
            )
            backend.apply_ops([OperationGroup(document=created_doc, operations=(close_op,))])

        # Clean up generated format and saved drawing files
        for p in (format_path, save_target):
            if p is not None:
                with contextlib.suppress(Exception):
                    if Path(p).exists():
                        Path(p).unlink(missing_ok=True)

        if isinstance(backend, IpcBackend):
            with contextlib.suppress(Exception):
                backend.close()

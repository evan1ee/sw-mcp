"""IPC transcripts (spec 8.7, 15.5): headers, schema conformance, and Python replay to the end."""

import base64
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from cad_ir.core.json_types import JsonValue
from cad_ir.core.schema_validation import validate_against_schema
from cad_ir.generated.ipc import Operation, OperationGroup
from cad_protocol.client.ipc_client import IpcClient
from cad_protocol.errors import IpcError
from cad_protocol.replay import ReplayTransport, Transcript, load_transcript

ROOT = Path(__file__).resolve().parents[2]
TRANSCRIPTS = ROOT / "tests" / "fixtures" / "ipc"
IPC_ID = "https://sw-mcp.invalid/schemas/ipc/v0.json"
OPS_ID = "https://sw-mcp.invalid/schemas/ipc/ops/{op}.json"
WRONG_TOKEN = "wrong-token-0000"
DWG = "C:/d/bracket.slddrw"
WORK = r"C:\Work\a.slddrw"  # the path the check_drawing transcripts use (normalised form)
JOB = "job_00000000000000000000000001"  # the first ID of SequentialIdSource

SCENARIOS = {
    "handshake",
    "wrong_token",
    "not_hello_first",
    "protocol_major_mismatch",
    "solidworks_unsupported",
    "snapshot_ok",
    "snapshot_chunked",
    "cancel_running",
    "ops_duplicate",
    "ops_failure_stops",
    "ui_blocked",
    "timeout_late_response",
    "backend_lost",
    "unknown_method",
    "invalid_params",
    "check_drawing_owned",
    "check_drawing_borrowed",
    "check_drawing_bad_sheet",
    "check_drawing_ui_blocked",
    "check_drawing_timeout",
    "check_drawing_lost",
    "check_drawing_sp_warning",
    "plan_plate_committed",
    "plan_plate_recorded",
    "plan_op_failed",
    "plan_wrong_volume",
    "plan_cancelled",
    "plan_backend_lost",
}
# The add-in must answer -32602 to these requests, so their params are invalid by design.
BAD_PARAMS_ON_PURPOSE = {"invalid_params"}
PARAMS_DEF = {
    "session.hello": "HelloParams",
    "session.ping": "PingParams",
    "session.completed_operations": "CompletedOperationsParams",
    "drawing.snapshot": "SnapshotParams",
    "part.measure": "PartMeasureParams",
    "ops.apply": "OpsApplyParams",
    "job.cancel": "JobCancelParams",
    "job.progress": "JobProgressParams",
    "document.event": "DocumentEventParams",
    "session.ui_blocked": "UiBlockedParams",
    "response.chunk": "ResponseChunkParams",
}
RESULT_DEF = {
    "session.hello": "HelloResult",
    "session.ping": "PingResult",
    "session.completed_operations": "CompletedOperationsResult",
    "drawing.snapshot": "SnapshotResult",
    "part.measure": "PartMeasureResult",
    "ops.apply": "OpsApplyResult",
    "job.cancel": "JobCancelResult",
}
SNAPSHOT_ID = "https://sw-mcp.invalid/schemas/drawing-geometry-snapshot/v0.json"

type Frame = dict[str, Any]


def _load(name: str) -> Transcript:
    return load_transcript((TRANSCRIPTS / f"{name}.jsonl").read_text(encoding="utf-8"))


def _names() -> list[str]:
    return sorted(p.stem for p in TRANSCRIPTS.glob("*.jsonl"))


def _issues(instance: Any, schema_ref: str) -> list[Any]:
    return list(validate_against_schema(instance, schema_ref))


def _joined(frames: list[Frame]) -> Iterator[Frame]:
    """The frames with each run of ``response.chunk`` notifications replaced by the whole frame."""
    parts: dict[int, list[bytes]] = {}
    for frame in frames:
        if frame.get("method") != "response.chunk":
            yield frame
            continue
        params = frame["params"]
        parts.setdefault(params["id"], []).append(base64.b64decode(params["data"], validate=True))
        assert params["index"] == len(parts[params["id"]]) - 1
        if params["index"] == params["count"] - 1:
            yield json.loads(b"".join(parts.pop(params["id"])))


def _check_ops(request: Frame, reply: Frame | None) -> list[Any]:
    """Each operation's params and result against its ``ops/<op>.json`` schema."""
    issues: list[Any] = []
    by_id: dict[str, str] = {}
    for group in request["params"]["groups"]:
        for operation in group["operations"]:
            by_id[operation["operation_id"]] = operation["op"]
            ref = OPS_ID.format(op=operation["op"]) + "#/$defs/Params"
            issues += _issues(operation.get("params", {}), ref)
    result: dict[str, Any] = (reply or {}).get("result") or {}
    for outcome in result.get("outcomes", []):
        if "result" in outcome and outcome["operation_id"] in by_id:
            ref = OPS_ID.format(op=by_id[outcome["operation_id"]]) + "#/$defs/Result"
            issues += _issues(outcome["result"], ref)
    return issues


def _frame_issues(name: str) -> list[str]:
    transcript = _load(name)
    frames = [e.frame for e in transcript.entries if e.frame is not None]
    sent: dict[int, Frame] = {}
    problems: list[str] = []
    for frame in _joined(frames):
        problems += [f"{name}: {i}" for i in _issues(frame, IPC_ID)]
        method = frame.get("method")
        if method in PARAMS_DEF and "params" in frame and name not in BAD_PARAMS_ON_PURPOSE:
            ref = f"{IPC_ID}#/$defs/{PARAMS_DEF[method]}"
            problems += [f"{name}: {method} params {i}" for i in _issues(frame["params"], ref)]
        if "id" in frame and method is not None:
            sent[frame["id"]] = frame
        elif frame.get("id") in sent and "result" in frame:
            request = sent[frame["id"]]
            if request["method"] in RESULT_DEF:
                ref = f"{IPC_ID}#/$defs/{RESULT_DEF[request['method']]}"
                problems += [f"{name}: result {i}" for i in _issues(frame["result"], ref)]
            if request["method"] == "drawing.snapshot":
                problems += [f"{name}: snapshot {i}" for i in _issues(frame["result"], SNAPSHOT_ID)]
            if request["method"] == "ops.apply":
                problems += [f"{name}: op {i}" for i in _check_ops(request, frame)]
    return problems


def test_all_scenarios_present() -> None:
    assert set(_names()) == SCENARIOS


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_every_transcript_header_valid(name: str) -> None:
    header = _load(name).header
    assert header.scenario == name
    assert header.source == ("recorded" if name.endswith("_recorded") else "synthetic")
    assert header.sides
    assert isinstance(header.config["token"], str)
    assert header.config["backend"]["protocol"] == "0.1"
    assert isinstance(header.config["version_supported"], bool)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_every_frame_matches_ipc_schema(name: str) -> None:
    assert _frame_issues(name) == []


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_frames_fit_the_declared_limit(name: str) -> None:
    transcript = _load(name)
    limit = transcript.header.config.get("max_frame_bytes")
    if limit is None:
        return
    sizes = [
        len(json.dumps(e.frame, ensure_ascii=False, separators=(",", ":")).encode())
        for e in transcript.entries
        if e.frame is not None
    ]
    assert max(sizes) <= limit
    assert any(e.frame and e.frame.get("method") == "response.chunk" for e in transcript.entries)


def test_chunked_scenario_splits_inside_a_character() -> None:
    entries = _load("snapshot_chunked").entries
    pieces = [
        base64.b64decode(e.frame["params"]["data"])
        for e in entries
        if e.frame and e.frame.get("method") == "response.chunk"
    ]
    broken = 0
    for piece in pieces:
        try:
            piece.decode("utf-8")
        except UnicodeDecodeError:
            broken += 1
    assert broken >= 1


def _client(transcript: Transcript, transport: ReplayTransport, **kwargs: Any) -> IpcClient:
    token = kwargs.pop("token", transcript.header.config["token"])
    return IpcClient(transport, token=token, **kwargs)


def _expect(code: str, call: Callable[[], object]) -> None:
    with pytest.raises(IpcError) as info:
        call()
    assert info.value.code == code


def _handshake(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    assert client.hello().addin_version == "0.1.0"
    assert client.ping().pong is True
    assert client.completed_operations() == ()


def _wrong_token(t: Transcript, tr: ReplayTransport) -> None:
    _expect("BACKEND_LOST", _client(t, tr, token=WRONG_TOKEN).hello)


def _not_hello_first(t: Transcript, tr: ReplayTransport) -> None:
    _expect("BACKEND_LOST", _client(t, tr).ping)


def _major_mismatch(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr, protocol="9.0")
    _expect("BACKEND_VERSION_UNSUPPORTED", client.hello)
    _expect("BACKEND_LOST", client.ping)


def _sw_unsupported(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    _expect("BACKEND_VERSION_UNSUPPORTED", client.hello)
    _expect("BACKEND_VERSION_UNSUPPORTED", client.hello)


def _snapshot(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    result = client.snapshot_drawing(DWG)
    assert isinstance(result, dict)
    assert result["schema_version"] == "0.1"


def _snapshot_of_sheet(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    result = client.snapshot_drawing(DWG, ["Sheet1"])
    assert isinstance(result, dict)
    assert result["schema_version"] == "0.1"


def _cancel(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    pending = [client.begin_snapshot_drawing(DWG), client.begin_snapshot_drawing(DWG)]
    assert client.cancel() is True
    for call in pending:
        _expect("EXEC_CANCELLED", call.wait)


def _op(operation_id: str, path: str) -> Operation:
    params: dict[str, JsonValue] = {"path": path, "read_only": False, "fully_resolved": True}
    return Operation(operation_id=operation_id, op="document.open", params=params)


def _ops_duplicate(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    a, b = "C:/d/a.sldprt", "C:/d/b.sldprt"
    client.apply_ops(
        [
            OperationGroup(document=a, operations=(_op("j1:1", a),)),
            OperationGroup(document=b, operations=(_op("j1:2", b),)),
        ]
    )
    again = OperationGroup(document=b, operations=(_op("j1:2", b), _op("j1:3", a)))
    assert len(client.apply_ops([again]).outcomes) == 1
    assert client.completed_operations() == ("j1:1", "j1:2")


def _ops_failure(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    path = "C:/d/a.sldprt"
    close = Operation(operation_id="j2:3", op="document.close", params={"path": path})
    ops = (_op("j2:1", path), _op("j2:2", "D:/x/c.sldprt"), close)
    result = client.apply_ops([OperationGroup(document=path, operations=ops)])
    assert len(result.outcomes) == 2  # noqa: PLR2004
    assert client.completed_operations() == ("j2:1",)


def _timeout(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    _expect("EXEC_TIMEOUT", lambda: client.snapshot_drawing(DWG))
    assert client.completed_operations() == ()


def _lost(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    _expect("BACKEND_LOST", lambda: client.snapshot_drawing(DWG))


def _job_open(client: IpcClient, *, owned: bool) -> None:
    params: dict[str, JsonValue] = {"path": WORK, "read_only": True, "fully_resolved": True}
    operation = Operation(operation_id=f"{JOB}:1", op="document.open", params=params)
    result = client.apply_ops([OperationGroup(document=WORK, operations=(operation,))])
    assert result.outcomes[0].result == {"owned": owned}


def _job_close(client: IpcClient) -> None:
    operation = Operation(operation_id=f"{JOB}:2", op="document.close", params={"path": WORK})
    result = client.apply_ops([OperationGroup(document=WORK, operations=(operation,))])
    assert result.outcomes[0].result == {"closed": True}


def _check_owned(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    _job_open(client, owned=True)
    snapshot = client.snapshot_drawing(WORK)
    assert isinstance(snapshot, dict)
    _job_close(client)


def _check_borrowed(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    _job_open(client, owned=False)
    assert isinstance(client.snapshot_drawing(WORK), dict)


def _check_bad_sheet(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    _job_open(client, owned=True)
    with pytest.raises(IpcError) as info:
        client.snapshot_drawing(WORK, ["Nope"])
    assert info.value.code == "IR_REFERENCE_UNRESOLVED"
    _job_close(client)


def _check_ui_blocked(t: Transcript, tr: ReplayTransport) -> None:
    seen: list[str] = []

    def note(method: str, _params: JsonValue) -> None:
        seen.append(method)

    client = _client(t, tr, on_notification=note)
    client.hello()
    _job_open(client, owned=True)
    assert isinstance(client.snapshot_drawing(WORK), dict)
    assert seen == ["session.ui_blocked"]


def _check_timeout(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    _job_open(client, owned=True)
    _expect("EXEC_TIMEOUT", lambda: client.snapshot_drawing(WORK))
    assert client.completed_operations() == (f"{JOB}:1",)


def _check_lost(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    client.hello()
    _job_open(client, owned=True)
    _expect("BACKEND_LOST", lambda: client.snapshot_drawing(WORK))


def _check_sp_warning(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    assert client.hello().warnings
    _job_open(client, owned=True)
    assert isinstance(client.snapshot_drawing(WORK), dict)
    _job_close(client)


def _drive_plan(t: Transcript, tr: ReplayTransport) -> None:
    client = _client(t, tr)
    entries = t.entries
    for idx, entry in enumerate(entries):
        if entry.direction != "core_to_addin" or entry.frame is None:
            continue
        method = entry.frame["method"]
        params = entry.frame.get("params", {})
        next_is_close = idx + 1 < len(entries) and entries[idx + 1].is_close
        if method == "session.hello":
            client.hello()
        elif method == "ops.apply":
            groups = [OperationGroup.from_json(g) for g in params["groups"]]
            if next_is_close:
                _expect("BACKEND_LOST", lambda g=groups: client.apply_ops(g))
            else:
                client.apply_ops(groups)
        elif method == "part.measure":
            assert isinstance(client.measure_part(params["document"]), dict)
        elif method == "job.cancel":
            assert client.cancel() is True


DRIVERS: dict[str, Callable[[Transcript, ReplayTransport], None]] = {
    "handshake": _handshake,
    "wrong_token": _wrong_token,
    "not_hello_first": _not_hello_first,
    "protocol_major_mismatch": _major_mismatch,
    "solidworks_unsupported": _sw_unsupported,
    "snapshot_ok": _snapshot_of_sheet,
    "snapshot_chunked": _snapshot,
    "cancel_running": _cancel,
    "ops_duplicate": _ops_duplicate,
    "ops_failure_stops": _ops_failure,
    "ui_blocked": _snapshot,
    "timeout_late_response": _timeout,
    "backend_lost": _lost,
    "check_drawing_owned": _check_owned,
    "check_drawing_borrowed": _check_borrowed,
    "check_drawing_bad_sheet": _check_bad_sheet,
    "check_drawing_ui_blocked": _check_ui_blocked,
    "check_drawing_timeout": _check_timeout,
    "check_drawing_lost": _check_lost,
    "check_drawing_sp_warning": _check_sp_warning,
    "plan_plate_committed": _drive_plan,
    "plan_plate_recorded": _drive_plan,
    "plan_op_failed": _drive_plan,
    "plan_wrong_volume": _drive_plan,
    "plan_cancelled": _drive_plan,
    "plan_backend_lost": _drive_plan,
}


def test_every_python_scenario_has_a_driver() -> None:
    python_side = {n for n in SCENARIOS if "python" in _load(n).header.sides}
    assert set(DRIVERS) == python_side


@pytest.mark.parametrize("name", sorted(DRIVERS))
def test_every_python_scenario_replays_to_the_end(name: str) -> None:
    transcript = _load(name)
    transport = ReplayTransport(transcript)
    DRIVERS[name](transcript, transport)
    assert transport.exhausted

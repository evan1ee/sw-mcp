"""Integration tests for the plan job (spec 8.4, design 8, Task 9b)."""

import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from cad_application.config.settings import Settings
from cad_application.jobs.engine import JobEngine
from cad_application.jobs.model import JobView, PlanSpec
from cad_application.jobs.part_files import failed_path, partial_path, working_path
from cad_application.paths import Authorized
from cad_application.ports import BackendCallError
from cad_application.store.file_store import FileStore
from cad_application.store.job_records import JobRecord
from cad_application.store.journal_records import (
    BatchSentRecord,
    DocumentRecord,
    JournalRecord,
    OpVerifiedRecord,
    PublishedRecord,
    PublishIntentRecord,
    StateRecord,
)
from cad_application.store.records import PartRecord
from cad_application.store.store_set import StoreSet
from cad_application.testing.builders import PROJECT_ROOT, STORE_DIR
from cad_application.testing.fake_clock import FakeClock
from cad_application.testing.fakes import (
    FakeBackend,
    FakeBackendProvider,
    ListEventLog,
    SequentialIdSource,
)
from cad_application.testing.job_rig import make_rig
from cad_application.testing.memory_fs import MemoryFileSystem
from cad_application.tools.context import ToolContext
from cad_application.tools.registry import build_registry
from cad_ir.core.json_types import JsonValue
from cad_ir.generated import ErrorCode
from cad_ir.generated.ipc import (
    HelloResult,
    Meta,
    OperationGroup,
    OperationInfo,
    OperationOutcome,
    OpsApplyResult,
    SolidWorksInfo,
)
from cad_protocol.backend import IpcBackend
from cad_protocol.client.ipc_client import IpcClient, NotificationHandler
from cad_protocol.replay import ReplayTransport, load_transcript
from core_service.service import CoreService

from tests.live.test_live_part_chain import DepthAlteringBackendProvider

ROOT = Path(__file__).resolve().parents[2]
PLATE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "schemas" / "part-feature-graph" / "valid" / "plate_4h.json"
)
TARGET_PATH = "C:\\Work\\plate.SLDPRT"
TEMPLATE_PATH = "C:\\Templates\\ISO-mm.prtdot"
KNOWN_STORES = "C:\\Users\\u\\AppData\\Local\\sw-mcp\\known-stores.json"


def _make_plate_measurement(dirty: bool = False) -> dict[str, Any]:
    return {
        "solid_body_count": 1,
        "bbox_m": {
            "min": [-0.05, -0.03, 0.0],
            "max": [0.05, 0.03, 0.01],
        },
        "volume_m3": 5.798938070170252e-05,
        "surface_area_m2": 0.015803185789489239,
        "center_of_mass_m": [0.0, 0.0, 0.005],
        "cylinders_m": [
            {"point": [-0.04, -0.02, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
            {"point": [0.04, -0.02, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
            {"point": [0.04, 0.02, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
            {"point": [-0.04, 0.02, 0.0], "direction": [0.0, 0.0, 1.0], "radius": 0.004},
        ],
        "rebuild": {
            "ok": True,
            "errors": [],
        },
        "features": [
            {"feature_id": "f73", "native_id": 73, "type": "ProfileFeature", "status": "ok"},
            {"feature_id": "f79", "native_id": 79, "type": "Extrusion", "status": "ok"},
            {"feature_id": "f80", "native_id": 80, "type": "ProfileFeature", "status": "ok"},
            {"feature_id": "f86", "native_id": 86, "type": "ICE", "status": "ok"},
        ],
        "dirty": dirty,
        "read_only": False,
    }


def _make_part_hello() -> HelloResult:
    return HelloResult(
        protocol="0.1",
        addin_version="0.1.0",
        solidworks=SolidWorksInfo(version="2025", service_pack="SP3.0", ui_language="en-US"),
        capabilities=("ops.apply", "part.measure"),
        operations=(
            OperationInfo(op="part.create", schema_version="0.1"),
            OperationInfo(op="sketch.create", schema_version="0.1"),
            OperationInfo(op="feature.create", schema_version="0.1"),
            OperationInfo(op="document.save", schema_version="0.1"),
            OperationInfo(op="document.close", schema_version="0.1"),
            OperationInfo(op="document.rebuild", schema_version="0.1"),
            OperationInfo(op="document.open", schema_version="0.1"),
        ),
        licensed_modules=(),
        warnings=(),
    )


class PartRig:
    def __init__(
        self,
        *,
        fs: MemoryFileSystem | None = None,
        clock: FakeClock | None = None,
        measurement: Any = None,
        op_results: dict[str, JsonValue] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.fs = fs or MemoryFileSystem()
        self.clock = clock or FakeClock()
        self.ids = SequentialIdSource()
        self.log = ListEventLog()
        self.fs.make_dirs(PROJECT_ROOT)
        self.fs.make_dirs("C:\\Templates")
        self.fs.write_new(TEMPLATE_PATH, b"TEMPLATE_CONTENT")

        self.instance_counter = 0
        self.open_instances: dict[str, str] = {}
        self._custom_measurement = measurement

        # Default scripted op results
        results: dict[str, JsonValue] = {
            "part.create": {
                "native_id": 1,
                "path": "dummy",
                "instance_id": "inst_1",
                "previous_active": "",
                "template": TEMPLATE_PATH,
            },
            "sketch.create": {
                "native_id": 73,
                "feature_id": "f73",
                "entity_count": 4,
                "observation": {
                    "native_type": "ProfileFeature",
                    "type": "sketch",
                    "error_code": 0,
                    "is_warning": False,
                    "suppressed": False,
                    "parents": [],
                    "update_stamp": 1,
                    "completeness": {"type": "present"},
                },
            },
            "feature.create": {
                "native_id": 79,
                "feature_id": "f79",
                "status": "ok",
                "observation": {
                    "native_type": "Extrusion",
                    "type": "extrude",
                    "error_code": 0,
                    "is_warning": False,
                    "suppressed": False,
                    "parents": ["f73"],
                    "update_stamp": 2,
                    "completeness": {"type": "present"},
                },
            },
            "document.rebuild": {"rebuilt": True, "ok": True, "errors": []},
            "document.save": {"saved_path": "dummy"},
            "document.close": {"closed": True},
            "document.open": {"owned": True, "instance_id": "inst_2"},
        }
        if op_results:
            results.update(op_results)

        self.backend = FakeBackend(
            _make_part_hello(),
            measurement=self._measure,
            op_results=results,
        )
        # Hook after apply_ops to write dummy bytes on part.create or document.save
        orig_apply = self.backend.apply_ops

        def _apply_ops_hook(groups: Sequence[OperationGroup], *, meta: Meta | None = None) -> Any:
            res = orig_apply(groups, meta=meta)
            outcomes = list(res.outcomes)
            for g in groups:
                for op in g.operations:
                    if (
                        op.op in ("part.create", "document.save")
                        and self.fs.stat(g.document) is None
                    ):
                        self.fs.write_new(g.document, b"SLDPRT_CONTENT")
                    op_params = op.params if isinstance(op.params, dict) else {}
                    nid = op_params.get("node_id")
                    if op_results and isinstance(nid, str) and nid in op_results:
                        idx = next(
                            i for i, o in enumerate(outcomes) if o.operation_id == op.operation_id
                        )
                        outcomes[idx] = OperationOutcome(
                            operation_id=op.operation_id, result=op_results[nid]
                        )
                        continue
                    if op.op == "sketch.create" and op_params.get("node_id") == "sketch_holes":
                        idx = next(
                            i for i, o in enumerate(outcomes) if o.operation_id == op.operation_id
                        )
                        outcomes[idx] = OperationOutcome(
                            operation_id=op.operation_id,
                            result={
                                "native_id": 80,
                                "feature_id": "f80",
                                "entity_count": 4,
                                "observation": {
                                    "native_type": "ProfileFeature",
                                    "type": "sketch",
                                    "error_code": 0,
                                    "is_warning": False,
                                    "suppressed": False,
                                    "parents": [],
                                    "update_stamp": 3,
                                    "completeness": {"type": "present"},
                                },
                            },
                        )
                    elif op.op == "feature.create" and (
                        op_params.get("node_id") == "cut_holes"
                        or op_params.get("type") == "cut_extrude"
                    ):
                        idx = next(
                            i for i, o in enumerate(outcomes) if o.operation_id == op.operation_id
                        )
                        outcomes[idx] = OperationOutcome(
                            operation_id=op.operation_id,
                            result={
                                "native_id": 86,
                                "feature_id": "f86",
                                "status": "ok",
                                "observation": {
                                    "native_type": "ICE",
                                    "type": "cut_extrude",
                                    "error_code": 0,
                                    "is_warning": False,
                                    "suppressed": False,
                                    "parents": ["f80"],
                                    "update_stamp": 4,
                                    "completeness": {"type": "present"},
                                },
                            },
                        )
            return OpsApplyResult(outcomes=tuple(outcomes))

        self.backend.apply_ops = _apply_ops_hook

        self.provider = FakeBackendProvider(self.backend)
        self.stores = StoreSet(self.fs, self.clock, KNOWN_STORES)
        self.user_settings = settings or Settings(
            allowed_roots=(PROJECT_ROOT,), part_template=TEMPLATE_PATH
        )
        self.engine = JobEngine(
            self.stores,
            self.provider,
            self.clock,
            self.ids,
            self.log,
            lambda _root: self.user_settings,
            lambda _s: {},
        )

        # Store plate graph in store
        self.plate_raw = json.loads(PLATE_FIXTURE.read_text(encoding="utf-8"))
        store = self.stores.open_for(
            Authorized(TARGET_PATH, PROJECT_ROOT, PROJECT_ROOT, STORE_DIR, False)
        )
        assert isinstance(store, FileStore)
        self.store = store
        self.store.put_part_revision("part:plate_4h", self.plate_raw, None)

    def _measure(self, doc_path: str) -> Any:
        if callable(self._custom_measurement):
            return self._custom_measurement(doc_path)
        if self._custom_measurement is not None:
            return self._custom_measurement
        return _make_plate_measurement()

    def spec(
        self, target: str = TARGET_PATH, ref: str = "part:plate_4h@1", template: str | None = None
    ) -> PlanSpec:
        auth = Authorized(target, PROJECT_ROOT, PROJECT_ROOT, STORE_DIR, False)
        return PlanSpec(authorized=auth, target_path=target, ref=ref, template=template)

    def submit(self, spec: PlanSpec | None = None) -> str:
        s = spec or self.spec()
        view = self.engine.submit(s, self.ids.new_id("req"))
        assert isinstance(view, JobView)
        return view.job_id

    def journal(self, job_id: str) -> tuple[JournalRecord, ...]:
        j = self.store.read_journal(job_id)
        assert isinstance(j, tuple)
        return j

    def job(self, job_id: str) -> JobRecord:
        rec = self.store.get_job(job_id)
        assert isinstance(rec, JobRecord)
        return rec


# --- Tests ---


def test_plate_commits() -> None:
    rig = PartRig()
    job_id = rig.submit()
    assert rig.engine.run_next()

    record = rig.job(job_id)
    assert record.state == "COMMITTED"
    assert record.error is None
    assert rig.fs.stat(TARGET_PATH) is not None

    # part_result holds passes and feature_ids
    assert record.part_result is not None
    pr = record.part_result
    assert pr["path"] == TARGET_PATH
    assert pr["fingerprint"] == record.fingerprint
    checks = pr["checks"]
    assert isinstance(checks, list)
    assert len(checks) > 0

    # PartRecord in store
    fp = record.fingerprint
    assert fp is not None
    part_key = f"fp-{fp.removeprefix('sha256:')[:16]}"
    part_rec = rig.store.get_part_record(part_key)
    assert isinstance(part_rec, PartRecord)
    assert part_rec.produced is True
    assert part_rec.path == TARGET_PATH

    # Transitions PLANNED -> VALIDATED -> EXECUTING -> VERIFYING -> COMMITTED
    transitions = [(r.from_state, r.to) for r in rig.journal(job_id) if isinstance(r, StateRecord)]
    assert transitions == [
        (None, "PLANNED"),
        ("PLANNED", "VALIDATED"),
        ("VALIDATED", "EXECUTING"),
        ("EXECUTING", "VERIFYING"),
        ("VERIFYING", "COMMITTED"),
    ]


def test_binds_symbols() -> None:
    # Sketch ops should return f73 and f80, and feature.create should use them
    op_results: dict[str, JsonValue] = {
        "part.create": {"native_id": 1, "instance_id": "inst_1"},
        "sketch_base": {
            "native_id": 73,
            "feature_id": "f73",
            "entity_count": 4,
            "observation": {
                "native_type": "ProfileFeature",
                "type": "sketch",
                "error_code": 0,
                "is_warning": False,
                "suppressed": False,
                "parents": [],
                "completeness": {"type": "present"},
            },
        },
        "extrude_base": {
            "native_id": 79,
            "feature_id": "f79",
            "status": "ok",
            "observation": {
                "native_type": "Extrusion",
                "type": "extrude",
                "error_code": 0,
                "is_warning": False,
                "suppressed": False,
                "parents": ["f73"],
                "completeness": {"type": "present"},
            },
        },
        "sketch_holes": {
            "native_id": 80,
            "feature_id": "f80",
            "entity_count": 4,
            "observation": {
                "native_type": "ProfileFeature",
                "type": "sketch",
                "error_code": 0,
                "is_warning": False,
                "suppressed": False,
                "parents": [],
                "completeness": {"type": "present"},
            },
        },
        "cut_holes": {
            "native_id": 86,
            "feature_id": "f86",
            "status": "ok",
            "observation": {
                "native_type": "ICE",
                "type": "cut_extrude",
                "error_code": 0,
                "is_warning": False,
                "suppressed": False,
                "parents": ["f80"],
                "completeness": {"type": "present"},
            },
        },
    }
    rig = PartRig(op_results=op_results)
    job_id = rig.submit()
    flushed_before_apply: list[JournalRecord] = []

    def _before(name: str) -> None:
        if name == "apply_ops":
            flushed_before_apply.append(rig.journal(job_id)[-1])

    rig.backend.before = _before
    assert rig.engine.run_next()

    assert all(isinstance(r, BatchSentRecord) for r in flushed_before_apply)

    # Check journal for BatchSentRecord and DocumentRecord before part.create
    journal = rig.journal(job_id)
    doc_create_idx = next(
        i for i, r in enumerate(journal) if isinstance(r, DocumentRecord) and r.action == "create"
    )
    first_batch_idx = next(i for i, r in enumerate(journal) if isinstance(r, BatchSentRecord))
    assert doc_create_idx < first_batch_idx

    # Inspect calls made to apply_ops: 1 op per batch, working path on every batch
    work_p = working_path(TARGET_PATH, job_id)
    apply_calls = [c for c in rig.backend.calls if c.name == "apply_ops"]
    for call in apply_calls:
        groups = cast("tuple[OperationGroup, ...]", call.args[0])
        assert len(groups) == 1
        assert groups[0].document == work_p
        assert len(groups[0].operations) == 1

    # Check that feature.create had bound profiles
    ops_sent = [
        op
        for c in apply_calls
        for g in cast("tuple[OperationGroup, ...]", c.args[0])
        for op in g.operations
    ]
    extrude_op = next(
        o
        for o in ops_sent
        if o.op == "feature.create"
        and isinstance(o.params, dict)
        and o.params.get("node_id") == "extrude_base"
    )
    assert isinstance(extrude_op.params, dict)
    assert extrude_op.params["profile"] == "f73"
    cut_op = next(
        o
        for o in ops_sent
        if o.op == "feature.create"
        and isinstance(o.params, dict)
        and o.params.get("node_id") == "cut_holes"
    )
    assert isinstance(cut_op.params, dict)
    assert cut_op.params["profile"] == "f80"


def test_measures_twice() -> None:
    rig = PartRig()
    rig.submit()
    assert rig.engine.run_next()

    measure_calls = [c for c in rig.backend.calls if c.name == "measure_part"]
    expected_calls = 2
    assert len(measure_calls) == expected_calls


def test_same_instance_on_reopen_fails() -> None:
    # Reopen returns same instance_id
    op_results: dict[str, JsonValue] = {
        "part.create": {"native_id": 1, "instance_id": "inst_1"},
        "document.open": {"owned": True, "instance_id": "inst_1"},  # Same!
    }
    rig = PartRig(op_results=op_results)
    job_id = rig.submit()
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "FAILED"
    assert rec.error is not None
    assert rec.error["code"] == ErrorCode.BACKEND_OPERATION_FAILED.value
    assert rig.fs.stat(TARGET_PATH) is None


def test_still_open_after_close_fails() -> None:
    op_results: dict[str, JsonValue] = {
        "document.close": {"closed": False},
    }
    rig = PartRig(op_results=op_results)
    job_id = rig.submit()
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "FAILED"
    assert rec.error is not None
    assert rec.error["code"] == ErrorCode.BACKEND_OPERATION_FAILED.value


def test_fingerprint_change_fails() -> None:
    rig = PartRig()
    # Change file between reopen and publish
    orig_apply = rig.backend.apply_ops

    def _alter_file(groups: Sequence[OperationGroup], *, meta: Meta | None = None) -> Any:
        res = orig_apply(groups, meta=meta)
        for g in groups:
            for op in g.operations:
                if op.op == "document.open":
                    # Alter the working file!
                    rig.fs.write_atomic(g.document, b"MODIFIED_CORRUPTED_BYTES")
        return res

    rig.backend.apply_ops = _alter_file
    job_id = rig.submit()
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "FAILED"
    assert rec.error is not None
    assert rec.error["code"] == ErrorCode.PART_VERIFICATION_FAILED.value
    assert rig.fs.stat(TARGET_PATH) is None


def test_publish_rechecks_path() -> None:
    rig = PartRig()
    # Before publish rename, change settings to remove allowed roots
    orig_apply = rig.backend.apply_ops

    def _remove_root(groups: Sequence[OperationGroup], *, meta: Meta | None = None) -> Any:
        res = orig_apply(groups, meta=meta)
        for g in groups:
            for op in g.operations:
                if op.op == "document.open":
                    rig.user_settings = replace(rig.user_settings, allowed_roots=())
        return res

    rig.backend.apply_ops = _remove_root
    job_id = rig.submit()
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "FAILED"
    assert rec.error is not None
    assert rec.error["code"] == ErrorCode.AUTH_PATH_DENIED.value
    assert rig.fs.stat(TARGET_PATH) is None


def test_publish_order() -> None:
    rig = PartRig()
    job_id = rig.submit()
    assert rig.engine.run_next()

    journal = rig.journal(job_id)
    pi_idx = next(i for i, r in enumerate(journal) if isinstance(r, PublishIntentRecord))
    pub_idx = next(i for i, r in enumerate(journal) if isinstance(r, PublishedRecord))
    committed_idx = next(
        i for i, r in enumerate(journal) if isinstance(r, StateRecord) and r.to == "COMMITTED"
    )
    assert pi_idx < pub_idx < committed_idx


def test_cancel_after_publish_intent_has_no_effect() -> None:
    rig = PartRig()
    job_id = rig.submit()
    orig_rename = rig.fs.rename_new

    def _cancel_on_rename(src: str, dst: str) -> None:
        if dst == TARGET_PATH:
            rig.engine.cancel(job_id)
        orig_rename(src, dst)

    rig.fs.rename_new = _cancel_on_rename  # type: ignore[method-assign]
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "COMMITTED"
    assert rig.fs.stat(TARGET_PATH) is not None


def test_cancel_before_publish_intent_aborts() -> None:
    rig = PartRig()
    job_id = rig.submit()
    measure_count = 0
    second_measure = 2

    def _cancel_on_second_measure(doc_path: str) -> Any:
        del doc_path
        nonlocal measure_count
        measure_count += 1
        if measure_count == second_measure:
            rig.engine.cancel(job_id)
        return _make_plate_measurement()

    rig.backend._measurement = _cancel_on_second_measure  # type: ignore[attr-defined]
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "ABORTED"
    assert rig.fs.stat(TARGET_PATH) is None
    assert not any(isinstance(r, PublishIntentRecord) for r in rig.journal(job_id))


def test_failed_contract_stops_the_job() -> None:
    bad_observations: tuple[dict[str, JsonValue], ...] = (
        {
            "native_type": "ProfileFeature",
            "type": "sketch",
            "error_code": 1,
            "is_warning": False,
            "suppressed": False,
            "parents": [],
            "completeness": {"type": "present"},
        },
        {
            "native_type": "Extrusion",
            "type": "extrude",
            "error_code": 0,
            "is_warning": False,
            "suppressed": False,
            "parents": [],
            "completeness": {"type": "present"},
        },
        {
            "native_type": "ProfileFeature",
            "type": "sketch",
            "error_code": 0,
            "is_warning": True,
            "suppressed": False,
            "parents": [],
            "completeness": {"type": "present"},
        },
    )
    for bad_obs in bad_observations:
        op_results: dict[str, JsonValue] = {
            "sketch.create": {
                "native_id": 73,
                "feature_id": "f73",
                "entity_count": 4,
                "observation": bad_obs,
            },
        }
        rig = PartRig(op_results=op_results)
        job_id = rig.submit()
        assert rig.engine.run_next()

        rec = rig.job(job_id)
        assert rec.state == "FAILED"
        assert rec.error is not None
        assert rec.error["code"] == ErrorCode.FEATURE_VERIFICATION_FAILED.value
        details = rec.error["details"]
        assert isinstance(details, dict)
        assert details["node"] == "sketch_base"

        # No further build ops sent (only part.create, sketch.create, then save + close)
        apply_calls = [c for c in rig.backend.calls if c.name == "apply_ops"]
        ops_sent = [
            op.op
            for c in apply_calls
            for g in cast("tuple[OperationGroup, ...]", c.args[0])
            for op in g.operations
        ]
        assert ops_sent == ["part.create", "sketch.create", "document.save", "document.close"]

        # op_verified journalled before FAILED
        journal = rig.journal(job_id)
        ver_idx = next(i for i, r in enumerate(journal) if isinstance(r, OpVerifiedRecord))
        fail_idx = next(
            i for i, r in enumerate(journal) if isinstance(r, StateRecord) and r.to == "FAILED"
        )
        assert ver_idx < fail_idx
        verified = [r for r in journal if isinstance(r, OpVerifiedRecord)]
        assert len(verified) == 1
        assert verified[0].node == "sketch_base"
        assert verified[0].status == "failed"


def test_wrong_volume_fails() -> None:
    meas = _make_plate_measurement()
    meas["volume_m3"] = 1.0  # Completely wrong volume
    rig = PartRig(measurement=meas)
    job_id = rig.submit()
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "FAILED"
    assert rec.error is not None
    assert rec.error["code"] == ErrorCode.PART_VERIFICATION_FAILED.value
    assert rig.fs.stat(TARGET_PATH) is None

    # .failed present and named
    fail_p = failed_path(TARGET_PATH, job_id)
    assert rig.fs.stat(fail_p) is not None
    details = rec.error["details"]
    assert isinstance(details, dict)
    assert details["failed_path"] == fail_p
    assert details["checks"] == ["volume"]


def test_reopen_mismatch_fails() -> None:
    call_count = 0
    second_call = 2

    def _measure_hook(doc_path: str) -> Any:
        nonlocal call_count
        call_count += 1
        m = _make_plate_measurement()
        if call_count == second_call:
            m["volume_m3"] = 0.001  # Wrong only on second measurement
        return m

    rig = PartRig(measurement=_measure_hook)
    job_id = rig.submit()
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "FAILED"
    assert rec.error is not None
    assert rec.error["code"] == ErrorCode.PART_VERIFICATION_FAILED.value


def test_op_error_fails_and_keeps_file() -> None:
    # Operation failure in apply_ops
    rig = PartRig()
    orig_apply = rig.backend.apply_ops

    def _fail_op(groups: Sequence[OperationGroup], *, meta: Meta | None = None) -> Any:
        for g in groups:
            for op in g.operations:
                if op.op == "feature.create":
                    raise BackendCallError("BACKEND_REBUILD_ERROR", "Extrusion failed.")
        return orig_apply(groups, meta=meta)

    rig.backend.apply_ops = _fail_op
    job_id = rig.submit()
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "FAILED"
    assert rec.error is not None
    assert rec.error["code"] == "BACKEND_REBUILD_ERROR"
    # .failed file kept
    fail_p = failed_path(TARGET_PATH, job_id)
    assert rig.fs.stat(fail_p) is not None


def test_cancel_removes_working() -> None:
    rig = PartRig()
    # Cancel when sketch.create is sent
    orig_apply = rig.backend.apply_ops

    def _cancel_during_op(groups: Sequence[OperationGroup], *, meta: Meta | None = None) -> Any:
        for g in groups:
            for op in g.operations:
                if op.op == "sketch.create":
                    rig.engine.cancel(job_id)
        return orig_apply(groups, meta=meta)

    rig.backend.apply_ops = _cancel_during_op
    job_id = rig.submit()
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "ABORTED"
    work_p = working_path(TARGET_PATH, job_id)
    assert rig.fs.stat(work_p) is None
    assert rig.fs.stat(TARGET_PATH) is None
    # changes names the deleted file
    assert rec.error is not None
    details = rec.error["details"]
    assert isinstance(details, dict)
    changes = details["changes"]
    assert isinstance(changes, list)
    assert any(
        isinstance(c, dict) and c.get("document") == work_p and c.get("action") == "deleted"
        for c in changes
    )


def test_keep_partial_renames() -> None:
    rig = PartRig()
    orig_apply = rig.backend.apply_ops

    def _cancel_during_op(groups: Sequence[OperationGroup], *, meta: Meta | None = None) -> Any:
        for g in groups:
            for op in g.operations:
                if op.op == "sketch.create":
                    rig.engine.cancel(job_id, keep_partial=True)
        return orig_apply(groups, meta=meta)

    rig.backend.apply_ops = _cancel_during_op
    job_id = rig.submit()
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "ABORTED"
    part_p = partial_path(TARGET_PATH, job_id)
    assert rig.fs.stat(part_p) is not None
    assert rig.fs.stat(TARGET_PATH) is None
    assert rec.error is not None
    details = rec.error["details"]
    assert isinstance(details, dict)
    changes = details["changes"]
    assert isinstance(changes, list)
    assert any(
        isinstance(c, dict) and c.get("document") == part_p and c.get("action") == "renamed"
        for c in changes
    )


def test_backend_lost_leaves_files() -> None:
    for code in (
        ErrorCode.BACKEND_LOST.value,
        ErrorCode.BACKEND_UI_BLOCKED.value,
        ErrorCode.EXEC_TIMEOUT.value,
        ErrorCode.EXEC_INTERRUPTED_BY_USER.value,
    ):
        rig = PartRig()
        orig_apply = rig.backend.apply_ops

        def _fail_backend(
            groups: Sequence[OperationGroup],
            *,
            meta: Meta | None = None,
            err_code: str = code,
            apply_fn: Any = orig_apply,
        ) -> Any:
            for g in groups:
                for op in g.operations:
                    if op.op == "feature.create":
                        raise BackendCallError(err_code, f"Backend error {err_code}")
            return apply_fn(groups, meta=meta)

        rig.backend.apply_ops = _fail_backend
        job_id = rig.submit()
        assert rig.engine.run_next()

        rec = rig.job(job_id)
        assert rec.state == "FAILED"
        work_p = working_path(TARGET_PATH, job_id)
        # Working file left alone, no document.close sent
        assert rig.fs.stat(work_p) is not None
        apply_calls = [c for c in rig.backend.calls if c.name == "apply_ops"]
        ops_sent = [
            op.op
            for c in apply_calls
            for g in cast("tuple[OperationGroup, ...]", c.args[0])
            for op in g.operations
        ]
        assert "document.close" not in ops_sent
        # Document marked unknown
        assert len(rec.documents) == 1
        assert rec.documents[0].state == "unknown"


def test_foreign_event_fails() -> None:
    for event_kind in ("regen", "save", "close"):
        rig = PartRig()
        orig_apply = rig.backend.apply_ops

        def _trigger_event(
            groups: Sequence[OperationGroup],
            *,
            meta: Meta | None = None,
            ev: str = event_kind,
            apply_fn: Any = orig_apply,
            r: PartRig = rig,
        ) -> Any:
            for g in groups:
                for op in g.operations:
                    if op.op == "feature.create":
                        r.provider.notify(
                            "document.event",
                            {"document": g.document, "event": ev},
                        )
            return apply_fn(groups, meta=meta)

        rig.backend.apply_ops = _trigger_event
        job_id = rig.submit()
        assert rig.engine.run_next()

        rec = rig.job(job_id)
        assert rec.state == "FAILED"
        assert rec.error is not None
        assert rec.error["code"] == ErrorCode.EXEC_INTERRUPTED_BY_USER.value


def test_two_jobs_same_target() -> None:
    rig = PartRig()
    job1_id = rig.submit()
    assert rig.engine.run_next()
    assert rig.job(job1_id).state == "COMMITTED"
    orig_bytes = rig.fs.read_bytes(TARGET_PATH)

    # Second job with same target path
    job2_id = rig.submit()
    assert rig.engine.run_next()
    rec2 = rig.job(job2_id)
    assert rec2.state == "FAILED"
    assert rec2.error is not None
    assert rec2.error["code"] == ErrorCode.AUTH_SOURCE_WRITE_NOT_ALLOWED.value
    assert rec2.error.get("details") is None
    # Target unchanged
    assert rig.fs.read_bytes(TARGET_PATH) == orig_bytes


def test_rename_blocked() -> None:
    rig = PartRig()
    orig_rename = rig.fs.rename_new

    # Make rename_new fail with persistent lock / error only when renaming to TARGET_PATH
    def _fail_rename(src: str, dst: str) -> None:
        if dst == TARGET_PATH:
            raise OSError("Access is denied")
        orig_rename(src, dst)

    rig.fs.rename_new = _fail_rename  # type: ignore[method-assign]
    job_id = rig.submit()
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "FAILED"
    assert rig.fs.stat(TARGET_PATH) is None
    assert rig.fs.stat(failed_path(TARGET_PATH, job_id)) is None
    # Working file kept and named
    work_p = working_path(TARGET_PATH, job_id)
    assert rig.fs.stat(work_p) is not None
    assert rec.error is not None
    details = rec.error["details"]
    assert isinstance(details, dict)
    assert details["working_path"] == work_p
    assert "failed_path" not in details


def test_close_after_final_state() -> None:
    rig = PartRig()
    job_id = rig.submit()
    state_at_close: list[str] = []

    orig_close = rig.backend.close

    def _track_close() -> None:
        state_at_close.append(rig.job(job_id).state)
        orig_close()

    rig.backend.close = _track_close  # type: ignore[method-assign]
    assert rig.engine.run_next()

    rec = rig.job(job_id)
    assert rec.state == "COMMITTED"
    assert rig.backend.closed is True
    assert state_at_close == ["COMMITTED"]

    # A failing close only logs backend.close_failed and does not change the job outcome
    rig2 = PartRig()
    job2_id = rig2.submit(rig2.spec(target="C:\\Work\\plate_close_err.SLDPRT"))

    def _boom_close() -> None:
        raise RuntimeError("pipe close failed")

    rig2.backend.close = _boom_close  # type: ignore[method-assign]
    assert rig2.engine.run_next()
    assert rig2.job(job2_id).state == "COMMITTED"
    assert any(e.event == "backend.close_failed" for e in rig2.log.events)

    # Also verify backend.close() runs for check_drawing jobs too
    dwg_rig = make_rig(snapshot={"schema_version": "0.1"})
    dwg_job = dwg_rig.submit()
    assert dwg_rig.engine.run_next()
    assert dwg_rig.job(dwg_job.job_id).state == "FAILED"
    assert dwg_rig.backend.closed is True


def test_second_job_reconnects() -> None:
    rig = PartRig()
    rig.submit()
    assert rig.engine.run_next()
    assert rig.backend.closed is True

    # Second job with different target
    spec2 = rig.spec(target="C:\\Work\\plate2.SLDPRT")
    job2_id = rig.submit(spec2)
    assert rig.engine.run_next()
    assert rig.job(job2_id).state == "COMMITTED"


class _HookReplayTransport(ReplayTransport):
    def __init__(self, transcript: Any, on_sketch: Any = None) -> None:
        super().__init__(transcript)
        self._on_sketch = on_sketch

    def receive(self, timeout_s: float) -> bytes:
        data = super().receive(timeout_s)
        if self._on_sketch is not None and self._sent:
            last = self._sent[-1]
            groups = last.get("params", {}).get("groups", [])
            if any(
                op.get("op") == "sketch.create" for g in groups for op in g.get("operations", [])
            ):
                cb, self._on_sketch = self._on_sketch, None
                cb()
        return data


def _replay_plan_transcript(
    scenario: str, *, cancel_on_sketch: bool = False
) -> tuple[JobRecord, MemoryFileSystem, _HookReplayTransport]:
    text = (ROOT / "tests" / "fixtures" / "ipc" / f"{scenario}.jsonl").read_text(encoding="utf-8")
    transcript = load_transcript(text)
    fs = MemoryFileSystem()
    clock = FakeClock()
    ids = SequentialIdSource()
    log = ListEventLog()
    fs.make_dirs(PROJECT_ROOT)
    fs.make_dirs("C:\\Templates")
    fs.write_new(TEMPLATE_PATH, b"TEMPLATE_CONTENT")

    stores = StoreSet(fs, clock, KNOWN_STORES)
    auth = Authorized(TARGET_PATH, PROJECT_ROOT, PROJECT_ROOT, STORE_DIR, False)
    store = stores.open_for(auth)
    assert isinstance(store, FileStore)
    plate_raw = json.loads(PLATE_FIXTURE.read_text(encoding="utf-8"))
    store.put_part_revision("part:plate_4h", plate_raw, None)

    engine_holder: list[JobEngine] = []
    job_id_holder: list[str] = []

    def _trigger_cancel() -> None:
        if cancel_on_sketch and engine_holder and job_id_holder:
            engine_holder[0].cancel(job_id_holder[0])

    transport = _HookReplayTransport(
        transcript, on_sketch=_trigger_cancel if cancel_on_sketch else None
    )

    class _ReplayProvider:
        def acquire(self, on_notification: NotificationHandler) -> IpcBackend:
            client = IpcClient(
                transport,
                token=transcript.header.config["token"],
                on_notification=on_notification,
                monotonic=lambda: 0.0,
            )
            return IpcBackend(client)

    user_settings = Settings(allowed_roots=(PROJECT_ROOT,), part_template=TEMPLATE_PATH)
    engine = JobEngine(
        stores,
        _ReplayProvider(),
        clock,
        ids,
        log,
        lambda _root: user_settings,
        lambda _s: {},
    )
    engine_holder.append(engine)
    spec = PlanSpec(authorized=auth, target_path=TARGET_PATH, ref="part:plate_4h@1", template=None)
    view = engine.submit(spec, ids.new_id("req"))
    assert isinstance(view, JobView)
    job_id = view.job_id
    job_id_holder.append(job_id)

    # Pre-seed the working file so filesystem operations after save/create see the file bytes
    fs.write_new(working_path(TARGET_PATH, job_id), b"SLDPRT_CONTENT")

    assert engine.run_next()
    rec = store.get_job(job_id)
    assert isinstance(rec, JobRecord)
    return rec, fs, transport


def test_transcript_replay_committed() -> None:
    rec, fs, transport = _replay_plan_transcript("plan_plate_committed")
    assert rec.state == "COMMITTED"
    assert fs.stat(TARGET_PATH) is not None
    assert transport.exhausted
    assert transport.closed


def test_transcript_replay_op_failed() -> None:
    rec, fs, transport = _replay_plan_transcript("plan_op_failed")
    assert rec.state == "FAILED"
    assert rec.error is not None
    assert rec.error["code"] == "BACKEND_REBUILD_ERROR"
    assert fs.stat(failed_path(TARGET_PATH, rec.job_id)) is not None
    assert transport.exhausted
    assert transport.closed


def test_transcript_replay_wrong_volume() -> None:
    rec, fs, transport = _replay_plan_transcript("plan_wrong_volume")
    assert rec.state == "FAILED"
    assert rec.error is not None
    assert rec.error["code"] == ErrorCode.PART_VERIFICATION_FAILED.value
    assert fs.stat(failed_path(TARGET_PATH, rec.job_id)) is not None
    assert transport.exhausted
    assert transport.closed


def test_transcript_replay_cancelled() -> None:
    rec, fs, transport = _replay_plan_transcript("plan_cancelled", cancel_on_sketch=True)
    assert rec.state == "ABORTED"
    assert fs.stat(working_path(TARGET_PATH, rec.job_id)) is None
    assert fs.stat(TARGET_PATH) is None
    assert transport.exhausted
    assert transport.closed


def test_transcript_replay_backend_lost() -> None:
    rec, fs, transport = _replay_plan_transcript("plan_backend_lost")
    assert rec.state == "FAILED"
    assert rec.error is not None
    assert rec.error["code"] == ErrorCode.BACKEND_LOST.value
    assert fs.stat(working_path(TARGET_PATH, rec.job_id)) is not None
    assert len(rec.documents) == 1
    assert rec.documents[0].state == "unknown"
    assert transport.exhausted
    assert transport.closed


def test_transcript_replay_recorded() -> None:
    text = (ROOT / "tests" / "fixtures" / "ipc" / "plan_plate_recorded.jsonl").read_text(
        encoding="utf-8"
    )
    transcript = load_transcript(text)
    assert transcript.header.source == "recorded"

    fs = MemoryFileSystem()
    clock = FakeClock()
    ids = SequentialIdSource()
    log = ListEventLog()
    fs.make_dirs(PROJECT_ROOT)
    fs.make_dirs("C:\\Templates")
    fs.write_new(TEMPLATE_PATH, b"TEMPLATE_CONTENT")

    stores = StoreSet(fs, clock, KNOWN_STORES)
    transport = _HookReplayTransport(transcript)

    class _ReplayProvider:
        def acquire(self, on_notification: NotificationHandler) -> IpcBackend:
            client = IpcClient(
                transport,
                token=transcript.header.config["token"],
                on_notification=on_notification,
                monotonic=lambda: 0.0,
            )
            return IpcBackend(client)

    user_settings = Settings(allowed_roots=(PROJECT_ROOT,), part_template=TEMPLATE_PATH)
    engine = JobEngine(
        stores,
        _ReplayProvider(),
        clock,
        ids,
        log,
        lambda _root: user_settings,
        lambda _s: {},
    )
    ctx = ToolContext(
        engine=engine,
        stores=stores,
        fs=fs,
        clock=clock,
        settings_user=user_settings,
        project_settings=lambda _root: user_settings,
        log=log,
    )
    service = CoreService(
        engine,
        build_registry(ctx),
        stores,
        ids,
        log,
        settings=user_settings,
    )

    plate_raw = json.loads(PLATE_FIXTURE.read_text(encoding="utf-8"))
    apply_res = service.call_tool(
        "apply_part_graph",
        {"graph": plate_raw, "target_path": TARGET_PATH},
    )
    apply_env = cast(dict[str, Any], apply_res.envelope)
    assert apply_env["ok"] is True
    job_id = str(cast(dict[str, Any], apply_env["data"])["execution_id"])

    fs.write_new(working_path(TARGET_PATH, job_id), b"SLDPRT_RECORDED_BYTES")
    assert engine.run_next()

    status_res = service.call_tool("get_execution_status", {"execution_id": job_id})
    status_env = cast(dict[str, Any], status_res.envelope)
    assert status_env["ok"] is True
    status_data = cast(dict[str, Any], status_env["data"])
    assert status_data["state"] == "COMMITTED"
    assert fs.stat(TARGET_PATH) is not None
    part_result = cast(dict[str, Any], status_data["part_result"])
    assert part_result["path"] == TARGET_PATH
    assert part_result["feature_ids"] == {
        "sketch_base": "f73",
        "extrude_base": "f79",
        "sketch_holes": "f80",
        "cut_holes": "f86",
    }
    assert transport.exhausted
    assert transport.closed


def test_depth_altering_provider_fails_plan() -> None:
    observed_depths: list[float] = []

    def _measure_from_depth(_doc_path: str) -> Any:
        depth_mm = observed_depths[-1] if observed_depths else 10.0
        scale = depth_mm / 10.0
        meas = _make_plate_measurement()
        meas["volume_m3"] = meas["volume_m3"] * scale
        meas["bbox_m"] = {
            "min": [-0.05, -0.03, 0.0],
            "max": [0.05, 0.03, 0.01 * scale],
        }
        return meas

    rig = PartRig(measurement=_measure_from_depth)
    orig_apply = rig.backend.apply_ops

    def _capture_depth(groups: Sequence[OperationGroup], *, meta: Meta | None = None) -> Any:
        for g in groups:
            for op in g.operations:
                if (
                    op.op == "feature.create"
                    and isinstance(op.params, dict)
                    and op.params.get("node_id") == "extrude_base"
                ):
                    ec = op.params.get("end_condition")
                    if isinstance(ec, dict):
                        depth_val = ec.get("depth")
                        if isinstance(depth_val, int | float) and not isinstance(depth_val, bool):
                            observed_depths.append(float(depth_val))
        return orig_apply(groups, meta=meta)

    rig.backend.apply_ops = _capture_depth
    rig.engine = JobEngine(
        rig.stores,
        DepthAlteringBackendProvider(rig.provider, target_node="extrude_base", new_depth=9.0),
        rig.clock,
        rig.ids,
        rig.log,
        lambda _root: rig.user_settings,
        lambda _s: {},
    )

    job_id = rig.submit()
    assert rig.engine.run_next()
    assert observed_depths == [9.0]

    rec = rig.job(job_id)
    assert rec.state == "FAILED"
    assert rec.error is not None
    assert rec.error["code"] == ErrorCode.PART_VERIFICATION_FAILED.value
    assert rig.fs.stat(TARGET_PATH) is None
    fail_p = failed_path(TARGET_PATH, job_id)
    assert rig.fs.stat(fail_p) is not None
    details = rec.error["details"]
    assert isinstance(details, dict)
    assert details["failed_path"] == fail_p

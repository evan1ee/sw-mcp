"""The ``plan`` job (spec 8.4, design 8): compile, create, build, verify, publish.

Backend errors are read through their ``code`` attribute (see ``ports``), so this module never
imports an IPC type. ``JobStop`` carries a failure or a cancellation out of any step; ``_stopped``
turns it into the final state after cleaning up the working file.
"""

import contextlib
import hashlib
import ntpath
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Final, cast

from cad_compiler.api import (
    CompileContext,
    CompileInput,
    compile_bundle,
)
from cad_compiler.profile import CapabilityProfile
from cad_compiler.validator.semantic import validate_graph
from cad_ir.bundle.manifest import BundleManifest
from cad_ir.core.json_types import JsonValue
from cad_ir.core.refs import parse_document_ref
from cad_ir.generated.error_codes import ErrorCode
from cad_ir.generated.ipc import HelloResult, Meta, Operation, OperationGroup
from cad_ir.part_feature_graph.model import PartGraph
from cad_ir.part_feature_graph.parse import parse_part_graph
from cad_verification import (
    CheckResult,
    ExpectedGeometry,
    compare,
    evaluate,
    expected_geometry,
    feature_contracts,
)

from cad_application.config.settings import Settings
from cad_application.jobs.handle import JobHandle
from cad_application.jobs.model import JobStop, Outcome, PlanSpec
from cad_application.jobs.part_files import failed_path, partial_path, working_path
from cad_application.paths import ToolError, authorize
from cad_application.ports import Backend, BackendProvider, Clock, EventLog, FileSystem, IdSource
from cad_application.store.job_records import JobDocument
from cad_application.store.journal_records import (
    BatchSentRecord,
    DocumentRecord,
    NoteRecord,
    OpResultRecord,
    OpVerifiedRecord,
    PublishedRecord,
    PublishIntentRecord,
)
from cad_application.store.records import JobWarning, PartRecord

_STEPS: Final = 6
_CAPABILITIES: Final = ("ops.apply", "part.measure")
_OPERATIONS: Final = (
    "part.create",
    "sketch.create",
    "feature.create",
    "document.open",
    "document.save",
    "document.close",
    "document.rebuild",
)
_NO_CLOSE: Final = frozenset(
    {
        ErrorCode.BACKEND_LOST.value,
        ErrorCode.BACKEND_UI_BLOCKED.value,
        ErrorCode.EXEC_TIMEOUT.value,
        ErrorCode.EXEC_INTERRUPTED_BY_USER.value,
    }
)


def resolve_node_refs(
    op_name: str, params: dict[str, JsonValue], feature_ids: dict[str, str]
) -> dict[str, JsonValue]:
    """Swap node ids in an operation's parameters for the feature ids the add-in returned.

    ``feature.create`` names its profile sketch; ``sketch.create`` names the extrude whose cap
    face it sits on (ADR-070). An id not yet known is left as it is. The input is not changed.
    """
    resolved = dict(params)
    if op_name == "feature.create":
        profile = resolved.get("profile")
        if isinstance(profile, str) and profile in feature_ids:
            resolved["profile"] = feature_ids[profile]
    elif op_name == "sketch.create":
        face = resolved.get("face")
        if isinstance(face, dict):
            node = face.get("feature")
            if isinstance(node, str) and node in feature_ids:
                resolved["face"] = {**face, "feature": feature_ids[node]}
    return resolved


@dataclass(frozen=True, slots=True)
class RunContext:
    handle: JobHandle[PlanSpec]
    provider: BackendProvider
    ids: IdSource
    log: EventLog
    settings_for: Callable[[str], Settings]
    fs: FileSystem
    clock: Clock

    @property
    def settings(self) -> Settings:
        return self.settings_for(self.handle.record.project_root)


def run(ctx: RunContext) -> Outcome:
    """Run the plan job to a final state; every state change goes through ``ctx.handle``."""
    return _Run(ctx).execute()


def _stop_from(error: Exception) -> JobStop | None:
    code = getattr(error, "code", None)
    if not isinstance(code, str):
        return None
    message = getattr(error, "message", None)
    details = getattr(error, "details", None)
    text = message if isinstance(message, str) else "The backend call failed."
    return JobStop(code, text, cast("JsonValue", details))


def _check_result_dict(r: CheckResult, stage: str) -> dict[str, Any]:
    res: dict[str, Any] = {
        "check": r.requirement,
        "stage": stage,
        "status": r.status,
        "requirement": r.requirement,
        "expected": r.expected,
        "measured": r.measured,
        "method": r.method,
    }
    if r.reason is not None:
        res["reason"] = r.reason
    if r.tolerance is not None:
        kind = "relative" if r.requirement in ("volume", "surface_area") else "absolute"
        res["tolerance"] = {"kind": kind, "value": r.tolerance}
    return res


class _Run:
    def __init__(self, ctx: RunContext) -> None:
        self._ctx = ctx
        self._h = ctx.handle
        assert isinstance(ctx.handle.spec, PlanSpec)
        self._spec: PlanSpec = ctx.handle.spec
        self._target_path = self._spec.target_path
        self._work_path = working_path(self._target_path, self._h.record.job_id)
        self._backend: Backend | None = None
        self._open = False
        self._owned = False
        self._read_only = False
        self._batches = 0
        self._template: str = ""
        self._graph: PartGraph | None = None
        self._geom: ExpectedGeometry | None = None
        self._plan: dict[str, Any] | None = None
        self._plan_hash: str | None = None
        self._feature_ids: dict[str, str] = {}
        self._first_instance_id: str | None = None
        self._in_publish = False
        self._last_op_id: str = ""

    def execute(self) -> Outcome:
        try:
            backend = self._validate()
            self._execute_plan(backend)
            self._verify_and_commit(backend)
        except JobStop as stop:
            return self._stopped(stop)
        except Exception:
            self._stopped(
                JobStop(
                    ErrorCode.EXEC_INTERRUPTED.value, "Unexpected exception during job execution."
                )
            )
            raise
        return Outcome("COMMITTED")

    # --- PLANNED -> VALIDATED ----------------------------------------------------------

    def _validate(self) -> Backend:
        try:
            backend = self._ctx.provider.acquire(self._h.on_notification)
        except Exception as error:
            stop = _stop_from(error)
            if stop is None:
                raise
            raise stop from error

        self._backend = backend
        self._h.set_backend(backend)
        self._note_session_warnings(backend.session)
        self._checkpoint()
        self._require_capabilities(backend.session)

        self._template = self._resolve_template()

        # Re-check target does not exist on disk
        if self._ctx.fs.stat(self._target_path) is not None:
            raise JobStop(
                ErrorCode.AUTH_SOURCE_WRITE_NOT_ALLOWED.value,
                f"Target file already exists: {self._target_path}",
            )

        raw_doc, parsed = self._load_graph()
        self._graph = parsed
        self._geom = expected_geometry(parsed)

        self._plan, self._plan_hash = self._compile_plan(backend, raw_doc)

        self._h.advance("VALIDATED", "backend acquired; plan compiled")
        return backend

    def _resolve_template(self) -> str:
        template = self._spec.template or self._ctx.settings.part_template
        if not template:
            raise JobStop(
                ErrorCode.CONFIG_INVALID.value,
                "part.template setting is not configured.",
                {"setting": "part.template"},
            )
        if self._ctx.fs.stat(template) is None:
            raise JobStop(
                ErrorCode.FILE_NOT_FOUND.value,
                f"Part template file not found: {template}",
                {"setting": "part.template"},
            )
        return template

    def _load_graph(self) -> tuple[dict[str, JsonValue], PartGraph]:
        raw_doc = self._h.store.get_part_revision(self._spec.ref)
        if not isinstance(raw_doc, dict):
            raise JobStop(
                ErrorCode.IR_MODULE_MISSING.value,
                f"Part revision '{self._spec.ref}' not found in store.",
            )

        parsed = parse_part_graph(raw_doc)
        if not isinstance(parsed, PartGraph):
            raise JobStop(
                ErrorCode.IR_SCHEMA_INVALID.value,
                "Part graph is invalid.",
                {"issue_count": len(parsed.issues)},
            )
        semantic_issues = validate_graph(parsed)
        if any(i.severity == "error" for i in semantic_issues):
            first_err = next(i for i in semantic_issues if i.severity == "error")
            raise JobStop(first_err.code.value, first_err.message)
        return raw_doc, parsed

    def _compile_plan(
        self, backend: Backend, raw_doc: dict[str, JsonValue]
    ) -> tuple[dict[str, Any], str | None]:
        doc_ref = parse_document_ref(self._spec.ref)
        manifest = BundleManifest(
            bundle_schema_version="1.0",
            modules=(doc_ref,),
        )
        source = CompileInput(
            manifest=manifest,
            documents={str(doc_ref): raw_doc},
        )
        profile = CapabilityProfile.from_session(backend.session)
        compile_ctx = CompileContext(
            compiler_version="0.1.0",
            profile=profile,
            defaults={},
        )
        compile_res = compile_bundle(source, compile_ctx)
        if compile_res.plan is None or any(d.severity == "error" for d in compile_res.diagnostics):
            err_diag = next((d for d in compile_res.diagnostics if d.severity == "error"), None)
            code = err_diag.code.value if err_diag else ErrorCode.COMPILE_UNSUPPORTED_FEATURE.value
            msg = err_diag.message if err_diag else "Failed to compile bundle."
            raise JobStop(code, msg)

        plan = cast(dict[str, Any], compile_res.plan)
        plan_hash = compile_res.plan_hash

        if plan_hash is not None and not self._h.store.put_plan(plan_hash, plan):
            self._h.append(
                NoteRecord(
                    self._h.timestamp(),
                    self._h.record.job_id,
                    f"reused existing plan {plan_hash}",
                )
            )
        return plan, plan_hash

    def _note_session_warnings(self, session: HelloResult) -> None:
        found = tuple(JobWarning("solidworks_version_warning", w) for w in session.warnings)
        if found:
            self._h.edit(lambda r: replace(r, warnings=(*r.warnings, *found)))

    def _require_capabilities(self, session: HelloResult) -> None:
        operations = {o.op for o in session.operations}
        missing = [c for c in _CAPABILITIES if c not in session.capabilities]
        missing += [op for op in _OPERATIONS if op not in operations]
        if missing:
            raise JobStop(
                ErrorCode.BACKEND_CAPABILITY_MISSING.value,
                "The SOLIDWORKS add-in lacks a capability this job needs.",
                {"missing": cast("list[JsonValue]", missing)},
            )

    # --- VALIDATED -> EXECUTING --------------------------------------------------------

    def _execute_plan(self, backend: Backend) -> None:
        assert self._graph is not None
        assert self._plan is not None

        contracts = feature_contracts(self._graph)
        contracts_by_node = {c.node: c for c in contracts}

        self._checkpoint()
        self._h.advance("EXECUTING", "executing plan operations")

        # Journal document create and record ownership
        self._owned = True
        self._open = True
        record = DocumentRecord(
            self._h.timestamp(), self._h.record.job_id, self._work_path, "create", True
        )
        self._h.append(record)
        self._h.edit(lambda r: replace(r, documents=(JobDocument(self._work_path, True, "known"),)))

        ops_dict = cast(dict[str, Any], self._plan.get("operations", {}))
        sorted_ops = sorted(ops_dict.values(), key=lambda o: int(o["sequence"]))

        for op_spec in sorted_ops:
            self._execute_op_step(backend, op_spec, contracts_by_node)

        # Forced rebuild
        self._checkpoint()
        self._check_notifications()
        res_rebuild = self._send(backend, "document.rebuild", {"force": True}, check=True)
        if isinstance(res_rebuild, dict) and res_rebuild.get("ok") is False:
            raise JobStop(
                ErrorCode.BACKEND_REBUILD_ERROR.value,
                "Forced document rebuild reported errors.",
                cast("JsonValue", res_rebuild),
            )
        # Save working file
        self._checkpoint()
        self._check_notifications()
        self._send(backend, "document.save", {"path": self._work_path}, check=True)
        self._h.append(
            DocumentRecord(
                self._h.timestamp(), self._h.record.job_id, self._work_path, "save", True
            )
        )

    def _execute_op_step(
        self,
        backend: Backend,
        op_spec: dict[str, Any],
        contracts_by_node: dict[str, Any],
    ) -> None:
        self._checkpoint()
        self._check_notifications()

        op_name = op_spec["op"]
        params = dict(op_spec.get("params", {}))

        if op_name == "part.create":
            params["template"] = self._template
        else:
            params = resolve_node_refs(op_name, params, self._feature_ids)

        res = self._send(backend, op_name, params, check=True)

        if op_name == "part.create" and isinstance(res, dict):
            inst = res.get("instance_id")
            if isinstance(inst, str):
                self._first_instance_id = inst

        node = op_spec.get("source")
        if node and node in contracts_by_node:
            self._verify_node_contract(node, contracts_by_node[node], res)

    def _verify_node_contract(
        self,
        node: str,
        contract: Any,
        res: JsonValue,
    ) -> None:
        raw_obs = res.get("observation") if isinstance(res, dict) else None
        obs_dict = raw_obs if isinstance(raw_obs, dict) else None
        eval_obs: dict[str, JsonValue] | None = obs_dict
        if (
            obs_dict is not None
            and isinstance(res, dict)
            and "entity_count" in res
            and "entity_count" not in obs_dict
        ):
            eval_obs = dict(obs_dict)
            eval_obs["entity_count"] = res["entity_count"]

        check_results = evaluate(contract, eval_obs)
        has_warning = any(c.status == "warning" for c in check_results)
        has_failed = any(c.status == "failed" for c in check_results)
        has_not_eval = any(c.status == "not_evaluated" and c.required for c in check_results)

        if has_failed or has_warning:
            verif_status = "failed"
        elif has_not_eval:
            verif_status = "not_evaluated"
        elif all(c.status == "passed" for c in check_results if c.required):
            verif_status = "passed"
        else:
            verif_status = "failed"

        raw_fid = res.get("feature_id") if isinstance(res, dict) else None
        feature_id = raw_fid if isinstance(raw_fid, str) else None
        if feature_id is not None:
            self._feature_ids[node] = feature_id

        checks_json = [c.to_dict() for c in check_results]
        verified_rec = OpVerifiedRecord(
            ts=self._h.timestamp(),
            job_id=self._h.record.job_id,
            operation_id=self._last_op_id,
            node=node,
            feature_id=feature_id,
            observation=obs_dict,
            checks=checks_json,
            status=verif_status,
        )
        self._h.append(verified_rec)

        if has_warning or has_failed or verif_status != "passed":
            raise JobStop(
                ErrorCode.FEATURE_VERIFICATION_FAILED.value,
                f"Feature verification failed on node '{node}'.",
                cast("JsonValue", {"node": node, "checks": checks_json}),
            )

    # --- EXECUTING -> VERIFYING --------------------------------------------------------

    def _verify_and_commit(self, backend: Backend) -> None:
        assert self._geom is not None

        self._checkpoint()
        self._h.advance("VERIFYING", "measuring and verifying part")

        meta = Meta(request_id=self._h.record.request_id, job_id=self._h.record.job_id)

        # 1. In-session measurement
        measured_1 = self._call(lambda: backend.measure_part(self._work_path, meta=meta))
        checks_1 = compare(self._geom, measured_1, self._feature_ids)
        if not all(c.passed for c in checks_1):
            failed_1: list[JsonValue] = [c.requirement for c in checks_1 if not c.passed]
            raise JobStop(
                ErrorCode.PART_VERIFICATION_FAILED.value,
                f"Part verification failed: {failed_1}",
                {"checks": failed_1},
            )
        self._checkpoint()

        # Pre-reopen fingerprint
        data_pre = self._ctx.fs.read_bytes(self._work_path)
        fp_pre = f"sha256:{hashlib.sha256(data_pre).hexdigest()}"

        # 2. Close working document
        res_close = self._send(backend, "document.close", {"path": self._work_path}, check=True)
        if isinstance(res_close, dict) and res_close.get("closed") is False:
            raise JobStop(
                ErrorCode.BACKEND_OPERATION_FAILED.value,
                f"Document remained open after close: {self._work_path}",
            )
        self._open = False
        self._h.append(
            DocumentRecord(
                self._h.timestamp(), self._h.record.job_id, self._work_path, "close", True
            )
        )
        self._checkpoint()

        # 3. Reopen read-only
        res_open = self._send(
            backend,
            "document.open",
            {"path": self._work_path, "read_only": True, "fully_resolved": True},
            check=True,
        )
        self._open = True
        self._read_only = True
        self._h.append(
            DocumentRecord(
                self._h.timestamp(), self._h.record.job_id, self._work_path, "open", True
            )
        )
        new_inst = res_open.get("instance_id") if isinstance(res_open, dict) else None
        if new_inst and self._first_instance_id and new_inst == self._first_instance_id:
            raise JobStop(
                ErrorCode.BACKEND_OPERATION_FAILED.value,
                f"Reopened document has same instance_id {new_inst} as before close.",
            )
        self._checkpoint()

        # 4. Reopen measurement
        measured_2 = self._call(lambda: backend.measure_part(self._work_path, meta=meta))
        meas_inst = measured_2.get("instance_id") if isinstance(measured_2, dict) else None
        if meas_inst and self._first_instance_id and meas_inst == self._first_instance_id:
            raise JobStop(
                ErrorCode.BACKEND_OPERATION_FAILED.value,
                f"Reopened measurement has same instance_id {meas_inst} as before close.",
            )
        if isinstance(measured_2, dict) and measured_2.get("dirty") is True:
            raise JobStop(
                ErrorCode.PART_VERIFICATION_FAILED.value,
                "Reopened document is dirty.",
                {"checks": ["dirty"]},
            )
        checks_2 = compare(self._geom, measured_2, self._feature_ids)
        if not all(c.passed for c in checks_2):
            failed_2: list[JsonValue] = [c.requirement for c in checks_2 if not c.passed]
            raise JobStop(
                ErrorCode.PART_VERIFICATION_FAILED.value,
                f"Part verification failed after reopen: {failed_2}",
                {"checks": failed_2},
            )
        self._checkpoint()

        # Close read-only document
        self._send(backend, "document.close", {"path": self._work_path}, check=False)
        self._open = False
        self._read_only = False
        self._h.append(
            DocumentRecord(
                self._h.timestamp(), self._h.record.job_id, self._work_path, "close", True
            )
        )

        self._publish(fp_pre, measured_1, checks_1, checks_2)

    def _publish(
        self,
        fp_pre: str,
        measured_1: JsonValue,
        checks_1: tuple[CheckResult, ...],
        checks_2: tuple[CheckResult, ...],
    ) -> None:
        # 5. Re-check 12.5 path checks on target
        self._in_publish = True
        auth = authorize(
            self._target_path,
            self._ctx.settings,
            self._ctx.fs,
            expect="new_file",
            suffix=".sldprt",
        )
        if isinstance(auth, ToolError):
            raise JobStop(auth.code, auth.message, auth.details)

        # 6. Check fingerprint matches fp_pre
        data_post = self._ctx.fs.read_bytes(self._work_path)
        fp_post = f"sha256:{hashlib.sha256(data_post).hexdigest()}"
        if fp_post != fp_pre:
            self._in_publish = False
            raise JobStop(
                ErrorCode.PART_VERIFICATION_FAILED.value,
                f"Working file fingerprint changed during verification: {fp_post} != {fp_pre}",
            )

        # 7. Journal PublishIntentRecord (last cancel boundary!)
        self._checkpoint()
        self._h.append(
            PublishIntentRecord(
                self._h.timestamp(), self._h.record.job_id, self._target_path, fp_pre
            )
        )

        # 8. Atomic rename with retry through clock
        self._rename_with_retry(self._work_path, self._target_path)

        # 9. Journal PublishedRecord
        self._h.append(
            PublishedRecord(self._h.timestamp(), self._h.record.job_id, self._target_path, fp_pre)
        )

        # 10. Store PartRecord
        part_key = f"fp-{fp_pre.removeprefix('sha256:')[:16]}"
        part_rec = PartRecord(
            part_key=part_key,
            path=self._target_path,
            fingerprint=fp_pre,
            produced=True,
            graph=self._spec.ref,
            job_id=self._h.record.job_id,
            updated_at=self._h.timestamp(),
        )
        self._h.store.put_part_record(part_rec)

        # 11. Record part_result on JobRecord
        all_checks = [_check_result_dict(c, "in_session") for c in checks_1] + [
            _check_result_dict(c, "reopened") for c in checks_2
        ]
        part_result: dict[str, JsonValue] = {
            "path": self._target_path,
            "fingerprint": fp_pre,
            "checks": cast("list[JsonValue]", all_checks),
            "measured": measured_1,
            "feature_ids": cast("dict[str, JsonValue]", self._feature_ids),
            "template": self._template,
        }
        self._h.edit(
            lambda r: replace(r, part_result=part_result, fingerprint=fp_pre, documents=())
        )

        # 12. Advance to COMMITTED
        self._h.advance("COMMITTED", "part published and verified")

    def _rename_with_retry(self, source: str, target: str) -> None:
        deadline = self._ctx.clock.monotonic_s() + 1.0
        cond = threading.Condition()
        while True:
            try:
                self._ctx.fs.rename_new(source, target)
                return
            except FileExistsError as error:
                raise JobStop(
                    ErrorCode.AUTH_SOURCE_WRITE_NOT_ALLOWED.value,
                    f"Target file already exists: {target}",
                ) from error
            except OSError as error:
                if self._ctx.clock.monotonic_s() >= deadline:
                    raise JobStop(
                        ErrorCode.STORE_UNAVAILABLE.value,
                        f"Rename failed: {error}",
                    ) from error
                with cond:
                    self._ctx.clock.wait(cond, 0.05)

    # --- ending ------------------------------------------------------------------------

    def _stopped(self, stop: JobStop) -> Outcome:
        if stop.code in _NO_CLOSE:
            return self._handle_no_close(stop)
        if stop.cancelled:
            return self._handle_cancel(stop)
        return self._handle_failure(stop)

    def _handle_no_close(self, stop: JobStop) -> Outcome:
        if self._open or self._ctx.fs.stat(self._work_path) is not None:
            unknown_doc = JobDocument(self._work_path, True, "unknown")
            self._h.edit(lambda r: replace(r, documents=(unknown_doc,)))
        self._h.advance("FAILED", stop.message, stop.error())
        return Outcome("FAILED", stop.code)

    def _handle_cancel(self, stop: JobStop) -> Outcome:
        # Best effort close
        self._best_effort_close()
        changes: list[JsonValue] = []
        if self._ctx.fs.stat(self._work_path) is not None:
            keep_partial = getattr(self._h, "keep_partial", False)
            if keep_partial:
                part_p = partial_path(self._target_path, self._h.record.job_id)
                with contextlib.suppress(Exception):
                    self._ctx.fs.rename_new(self._work_path, part_p)
                    changes.append({"document": part_p, "action": "renamed"})
            else:
                with contextlib.suppress(Exception):
                    self._ctx.fs.remove(self._work_path)
                    changes.append({"document": self._work_path, "action": "deleted"})

        err_body = stop.error()
        details = dict(stop.details) if isinstance(stop.details, dict) else {}
        details["changes"] = changes
        err_body["details"] = details
        self._h.edit(lambda r: replace(r, documents=()))
        self._h.advance("ABORTED", "cancelled", err_body)
        return Outcome("ABORTED", stop.code)

    def _handle_failure(self, stop: JobStop) -> Outcome:
        # Operation or verification failed: best-effort save, close, rename to failed
        self._best_effort_save_and_close()
        fail_p = failed_path(self._target_path, self._h.record.job_id)
        renamed = False
        if self._ctx.fs.stat(self._work_path) is not None and not self._in_publish:
            with contextlib.suppress(Exception):
                self._ctx.fs.rename_new(self._work_path, fail_p)
                renamed = True

        details = dict(stop.details) if isinstance(stop.details, dict) else {}
        if renamed:
            details["failed_path"] = fail_p
            details["failed_file"] = fail_p
        elif self._ctx.fs.stat(self._work_path) is not None:
            details["working_path"] = self._work_path
            details["working_file"] = self._work_path
        if details or isinstance(stop.details, dict):
            stop.details = details

        self._h.edit(lambda r: replace(r, documents=()))
        self._h.advance("FAILED", stop.message, stop.error())
        return Outcome("FAILED", stop.code)

    def _best_effort_close(self) -> None:
        backend = self._backend
        if backend is None or not self._open:
            return
        with contextlib.suppress(Exception):
            self._send(backend, "document.close", {"path": self._work_path}, check=False)
            self._h.append(
                DocumentRecord(
                    self._h.timestamp(), self._h.record.job_id, self._work_path, "close", True
                )
            )
        self._open = False
        self._read_only = False

    def _best_effort_save_and_close(self) -> None:
        backend = self._backend
        if backend is None or not self._open:
            return
        if not self._read_only:
            with contextlib.suppress(Exception):
                self._send(backend, "document.save", {"path": self._work_path}, check=False)
                self._h.append(
                    DocumentRecord(
                        self._h.timestamp(), self._h.record.job_id, self._work_path, "save", True
                    )
                )
        with contextlib.suppress(Exception):
            self._send(backend, "document.close", {"path": self._work_path}, check=False)
            self._h.append(
                DocumentRecord(
                    self._h.timestamp(), self._h.record.job_id, self._work_path, "close", True
                )
            )
        self._open = False
        self._read_only = False

    # --- helpers -----------------------------------------------------------------------

    def _checkpoint(self) -> None:
        if self._h.cancel_requested:
            raise JobStop(ErrorCode.EXEC_CANCELLED.value, "The job was cancelled.")

    def _send(self, backend: Backend, op: str, params: JsonValue, *, check: bool) -> JsonValue:
        h = self._h
        record = h.record
        op_id = f"{record.job_id}:{record.next_op_seq}"
        self._last_op_id = op_id
        self._batches += 1
        batch = BatchSentRecord(
            h.timestamp(), record.job_id, self._batches, (op_id,), (self._work_path,)
        )
        h.append(batch)
        h.edit(lambda r: replace(r, next_op_seq=r.next_op_seq + 1))
        operation = Operation(operation_id=op_id, op=op, params=params)
        groups = (OperationGroup(document=self._work_path, operations=(operation,)),)
        meta = Meta(request_id=record.request_id, job_id=record.job_id, operation_id=op_id)
        applied = self._call(lambda: backend.apply_ops(groups, meta=meta), check=check)
        outcome = next((o for o in applied.outcomes if o.operation_id == op_id), None)
        if outcome is None:
            raise JobStop(
                ErrorCode.EXEC_INTERRUPTED.value, "The add-in did not answer the operation."
            )
        error = outcome.error
        h.append(
            OpResultRecord(h.timestamp(), record.job_id, op_id, error is None, error and error.code)
        )
        if error is not None:
            raise JobStop(error.code, error.message, error.details)
        return outcome.result

    def _call[T](self, call: Callable[[], T], *, check: bool = True) -> T:
        try:
            value = call()
        except Exception as error:
            stop = _stop_from(error)
            if stop is None:
                raise
            raise stop from error
        if check:
            self._check_notifications()
        return value

    def _check_notifications(self) -> None:
        for method, params in self._h.take_notifications():
            if method == "session.ui_blocked":
                raise JobStop(
                    ErrorCode.BACKEND_UI_BLOCKED.value,
                    "SOLIDWORKS stopped responding to the add-in.",
                )
            if method == "document.event" and self._foreign_event(params):
                raise JobStop(
                    ErrorCode.EXEC_INTERRUPTED_BY_USER.value,
                    "The part was changed in SOLIDWORKS while the job was using it.",
                )

    def _foreign_event(self, params: JsonValue) -> bool:
        if not isinstance(params, dict):
            return False
        document = params.get("document")
        if not isinstance(document, str) or ntpath.normcase(document) != ntpath.normcase(
            self._work_path
        ):
            return False
        meta = params.get("_meta")
        own = isinstance(meta, dict) and meta.get("job_id") == self._h.record.job_id
        return not own

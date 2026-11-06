# `check_drawing` Job, Project Store and Phase 1a Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the project store and job journal (13.2), the job engine and the `check_drawing` job (8.4), and the contracts and handlers of `check_drawing`, `get_drawing_report`, `get_execution_status` and `cancel_execution` (12.4.5), tested over replayed transcripts with no SOLIDWORKS.

**Architecture:** Logic lives in `cad-application` behind ports (G2): `Backend`, `BackendProvider`, `Store`, `Clock`, `IdSource`, `FileSystem`, `EventLog`. `FileStore` is the one store implementation; over `MemoryFileSystem` it is the `FakeStore`. `JobEngine` is a synchronous, thread-safe state machine (ADR-053); `core_service` adds the OS adapters, the worker thread and an in-process `call_tool` entry. Contract files in `schemas/mcp/` are embedded by the generator, so handlers validate arguments without I/O. Reports stay pure (11.5.4) and always say `calibration.status: unverified`.

**Tech Stack:** Python 3.13, standard library only (`tomllib`, `threading`, `hashlib`, `msvcrt` in `core_service` only). No new dependencies. No C# source changes: only the generated `ErrorCodes.g.cs` changes, because the catalogue gains `FILE_NOT_FOUND`.

**Spec:** v1.22. Read first: §8.4 (lifecycle and the `check_drawing` table), §12.4.1–12.4.5, §12.5, §13.1, §13.2, §13.3, ADR-053. Also §8.7, §8.6.3, §11.5.4, ADR-037, ADR-043, ADR-044, ADR-046, guidelines G2 and G3.

## Scope decision

**M5 is one PR; the transport is milestone 6.** The orchestrator's recommendation stands, for its four reasons: M5 is already a full review (store, journal, engine, four contracts, config, paths); a reader thread in `IpcClient` deserves its own review; a pipe client needs a pipe host to test; and M5 leaves a port (`BackendProvider.acquire()`, raising `BACKEND_LOST` or `BACKEND_SESSION_AMBIGUOUS`) that the transport plugs into unchanged. One more reason: the core pipe (ADR-041) carries `ToolResult` (12.4.2), which only exists once M5's handlers do.

A split of M5 is not needed. If review load proves too high, the cut is after Task 7 ("store and jobs", no MCP surface) and before Task 8 ("contracts and tools").

**M6 ("transport and first live smoke"):** named-pipe transport, session discovery (8.6.1), heartbeat and the `IpcClient` reader thread (which also lifts the cancel and notification limits in ADR-053), the core pipe, the stdio front-end, and the add-in pipe host and snapshot adapter. This PC has a licensed SOLIDWORKS 2025, so M6 can include the first live smoke test and prove A14–A17 here. Live K3 work belongs to M6 or M7 as a named task: inspect the owner's sheet formats in SOLIDWORKS, define a `read` locator per field in 13.3.4, ship the mapping files, calibrate D8. That task needs the owner to confirm the mapping from `standards/iso/templates/`.

**Owner approvals needed before any live run (M6, not M5):**
1. Lift the "no SOLIDWORKS, no live tests" limit for M6, on this PC.
2. Registering the add-in per user (ADR-038), which writes to `HKCU`, and loading it into the owner's SOLIDWORKS.
3. Which drawings may be opened: copies made for testing, never source parts, assemblies or vaulted files (ADR-022, ADR-047). `check_drawing` opens read-only and never saves (ADR-046).
4. The preference changes the settings guard makes and restores (8.6.4), in the owner's own session (ADR-050).
5. Confirmation that the add-in is compiled code, not a macro: no SOLIDWORKS macro is run, ever (AGENTS.md section 2).
6. The K3 mapping, once the formats have been inspected.
7. Review of ADR-053 and the v1.22 decisions marked [Builder's call].

## Global Constraints

- The Global Constraints of `2026-11-03-shared-ir-core.md` apply: pyright strict, ruff, §3.4.8 schema rules, generated files only via `scripts/generate_contracts.py`.
- **Do not run git add or commit.** The controller commits after review.
- **Do not touch `standards/iso/templates/`.** Its three files were committed in `1b49268`; do not open, parse, move, restage or add LFS rules for them. Do not invent a title-block mapping or sheet-format fields (K3 stays open).
- No SOLIDWORKS, no live tests, no real named pipe, no stdio front-end, nothing from the reference implementation.
- `cad_application` performs no direct I/O: no `open`, `os`, `pathlib`, `shutil`, `tempfile`, `msvcrt`, `time`, `secrets`, `random`, `datetime.now`. Every effect goes through a port. `threading`, `hashlib`, `json`, `tomllib.loads` and `base64` are fine. Task 2 adds a test that enforces this.
- `cad_application` must not import `cad_protocol` (existing lint-imports contract). `core_service` may import both.
- Tests never sleep or wait on the wall clock. Use `FakeClock`; a cross-thread test uses `threading.Event` and joins with a 5 s guard timeout only.
- Never log or put in an error message: file contents, snapshot or report bodies, session tokens, environment variable values (G3).
- Python suite after every task, from the repo root: `uv run python scripts/generate_contracts.py --check && uv run ruff check && uv run ruff format --check && uv run pyright && uv run lint-imports && uv run pytest -q`.
- C# suite (Tasks 1 and 9, because the catalogue and transcripts change): `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`.

## Review Focus

Breaking any of these rules must make a named test fail; a script will mutation-test them after the review.

1. **Journal before state.** A `state` record is appended before `job.json` is replaced; a `batch_sent` record is on disk before `apply_ops` is called. Tests: `test_state_record_precedes_job_json`, `test_batch_sent_flushed_before_apply` (the backend double reads the journal when called).
2. **Atomic writes.** A crash at any write, `fsync` or rename leaves the target either old or new, never partial, and the temporary file is removed at the next open. Test: `test_atomic_write_survives_crash_at_every_step` (parametrized over every fault point).
3. **Lock exclusivity.** A second store on the same folder fails with `STORE_LOCKED` until the first closes. Tests: `test_second_open_is_store_locked` (memory), `test_os_lock_is_exclusive` (OS, `tmp_path`).
4. **Immutable files.** Snapshots, reports and meta files are written once; the stored report equals `build_report(...).to_json()` with nothing added. Tests: `test_write_new_refuses_existing`, `test_stored_report_is_exactly_build_report`.
5. **Path policy edge cases.** Relative, `~`, `%VAR%`, `$VAR`, `\\?\` and `\\.\` prefixes, `..` escaping a root, a junction leaving a root, case-only differences, a root that is a prefix of a sibling (`C:\a` vs `C:\ab`), UNC without a UNC root, no roots. Test: `test_authorize_cases` (one parametrized table).
6. **Cursors.** Valid only for the same arguments and under 10 minutes. Tests: `test_cursor_rejected_for_other_arguments`, `test_cursor_expires_at_ten_minutes`, `test_cursor_malformed`.
7. **Long-poll.** Returns on a state change, not on a progress change; returns at once for a final job; expires through `FakeClock`. Tests: `test_wait_returns_on_state_change` (two threads), `test_wait_ignores_progress`, `test_wait_final_returns_at_once`, `test_wait_expires_without_real_time`.
8. **Cancel ordering.** PLANNED → ABORTED at once; a running job's `Backend.cancel()` is called outside the engine lock; a cancel after the report write started ends COMMITTED; a cancelled job still closes the drawing it owns. Tests: `test_cancel_planned_aborts_at_once`, `test_cancel_running_calls_backend_outside_lock`, `test_cancel_after_report_write_commits`, `test_cancelled_job_closes_owned_drawing`.
9. **A failed check is a result.** A report with verdict `fail` ends the job COMMITTED, `ok: true`; every report says `unverified`. Tests: `test_fail_verdict_commits`, `test_report_calibration_unverified`.
10. **Crash recovery.** Running states → FAILED and PLANNED → ABORTED, both `EXEC_INTERRUPTED`; the journal wins over `job.json`; a torn last line is ignored; touched documents are listed as unknown; step 2 records only unanswered operation IDs. Tests: `test_recovery_marks_interrupted`, `test_journal_wins_over_job_json`, `test_torn_last_line_ignored`, `test_documents_unknown_after_crash`, `test_completed_operations_recorded_once`.
11. **Retention.** Keeps the drawing record's report and snapshot, every snapshot a kept report refers to, and every non-final job; expired IDs give `EXEC_NOT_FOUND`. Tests: `test_retention_keeps_referenced`, `test_retention_never_deletes_running_job`, `test_expired_report_not_found`.
12. **Contracts.** A handler returning a code not in its contract's `errors` fails the contract test; contract files and the 12.4.4 table agree. Tests: `test_handlers_return_only_listed_errors`, `test_table_matches_contract_files`.
13. **Security keys.** `access.*`, `solidworks.session` and `drawing.standard_dir` from a project file or the environment are ignored with a warning. Test: `test_security_keys_only_from_user_file`.
14. **Logs.** The sink drops unknown fields. Test: `test_sink_drops_unknown_fields`.
15. **Notifications.** `session.ui_blocked` or a foreign `document.event` fails the job and stores no snapshot. Tests: `test_ui_blocked_fails_job_and_stores_nothing`, `test_document_event_interrupts`.

---

### Task 1: Schemas, error code and fixtures

**Files:**
- Modify: `schemas/common/errors.json`: append `FILE_NOT_FOUND` (`after_fix`, "The file does not exist or is not a file."); change the `IR_SCHEMA_INVALID` description to "A document or a tool's arguments do not satisfy their JSON Schema."
- Modify: `tests/contract/test_error_catalogue.py`: add `FILE_NOT_FOUND` to the list, `EXPECTED_CODE_COUNT = 39`, `FILE` in `CODE_MENTION`
- Create: `schemas/mcp/contract/v0.json` (12.4.1 meta-schema); `schemas/store/v0.json` (`$defs`: `StoreManifest`, `Index`, `DrawingRecord`, `ReportMeta`, `JobRecord`, `JournalRecord` as `oneOf` of `StateRecord`, `BatchSentRecord`, `OpResultRecord`, `SnapshotRecord`, `DocumentRecord`, `NoteRecord`, per 13.2.1 and 13.2.3); `schemas/config/v1.json` (every 13.3.3 key except `references.high_confidence`, `additionalProperties: false` at every level, `config_version` const `"1.0"`); `schemas/config/title-block/v1.json` (13.3.4 format). Delete `.gitkeep` files in `schemas/mcp/` and `schemas/config/` if present.
- Create: `tests/fixtures/schemas/{store,config,mcp-contract}/{valid,invalid}/*.json`, in the existing fixture layout
- Modify: `tests/contract/test_schema_fixtures.py`
- Generated: `packages/cad-ir/src/cad_ir/generated/{error_codes.py,schemas.py}`, `apps/execution-server/ExecutionServer.Core/Ipc/Generated/ErrorCodes.g.cs`

The contract files themselves are written in Task 8. IDs: `^(job|rep|snap|drw|req)_[0-9A-HJKMNP-TV-Z]{26}$`, one `$def` per prefix in `store/v0.json`.

- [ ] **Step 1: Failing tests:** `test_store_valid_accepted`, `test_store_invalid_rejected`, `test_config_valid_accepted`, `test_config_invalid_rejected` (unknown key, wrong type, missing `config_version`), `test_title_block_mapping_schema`, `test_contract_meta_schema_valid_and_invalid` (bad name, description over 400, unknown toolset, unknown error code, empty examples, non-boolean `deprecated`); catalogue tests updated for 39 codes.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Write the schemas and fixtures; run `uv run python scripts/generate_contracts.py`.
- [ ] **Step 4:** Run the Python suite and the C# suite. Expected: PASS (`Error_codes_match_catalogue` reads the catalogue).

### Task 2: Ports, IDs and test doubles

**Files:**
- Modify: `packages/cad-application/src/cad_application/ports.py`
- Create: `packages/cad-application/src/cad_application/ids.py`, `cad_application/testing/__init__.py`, `testing/memory_fs.py`, `testing/fake_clock.py`, `testing/fakes.py` (`SequentialIdSource`, `ListEventLog`, `FakeBackend`)
- Test: `packages/cad-application/tests/test_ids.py`, `test_memory_fs.py`, `test_fake_clock.py`; `tests/contract/test_application_io.py`
- Modify: `pyproject.toml`: add an import-linter contract "core-service never imports the front-end" (`core_service` ↛ `mcp_server`)

**Interfaces (Produces):**
- `Clock`: `now() -> datetime` (aware UTC), `monotonic_s() -> float`, `wait(cond: threading.Condition, timeout_s: float) -> None` (caller holds `cond`).
- `IdSource`: `new_id(prefix: Literal["job","rep","snap","drw","req"]) -> str`. `ids.py`: pure `encode_ulid(ms: int, randomness: bytes) -> str` (Crockford, 26 chars) and `is_id(value, prefix) -> bool`.
- `FileSystem` (G2), paths as `str`: `resolve(path) -> str` (absolute, links and junctions followed; raises `FileNotFoundError` only if a parent is missing), `stat(path) -> FileStat | None` (`is_dir`, `size`, `mtime_ns`), `read_bytes`, `list_dir -> tuple[str, ...]` (names, sorted), `make_dirs`, `write_atomic(path, data)`, `write_new(path, data)` (raises `FileExistsError`), `append_line(path, line)`, `remove(path)`, `lock_exclusive(path) -> Lock` (raises `LockHeld`; `Lock.release()`).
- `EventLog.emit(event: str, level: str, **fields: str | int | None) -> None`.
- `BackendProvider.acquire(on_notification: Callable[[str, JsonValue], None]) -> Backend`; raises `BackendUnavailable(code, message, details)` with `BACKEND_LOST` or `BACKEND_SESSION_AMBIGUOUS`.
- `MemoryFileSystem(junctions: Mapping[str, str] = {}, fail_at: FaultPoint | None = None)`: Windows semantics (case-insensitive lookup, case-preserving names, `\` separators); `write_atomic` is tmp-write, `fsync`, rename in three countable steps; `fail_at=("write"|"fsync"|"rename", n)` raises `SimulatedCrash` at the nth such step and leaves the state a real crash would. `lock_exclusive` is per instance, shared by every store on it.
- `FakeBackend(session, *, snapshot=..., open_owned=True, block: threading.Event | None = None)`: records calls; `snapshot_drawing` waits on `block` when given, and raises `IpcError`-like `BackendCallError(code)` when `cancel()` was called meanwhile. It is defined in `cad_application.testing` and raises `cad_application`'s own `BackendCallError`, never `cad_protocol` types.

Backend errors: `cad_application` cannot import `cad_protocol.errors.IpcError`. Add `BackendCallError(Exception)` with `code`, `message`, `details` in `ports.py`, and have the job runner treat any exception with a string `code` attribute as a backend error (`IpcError` has one), via a small `Protocol`. Document this in the module docstring.

- [ ] **Step 1: Failing tests:** `test_ulid_golden` (fixed ms and bytes give a known string), `test_ulid_sorts_by_time`, `test_is_id_rejects_bad_alphabet`; `test_memory_fs_case_insensitive`, `test_memory_fs_junction_resolves`, `test_write_new_refuses_existing`, `test_atomic_write_survives_crash_at_every_step` (parametrized fault points: target old or new, never partial; a `*.tmp-*` may remain), `test_append_line_crash_leaves_torn_line`, `test_lock_is_exclusive_until_released`; `test_fake_clock_wait_advances_without_blocking`; `test_cad_application_has_no_direct_io` (AST scan of `packages/cad-application/src` for the banned imports and calls in Global Constraints; `testing/` included).
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the Python suite. Expected: PASS.

### Task 3: Configuration and title-block mappings

**Files:**
- Create: `packages/cad-application/src/cad_application/config/__init__.py`, `config/settings.py`, `config/merge.py`, `config/title_blocks.py`
- Test: `packages/cad-application/tests/test_config.py`, `test_title_blocks.py`

**Interfaces (Produces):**
- `Layer(source: Literal["defaults","user","project","env"], origin: str, values: Mapping[str, JsonValue])`; `parse_toml_layer(text, *, source, origin) -> Layer | ConfigError` (a `TOMLDecodeError` gives file and line); `parse_env_layer(environ: Mapping[str, str]) -> Layer` (only `SWMCP_*`, TOML-value parsing per 13.3.1).
- `merge_settings(layers: Sequence[Layer]) -> Settings | ConfigError`, in precedence order, key by key, validating each file layer against `schemas/config/v1.json` before merging. Security keys from `project` or `env` are dropped and returned in `Settings.warnings`. `ConfigError(code="CONFIG_INVALID", origin, key: str | None, line: int | None, message)`.
- `Settings` (frozen): `allowed_roots`, `pdm_vault_roots`, `job_retention_days`, `snapshot_keep`, `standard_dir`, `check_thresholds() -> CheckThresholds`, `logging_level`, `logging_retention_days`, `solidworks_session`, `command_timeout_s`, `read_timeout_s`, `warnings`.
- `load_title_block_mappings(fs, standard_dir) -> Mapping[str, TitleBlockMapping] | ConfigError`: reads `<standard_dir>\title-blocks\*.toml` only; a missing folder gives `{}`; `required` is the field names with `required = true`, in file order.

- [ ] **Step 1: Failing tests:** `test_defaults_match_13_3_3` (every default in the table), `test_precedence_defaults_user_project_env`, `test_security_keys_only_from_user_file`, `test_unknown_key_names_file_and_key`, `test_wrong_type_names_key`, `test_syntax_error_names_line`, `test_env_values_parsed_as_toml`, `test_thresholds_from_settings`; `test_no_title_block_folder_gives_no_mappings`, `test_mapping_loaded_from_synthetic_file` (a mapping written into `MemoryFileSystem` by the test), `test_invalid_mapping_is_config_invalid`, `test_only_title_blocks_folder_is_read` (the fake file system records reads; nothing under `templates\`).
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the Python suite. Expected: PASS.

### Task 4: Path policy

**Files:**
- Create: `packages/cad-application/src/cad_application/paths.py`
- Test: `packages/cad-application/tests/test_paths.py`

**Interfaces (Produces):** `authorize(path: str, settings: Settings, fs: FileSystem, *, expect: Literal["file","dir"] = "file", suffix: str | None = None) -> Authorized | ToolError`, where `Authorized(path, root, project_root, store_dir, in_vault)` and `ToolError(code, message, details)`. `local_app_data` comes from `Settings` (filled by core-service), so the function reads no environment. Order and reasons: 12.5. `store_dir` is `<project_root>\.cad` or, in a vault, `<local_app_data>\sw-mcp\stores\<sha256>`.

- [ ] **Step 1: Failing tests:** `test_authorize_cases` (the Review Focus 5 table, each row giving code and `details.reason`), `test_project_is_nearest_store_up_to_root`, `test_project_defaults_to_root`, `test_vault_store_goes_to_local_app_data` (golden hash), `test_missing_file_is_file_not_found`, `test_directory_is_not_a_file`, `test_suffix_case_insensitive`, `test_message_does_not_echo_env_values`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the Python suite. Expected: PASS.

### Task 5: File store

**Files:**
- Create: `packages/cad-application/src/cad_application/store/file_store.py`, `store/records.py`, `store/store_set.py`, `store/errors.py`; add `Store` Protocol to `ports.py`
- Test: `packages/cad-application/tests/test_file_store.py`, `test_store_set.py`

**Interfaces (Produces):**
- `FileStore.open(fs, store_dir, project_root, clock) -> FileStore | StoreError` (`STORE_LOCKED`, `STORE_CORRUPT`). Creates `store.json`, `.gitignore` (13.2.5 text, exactly) and folders on first open; deletes `*.tmp-*`; rebuilds `index.json` when missing, unreadable or older than any `drawings/*.json`.
- `Store` methods: `find_drawing(path, fingerprint) -> DrawingRecord | None` and `match_drawing(...)` per the 13.2.1 matching rule (returns the record and an optional warning); `put_drawing(record)`; `put_snapshot(drawing_id, snapshot_id, doc)` and `get_snapshot(drawing_id, snapshot_id)`; `put_report(report_id, report, meta)` (meta first, then report, both `write_new`) and `get_report(report_id) -> tuple[JsonValue, ReportMeta] | None`; `close()`. Jobs are in Task 6.
- Records are frozen dataclasses with `to_json` / `from_json`, validated against `schemas/store/v0.json` on read; an invalid record is `STORE_CORRUPT`.
- `StoreSet(fs, clock, known_stores_path)`: `open_for(authorized) -> Store | StoreError` (opens once, adds to `known-stores.json`), `open_known() -> tuple[str, ...]` (opens all listed, returns skipped ones), `store_of_job(job_id)`, `store_of_report(report_id)`.

- [ ] **Step 1: Failing tests:** `test_first_open_creates_layout_and_gitignore`, `test_gitignore_never_overwritten`, `test_second_open_is_store_locked`, `test_unknown_store_major_is_corrupt`, `test_tmp_files_removed_at_open`, `test_index_rebuilt_when_stale`, `test_match_drawing_by_path_then_fingerprint`, `test_ambiguous_fingerprint_makes_new_record_and_warning`, `test_write_new_refuses_existing` (snapshot and report), `test_put_report_writes_meta_first`, `test_invalid_record_is_store_corrupt`, `test_store_set_finds_job_and_report_by_id`, `test_known_store_locked_elsewhere_is_skipped`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the Python suite. Expected: PASS.

### Task 6: Job records, journal, recovery and retention

**Files:**
- Create: `packages/cad-application/src/cad_application/store/journal.py`, `store/recovery.py`, `store/retention.py`
- Test: `packages/cad-application/tests/test_journal.py`, `test_recovery.py`, `test_retention.py`

**Interfaces (Produces):**
- On `Store`: `create_job(record)` (first `state` record, then `job.json`), `append(job_id, record)`, `put_job(record)`, `get_job(job_id)`, `list_jobs()`, `read_journal(job_id) -> tuple[JournalRecord, ...] | StoreError`.
- `transition(store, record, to, reason, error=None) -> JobRecord`: validates against the 8.4 transition table (raises `InvalidTransition`), appends, then replaces `job.json`, and returns the new record (never mutates the old one).
- `recover(store, clock) -> RecoveryResult` (13.2.3 Phase 1a): reconcile `job.json` with the journal; FAILED or ABORTED with `EXEC_INTERRUPTED`; `documents` from `document` records; `pending_operation_ids` per job for step 2.
- `record_completed_operations(store, result, completed: Sequence[str])`: appends `op_result` with `recovered: true` only for pending IDs.
- `clean_up(store, clock, settings) -> CleanUpResult` (13.2.4 for jobs, reports with meta, snapshots).

- [ ] **Step 1: Failing tests:** `test_state_record_precedes_job_json` (crash between them: recovery sees the journal state), `test_invalid_transition_raises_and_writes_nothing`, `test_every_8_4_transition_allowed` (table-driven, including the negative set), `test_journal_wins_over_job_json`, `test_torn_last_line_ignored`, `test_corrupt_middle_line_is_store_corrupt`, `test_recovery_marks_interrupted` (parametrized PLANNED, VALIDATED, EXECUTING, VERIFYING), `test_final_jobs_untouched_by_recovery`, `test_documents_unknown_after_crash`, `test_completed_operations_recorded_once`, `test_retention_keeps_referenced`, `test_retention_keeps_last_n_snapshots_per_drawing`, `test_retention_never_deletes_running_job`, `test_retention_age_from_ended_at`, `test_expired_report_not_found`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the Python suite. Expected: PASS.

### Task 7: Job engine and the `check_drawing` job

**Files:**
- Create: `packages/cad-application/src/cad_application/jobs/engine.py`, `jobs/check_drawing.py`, `jobs/model.py`
- Test: `packages/cad-application/tests/test_job_engine.py`, `test_check_drawing_job.py`

**Interfaces (Produces):**
- `JobEngine(stores: StoreSet, provider: BackendProvider, clock, ids, log, settings_for: Callable[[str], Settings], mappings_for: Callable[[Settings], Mapping[str, TitleBlockMapping]])`: `submit(spec: CheckDrawingSpec, request_id) -> JobView` (`queued_position` per 8.4); `status(job_id) -> JobView | None`; `wait_for_change(job_id, wait_ms) -> tuple[JobView, bool]` (`changed`); `cancel(job_id) -> JobView`; `run_next() -> bool`; `wait_for_work(timeout_s)`; `recover_all()` and `reconcile(backend)` (step 2). `JobView` is an immutable copy; nothing outside the engine sees mutable state.
- `CheckDrawingSpec(authorized: Authorized, fingerprint: str, sheets: tuple[str, ...] | None)`.
- `check_drawing.run(ctx) -> Outcome`, following 8.4: acquire backend; check capabilities; `apply_ops` with `document.open` (`read_only: true`, `fully_resolved: true`) as operation `<job_id>:1`, journalling `batch_sent` before and `op_result` and `document` after; `snapshot_drawing(path, sheets, meta=...)`; store the snapshot and its `snapshot` record; VERIFYING; `build_report(doc, thresholds=..., title_block_mappings=...)`; an `IssueReport` fails the job with the issue's code; put the report and meta; update the drawing record; close if owned; COMMITTED. Cancel checks at the boundaries of 8.4. Job warnings: each `HelloResult.warnings` entry becomes `{code: "solidworks_version_warning", message}`; a drawing-match warning is added too.
- Notifications: the job passes a callback to `acquire(on_notification)` that records them for the running job. After each backend call, a `session.ui_blocked` received meanwhile fails the job with `BACKEND_UI_BLOCKED`; a `document.event` for the job's path that the job did not cause fails it with `EXEC_INTERRUPTED_BY_USER`. The call's result is discarded.
- `meta` on every call: `request_id`, `job_id`, and `operation_id` for `apply_ops` (G3).

- [ ] **Step 1: Failing tests** (all with `FakeBackend`, `MemoryFileSystem`, `FakeClock`, `SequentialIdSource`, run by `run_next()` on the test thread unless named):
  - engine: `test_queued_position_counts_running_and_earlier`, `test_jobs_run_in_submission_order`, `test_wait_returns_on_state_change` (second thread, `Event`), `test_wait_ignores_progress`, `test_wait_final_returns_at_once`, `test_wait_expires_without_real_time`, `test_cancel_planned_aborts_at_once`, `test_cancel_finished_is_no_op`, `test_cancel_running_calls_backend_outside_lock` (worker on a thread blocked in `FakeBackend`; the test asserts the engine lock is free during `cancel()`), `test_status_unknown_is_none`
  - job: `test_fail_verdict_commits`, `test_report_calibration_unverified`, `test_stored_report_is_exactly_build_report`, `test_batch_sent_flushed_before_apply`, `test_borrowed_drawing_not_closed`, `test_cancelled_job_closes_owned_drawing`, `test_cancel_after_report_write_commits`, `test_cancel_between_open_and_snapshot`, `test_backend_unavailable_fails_from_planned` (`BACKEND_LOST`, `BACKEND_SESSION_AMBIGUOUS`), `test_missing_capability_fails`, `test_timeout_fails_with_exec_timeout`, `test_ui_blocked_fails_job_and_stores_nothing`, `test_document_event_interrupts`, `test_invalid_snapshot_fails_with_issue_code`, `test_service_pack_warning_on_job`, `test_d8_not_evaluated_without_mapping`, `test_meta_carries_request_and_job_ids`, `test_progress_steps_1_to_4`
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the Python suite. Expected: PASS.

### Task 8: Contract files and tool handlers

**Files:**
- Create: `schemas/mcp/check_drawing.json`, `get_drawing_report.json`, `get_execution_status.json`, `cancel_execution.json` (12.4.1 format, 12.4.5 contents, at least two examples each: one success, one error); regenerate
- Create: `packages/cad-application/src/cad_application/tools/__init__.py`, `tools/contracts.py`, `tools/result.py`, `tools/cursor.py`, `tools/registry.py`, `tools/check_drawing.py`, `tools/get_drawing_report.py`, `tools/get_execution_status.py`, `tools/cancel_execution.py`, `tools/summaries.py`
- Test: `packages/cad-application/tests/test_tool_contracts.py`, `test_cursor.py`, `test_tools_check_drawing.py`, `test_tools_get_drawing_report.py`, `test_tools_status_and_cancel.py`

**Interfaces (Produces):**
- `contracts.py`: `load_contracts() -> Mapping[str, ToolContract]` from `cad_ir.generated.schemas.SCHEMAS` (ids under `.../schemas/mcp/`, excluding `contract/`); `ToolContract` (frozen) with the 12.4.1 fields and `annotations() -> Mapping[str, bool]` (12.4.1 derivation, all four hints).
- `result.py`: `ToolResult(envelope: JsonValue, summary: str)`; `ok(data, ids, summary)`, `error(code, message, details, ids, summary)` using `DEFAULT_RETRYABLE`.
- `cursor.py`: `encode_cursor(offset, issued_ms, args) -> str`, `decode_cursor(cursor, args, now_ms) -> int | ToolError` (12.4.2).
- `registry.py`: `ToolRegistry(contracts, handlers)`: `call(name, arguments, request_id) -> ToolResult`, raising `UnknownTool` for a name with no contract; validates arguments with `validate_against_schema(args, "<$id>#/input")` → `IR_SCHEMA_INVALID` with `details.issues`; after the handler, asserts in debug and tests that the error code is listed and that `data` validates against `#/output`.
- Handlers take a `ToolContext(engine, stores, fs, clock, settings_user, log)`; `check_drawing` authorizes (suffix `.slddrw`), fingerprints (`sha256:` of `fs.read_bytes`, 13.1), loads project settings (`CONFIG_INVALID`), opens the store, then `engine.submit`.

- [ ] **Step 1: Failing tests:** `test_contract_files_valid_against_meta_schema`, `test_description_first_sentence_within_120`, `test_annotations_derivation` (all four contracts, plus a synthetic `delete_feature` contract for `destructiveHint`), `test_examples_validate` (arguments against `input`, responses against the envelope and `output`); `test_cursor_round_trip`, `test_cursor_rejected_for_other_arguments`, `test_cursor_expires_at_ten_minutes` (valid at 599 999 ms, invalid at 600 000), `test_cursor_malformed`; `test_unknown_tool_raises`, `test_unknown_property_is_schema_invalid` (including `drawing_intent`), `test_report_id_xor_execution_id`, `test_cursor_requires_paginated_section`; `test_check_drawing_returns_execution_id_and_position`, `test_check_drawing_path_denied_creates_no_job`, `test_check_drawing_missing_file`, `test_check_drawing_not_slddrw`, `test_report_summary_fields`, `test_report_summary_within_600_tokens` (worst case: every check failing, 200 failures), `test_report_full_adds_checks_sheets_thresholds`, `test_report_sections_paginate`, `test_report_for_unfinished_job_has_null_report_id`, `test_status_fields_per_state`, `test_status_retry_after`, `test_cancel_output_changes_empty`, `test_ids_per_tool`, `test_summary_lines` (each ≤ 200 characters, golden strings), `test_handlers_return_only_listed_errors` (drives every error path above and checks each code against the contract).
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Write the contracts, regenerate, implement.
- [ ] **Step 4:** Run the Python suite. Expected: PASS.

### Task 9: Core-service composition and replayed end-to-end tests

**Files:**
- Create: `apps/core-service/src/core_service/os_fs.py` (`OsFileSystem`: `os.path.realpath` for `resolve`, `os.replace`, `os.fsync`, `msvcrt.locking` with `LK_NBLCK`), `system_clock.py`, `system_ids.py` (`secrets` + `time`), `jsonl_log.py` (G3 sink, daily file, field allow-list), `config_loader.py` (user file at `%APPDATA%\sw-mcp\config.toml`, environment, `LOCALAPPDATA`), `providers.py` (`ReplayBackendProvider(transcript)`, wrapping `cad_protocol.replay_backend`, translating `IpcError` to the port's error shape), `service.py` (`CoreService.start(...)`, `call_tool(name, arguments) -> ToolResult` creating `request_id`, the worker thread, `stop()`)
- Modify: `packages/cad-protocol/src/cad_protocol/replay.py`: `replay_backend(transcript, *, on_notification=None)`, passed to `IpcClient` (keyword-only, default unchanged)
- Create: `tests/fixtures/ipc/check_drawing_owned.jsonl` (hello; `ops.apply` open `owned: true`; snapshot; `ops.apply` close), `check_drawing_borrowed.jsonl` (open `owned: false`; snapshot), `check_drawing_bad_sheet.jsonl` (snapshot answers `IR_REFERENCE_UNRESOLVED`; close), all `sides: ["python", "csharp"]`; `check_drawing_ui_blocked.jsonl`, `check_drawing_timeout.jsonl`, `check_drawing_lost.jsonl`, `check_drawing_sp_warning.jsonl` (hello `warnings` non-empty), `sides: ["python"]`. Operation IDs use the `SequentialIdSource` job ID; document paths are the normalized form `authorize` returns. Snapshot results reuse the `snapshot_ok` result.
- Modify: `tests/contract/test_transcripts.py` (scenario list and drivers)
- Test: `apps/core-service/tests/test_os_fs.py`, `test_jsonl_log.py`, `test_config_loader.py`, `test_service_replay.py`

- [ ] **Step 1: Failing tests:** `test_os_lock_is_exclusive` (two `OsFileSystem` locks on one file in `tmp_path`), `test_os_atomic_write_replaces`, `test_os_resolve_follows_junction` (skip with a reason if creating a junction fails), `test_sink_drops_unknown_fields`, `test_sink_writes_one_json_object_per_line`, `test_user_file_and_env_layers`, `test_replay_backend_passes_notifications`; in `test_service_replay.py`, each through `call_tool` and a running worker thread, waiting with `get_execution_status` `wait_ms` (never `sleep`): `test_owned_drawing_commits_and_closes`, `test_borrowed_drawing_commits_without_close`, `test_bad_sheet_fails`, `test_ui_blocked_fails`, `test_timeout_fails`, `test_backend_lost_fails`, `test_sp_warning_reaches_status_and_report`, `test_restart_recovers_interrupted_job` (stop mid-job with a blocking provider, start a new `CoreService` on the same folder), `test_report_readable_after_restart`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the Python suite and the C# suite. Expected: PASS. If the C# transcript harness cannot replay a `csharp` scenario without a C# code change, set that scenario to `sides: ["python"]` and report it; do not change C# code.

### Task 10: Contract table check

**Files:**
- Create: `tests/contract/test_tool_table.py`

- [ ] **Step 1: Failing tests:** `test_table_matches_contract_files` (parses the 12.4.4 table in `docs/api/tool-contracts.md`; `SHIPPED_PHASES = {"1a"}`; rules of 12.4.4), `test_every_shipped_tool_registered` (the registry's names equal the shipped rows), `test_contract_errors_are_catalogued`. Write a broken temp copy of the table in the test to show the parser catches a mismatch (`test_table_check_detects_mismatch`).
- [ ] **Step 2:** Run. Expected: FAIL until the parser exists, then PASS.
- [ ] **Step 3:** Implement the parser in the test module.
- [ ] **Step 4:** Run the Python suite. Expected: PASS.

### Task 11: Handoff and full verification

**Files:**
- Modify: `HANDOFF.md` (AGENTS.md section 5): state M5, spec v1.22, open items K3 and J11, the M6 scope above and its owner approvals, the cancel and notification limits of ADR-053, and that `standards/iso/templates/` was committed in `1b49268` (correcting the Known Issues line that calls it untracked).
- Modify: `apps/core-service/README.md`, `packages/cad-application/README.md` only if they describe the scaffold wrongly.

- [ ] **Step 1:** Run, from the repo root, and paste the summary lines into the report: `uv sync`; `uv run python scripts/generate_contracts.py --check`; `uv run ruff check`; `uv run ruff format --check`; `uv run pyright`; `uv run lint-imports`; `uv run pytest`; `uv run pytest --cov=packages/cad-application/src --cov=apps/core-service/src --cov-report=term -q packages/cad-application apps/core-service` (expected ≥ 80%); `dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj`.
- [ ] **Step 2:** Confirm `git status --short standards/` prints nothing.
- [ ] **Step 3:** Update `HANDOFF.md` with the verified counts.

## Out of scope (milestone 6 and later)

- Named-pipe transport, session discovery, heartbeat, the `IpcClient` reader thread, the core pipe and `core.json`, the stdio front-end, MCP resources (`cad://…` links are returned but not served).
- The add-in pipe host and the snapshot adapter; any live run; A14–A17.
- Live K3: reading the owner's sheet formats and shipping title-block mappings.
- The draft-view warning (J11); `produce_drawing` and other mutating jobs; `recover_execution`.
- The CI token counter of 12.3 (M5 uses the bytes ÷ 4 bound).

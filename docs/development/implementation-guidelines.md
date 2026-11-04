# Implementation Guidelines

How to write the code, as opposed to what it must do. These guidelines change without a specification version bump, but a change that breaks one of the rules below needs a review that says why.

## G1 · COM objects in the in-process add-in

The add-in runs inside SOLIDWORKS (ADR-028), so it shares SOLIDWORKS's COM objects instead of owning separate proxies. Releasing objects SOLIDWORKS still uses can crash it, and holding objects across documents leaks memory.

- **Release only what you created and finished with**, with `Marshal.ReleaseComObject` in a `finally` block. Typical cases are enumerators, selection data, and temporary entities from loops over faces and edges.
- **Never call `Marshal.FinalReleaseComObject`.** Never release the `ISldWorks` application object, a document (`IModelDoc2`) or a feature manager that other code may hold.
- **Never cache SOLIDWORKS objects across commands.** A command looks up what it needs by ID (5.3.6) and drops it when it ends. Documents may be closed, rebuilt or replaced between commands.
- **No SOLIDWORKS object leaves the UI thread.** Commands convert results to plain data before returning (8.6.2).
- **Loops over many entities** release each per-iteration object before moving to the next.
- **Leak check.** The live suite runs a 1,000-command stress scenario and fails if the SOLIDWORKS process's handle count or private memory grows more than a set margin after a forced garbage collection.

## G2 · Python layering and the backend port

Principle 9 (core logic testable without CAD) only holds if nothing below the application layer imports the IPC client.

- **Dependency direction**, enforced by an import-linter contract in CI:

  ```
  apps/mcp-server        → core-service protocol client only
  apps/core-service      → cad-application
  cad-application        → cad-ir, cad-compiler, cad-drawing, cad-verification, cad-references, cad-geometry
                           + ports: Backend, BackendProvider, Store, Clock, IdSource, FileSystem, EventLog
  cad-protocol           implements Backend (talks to the add-in)
  cad-ir                 → nothing else of ours
  ```

- **Ports.** `Backend` is the operation vocabulary of 6.5 (`apply_batch`, `snapshot_drawing`, `read_features`, `geometry_candidates`, document actions), typed with the generated IPC models. Those live in `cad_ir.generated.ipc`, because `cad-application` may import `cad-ir` but never `cad-protocol`. It is declared as a `typing.Protocol` in `cad_application.ports`, and `cad-protocol` implements it structurally without importing it. `Store` is section 13.2. `Clock` and `IdSource` make time and ULIDs injectable for determinism tests (15.6); `Clock` also owns waiting on a condition (ADR-053).
- **Ports added for jobs and the store (v1.22) [Builder's call].** All are `typing.Protocol`s in `cad_application.ports`.
  - `BackendProvider.acquire(on_notification) -> Backend` returns the connected session, delivering its notifications to the callback, or raises with `BACKEND_LOST` or `BACKEND_SESSION_AMBIGUOUS` (8.6.1). Session discovery and the real pipe implement it in the transport milestone; until then core-service tests use one built on `replay_backend`.
  - `FileSystem`: `resolve` (links and junctions), `stat`, `read_bytes`, `list_dir`, `write_atomic`, `write_new`, `append_line` (flush and `fsync`), `remove`, `make_dirs`, `lock_exclusive`. The OS implementation lives in `core_service`; `MemoryFileSystem` in `cad_application.testing` can fail at the nth write, `fsync` or rename to simulate a crash.
  - `EventLog.emit(event, level, **fields)` (G3).
- **Test doubles.** `ReplayBackend` plays recorded transcripts (15.5); `FakeStore` is `FileStore` over `MemoryFileSystem`, so it has the same atomicity rules by construction. Tests never patch `cad-protocol` internals.
- **Pure core.** `cad-ir`, `cad-compiler`, `cad-drawing` checks and placement are pure functions of their inputs: no file I/O, no clock, no globals. Effects happen in `cad-application`.

## G3 · Logging and correlation

Section 14 lists what each operation logs. This is how.

- **Format:** JSON Lines, one object per event, from both the Python processes and the add-in. Common fields: `ts` (UTC, ISO 8601 with milliseconds), `level`, `process` (`front-end`, `core`, `addin`), `pid`, `event`, `request_id`, `job_id`, `operation_id`, `document`, `duration_ms`, `error_code`.
- **Location:** `%LOCALAPPDATA%\sw-mcp\logs\<process>-<date>.jsonl`, rotated daily, kept `logging.retention_days` (13.3).
- **Correlation:** the front-end creates `request_id`. Every core-service and add-in message carries `request_id`, `job_id` and `operation_id` in `params._meta` (ADR-036, ADR-041), and every log line written while handling it includes them.
- **Where IDs come from.** Until the front-end exists, the core-service entry point creates `request_id` (`req_` plus a ULID from `IdSource`) for each tool call. The job engine creates `job_id` when a job is submitted, and `operation_id` (`<job_id>:<seq>`, 13.2.3) per operation. Every `Backend` call passes them as `meta` (`cad_ir.generated.ipc.Meta`), which the client sends as `params._meta`.
- **Sink.** `cad_application` emits through the `EventLog` port and never formats lines itself. `core_service` provides the JSON Lines sink above; tests use a list. The sink drops any field outside the common list and an allowed extra list (`state`, `from`, `to`, `tool`, `reason`, `count`), so a value passed by mistake cannot reach the file.
- **Never logged:** part geometry, file contents, session tokens, custom-property values beyond part number and revision. Paths and IDs are fine.
- **Levels:** `info` for lifecycle events and one line per command; `debug` for per-operation detail; `warning` for recoverable problems (a fallback taken, a deprecated tool used, ADR-042); `error` with an error code for anything returned as an error.

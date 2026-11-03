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
                           + ports: Backend, Store, Clock, IdSource
  cad-protocol           implements Backend (talks to the add-in)
  cad-ir                 → nothing else of ours
  ```

- **Ports.** `Backend` is the operation vocabulary of 6.5 (`apply_batch`, `snapshot_sheet`, `read_features`, `geometry_candidates`, document actions), typed with the generated IPC models. `Store` is section 13.2. `Clock` and `IdSource` make time and ULIDs injectable for determinism tests (15.6).
- **Test doubles.** `ReplayBackend` plays recorded transcripts (15.5); `FakeStore` is an in-memory store with the same atomicity rules. Tests never patch `cad-protocol` internals.
- **Pure core.** `cad-ir`, `cad-compiler`, `cad-drawing` checks and placement are pure functions of their inputs: no file I/O, no clock, no globals. Effects happen in `cad-application`.

## G3 · Logging and correlation

Section 14 lists what each operation logs. This is how.

- **Format:** JSON Lines, one object per event, from both the Python processes and the add-in. Common fields: `ts` (UTC, ISO 8601 with milliseconds), `level`, `process` (`front-end`, `core`, `addin`), `pid`, `event`, `request_id`, `job_id`, `operation_id`, `document`, `duration_ms`, `error_code`.
- **Location:** `%LOCALAPPDATA%\sw-mcp\logs\<process>-<date>.jsonl`, rotated daily, kept `logging.retention_days` (13.3).
- **Correlation:** the front-end creates `request_id`. Every core-service and add-in message carries `request_id`, `job_id` and `operation_id` in `params._meta` (ADR-036, ADR-041), and every log line written while handling it includes them.
- **Never logged:** part geometry, file contents, session tokens, custom-property values beyond part number and revision. Paths and IDs are fine.
- **Levels:** `info` for lifecycle events and one line per command; `debug` for per-operation detail; `warning` for recoverable problems (a fallback taken, a deprecated tool used, ADR-042); `error` with an error code for anything returned as an error.

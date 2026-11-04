# 8.6 Add-in Runtime

> Specification v1.26, section 8.6. Index and section map: [specifications/README.md](../specifications/README.md).

How the C# add-in (ADR-028) starts, is found by the core service (ADR-041), runs commands on SOLIDWORKS's thread, bounds their time, and leaves the engineer's SOLIDWORKS as it found it. The wire protocol is ADR-036; version handling is ADR-045.

## 8.6.1 Loading and session discovery

The add-in can load two ways, and both must work:
- **The engineer starts SOLIDWORKS** with the add-in enabled at startup (registered per user, ADR-038). No launcher is involved.
- **The launcher** (`sw-mcp-launch`) starts `SLDWORKS.exe` with the add-in enabled and waits for the session file below. It does nothing else.

On `ConnectToSW`, the add-in:
1. Checks the SOLIDWORKS version (ADR-045). On an unsupported version, it stays loaded but answers every `session.hello` with `BACKEND_VERSION_UNSUPPORTED`.
2. Generates a session token: 32 random bytes from the OS cryptographic generator, base64url-encoded.
3. Creates the pipe `\\.\pipe\sw-mcp-addin-<SOLIDWORKS pid>-<8 random hex>` with an ACL for the current user only (section 14).
4. Writes `%LOCALAPPDATA%\sw-mcp\sessions\<SOLIDWORKS pid>.json`, readable only by the current user:

   ```json
   { "pipe": "sw-mcp-addin-14872-9f3c01ab", "token": "…", "pid": 14872,
     "solidworks": { "version": "2025", "service_pack": "5.0" },
     "addin_version": "0.1.0", "protocol": "1.0", "started_at": "2026-11-03T09:12:44Z" }
   ```

On `DisconnectFromSW` it deletes the file and closes the pipe.

**Discovery by the core service.** The core lists the session files, deletes those whose `pid` is no longer a running `SLDWORKS.exe`, and connects according to `solidworks.session` (13.3):
- `auto` (default): exactly one live session must exist. With none, tools that need SOLIDWORKS fail with `BACKEND_LOST`. With several, they fail with `BACKEND_SESSION_AMBIGUOUS`, listing the PIDs.
- `<pid>`: that session only.

This replaces the launcher handing the token to Python (ADR-032): the session file is the only handoff, whoever started SOLIDWORKS.

## 8.6.2 Threading and dispatch

All SOLIDWORKS API calls run on SOLIDWORKS's main (UI) thread (8.3 rule 2). Nothing else runs there for longer than one command.

| Thread | Does | Never does |
| --- | --- | --- |
| Pipe thread (one, background) | Reads and writes frames, parses JSON-RPC, validates the token, answers `session.ping`, puts commands on the command queue | Call any SOLIDWORKS API |
| UI thread | Takes one command at a time from the queue and runs it to completion; raises document-event notifications | Block on pipe I/O |

- **Handing work to the UI thread.** In `ConnectToSW`, which runs on the UI thread, the add-in captures the thread's `SynchronizationContext`. If there is none, it creates a hidden WinForms control and uses its `BeginInvoke`. The pipe thread posts each command through it. Phase 0 proves this under load (assumption A14, section 18).
- **One command at a time.** The queue has a single consumer. A posted command that finds another still running waits in the queue; it is never run in parallel.
- **Cancellation** is checked between operations of an `ops.apply` batch and before each sheet of a `drawing.snapshot`, never inside a SOLIDWORKS call (8.4).
- **Results** are serialized on the UI thread into plain data, so no SOLIDWORKS object ever reaches the pipe thread (implementation guideline G1).

## 8.6.3 Time limits and health

| Limit | Default | On expiry |
| --- | --- | --- |
| UI thread does not start a queued command | 30 s | `session.ui_blocked` notification. Commands stay queued. The core fails the running job with `BACKEND_UI_BLOCKED` (8.3 rule 12) |
| One command runs too long | 120 s (`cad-read`: 30 s) | The core reports `EXEC_TIMEOUT` and does not resend (8.3 rule 8). The add-in lets the command finish and records its result under its operation ID, so the core can ask later |
| Job total | Per job type (16): `produce_drawing` 10 min | Job FAILED with the conflict list so far |
| Heartbeat | `session.ping` every 10 s while idle | 3 missed pongs → the core treats the session as lost (`BACKEND_LOST`) |

All limits are configurable (13.3). A command cannot be cancelled while it runs inside a SOLIDWORKS call; the limits only decide when the core stops waiting.

## 8.6.4 Engineer settings guard

Rules 11 and 12 of 8.3 change SOLIDWORKS user preferences: sketch inference and snapping, rebuild error popups, missing-reference and newer-version prompts, and graphics updates. In a shared session (8.3 rule 13) those are the engineer's settings.

- **Every preference change goes through one `SettingsGuard`.** Direct calls to `SetUserPreferenceToggle`, `SetUserPreferenceIntegerValue` and similar setters outside the guard are banned by the analyzer (ADR-038).
- **Before the first change in a job,** the guard records the original value of each preference it will touch in memory and in `%LOCALAPPDATA%\sw-mcp\settings-restore-<pid>.json`.
- **At the end of every job,** whether COMMITTED, FAILED or ABORTED, the guard restores the originals and deletes the file. Per-view and per-document switches (`EnableGraphicsUpdate`, `AddToDB`) are restored when the command that set them ends.
- **After a crash,** the add-in finds the restore file on its next load and restores the values before it accepts any connection.
- The guard's list of preferences lives in code. Each entry has a live test that changes it, runs a job, and checks that it was restored, including after a simulated crash.

## 8.6.5 Documents and events

- **Ownership.** At the start of each job, the add-in records which documents are open and which is active. Documents opened during the job are owned by it; the rest are borrowed. Closing and saving follow ADR-046.
- **Document events** (`RegenNotify`, `FileSaveNotify`, `DestroyNotify`, active-document changes) are raised as `document.event` notifications (ADR-036). For a document the running job holds, an event the job did not cause interrupts the job between commands (8.3 rule 13). The core records events for other documents for external-edit detection (9.3).
- **The "AI job running" banner** (8.3 rule 13) is a non-modal window owned by the add-in. Its Stop button sends the same cancellation as `cancel_execution`.

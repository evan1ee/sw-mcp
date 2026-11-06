# ADR-032: Python owns jobs, lifecycle and journal

- **Status:** Proposed — Builder's call
- **Source:** specification v1.9, section 19

## Decision

Python owns jobs, lifecycle and journal; the add-in is stateless apart from completed operation IDs; IPC commands are coarse; the pipe is user-only with a session token

## Rationale

A crash on either side has a defined outcome; IPC cost stays bounded; other local processes cannot drive SOLIDWORKS

## Amendment: exceptions for the part chain MVP (owner decision, 2026-11-05)

"Stateless apart from completed operation IDs" gains two stated exceptions, both in the add-in and neither a second source of truth for jobs:

- **Ownership table.** A small table, keyed by document path and job ID, holds `owned`, `instance_id` and `previous_active`. `part.create` and `document.open` write it, and a check only ever matches the requesting job. It lets the add-in refuse to save or close a part the job does not own, so a core bug cannot damage an engineer's part (ADR-022, ADR-046).
- **Close tracking.** The add-in subscribes `DestroyNotify2` on each tracked part document and forgets its table and ledger entries there. Before it trusts an entry it also checks `GetOpenDocumentByName(fullPath)`, because `FileCloseNotify` did not fire for an API close in the 2026-11-05 spike. Nothing here survives an add-in restart, and the core's journal stays authoritative.

## Where it applies

- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.2

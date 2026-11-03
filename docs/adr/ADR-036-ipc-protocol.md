# ADR-036: IPC protocol between Python and the add-in

- **Status:** Proposed
- **Source:** specification v1.10, readiness review (2026-11-03)

## Context

ADR-028 and ADR-032 fix the shape of the link: a named pipe, user-only ACL, per-session token, coarse commands, Python owning job state and the add-in deduplicating by operation ID. The wire format, framing, versioning, cancellation and error reporting were not defined, and Phase 1a starts with this link.

## Decision

- **Transport.** One duplex named pipe per SOLIDWORKS session, `\\.\pipe\sw-mcp-addin-<SOLIDWORKS pid>-<random>`, created by the add-in with an ACL for the current user only (section 14). One client connection at a time; that client is the core service (ADR-041), which serves every MCP front-end.
- **Framing.** Each message is a 4-byte little-endian length followed by that many bytes of UTF-8 JSON. Maximum frame 64 MiB; larger results (a big sheet snapshot) are split into numbered chunks of one response.
- **Messages.** JSON-RPC 2.0 shape: requests with `id`, `method`, `params`; responses with `result` or `error`; notifications without `id`. Message schemas live in `schemas/ipc/` (ADR-035).
- **Handshake.** The first request is `session.hello` with the session token from the add-in's session file (8.6.1) and the protocol version. The add-in replies with its own protocol version, SOLIDWORKS version and service pack, and its capability list. A major-version mismatch or a wrong token closes the pipe.
- **Commands are coarse** (8.2): `ops.apply` (an operation batch), `drawing.snapshot` (a whole sheet into a Drawing Geometry Snapshot), `features.read` (a feature-tree page, 5.8), `geometry.candidates` (entities and signatures for a batch of references, ADR-049), `document.*`. Every mutating command carries `operation_id`; a repeated ID returns `DUPLICATE_OPERATION` with the original result (ADR-032).
- **Session methods:** `session.hello`; `session.ping` (heartbeat, 8.6.3); `session.completed_operations` (the operation IDs the add-in finished, asked for on every reconnect, 13.2.3).
- **Progress and events** are notifications from the add-in: `job.progress`, `document.event` (regen, save, close, active-document change, for 8.3 rule 13 and 9.3), `session.ui_blocked`.
- **Cancellation.** `job.cancel` is a request; the add-in finishes the current command, then answers. A timeout on the Python side is reported as a timeout and never resent (8.3 rule 8).
- **Errors** use the catalogue in ADR-037 in the JSON-RPC `error.data.code` field.
- **Units.** All lengths and angles on the wire are in the IR's declared units for IR payloads and sheet millimetres for drawing geometry; the add-in converts to and from system units (8.3 rule 9).

## Rationale

Length-prefixed JSON is simple to implement in both languages, easy to log and replay, and fast enough for coarse commands; A1 measures it on real sheets before 1a starts. JSON-RPC gives a well-known request/response/notification shape without adopting a framework. A versioned handshake lets the Python side and the add-in be upgraded separately.

## Consequences

- Recorded IPC transcripts double as integration-test fixtures and debugging evidence.
- If A1 shows JSON too slow for snapshots, the fallback is a binary encoding (MessagePack) for `drawing.snapshot` only, behind the same framing and a new minor protocol version.

## Where it applies

- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.2, 8.3, 8.4
- [architecture/production-drawings.md](../architecture/production-drawings.md) — section 11.5.1
- [architecture/security-reliability.md](../architecture/security-reliability.md) — section 14

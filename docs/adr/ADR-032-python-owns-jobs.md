# ADR-032: Python owns jobs, lifecycle and journal

- **Status:** Proposed — Builder's call
- **Source:** specification v1.9, section 19

## Decision

Python owns jobs, lifecycle and journal; the add-in is stateless apart from completed operation IDs; IPC commands are coarse; the pipe is user-only with a session token

## Rationale

A crash on either side has a defined outcome; IPC cost stays bounded; other local processes cannot drive SOLIDWORKS

## Where it applies

- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.2

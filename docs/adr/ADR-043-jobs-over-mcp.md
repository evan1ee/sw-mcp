# ADR-043: Long-running jobs over MCP

- **Status:** Proposed
- **Source:** specification v1.13, open decision M3

## Context

Jobs (8.4) such as `produce_drawing` can run for minutes (16). Section 12.2 says such tools return an execution ID at once, but not how the agent learns the outcome or how long results stay available. MCP offers several mechanisms: polling with a tool, progress notifications tied to a request, and, in newer protocol revisions, task primitives. Not every client supports the newer ones. An agent that polls in a tight loop spends a turn's worth of tokens on each check.

## Decision

- **Polling is the contract.** Every job tool returns `{execution_id, queued_position}` at once. The agent learns the outcome through `get_execution_status`, which every MCP client can call.
- **Long-poll to save turns.** `get_execution_status` takes an optional `wait_ms` (at most 20 000). It returns as soon as the job changes state or finishes, or when `wait_ms` runs out, whichever comes first. Tool descriptions tell agents to pass `wait_ms` instead of calling repeatedly.
- **Status response:** job type, state (8.4), `queued_position` while queued, `progress` (`{step, of, message}`), `started_at`, `elapsed_ms`, `retry_after_ms` (a hint for the next poll), and, once finished, `report_id` (when the job type produces a report) or `error` (ADR-037).
- **Progress notifications** are sent as well when the call that started the job carried an MCP progress token, for clients that show progress. They are a convenience; nothing depends on them.
- **MCP task primitives** are not used in Phase 1. When the pinned SDK (ADR-034) supports them, they may be added as an alternative in a minor tool contract version (ADR-042). Polling stays.
- **Results outlive the client.** Jobs belong to the core service (ADR-041), so any front-end can fetch status and reports by ID, including after the starting agent disconnected.
- **Retention.** Job records and reports are kept for 7 days after the job finishes (`core.job_retention_days`, 13.3). A report referenced by a stored drawing record (13.2) is kept as long as that record. An expired ID returns `EXEC_NOT_FOUND`.
- **Cancellation** of a job is only through `cancel_execution`. An MCP `notifications/cancelled` for the starting call, or for a waiting `get_execution_status`, ends that call only and never the job.

## Rationale

Polling works with every client and keeps jobs independent of the connection that started them, which ADR-041 requires. Long-polling keeps polling cheap: one call per state change instead of one per second. Treating progress notifications and tasks as optional extras avoids depending on client features that vary.

## Consequences

- `get_execution_status` is the most-called tool, so its response must stay well under the 800-token summary budget (12.3).
- The core keeps a small in-memory wait list per job to answer long-polls.
- Adds `EXEC_NOT_FOUND` to the error catalogue (ADR-037).

## Where it applies

- [api/tool-contracts.md](../api/tool-contracts.md) — section 12.4.5
- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.4
- [api/mcp-interface.md](../api/mcp-interface.md) — section 12.2, 12.3
- [ADR-041](ADR-041-core-service-topology.md), [ADR-044](ADR-044-mcp-protocol-baseline.md)

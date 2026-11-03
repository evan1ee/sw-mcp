# ADR-041: A long-lived core service behind stateless MCP front-ends

- **Status:** Proposed
- **Source:** specification v1.12, open decision X1

## Context

ADR-032 makes the Python side the single owner of jobs, the execution journal and the project store, and ADR-036 lets exactly one client hold the add-in's pipe. But MCP clients normally start their MCP server as a child process over stdio (ADR-034). Three problems follow:

- **Two agents mean two owners.** A second client starts a second Python process, which either cannot reach SOLIDWORKS or competes with the first for jobs and store writes.
- **Jobs die with the client.** Closing or restarting the agent kills its stdio server, and with it any running `produce_drawing` job, even though SOLIDWORKS is still working.
- **No one queue.** Section 8.4 requires one job queue per SOLIDWORKS session, which needs one process to hold it.

Options considered:

1. **Core service plus stateless stdio front-ends** (chosen).
2. **One MCP server with an exclusive lock.** Simple, but a second agent is refused, and losing the client still fails the running job.
3. **One MCP server over Streamable HTTP, run as a daemon.** One process, but it needs a localhost port and HTTP authentication, and many MCP clients are configured for stdio only.

## Decision

**Three kinds of process.**

| Process | Count | Owns | Language |
| --- | --- | --- | --- |
| MCP front-end (`apps/mcp-server`) | One per MCP client, started by the client over stdio | Nothing. Translates MCP requests and responses, holds no job or store state | Python |
| Core service (`apps/core-service`) | One per Windows user | Tool handlers, jobs and their queue (8.4), the execution journal, the project store (13.1), the add-in connections | Python |
| Execution add-in (`apps/execution-server`) | One per SOLIDWORKS process | Nothing beyond completed operation IDs (ADR-032) | C# |

```
MCP client ──stdio──▶ MCP front-end ─┐
MCP client ──stdio──▶ MCP front-end ─┼─core pipe──▶ Core service ──add-in pipe──▶ Add-in in SOLIDWORKS
                                     ┘   (ADR-036 framing)          (ADR-036)
```

**Front-end ↔ core link.**
- A named pipe `\\.\pipe\sw-mcp-core-<user SID>` with an ACL for the current user only, using the framing, JSON-RPC message shape and handshake of ADR-036. The core accepts many front-end connections at once.
- The core writes `%LOCALAPPDATA%\sw-mcp\core.json` (pipe name, session token, core version, protocol version), readable only by the current user. A front-end must present that token in `session.hello`.
- Methods mirror the MCP tool contracts (12.4): `tools.call` carries the tool name, arguments and `request_id`, and returns the result envelope (ADR-037). `tools.list` returns the tool definitions for the toolsets the front-end was configured with. Progress arrives as notifications, which the front-end forwards as MCP progress notifications when the client asked for them.

**Starting and stopping the core.**
- A front-end that finds no running core starts one as a detached process with no console, then waits up to 10 s for `core.json`. While it runs, the core holds an exclusive lock on `%LOCALAPPDATA%\sw-mcp\core.lock`, so a second core cannot start; a core that cannot take the lock exits.
- The core stays up while any front-end is connected or any job is queued or running. After 30 minutes with neither, it exits (configurable).
- `sw-mcp-core stop` asks a running core to finish its current command, mark queued jobs ABORTED, and exit.

**Behavior that follows.**
- **Client disconnects do not touch jobs.** A job started through one front-end keeps running when that front-end exits. Its result is fetched by execution ID through any front-end (ADR-043).
- **Several agents share one queue per SOLIDWORKS session** (8.4). Read-only tools run concurrently against the store. Mutating tools are serialized per module document and still require `expected_revision` (13.1).
- **The core is the only client of each add-in pipe** (ADR-036). It discovers SOLIDWORKS sessions as described in 8.6.1. In Phase 1 it drives exactly one session, chosen by configuration when more than one exists.
- **A core crash** is the "Python process dies" case of ADR-032. The next core reads the journal and marks unfinished jobs FAILED with `EXEC_INTERRUPTED` (13.2.3). Front-ends see the core pipe close, return `BACKEND_LOST` for calls in flight, and reconnect to the new core on the next call.
- **Version skew.** The front-end and core exchange protocol versions in the handshake. If they differ in major version and the core has no jobs, the front-end asks it to stop and starts its own version. If the core is busy, the front-end returns `BACKEND_BUSY` with the running core's version.

## Rationale

The core service is the only option that gives ADR-032's single owner and section 8.4's single queue a process that outlives any one agent, and it keeps the stdio setup every MCP client supports. Running the same framing on both pipes means one protocol implementation and one set of replay tests (15.5). Option 2 remains the fallback if Phase 1a needs to cut scope: it is the core service with the front-end merged in and only one connection allowed.

## Consequences

- One more process to package and observe. Logs carry `request_id` from front-end through core to add-in (section 14, guideline G3).
- Tool logic lives in the core (`packages/cad-application`). The front-end package stays small and changes rarely.
- The core's lifecycle needs its own tests: two front-ends sharing a queue, a front-end exiting mid-job, a core crash mid-job, and version skew.
- Moving to a Streamable HTTP transport later means adding an HTTP front-end next to the stdio one; the core does not change.

## Where it applies

- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.2, 8.4
- [architecture/data-management.md](../architecture/data-management.md) — section 13.1
- [architecture/security-reliability.md](../architecture/security-reliability.md) — section 14
- [development/repository-structure.md](../development/repository-structure.md) — section 17
- [ADR-032](ADR-032-python-owns-jobs.md), [ADR-034](ADR-034-python-toolchain.md), [ADR-036](ADR-036-ipc-protocol.md)

# ADR-053: A synchronous job engine driven by one worker thread

- **Status:** Proposed — Builder's call
- **Source:** specification v1.22, register J6 (milestone 5 planning)

## Context

The core service (ADR-041) runs one job at a time per SOLIDWORKS session (8.4) while `store` tools, long-polls (`get_execution_status` with `wait_ms`, ADR-043) and `cancel_execution` arrive at any moment from any front-end. The `IpcClient` behind the `Backend` port (G2) is synchronous and blocking, and single-threaded: one caller reads the transport. Tests must be deterministic, with no sleeps or wall-clock waits (15.6).

Options considered:

1. **Threads around a synchronous kernel** (chosen). A thread-safe `JobEngine` in `cad-application` holds jobs, the queue and a `threading.Condition`; its `run_next()` runs one queued job to its end on the calling thread. The core service owns one worker thread that calls it in a loop; tool handlers call the engine from request threads.
2. **asyncio core.** Natural for many concurrent long-polls, but every `Backend` call blocks, so each would go through `run_in_executor` anyway, and the store and journal writes would need an async file layer. Two concurrency models in one process.
3. **One thread for everything, jobs as cooperative steps.** Deterministic, but a blocking snapshot read (up to 120 s, 8.6.3) would stall every `store` tool, which 12.4.3 says runs at once.

## Decision

- `cad_application.jobs.JobEngine` is a state machine plus a FIFO queue, guarded by one lock and one `Condition`. Its public calls are `submit`, `status`, `wait_for_change`, `cancel`, `run_next` and `recover`. `run_next()` takes the oldest PLANNED job and runs it synchronously; it returns `False` when the queue is empty. It never starts a thread.
- `core_service` owns the only worker thread: `while running: engine.wait_for_work(); engine.run_next()`. Request handling runs on other threads and only calls `submit`, `status`, `wait_for_change` and `cancel`.
- **Waiting goes through the `Clock` port.** `Clock` has `now()` (UTC), `monotonic_s()` and `wait(condition, timeout_s)`. The system clock calls `condition.wait(timeout_s)`; `FakeClock.wait` advances its own time by `timeout_s` and returns at once. A long-poll whose wait expires therefore runs in a test without real waiting.
- **The engine lock is never held across a `Backend` call or a file write.** State changes take the lock, append the journal record, replace `job.json`, update memory, `notify_all()`, release.
- **Cancel while EXECUTING** sets the job's cancel flag under the lock, then calls `Backend.cancel()` outside it, from the request thread. The worker checks the flag at each boundary defined in 8.4.

## Rationale

The kernel is plain synchronous code, so every lifecycle rule is tested by calling `run_next()` on the test thread with a replay or fake backend, step by step. The one place threads meet, the `Condition`, is small and tested on its own. It keeps the blocking `IpcClient` unchanged and leaves asyncio out of a codebase that has none.

## Consequences

- **Known limitation until the transport milestone:** the real `IpcClient` cannot take `Backend.cancel()` from a second thread while the worker is blocked in a call, because one reader owns the transport. Until the client gains a reader thread (milestone 6), cancellation during EXECUTING is tested only with a fake backend that blocks on an `Event`. The `cancel_running` transcript is still used to test what the client does with the add-in's `EXEC_CANCELLED` answer.
- The same blocking client delivers `session.ui_blocked` and `document.event` notifications only when the current call returns, so the core acts on them then (8.4).
- One long-poll holds one request thread. The transport milestone bounds that thread pool; M5 has no pool.
- Revisit if many concurrent front-ends make thread-per-request too heavy, or when several SOLIDWORKS sessions are driven at once (one worker per session).

## Where it applies

- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.4
- [development/implementation-guidelines.md](../development/implementation-guidelines.md) — guideline G2
- [ADR-041](ADR-041-core-service-topology.md), [ADR-043](ADR-043-jobs-over-mcp.md)

# ADR-059: COM and STA execution rules in the add-in

- **Status:** Accepted — owner decision, 2026-11-05
- **Source:** specification v1.31, section 8.8.7; architecture review F13, F21, F29; settles the "COM release rule" decision that review listed as needing an ADR. Implements 8.3 and 8.6.2

## Context

Three problems exist in code that 8.3 and 8.6.2 appear to cover:

1. **Thread.** `SwAddin.cs:98` falls back to a base `SynchronizationContext`, whose `Post` runs on the thread pool. The spec requires a hidden WinForms control. A14 passed under load but did not record which path ran.
2. **Queue.** `RunNext` returns false while a command runs, and a drain refused then is lost. `RunNext` also writes the response on the UI thread, so a slow pipe can block SOLIDWORKS, against 8.6.2.
3. **Release rule.** G1 forbids releasing `ISldWorks` and `IModelDoc2`. `SwAddin.cs:255` and `:434` release them, and AGENTS.md's wording is broader than G1. An in-process add-in shares one runtime wrapper per COM object within its application domain, so a release can invalidate an object other code still holds.

## Decision

**Thread**
- `ConnectToSW` creates a hidden WinForms control on the UI thread, forces its handle, and uses `BeginInvoke`. The base-context fallback is removed. If the thread is not STA at that point, the add-in refuses to start its server and logs why.
- Before each command, the drain asserts it is on the captured thread. A failure is a defect, reported, and the command is not run.

**Queue**
- One consumer. When a command ends, the drain re-posts if the queue is not empty. A re-entrant drain is refused and relies on that re-post.
- The UI thread hands response bytes to the pipe thread's outgoing queue and never performs pipe I/O.

**Lifetime (applied to G1 and AGENTS.md)**
- Release, in `finally` or through `ComScope`: temporary objects a loop or a read obtained, such as enumerators, faces, edges, surfaces, selection data and math objects.
- Never release: `ISldWorks`, `IModelDoc2` and its derived interfaces, `IFeatureManager`, `ISketchManager`, `IModelDocExtension`, or any object obtained from another owner. Never call `FinalReleaseComObject`.
- Never cache across commands. No COM object leaves the UI thread. Results are plain data.
- Every thread, timer and event entry point catches, logs with correlation (G3), and survives. An unhandled exception there can end `SLDWORKS.exe`.

## Rationale

The hidden control is what 8.6.2 already specifies, and it runs on the thread that owns the message pump. Keeping all pipe I/O on the pipe thread keeps a stalled client from freezing an engineer's SOLIDWORKS. The narrower release rule follows G1, which was written for this in-process case. It avoids the crash risk of releasing shared wrappers, at the cost of holding a few objects until the garbage collector runs, and the leak test measures that cost.

## Consequences

- `System.Windows.Forms` is referenced by `ExecutionServer.AddIn` only. It is part of .NET Framework, so this is no new package.
- The stress test in G1 becomes the evidence for the release rule. If handles or memory grow past its margin, the rule returns here.
- `SwAddin.cs:98`, `:255`, `:434` and the response path change. Drawing adapters' releases change when the freeze lifts, unless shared code forces it earlier, in which case the owner is asked.
- Live test: log the thread ID, apartment state and dispatch path once per session, recording the fact F21 could not establish.

## Where it applies

- [architecture/solidworks-adapter.md](../architecture/solidworks-adapter.md) — section 8.8.7
- [architecture/addin-runtime.md](../architecture/addin-runtime.md) — section 8.6.2
- [development/implementation-guidelines.md](../development/implementation-guidelines.md) — G1
- [AGENTS.md](../../AGENTS.md) — section 2

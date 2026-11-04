# ADR-052: Newtonsoft.Json for the add-in's IPC messages

- **Status:** Proposed — Builder's call
- **Source:** specification v1.21, register K6

## Context

The add-in targets .NET Framework 4.8 and loads inside `SLDWORKS.exe` (ADR-028, ADR-038), which has no JSON library in the framework and whose `.exe.config` is not ours. So binding redirects are not available to us.

| Option | For | Against |
| --- | --- | --- |
| `System.Text.Json` from NuGet | Current Microsoft library | On net48 it pulls in `System.Memory`, `System.Buffers`, `System.Threading.Tasks.Extensions` and others, whose version conflicts are normally fixed by binding redirects, which an in-process add-in cannot supply |
| `Newtonsoft.Json` | One strong-named assembly, no dependencies on net48; `JToken` suits opaque payloads | Older design; SOLIDWORKS may load a different version into the process |
| Hand-written JSON | No dependency | Code to own and test, for no benefit |

## Decision

`ExecutionServer.Core` uses `Newtonsoft.Json` 13.x, the assembly deployed beside the add-in.

## Rationale

A dependency-free, strong-named assembly is the option least exposed to the one hazard specific to in-process add-ins. Strong naming means another version already in the process loads side by side rather than conflicting. This is expected, not proven: **assumption A17** tests it on real SOLIDWORKS.

## Consequences

- If A17 fails, the fallback is merging the library into the add-in assembly at build time (ILRepack), with no code change.
- JSON handling stays inside `Core`, so a later swap touches one project and the generator's output.

## Where it applies

- [ADR-028](ADR-028-in-process-solidworks-add-in.md), [ADR-036](ADR-036-ipc-protocol.md), [ADR-038](ADR-038-csharp-add-in-build.md)
- [specifications/roadmap.md](../specifications/roadmap.md) — section 18 (A17)

# ADR-038: Building, registering and testing the C# add-in

- **Status:** Proposed
- **Source:** specification v1.10, readiness review (2026-11-03)

## Context

ADR-002 and ADR-028 fix .NET Framework 4.8 and an in-process `ISwAddin`. How the add-in is built, which SOLIDWORKS assemblies it references, how it is registered on a developer machine and how its logic is tested without SOLIDWORKS were not defined.

## Decision

- **Project format.** SDK-style `.csproj` files targeting `net48`, platform `x64`, C# latest language version, nullable reference types on, warnings as errors. One solution, `apps/execution-server/ExecutionServer.sln`.
- **Structure.** `ExecutionServer.AddIn` (the `ISwAddin`, pipe host, dispatcher; thin), `ExecutionServer.Core` (protocol handling, operation-ID ledger, unit conversion, no SOLIDWORKS references), `ExecutionServer.Adapters` (per-domain SOLIDWORKS adapters: documents, sketches, features, geometry, assemblies, drawings), and `ExecutionServer.Tests`.
- **SOLIDWORKS interop.** The interop assemblies (`SolidWorks.Interop.sldworks`, `swconst`, `swpublished`) are referenced from the local SOLIDWORKS installation through an MSBuild property `SolidWorksInstallDir`, never committed. A build without SOLIDWORKS builds and tests `Core` only.
- **Registration.** A development script registers the add-in for the current user (`HKCU`), not machine-wide, so developers need no admin rights. Assumption A13 confirms SOLIDWORKS 2025 loads a per-user registered add-in; the fallback is an elevated `RegAsm /codebase` script.
- **Tests.** xUnit for `Core` on any Windows machine; adapter tests run in the live suites (15.2) on the SOLIDWORKS machine.
- **Banned APIs.** A Roslyn analyzer config bans document-unit dimension calls (8.3 rule 9), `SelectByID2` with display names (8.3 rule 11) and `RunMacro2` (section 14).

## Rationale

Keeping `Core` free of SOLIDWORKS references makes most of the C# side testable on a normal CI runner, matching principle 9. Referencing the installed interop assemblies avoids redistributing vendor binaries. Per-user registration keeps the developer loop fast and avoids admin prompts.

## Consequences

- The C# build has two modes: `Core`-only (CI) and full (SOLIDWORKS machine).
- The banned-API rules become build errors, not review comments.

## Where it applies

- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.2, 8.3
- [development/repository-structure.md](../development/repository-structure.md) — section 17
- [development/testing-strategy.md](../development/testing-strategy.md) — section 15.1, 15.2
- [specifications/roadmap.md](../specifications/roadmap.md) — section 18 (A13)

# ADR-062: Version isolation through one capability table

- **Status:** Accepted — owner decision, 2026-11-05
- **Source:** specification v1.31, sections 8.8.10 and 8.9.7; architecture review F3, F24. Extends ADR-045

## Context

ADR-045 sets the policy: build against the oldest supported version, gate newer members by named capability, and admit a version only through the benchmark. The code does not follow it yet. It has an exact `== "2025"` check, hard-coded lists in `SwAddin.cs`, an invented fallback revision, and a parser that loses the revision's third segment. `feature.create` also hides which feature types an add-in supports. The options for version differences are scattered checks, per-version assemblies, conditional compilation, or a central table.

## Decision

- One pure `CapabilityTable` in `ExecutionServer.Core` maps a parsed version to support status and named capabilities. Only `SessionProbe` reads the running version. Handlers ask for capabilities, and an architecture test bans version checks elsewhere.
- Capability names add `op:<op>:<variant>`, so lowering can reject a missing feature type at compile time (6.6). This needs no schema change.
- A version value that cannot be read is an error, never a default.
- No per-version assemblies and no conditional compilation. Native signatures sit in one method per call, behind neutral call records.
- Observed behaviour differences are named facts in the table, tested again when a version is admitted.

## Rationale

A central pure table can be unit-tested with any version string, offline. Numbered member names such as `FeatureExtrusion3` suggest that the API adds new members rather than changing old ones, so one interop build may serve several versions, and per-version assemblies are not needed yet. That is unproven here, and K13 tracks it.

## Consequences

- **K13 is a precondition for supporting a second major.** `Private=false` with an add-in-folder-only resolver may not bind on a newer install.
- Per-version assemblies need a new ADR, and only if a required member is removed with no replacement.
- The compiler's profile hash changes when capability contents change, so cached plans are recompiled, as 6.6 intends.

## Where it applies

- [architecture/solidworks-adapter.md](../architecture/solidworks-adapter.md) — section 8.8.10
- [specifications/solidworks-adapter.md](../specifications/solidworks-adapter.md) — section 8.9.7
- [ADR-016](ADR-016-solidworks-2025-only.md), [ADR-038](ADR-038-csharp-add-in-build.md), [ADR-045](ADR-045-solidworks-version-compatibility.md)

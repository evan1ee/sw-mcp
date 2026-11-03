# ADR-045: SOLIDWORKS version and service-pack compatibility

- **Status:** Proposed
- **Source:** specification v1.13, open decision S1

## Context

The target is SOLIDWORKS 2025 and newer (ADR-016), with supported versions pinned to exact service packs (15.2). The add-in is compiled once against one set of interop assemblies (ADR-038) but must load and behave correctly on every supported version. Some API members exist only from a given version or service pack, and drawing and annotation behavior changes between service packs.

## Decision

- **Build against the oldest supported version.** The interop assemblies come from the oldest supported version and service pack. Code that compiles therefore uses only members that exist everywhere.
- **Newer API members only behind a capability check.** A member added after the oldest version is called through a small, named capability (for example `api.annotation_display_data_v2`). The add-in sets each capability at startup from the running version, reports the list in `session.hello` (ADR-036, 6.6), and every use falls back or fails with `BACKEND_CAPABILITY_MISSING`. A call that assumes a capability without checking it is a build error through the analyzer of ADR-038.
- **Supported-versions table.** `docs/development/supported-versions.md`, created in Phase 0, lists each supported major version with its pinned service pack, the date it was added, the benchmark run that admitted it, and known deviations. It is the only source for "supported".
- **Admitting a version or service pack** requires the live suites and the full drawing benchmark to pass on it (15.2, 11.8). Until then, it is unsupported.
- **At startup** the add-in compares the running version with the table, compiled into the add-in:
  - Supported: normal operation.
  - Same major, newer service pack than any pinned: runs, with a warning in `session.hello` and in every drawing report.
  - Older than the oldest supported, or a newer major: the add-in loads but refuses `session.hello` with `BACKEND_VERSION_UNSUPPORTED`, naming the running and supported versions.
- **Every report records** the SOLIDWORKS version and service pack it was produced on (11.5.1).

## Rationale

Building against the oldest version turns accidental use of newer API members into compile errors. Named capabilities make version-dependent behavior explicit and testable, and they feed the backend capability profile the compiler needs. Gating on the benchmark ties "supported" to evidence, not to a release date.

## Consequences

- Dropping the oldest supported version is a deliberate change: move the interop assemblies forward, then remove capability checks that are now always true.
- The SOLIDWORKS CI machine needs every supported version available, as separate installs or images (15.2).
- Adds `BACKEND_CAPABILITY_MISSING` and `BACKEND_VERSION_UNSUPPORTED` to the error catalogue (ADR-037).

## Where it applies

- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.2, 8.6
- [development/testing-strategy.md](../development/testing-strategy.md) — section 15.2
- [ADR-016](ADR-016-solidworks-2025-only.md), [ADR-036](ADR-036-ipc-protocol.md), [ADR-038](ADR-038-csharp-add-in-build.md)

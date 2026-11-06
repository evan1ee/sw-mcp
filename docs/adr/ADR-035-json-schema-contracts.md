# ADR-035: JSON Schema files are the contract

- **Status:** Proposed
- **Source:** specification v1.10, readiness review (2026-11-03)

## Context

Every IR module, derived artifact and report must be versioned, validatable without SOLIDWORKS and readable by agents (3.3, 5.5). `get_feature_schema` returns JSON Schema to agents (12.3). The IPC protocol (ADR-036) is shared between Python and C#. One of the two languages' type definitions could be the source, or a neutral schema file could.

## Decision

- **JSON Schema draft 2020-12 files in `schemas/` are the source of truth** for every IR module, the IR bundle manifest, derived artifacts (Resolved Scheme, Drawing Layout snapshots, Drawing Geometry Snapshot, execution plan, reports), IPC messages and the error catalogue (ADR-037).
- One directory per contract, one file per major version: `schemas/drawing-intent/v0.json`. `schemas/common/` holds the shared-core types (IDs, `<module>:<document_id>/<item_id>` references, units, tolerances, geometry references).
- Every document carries `schema_version` (`major.minor`). Minor versions only add optional fields (3.3 rule 6).
- Python models and C# IPC message types are generated from the schemas by the project's own generator ([ADR-051](ADR-051-contract-type-generator.md), replacing `datamodel-code-generator`). CI regenerates both and fails on any diff.
- Validation: structural checks use the JSON Schema; semantic checks (cycles, cross-module references, ownership rules) are Python code in `cad-ir`, with error codes from ADR-037.
- `get_feature_schema` serves a compacted view of the same files (no descriptions beyond one line, no `$defs` the request does not need), so agent-facing schemas cannot drift from the validator.

## Rationale

A language-neutral contract keeps Python and C# honest, gives agents the exact schema the validator uses, and lets schemas be reviewed and diffed on their own. Generating code from schemas, rather than schemas from code, keeps the contract stable when internal code is refactored.

## Consequences

- Schema changes are reviewed as contract changes; code follows.
- Some Pydantic conveniences (custom validators on models) are not used; semantic rules live in `cad-ir` instead.
- Phase 0 schema work is writing these files, with example documents from the spec as test fixtures.

## Where it applies

- [architecture/overview.md](../architecture/overview.md) — section 3.3
- [architecture/part-feature-graph-ir.md](../architecture/part-feature-graph-ir.md) — section 5.5
- [api/mcp-interface.md](../api/mcp-interface.md) — section 12.3
- [specifications/roadmap.md](../specifications/roadmap.md) — section 18 (Phase 0)

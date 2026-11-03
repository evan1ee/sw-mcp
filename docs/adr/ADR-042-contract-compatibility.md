# ADR-042: One compatibility policy for every contract

- **Status:** Proposed
- **Source:** specification v1.12, open decision V1

## Context

The system has several contracts that change independently: the IR module schemas, derived artifacts (Resolved Scheme, layout snapshots, Drawing Geometry Snapshot, plans, reports), MCP tool definitions, the add-in IPC protocol (ADR-036), the core-service protocol (ADR-041), the configuration schema and the project-store layout (13.1). ADR-035 says only that minor versions add optional fields. Nothing says what a reader does with unknown fields, how many old versions are accepted, how stored files written by an older release are read, or how a breaking change ships. DoD item 13 requires backward-compatible MCP interfaces, and engineers will keep `.cad/` stores in version control for years.

## Decision

**Versions.** Every contract carries `<major>.<minor>`: IR and artifacts in `schema_version`, IPC and core-service protocols in the handshake, MCP tools as one **tool contract version** reported in the server's `serverInfo` and in `tools.list`, configuration in `config_version`, the store in `.cad/store.json`.

**What a minor version may do.** Add an optional input field; add an output field; add an enum value to an *output*; add a tool, IPC method or error code; relax a constraint on input. Everything else is breaking and needs a new major version, including:

- removing or renaming a field, tool, method or error code;
- adding a required input field, or making an optional one required;
- narrowing a type, range or input enum;
- changing a field's meaning, units or default;
- adding an enum value to an *input* that older servers would reject (allowed in a minor only when the server ships it in the same release).

**Readers.**

| Contract | Unknown fields | Unknown output enum values | Versions accepted |
| --- | --- | --- | --- |
| Authored IR (submitted by agents or engineers) | Rejected (`additionalProperties: false`), so typos fail loudly | — | Current and previous major |
| Derived artifacts, reports, stored snapshots | Ignored and preserved on rewrite | Treated as "unknown", never as an error | Current and every older major that has a migration |
| IPC and core-service messages | Ignored | Treated as "unknown" | Negotiated in the handshake: same major required |
| MCP tool inputs | Rejected | — | Current tool contract major, plus previous major during deprecation |
| Configuration | Rejected, with the file and key named | — | Current and previous major |

**Stored data.** Each major version of each schema ships a pure migration function from the previous major, with fixtures of real old documents. The store migrates on read, in memory. A stored revision is never rewritten in place (3.4.5); a migrated document is written only as a new revision when it next changes, so old revisions stay byte-identical for version control.

**Deprecation.** A field, tool, method or error code is marked `deprecated` in its schema, with the replacement named, for at least one minor release before the major release that removes it. Deprecated MCP tools say so in the first line of their description. Using a deprecated item is logged with the caller's `request_id`.

**Enforcement in CI.** Each release tags a snapshot of every contract (schemas, generated tool definitions, IPC method list, error catalogue). CI diffs the working tree against the last release snapshot with a schema-diff tool and classifies every change as minor or breaking by the rules above. A breaking change without a major bump fails, and so does a removal without a prior deprecation. Migration fixtures for every supported old major run in the unit suite.

## Rationale

One rule set across all contracts means one diff tool, one review checklist, and no layer inventing its own policy. Strict input readers catch agent mistakes early; lenient readers of derived data let the system read its own older output. Migrating on read and never rewriting stored revisions keeps the store diff-friendly and auditable.

## Consequences

- Every schema change gets classified in review, with CI as the backstop.
- Supporting the previous major means carrying migration code for one major cycle, which is the price of stores that outlive releases.
- The tool contract version covers all tools together, so a breaking change to one tool bumps the whole MCP contract. Breaking changes are therefore batched into major releases.

## Where it applies

- [architecture/shared-ir-core.md](../architecture/shared-ir-core.md) — section 3.4.5
- [architecture/overview.md](../architecture/overview.md) — section 3.3 rule 6
- [architecture/data-management.md](../architecture/data-management.md) — section 13.1
- [api/mcp-interface.md](../api/mcp-interface.md) — section 12
- [ADR-035](ADR-035-json-schema-contracts.md), [ADR-036](ADR-036-ipc-protocol.md), [ADR-041](ADR-041-core-service-topology.md)

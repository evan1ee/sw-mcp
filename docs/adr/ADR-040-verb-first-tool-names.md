# ADR-040: Verb-first MCP tool names, distinct from the reference

- **Status:** Accepted (owner decision)
- **Source:** specification v1.11, section 12.1. Replaces the noun-first `<object>_<action>` rule adopted in v1.8.

## Context

Version 1.8 made tool names noun-first (`document_open`, `part_graph_apply`) partly so they could never equal the reference implementation's verb-first names. The owner prefers verb-first names, which read as commands and match common MCP practice. With verb-first names, three natural names equal reference tools: `open_document`, `save_document` and `close_document`. Running both servers side by side (2.4) still needs distinct names.

## Decision

- Every tool is named `<action>_<object>`: `apply_part_graph`, `produce_drawing`, `check_drawing`, `get_execution_status`.
- The rule against sharing a name with the reference implementation stays, enforced by the CI check in 12.1. When a natural name collides, the object word changes, not the action. Because `open_document`, `save_document` and `close_document` collide, all six file tools use `cad_file` so they read as one family: `list_cad_files`, `create_cad_file`, `open_cad_file`, `save_cad_file`, `close_cad_file`, `inspect_cad_file`.
- Distinctive reference action words stay replaced: `apply` for `submit`, `check` for `verify`, `diff` for `compare`.
- Job types (8.4) use the name of the tool that starts them: `produce_drawing`, `check_drawing`.

## Rationale

Verb-first names are the owner's preference and what agents most often see in other MCP servers. Keeping the clash check, rather than word order, as the guarantee of distinctness protects coexistence (2.4) at the cost of one object word for the file tools.

## Consequences

- Distinctness now depends entirely on the CI check, so the reference tool list recorded in Phase 0 must be complete and kept current.
- The Phase 0 name-mapping table maps reference names to these verb-first names.
- Checked on 2026-11-03 against the 51 tools the reference server exposes: no collisions.

## Where it applies

- [api/mcp-interface.md](../api/mcp-interface.md) — section 12.1, 12.2, 12.3
- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.4
- [specifications/product-spec.md](../specifications/product-spec.md) — section 2.4

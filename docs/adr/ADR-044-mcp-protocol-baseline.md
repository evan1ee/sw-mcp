# ADR-044: MCP protocol baseline and the features used

- **Status:** Proposed
- **Source:** specification v1.13, open decision M4

## Context

The MCP specification is published in dated revisions, and later revisions added features this system wants: structured tool output with an `outputSchema`, resource links in tool results, and tool annotations. Section 17 plans "tools, resources, prompts" without fixing a minimum revision or saying which results are tool output and which are resources. Changing that after the tools exist touches every tool contract (12.4).

## Decision

- **Minimum protocol revision: 2025-06-18**, the first with structured tool output, `outputSchema` and resource links. The front-end advertises the newest revision the pinned SDK supports (ADR-034) and negotiates down to the client's, but not below the minimum. A client that cannot reach it gets an initialization error naming the required revision.
- **Transport:** stdio only, from the front-end (ADR-041). A Streamable HTTP front-end may be added later without changing the core.
- **Tools**
  - Each result carries the ADR-037 envelope as `structuredContent`, valid against the tool's `outputSchema` (12.4.1).
  - The text content is a single line of summary, for example `drawing check FAIL: D1 ×2, D7 ×1 (report rep_01J…)`. It never repeats the JSON, which would double the token cost (12.3).
  - `isError` is `true` exactly when the envelope's `ok` is `false`. A failed drawing check is `ok: true` (ADR-037).
  - Tool annotations come from the contract file (12.4.1).
- **Resources** hold large, read-on-demand data. Tool results point to them with resource links instead of embedding them:

  | URI template | Content |
  | --- | --- |
  | `cad://reports/{report_id}` and `cad://reports/{report_id}/{section}` | Full drawing and verification reports |
  | `cad://snapshots/{snapshot_id}` | Drawing Geometry Snapshot (11.5.1) |
  | `cad://modules/{module}/{document_id}@{revision}` | A stored IR module document |
  | `cad://schemas/{name}/v{major}` | JSON Schemas (ADR-035), for agents that want more than `get_feature_schema` gives |

  The server exposes them as resource templates, not as a full listing, so large stores do not flood `resources/list`. Reading a resource is checked against 12.5 like any file access.
- **Prompts:** none in Phase 1.
- **Not used:** sampling, elicitation and roots. When a reference is ambiguous, the tool returns `REF_AMBIGUOUS` with the candidates, and the agent asks the user (7.4); the server never prompts the user itself. Allowed folders come from configuration (12.5), not from client roots.
- **Progress and cancellation:** as in ADR-043.
- **Server identity:** `serverInfo.version` is the release version. The tool contract version (ADR-042) is in the server's `instructions` text and in every `tools.list` response's metadata.

## Rationale

Structured output with schemas lets agents and tests rely on exact shapes, and that requires the 2025-06-18 revision. Moving bulk data into resources keeps tool responses inside the 12.3 budgets while full detail stays one read away. Leaving out client-dependent features (sampling, elicitation, roots) keeps behavior the same in every client.

## Consequences

- Clients older than the minimum revision are not supported.
- Every tool contract needs an `output` schema from the start.
- The contract tests (15.5) check `structuredContent` against `outputSchema` and the text line against a length limit.

## Where it applies

- [api/tool-contracts.md](../api/tool-contracts.md) — section 12.4
- [api/mcp-interface.md](../api/mcp-interface.md) — section 12.1, 12.3
- [development/repository-structure.md](../development/repository-structure.md) — section 17
- [ADR-037](ADR-037-error-model.md), [ADR-041](ADR-041-core-service-topology.md), [ADR-043](ADR-043-jobs-over-mcp.md)

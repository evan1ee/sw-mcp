# ADR-037: Error model and response envelope

- **Status:** Proposed
- **Source:** specification v1.10, readiness review (2026-11-03)

## Context

The spec requires structured errors (8.2), stable failure reporting (10.4, 11.6), correlated logs with error codes (section 14) and summary-first responses (12.3), but defines no error codes or response shape. Agents need to branch on errors without parsing English text.

## Decision

- **One error catalogue**, `schemas/common/errors.json`, shared by Python and C#. Codes are `UPPER_SNAKE_CASE` with a domain prefix and never reused:

  | Prefix | Domain | Examples |
  | --- | --- | --- |
  | `IR_` | Schema and semantic validation | `IR_SCHEMA_INVALID`, `IR_SCHEMA_VERSION_UNSUPPORTED`, `IR_REFERENCE_UNRESOLVED`, `IR_MODULE_MISSING`, `IR_RULE_VIOLATED`, `IR_CYCLE` |
  | `REV_` | Revisions and concurrency | `REV_CONFLICT` (13.1 `expected_revision`) |
  | `REF_` | Geometry references | `REF_AMBIGUOUS`, `REF_NOT_FOUND`, `REF_SIGNATURE_MISMATCH`, `REF_NOT_IN_VIEW`, `REF_LOW_CONFIDENCE` |
  | `COMPILE_` | Compiler (6.7) | `COMPILE_FAILED`, `COMPILE_UNSUPPORTED_FEATURE`, `COMPILE_PLAN_INVALID` |
  | `EXEC_` | Jobs and lifecycle | `EXEC_TIMEOUT`, `EXEC_CANCELLED`, `EXEC_INTERRUPTED`, `EXEC_INTERRUPTED_BY_USER`, `EXEC_NOT_FOUND`, `EXEC_DOCUMENT_DIRTY`, `DUPLICATE_OPERATION` |
  | `BACKEND_` | SOLIDWORKS and IPC | `BACKEND_LOST`, `BACKEND_BUSY`, `BACKEND_UI_BLOCKED`, `BACKEND_REBUILD_ERROR`, `BACKEND_READ_ONLY`, `BACKEND_SESSION_AMBIGUOUS`, `BACKEND_VERSION_UNSUPPORTED`, `BACKEND_CAPABILITY_MISSING` |
  | `DRAWING_` | Drawing pipeline and checks | `DRAWING_CHECK_FAILED`, `DRAWING_RELAYOUT_EXHAUSTED`, `DRAWING_UNSUPPORTED_PART` |
  | `AUTH_` | Permissions | `AUTH_SOURCE_WRITE_NOT_ALLOWED` (ADR-022), `AUTH_PATH_DENIED` |
  | `STORE_` | Project store (13.2) | `STORE_LOCKED`, `STORE_CORRUPT` |
  | `CONFIG_` | Configuration (13.3) | `CONFIG_INVALID` |

- Each error carries `code`, a one-line `message`, `retryable` (`never`, `after_fix`, `safe`), and `details` (IDs of the module, item, feature, view or check involved). Stack traces go to logs, never to the agent.
- **MCP tool responses** use one envelope: `{ "ok": bool, "data": … | null, "error": … | null, "ids": { "request_id", "execution_id"?, "report_id"? } }`. Failed checks are results (`ok: true`, report says FAIL), not errors; errors mean the tool could not do its job.
- Every log line carries the same `request_id` and `operation_id` across Python and C# (section 14).

## Rationale

Agents act on codes, not prose; a closed, versioned catalogue keeps codes stable across releases (DoD item 13). Separating "the check failed" from "the tool failed" stops an agent from retrying a drawing that ran correctly and found defects.

## Consequences

- Adding a code is a schema change reviewed like any other contract change.
- The envelope counts against the response token budgets in 12.3, so it stays small.

## Where it applies

- [api/mcp-interface.md](../api/mcp-interface.md) — section 12.3
- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.2
- [architecture/verification-engine.md](../architecture/verification-engine.md) — section 10.4
- [architecture/security-reliability.md](../architecture/security-reliability.md) — section 14

# 14. Security and Reliability

> Specification v1.37, section 14. Index and section map: [specifications/README.md](../specifications/README.md).

**Security:** local execution by default; both local pipes, MCP front-end to core service (ADR-041) and core service to add-in (8.2), are restricted to the current user and require a session token; explicit authorization for file access; path validation; source parts and models are not modified without explicit permission, read-only and PDM-managed files are never made writable or checked out by the system (11.1, ADR-022); no arbitrary shell execution through CAD tools; no unrestricted execution of generated scripts; no SOLIDWORKS macro execution (`RunMacro2`, VBA or VSTA macros) through any tool; confirmation for destructive operations; isolated handling of external CAD files; auditable logs.

**Reliability:** detect CAD disconnection and unexpected document closure; handle COM exceptions; prevent conflicting concurrent document operations; timeouts distinct from cancellation; detect stale references; keep diagnostics; recover from partial execution where possible.

**Observability:** each operation logs request ID, operation ID, document ID, feature ID, backend, start/end time, duration, result, error code and message. Logs are correlated across Python and C#.

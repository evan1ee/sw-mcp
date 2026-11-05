# 12.4 Tool Contracts and 12.5 File Access

> Specification v1.29, sections 12.4–12.5. Index and section map: [specifications/README.md](../specifications/README.md).

## 12.4 Tool Contracts

Every MCP tool has one contract file. Tool definitions sent to agents, the core-service handlers (ADR-041), the tool reference pages and the contract tests (15.5) are all generated from or checked against it. A tool without a contract file does not exist.

### 12.4.1 Contract file

`schemas/mcp/<tool>.json`, JSON Schema 2020-12 (ADR-035), versioned with the tool contract version (ADR-042):

| Field | Description |
| --- | --- |
| `name` | `<action>_<object>` (12.1, ADR-040) |
| `description` | First sentence ≤ 120 characters, the whole description ≤ 400 characters. No embedded per-feature schemas (12.3 rule 2). A deprecated tool starts with `Deprecated: use <tool>.` |
| `toolset` | One of the toolsets in 12.3 |
| `phase` | First increment that ships it (`1a`, `1b`, `1c`, `2`, …). Tools from later phases are not registered |
| `kind` | `store`, `cad-read`, `cad-session` or `job` (12.4.3) |
| `mutates` | `true` if it changes a store document, a CAD document, a file or a job. Mutating tools on store documents take `expected_revision` (13.1) |
| `input` | JSON Schema of the arguments. `additionalProperties: false` (ADR-042) |
| `output` | JSON Schema of the envelope's `data` (ADR-037) |
| `errors` | Error codes it may return, from the catalogue (ADR-037). Returning an unlisted code is a contract-test failure |
| `examples` | At least one valid call with its response, used by the contract tests |
| `deprecated` | Optional, with `replacement` |

**File format [Builder's call].** A contract file is a JSON document with `$schema` (2020-12) and `$id` (`https://sw-mcp.invalid/schemas/mcp/<tool>.json`, 3.4.8) beside the fields above, so the schema registry holds it and `input` and `output` are reachable as `<$id>#/input` and `<$id>#/output`; they refer to shared types by relative `$ref`. Because `deprecated` is a JSON Schema keyword, it is the boolean `true`, and `replacement` is a separate field naming the tool. The contract files themselves are validated against `schemas/mcp/contract/v0.json`, which fixes the field types, the `name` pattern `^[a-z]+(_[a-z]+)+$`, the enums for `toolset`, `phase` and `kind`, `description` ≤ 400 characters, `errors` as catalogue codes with no duplicates, and `examples` as a non-empty list of `{arguments, response}`, where `response` is a whole envelope (ADR-037). The 120-character first sentence, the `Deprecated: use <tool>.` prefix, and `mutates: true` requiring `expected_revision` in `input` for `store` tools that change a store document are checked by the contract tests, since a schema cannot express them.

Generated MCP tool definitions map `input` to `inputSchema` and `output` (wrapped in the envelope) to `outputSchema`, and set the tool annotations from the contract: `readOnlyHint` = not `mutates`, `destructiveHint` for `delete_feature` and `close_cad_file`, `idempotentHint` for `store` and `cad-read` tools (ADR-044). All four hints are always written, because MCP's default for `destructiveHint` is `true`; `openWorldHint` is `false` **[Builder's call]**. The derivation is one function in `cad-application`, tested on every contract file.

### 12.4.2 Shared conventions

**Inputs.**
- References use the forms of 3.4.2. File paths are absolute Windows paths, checked by 12.5.
- `detail`: `"summary"` (default) or `"full"` on every tool that can return large data (12.3 rule 4).
- Pagination: `cursor` (opaque string from the previous response) and `page_size` (default 50, maximum 200). Responses carry `next_cursor`, absent on the last page. A cursor is valid for 10 minutes and only for the same call arguments.
- `expected_revision`: required on every mutating tool that changes a store document. Omitting it is a schema error, not "latest wins".
- IR documents: `create_*` and `apply_*` take the whole document; `update_*` takes `{ref, expected_revision, patch}` with an RFC 6902 JSON Patch; all other tools take `DocumentRef`s or a bundle manifest (ADR-048).
- No tool takes a `request_id`; the front-end assigns one per call (ADR-041) and returns it in `ids`.

**Outputs.**
- Always the ADR-037 envelope. References in outputs are always pinned (`@<revision>`, 3.4.2 rule 4).
- Summaries follow 12.3 rule 4: failures listed, passes counted, large sections replaced by a resource link (ADR-044).
- Numbers follow 3.4.3: lengths in the document's units, angles in degrees, sheet coordinates in millimetres.
- `ids` [Builder's call]: always `request_id`; `execution_id` whenever the call names or creates a job; `report_id` whenever the response is about a stored report. The values repeat those in `data` so a client can correlate without reading `data`.

**Arguments and unknown tools [Builder's call].** Arguments that fail the contract's `input` schema, including an unknown property, a missing required one or an invalid `cursor`, return `IR_SCHEMA_INVALID` with `details.issues` (3.4.7 issues, pointers into the arguments). A tool name with no contract file is not a tool: the core answers a protocol error, which the front-end turns into an MCP `-32602` error, never an envelope. In process, `CoreService.call_tool` raises `UnknownTool` for it (a name that is not a string included), and the transport (milestone 6) maps that to the protocol error (register J14). An unexpected exception in a handler is a defect, not an input problem: `call_tool` lets it through like a contract violation, and the transport answers JSON-RPC `-32603`, logging the exception's class name only. An `OSError` from the store is not unexpected: it is `STORE_UNAVAILABLE` (13.2.2) (register J13).

**Handler result [Builder's call].** Handlers in `cad-application` return a `ToolResult`: the envelope (ADR-037) and `summary`, the one-line text of ADR-044, at most 200 characters. The transport milestone carries exactly this through the core pipe; the front-end maps `summary` to the text content and the envelope to `structuredContent`.

**Cursors [Builder's call].** A cursor is base64url of a small JSON object: the offset, the issue time, and a hash of the call's other arguments (canonical form, 3.4.4, without `cursor`). A cursor 10 minutes old or older (by the `Clock` port), from different arguments, or that does not decode, is an invalid argument. Cursors are not secret; a forged offset only selects another page of data the caller may already read.

### 12.4.3 Tool kinds

| Kind | Touches | Concurrency | Time limit | Returns |
| --- | --- | --- | --- | --- |
| `store` | Project store and local files only | Runs at once, alongside jobs. Writes to one document are serialized | 5 s | Result |
| `cad-read` | One short read command through the add-in | Queued; runs between two commands of a running job. Fails with `BACKEND_BUSY` if it needs a document the running job holds (8.4) | 30 s | Result |
| `cad-session` | Opens, creates, saves or closes a file in SOLIDWORKS | Same as `cad-read` | 120 s | Result |
| `job` | Anything longer or multi-step | One job at a time per SOLIDWORKS session (8.4) | Per job type (16) | `execution_id` at once (ADR-043) |

A `cad-read` or `cad-session` call that exceeds its limit returns `EXEC_TIMEOUT`. The command is not resent (8.3 rule 8), and its outcome is checked on the next call that needs the document.

### 12.4.4 Tool table

Every tool in 12.2, its toolset, first phase, kind and whether it mutates. This table and the contract files must agree; CI checks it. The check parses this table: every contract file must have a row with the same toolset, phase, kind and `mutates` (a cell starting with `yes`); every row of a phase that ships in the current build (`1a` until Phase 1b starts) must have a contract file; rows of later phases may have none yet, but a file that exists must match its row **[Builder's call]**.

| Tool | Toolset | Phase | Kind | Mutates |
| --- | --- | --- | --- | --- |
| `check_drawing` | drawing | 1a | job | no (reads only; never saves, 8.4) |
| `get_drawing_report` | drawing | 1a | store | no |
| `get_execution_status` | core | 1a | store | no |
| `cancel_execution` | core | 1a | store | yes (job) |
| `list_cad_files` | core | 1b | store | no |
| `create_cad_file` | core | 1b | cad-session | yes |
| `open_cad_file` | core | 1b | cad-session | no (session only) |
| `save_cad_file` | core | 1b | cad-session | yes |
| `close_cad_file` | core | 1b | cad-session | no (session only) |
| `inspect_cad_file` | core | 1b | cad-read | no |
| `get_feature_tree` | core | 1b | cad-read | no (stores the read-only graph) |
| `inspect_part_graph` | core | 1b | store | no |
| `validate_bundle` | core | 1b | store | no |
| `inspect_geometry` | geometry | 1b | cad-read | no |
| `create_drawing_intent` | drawing | 1b | store | yes |
| `update_drawing_intent` | drawing | 1b | store | yes |
| `validate_drawing_intent` | drawing | 1b | store | no |
| `produce_drawing` | drawing | 1b | job | yes |
| `relayout_drawing` | drawing | 1b | job | yes |
| `get_drawing_layout` | drawing | 1b | store | no |
| `update_drawing_layout` | drawing | 1b | job | yes |
| `apply_part_graph` | core | 1c | job | yes |
| `update_part_graph` | core | 1c | job | yes |
| `validate_part_graph` | core | 1c | store | no |
| `diff_part_graph` | core | 1c | store | no |
| `list_feature_types` | core | 1c | store | no |
| `get_feature_schema` | core | 1c | store | no |
| `compile_bundle` | core | 1c | cad-read | no |
| `validate_plan` | core | 1c | store | no |
| `execute_plan` | core | 1c | job | yes |
| `suppress_feature` | detail | 2 | job | yes |
| `delete_feature` | detail | 2 | job | yes |
| `apply_assembly_graph` | assembly | 2 | job | yes |
| `update_assembly_graph` | assembly | 2 | job | yes |
| `validate_assembly_graph` | assembly | 2 | store | no |
| `inspect_assembly_graph` | assembly | 2 | store | no |
| `resolve_geometry` | geometry | 2 | cad-read | no |
| `create_geometry_ref` | geometry | 2 | cad-read | yes (store) |
| `validate_geometry_ref` | geometry | 2 | cad-read | no |
| `check_model` | core | 2 | job | no |
| `diff_model` | verification | 2 | job | no |
| `check_dimensions` | verification | 2 | job | no |
| `get_verification_report` | verification | 2 | store | no |
| `create_design_intent` | design_intent | 3 | store | yes |
| `update_design_intent` | design_intent | 3 | store | yes |
| `validate_design_intent` | design_intent | 3 | store | no |
| `check_wall_thickness` | verification | 3 | job | no |
| `check_draft_angle` | verification | 3 | job | no |
| `get_design_parameters` | design_intent | later (P3) | store | no |
| `recover_execution` | core | 4 | job | yes |

`apply_part_graph` and `update_part_graph` store the graph and build it in one job, which is why the `core` toolset needs no separate compile and execute tools. Creating sends a document by value, updating sends a JSON Patch, and everything else takes references (ADR-048).

### 12.4.5 Phase 1a contracts

The four tools Phase 1a ships. Their contract files are `schemas/mcp/<tool>.json`, written from this section **[Builder's call]**. IDs in inputs are checked by pattern: `job_`, `rep_` or `snap_` plus a 26-character Crockford ULID (13.2.1).

| Tool | Input | `data` |
| --- | --- | --- |
| `check_drawing` | `path` (absolute, ending `.SLDDRW` in any case); optional `sheets`: 1–64 unique, non-empty names | `execution_id`, `queued_position` |
| `get_drawing_report` | Exactly one of `report_id` and `execution_id`; `detail` (`summary`, `full`); optional `section` (`checks`, `conflicts`, `warnings`, `soft_metrics`); `cursor` and `page_size` only with `conflicts` or `warnings` | See below |
| `get_execution_status` | `execution_id`; optional `wait_ms`, 0–20000, default 0 (ADR-043) | See below |
| `cancel_execution` | `execution_id`; optional `keep_partial` (default `false`) | `execution_id`, `state`, `final`, `changes` |

**`check_drawing`.** Validates the arguments and the path (12.5), reads the file's fingerprint (13.1), then queues a job (8.4) and returns at once. Errors: `IR_SCHEMA_INVALID`, `AUTH_PATH_DENIED`, `FILE_NOT_FOUND`, `CONFIG_INVALID`, `STORE_LOCKED`, `STORE_CORRUPT`, `STORE_UNAVAILABLE`. Everything that goes wrong after the job exists is the job's `error`, not the call's. Phase 1a has no `drawing_intent` argument: D4, D6 and D9 stay `not_evaluated` (11.5.4), and supplying one is an unknown property. Phase 1b adds it as an optional argument, which is a minor change (ADR-042). Summary line: `drawing check queued: job_… (position 0)`.

**`get_drawing_report`.** Errors: `IR_SCHEMA_INVALID`, `EXEC_NOT_FOUND` (unknown or expired job or report, 13.2.4), `STORE_CORRUPT`, `STORE_UNAVAILABLE`.
- By `execution_id`, a job that has not reached COMMITTED has no report yet, and a FAILED or ABORTED one never will: `data` is then only `{execution_id, state, report_id: null}`.
- Without `section`, `detail: "summary"` returns: `report_id`, `execution_id` (when known), `drawing` (`path`, `drawing_id`), `verdict`, `calibration`, `checks` (D1–D10, each `status`, `failure_count`, `reasons`), `conflict_count`, `top_failures` (the first 5 in report order, each `check`, `sheet`, `code` or null, and at most 3 item IDs), `warning_count`, `job_warnings` (8.4) and `links` (`report`: `cad://reports/{report_id}`, `snapshot`: `cad://snapshots/{snapshot_id}`). It must stay within 600 tokens (12.3); until the CI token counter exists, a test bounds it as UTF-8 bytes of compact JSON ÷ 4 on a worst-case report. `detail: "full"` adds the report's `checks` entries in full, `sheets` and `thresholds`; the failure and warning lists stay behind `section` or the resource.
- With `section`, `detail` is ignored and `data` is `{report_id, section, items, next_cursor?}`: `checks` and `soft_metrics` (the report's `sheets`) whole, `conflicts` (the report's `failures`) and `warnings` paginated (12.4.2).
- Summary line: `drawing check FAIL: D1 ×2, D7 ×1 (report rep_…)`; with a `not_evaluated` verdict it names the unevaluated checks instead.

**`get_execution_status`.** Errors: `IR_SCHEMA_INVALID`, `EXEC_NOT_FOUND`, `STORE_UNAVAILABLE`. `data`: `execution_id`, `job_type`, `state`; `queued_position` (PLANNED only); `progress` `{step, of, message}` (EXECUTING and VERIFYING; for `check_drawing` `of` is 4: open, read back, check, store); `started_at` (entering VALIDATED, null before); `elapsed_ms` (since `started_at`, until the job ended; absent while `started_at` is null, register J19); `retry_after_ms` (non-final states only: 0 when the call returned on a state change, 1000 otherwise); `report_id` (COMMITTED with a report); `error` (FAILED and ABORTED, the ADR-037 object); `warnings` (job warnings); `documents_unknown` (paths whose state is unknown after a crash, 13.2.3). With `wait_ms`, the call returns as soon as the state differs from the state when the call arrived, or when `wait_ms` runs out; a job already final returns at once. Progress changes do not end the wait. Summary line: `job_… check_drawing EXECUTING (2/4 reading back)`.

**`cancel_execution`.** Errors: `IR_SCHEMA_INVALID`, `EXEC_NOT_FOUND`, `STORE_UNAVAILABLE`. A PLANNED job is ABORTED before the call returns; a running one gets a cancel request (8.4) and the call returns at once with its current state and `final: false`, after which the agent polls `get_execution_status`. A finished job is left alone and returned with `final: true`; this is not an error. `changes` lists `{document, action}` for what the job changed; `keep_partial` keeps a partial result where a job type has one (ADR-046). `check_drawing` changes nothing, so its `changes` is always `[]` and `keep_partial` has no effect. Summary line: `job_… ABORTED` or `cancel requested: job_… EXECUTING`.

## 12.5 Projects and File Access

**Allowed roots.** The core service reads and writes only below the roots listed in the user configuration (`access.allowed_roots`, 13.3). Project configuration cannot add roots. A path outside every root fails with `AUTH_PATH_DENIED`. With no roots configured, every file tool fails with that error and a message naming the setting.

**Path checks**, in this order, before any file is touched:
1. The path is absolute. Relative paths, `~`, environment variables and `\\?\` prefixes are rejected.
2. Normalize it: resolve `.` and `..`, then resolve symbolic links and junctions to their targets.
3. Compare the result against each root case-insensitively (Windows semantics), after the same normalization of the root.
4. UNC paths are allowed only when a root is itself a UNC path.

**Implementation [Builder's call].** The checks are one pure function in `cad_application.paths`, `authorize(path, settings, fs)`, over the `FileSystem` port (G2), which is the only thing that resolves links and junctions. A path that fails steps 1–4 returns `AUTH_PATH_DENIED` with `details.reason` (`not_absolute`, `home_or_env`, `device_prefix`, `outside_roots`, `unc_not_allowed`, `no_roots`); the message never echoes environment variable values. After authorization, a path that does not exist, or is a folder where a file is expected, returns `FILE_NOT_FOUND` (`after_fix`); a file that exists but cannot be read (access denied, locked by another program) returns `FILE_NOT_FOUND` with `details.reason: unreadable`, since to the caller it is equally a file the core cannot use (register J13). Step 1 also refuses a `:` anywhere after the drive (`C:`), which would name an alternate data stream (`details.reason: stream`). An environment reference is `%NAME%`, `$env:`, `${` or `$(`; any other `$` (`C:\Prices$2026\a.slddrw`) is an ordinary character. The store folder is resolved like the path: a `.cad` that is a link or junction resolving outside the allowed root of its project fails with `AUTH_PATH_DENIED`, `details.reason: store_outside_roots`; a store under `%LOCALAPPDATA%` (vault projects) is exempt **[Builder's call]**. The function also returns the project folder and the store folder, by the rules below. The store hash is SHA-256 hex of the project path after normalization and `ntpath.normcase`, as UTF-8.

**Projects.** A file's project is the nearest ancestor folder, up to its allowed root, that contains a `.cad/` store. If none does, the project is the allowed root itself, and its store is created there on the first write. When the project folder is inside a SOLIDWORKS PDM local view (`access.pdm_vault_roots`, 13.3), the store is never created in the vault. It goes to `%LOCALAPPDATA%\sw-mcp\stores\<sha256 of the normalized project path>\` instead, so the system never adds files to the vault.

**What may be written.** Store files; drawings and exports the system produced, under ADR-046; and nothing else. Source parts, assemblies and anything in a PDM vault are read-only (ADR-022). A write anywhere else fails with `AUTH_SOURCE_WRITE_NOT_ALLOWED`.

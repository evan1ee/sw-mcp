# 12.4 Tool Contracts and 12.5 File Access

> Specification v1.16, sections 12.4–12.5. Index and section map: [specifications/README.md](../specifications/README.md).

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

Generated MCP tool definitions map `input` to `inputSchema` and `output` (wrapped in the envelope) to `outputSchema`, and set the tool annotations from the contract: `readOnlyHint` = not `mutates`, `destructiveHint` for `delete_feature` and `close_cad_file`, `idempotentHint` for `store` and `cad-read` tools (ADR-044).

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

### 12.4.3 Tool kinds

| Kind | Touches | Concurrency | Time limit | Returns |
| --- | --- | --- | --- | --- |
| `store` | Project store and local files only | Runs at once, alongside jobs. Writes to one document are serialized | 5 s | Result |
| `cad-read` | One short read command through the add-in | Queued; runs between two commands of a running job. Fails with `BACKEND_BUSY` if it needs a document the running job holds (8.4) | 30 s | Result |
| `cad-session` | Opens, creates, saves or closes a file in SOLIDWORKS | Same as `cad-read` | 120 s | Result |
| `job` | Anything longer or multi-step | One job at a time per SOLIDWORKS session (8.4) | Per job type (16) | `execution_id` at once (ADR-043) |

A `cad-read` or `cad-session` call that exceeds its limit returns `EXEC_TIMEOUT`. The command is not resent (8.3 rule 8), and its outcome is checked on the next call that needs the document.

### 12.4.4 Tool table

Every tool in 12.2, its toolset, first phase, kind and whether it mutates. This table and the contract files must agree; CI checks it.

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

The four tools Phase 1a ships, in outline. Their contract files are written in Phase 0 from this table.

| Tool | Input | `data` |
| --- | --- | --- |
| `check_drawing` | `path` (`.SLDDRW`), optional `drawing_intent` (`DocumentRef`), optional `sheets` (names) | `execution_id`, `queued_position` |
| `get_drawing_report` | `report_id` or `execution_id`; `detail`; optional `section` (`checks`, `conflicts`, `soft_metrics`, `scheme`) with `cursor` | Verdict (`done`, `fail`, `not_evaluated`), per-check result D1–D10, conflict count, failures (paginated), soft metrics, links to the snapshot and full report resources |
| `get_execution_status` | `execution_id`, optional `wait_ms` (≤ 20000, ADR-043) | Job type, state (8.4), `queued_position`, progress, `report_id` when finished, error when FAILED |
| `cancel_execution` | `execution_id`, optional `keep_partial` (default `false`) | Final state and the list of changes the job made (8.4) |

## 12.5 Projects and File Access

**Allowed roots.** The core service reads and writes only below the roots listed in the user configuration (`access.allowed_roots`, 13.3). Project configuration cannot add roots. A path outside every root fails with `AUTH_PATH_DENIED`. With no roots configured, every file tool fails with that error and a message naming the setting.

**Path checks**, in this order, before any file is touched:
1. The path is absolute. Relative paths, `~`, environment variables and `\\?\` prefixes are rejected.
2. Normalize it: resolve `.` and `..`, then resolve symbolic links and junctions to their targets.
3. Compare the result against each root case-insensitively (Windows semantics), after the same normalization of the root.
4. UNC paths are allowed only when a root is itself a UNC path.

**Projects.** A file's project is the nearest ancestor folder, up to its allowed root, that contains a `.cad/` store. If none does, the project is the allowed root itself, and its store is created there on the first write. When the project folder is inside a SOLIDWORKS PDM local view (`access.pdm_vault_roots`, 13.3), the store is never created in the vault. It goes to `%LOCALAPPDATA%\sw-mcp\stores\<sha256 of the normalized project path>\` instead, so the system never adds files to the vault.

**What may be written.** Store files; drawings and exports the system produced, under ADR-046; and nothing else. Source parts, assemblies and anything in a PDM vault are read-only (ADR-022). A write anywhere else fails with `AUTH_SOURCE_WRITE_NOT_ALLOWED`.

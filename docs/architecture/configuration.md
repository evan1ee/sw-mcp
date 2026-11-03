# 13.3 Configuration

> Specification v1.18, section 13.3. Index and section map: [specifications/README.md](../specifications/README.md).

One configuration format for the core service, the MCP front-end and the add-in's limits, so no module invents its own.

## 13.3.1 Sources and precedence

Later sources override earlier ones, key by key:

1. Built-in defaults (in code, matching this section).
2. User file: `%APPDATA%\sw-mcp\config.toml`.
3. Project file: `.cad/config.toml` in the project (12.5). Read when a job or tool first touches that project, and re-read when the file changes.
4. Environment variables: `SWMCP_<SECTION>__<KEY>`, for example `SWMCP_CORE__IDLE_SHUTDOWN_MIN=60`.
5. Front-end command-line flags, for `mcp.toolsets` only.

**Security keys come from the user file only.** `access.*` and `solidworks.session` are ignored, with a warning, in project files and environment variables, so a project cannot widen what the core may touch (12.5).

## 13.3.2 Format and validation

- TOML, with `config_version = "1.0"` at the top (ADR-042). The schema is `schemas/config/v1.json`.
- Validated when read. Unknown keys and wrong types are errors that name the file, line and key. The core refuses to start on an invalid user file. An invalid project file fails the tool call that read it with `CONFIG_INVALID`.
- Durations are integers with the unit in the key name (`_s`, `_ms`, `_min`, `_days`). Lengths are millimetres (`_mm`).

## 13.3.3 Keys

| Key | Default | Meaning |
| --- | --- | --- |
| `access.allowed_roots` | `[]` | Folders the core may read and write below (12.5). Empty means no file access |
| `access.pdm_vault_roots` | `[]` | SOLIDWORKS PDM local views. Read-only; stores go outside them (12.5) |
| `mcp.toolsets` | `["core", "drawing"]` | Toolsets the front-end exposes (12.3). `["full"]` enables all |
| `core.idle_shutdown_min` | `30` | Core exits after this long with no front-ends and no jobs (ADR-041) |
| `core.job_retention_days` | `7` | Job records and reports kept (ADR-043, 13.2.4) |
| `solidworks.session` | `"auto"` | `"auto"` or a SOLIDWORKS process ID (8.6.1) |
| `solidworks.command_timeout_s` | `120` | One command (8.6.3) |
| `solidworks.read_timeout_s` | `30` | One `cad-read` command (12.4.3) |
| `solidworks.ui_blocked_s` | `30` | UI-blocked detection (8.6.3) |
| `solidworks.heartbeat_s` | `10` | Idle heartbeat interval (8.6.3) |
| `drawing.job_timeout_min` | `10` | `produce_drawing` job limit (16) |
| `drawing.relayout_max_iterations` | `8` | Re-layout bound per sheet (11.6) |
| `drawing.pin_threshold_mm` | `0.5` | Position change that counts as a manual move (11.11) |
| `drawing.check.epsilon_mm` | `0.01` | Equality tolerance for D1–D3 geometry (11.5.2) |
| `drawing.check.text_clearance_mm` | `0.5` | Minimum gap between text boxes of different annotations, D2 (11.5.2) |
| `drawing.check.line_clearance_mm` | `0.25` | Minimum gap between a text box and another annotation's lines, D2 (11.5.2) |
| `drawing.check.edge_clearance_mm` | `0.25` | Minimum gap between a text box and a model edge, D3 (11.5.2) |
| `drawing.check.font_metric_margin` | `0.1` | Text-box enlargement per side, as a fraction of text height, when extents come from font metrics (11.5.2) |
| `drawing.standard_dir` | `standards/iso` in the installation | Drafting standard, templates and title-block mapping (11.2) |
| `references.high_confidence` | set in Phase 2 | Thresholds for 7.4, calibrated on the CAD benchmark |
| `store.snapshot_keep` | `10` | Snapshots and layouts kept per drawing (13.2.4) |
| `store.backup_keep` | `5` | Drawing backups kept (ADR-046) |
| `logging.level` | `"info"` | `debug`, `info`, `warning` or `error` (guideline G3) |
| `logging.retention_days` | `14` | Log files kept (guideline G3) |

## 13.3.4 Title-block mapping

The mapping from title-block fields to value sources (11.1, 11.2) is data, kept beside the template it describes: `standards/iso/title-blocks/<template name>.toml`.

```toml
config_version = "1.0"
template = "Company-A3.slddrt"

[fields.part_number]
source = ["design_intent:metadata.part_number", "drawing_intent:context.metadata.part_number", "part_property:PartNo"]
required = true

[fields.material]
source = ["design_intent:material", "drawing_intent:context.material", "part_material"]
required = true

[fields.general_tolerance]
source = ["drawing_intent:general_tolerance"]
required = true
```

`source` lists candidates in order, and the first one present wins (3.3 rule 4). `required` fields feed check D8. The field names and template are filled in from the owner's template in Phase 0.

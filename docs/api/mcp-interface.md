# 12. MCP Interface

> Specification v1.28, section 12. Index and section map: [specifications/README.md](../specifications/README.md).

## 12.1 Principles

MCP is the interface between agent and platform, not the place for CAD logic. Tools expose semantic operations rather than hundreds of low-level calls. **Tool names are this system's own (owner decision, ADR-040).** No tool has the same name as a reference implementation tool, so the two servers can't be confused, even when both are connected to the same agent. Names are verb-first, `<action>_<object>` (`apply_part_graph`, `produce_drawing`, `check_drawing`). The reference implementation's names are verb-first too, so word order does not keep the two apart; the CI check below does. Where the natural name equals a reference tool name, the object word changes instead of the action: the reference has `open_document`, `save_document` and `close_document`, so this system's file tools all use `cad_file` (`list_cad_files`, `create_cad_file`, `open_cad_file`, `save_cad_file`, `close_cad_file`, `inspect_cad_file`). Common action words (`open`, `save`, `close`, `create`, `get`, `update`, `list`, `delete`) are used as they are. A distinctive action word the reference uses is replaced when a fitting alternative exists: `apply` instead of `submit`, `check` instead of `verify`, `diff` instead of `compare`. A CI check fails if any tool name equals one in the reference implementation's tool list recorded in Phase 0. Existing agent prompts written for the reference implementation are migrated with a name-mapping table produced in Phase 0, not by reusing its names. The code behind the tools is new.

## 12.2 Tool Categories

**A. Documents** — list_cad_files, create_cad_file, open_cad_file, save_cad_file, close_cad_file, inspect_cad_file, get_feature_tree.

**B. Intent** — create_design_intent, update_design_intent, validate_design_intent (minimum, Phase 3; get_design_parameters with the full IR in P3); create_drawing_intent, update_drawing_intent, validate_drawing_intent (P0).

**C. Part feature graph** — apply_part_graph, update_part_graph, validate_part_graph, inspect_part_graph, diff_part_graph; suppress_feature, delete_feature; list_feature_types, get_feature_schema (12.3).

**C2. Assembly graph (optional module)** — apply_assembly_graph, update_assembly_graph, validate_assembly_graph, inspect_assembly_graph (Phase 2).

**C3. IR bundle** — validate_bundle checks each module and the references between them. compile_bundle and execute_plan take a bundle, so a task sends only the modules it uses.

**D. Execution** — compile_bundle, validate_plan, execute_plan, get_execution_status, cancel_execution, recover_execution.

**E. Geometry** — inspect_geometry, resolve_geometry, create_geometry_ref, validate_geometry_ref.

**F. Verification** — check_model, diff_model, check_dimensions, check_wall_thickness, check_draft_angle, get_verification_report.

Each tool's inputs, outputs, kind, phase and errors are fixed by its contract file (12.4); the tables below only name the tools.

**G. Production drawings (P0, new)**

| Tool | Purpose |
| --- | --- |
| produce_drawing | Run the full pipeline (11.4) for a part + Drawing Intent IR (+ Design Intent IR if attached); returns an execution ID |
| check_drawing | Run hard checks D1–D10 on any drawing, including hand-made ones |
| get_drawing_report | Check results, conflict list, soft metrics |
| relayout_drawing | Re-run placement and checks on an existing drawing (pins kept) |
| get_drawing_layout | Drawing Layout IR of a drawing; summary by default (sheets, views, annotation counts, pins, planned vs as-built differences), full detail paginated by view |
| update_drawing_layout | Layout-only edits: move or pin/unpin an annotation, move a view, change a view scale. Applies them, reads back and re-checks. Cannot change Drawing Intent |

Long-running tools return an execution ID immediately.

## 12.3 Tool Surface and Token Budget

Every exposed tool's definition is loaded into the agent's context, and every response is read by it. Tool definitions and responses therefore cost tokens on every turn, which means money, latency and a context window that fills faster. The reference implementation exposes about 55 tools. One tool per feature type would add 60+ more. The design keeps coverage growing while the token cost stays flat.

### Rules

1. **Features are data, not tools.** All modeling goes through `apply_part_graph` / `update_part_graph` with typed nodes. New feature types extend the IR schema, not the tool list.
2. **Schemas on demand.** Tool descriptions stay short and do not embed per-feature schemas. Two tools serve them when needed:
   - `list_feature_types` — names plus one-line descriptions, grouped by tier, with Create/Read support.
   - `get_feature_schema(types[])` — compact JSON schema plus one minimal example for the requested types only.
   The reference implementation's `get_recipe` tool is prior art for this.
3. **Toolsets.** Tools are grouped and enabled per session through server configuration:

   | Toolset | Contents |
   | --- | --- |
   | `core` | Document tools (12.2 A); part graph tools; bundle, plan and execution tools; `check_model` (summary); `list_feature_types`, `get_feature_schema`. The exact list is the `core` rows of 12.4.4 |
   | `drawing` | Production drawing tools (12.2 G) and the Drawing Intent tools (12.2 B) |
   | `sheet_metal` | Flat pattern and bend inspection helpers |
   | `assembly` | Assembly graph tools (C2) and assembly inspection |
   | `design_intent` | Design Intent IR tools (B, design part) |
   | `geometry` | Geometry inspection and references |
   | `detail` | Fine-grained tools (sketch entities, single features, drawing dimension edits) |
   | `verification` | Verification tools beyond `check_model` (12.2 F) |

   The default profile is `core` + `drawing`, and `full` enables everything **[Builder's call]**. Toolsets change only which tools are visible; they never change any tool's contract.
4. **Responses: summary first.**
   - Default responses are summaries. Tools that can return large data take `detail: "summary" | "full"`.
   - Lists (feature tree, faces, dimensions) are paginated.
   - Geometry comes back as IDs plus key metrics, never as full B-rep dumps.
   - Failed checks list only the failures. Passing checks are counted, not listed.
   - Full reports are stored server-side under a report ID and can be fetched by section.
   - Every response uses the envelope and error codes in ADR-037. A failed drawing check is a result, not a tool error.
5. **Compact IR.** Defaults may be omitted from submitted IR. The compiler fills them explicitly and records them in the execution plan, but does not echo them back in responses. Units are declared once per document.
6. **Batch over chatter.** One graph submission per modeling step, not one call per feature. The production drawing pipeline is one call (`produce_drawing`), not dozens of dimension calls.

### Budgets

Targets are measured in CI by a script that counts tokens in tool definitions and recorded benchmark responses **[Builder's call on numbers]**:

| Item | Target |
| --- | --- |
| Tool definitions, `core` + `drawing` profile | ≤ 6,000 tokens |
| Tool definitions, `full` profile | Reported; must not grow when feature types are added |
| `get_feature_schema`, per feature type | ≤ 400 tokens |
| Typical tool response (summary) | ≤ 800 tokens |
| Drawing report summary | ≤ 600 tokens |
| Drawing layout summary (`get_drawing_layout`) | ≤ 600 tokens; full detail ≤ 1,500 tokens per view page |
| Feature tree, per page | ≤ 1,500 tokens |
| End-to-end tokens per benchmark part | Tracked per part; a rise of more than 20% fails the regression run |

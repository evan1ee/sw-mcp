# Part MCP MVP review

**Date:** 2026-11-06. **Scope:** the Part MCP chain at `da7af92` against the [MVP design](../specs/2026-11-05-part-chain-mvp-design.md), ADR-057 and the spec in `docs/`. **Result:** no code change is justified. The MVP is complete and matches the architecture.

## Evidence (run 2026-11-06, fresh)

| Check | Result |
| --- | --- |
| `generate_contracts.py --check` | clean |
| `ruff check`, `ruff format --check` | clean (474 files) |
| `pyright` | 0 errors |
| `lint-imports` | 5 contracts kept, 0 broken |
| `pytest` | 3,369 passed, 32 deselected |
| `dotnet test` | 340 passed |

Not run: live SOLIDWORKS tests (they drive the open instance; owner's call). The last live evidence is in [HANDOFF.md](../../../HANDOFF.md).

## Retain (correct, essential)

- Chain: Claude, `mcp-server` (official SDK), `core-service`, `plan` job, `cad-compiler` (6.7 stages), add-in, `cad-verification`, rename with no replace. Layering holds under `lint-imports`.
- IR-first with expected values computed from the IR, not from SOLIDWORKS; a static plan with symbols bound at send time; the working file plus atomic publish; add-in ownership table (D5).
- Narrow IR (`sketch`, `extrude`, `cut_extrude`, cap-face sketch) with refusal instead of approximation.
- Drawing tools hidden by default (`mcp.toolsets = ["core"]`).

## Deviations and complexity found

| # | Finding | Severity | Action |
| --- | --- | --- | --- |
| 1 | `jobs/plan_job.py` is 811 lines, over the 800-line guideline. It is signed off and live-verified. | Low | Defer. Split only when the next feature touches it. |
| 2 | `cad_compiler/validator/semantic.py` is 663 lines of narrow rules. Each rule exists so expected geometry stays exact (design section 5). | Low | Keep. Complexity is the price of verifiable output. |
| 3 | Authoring guide limits are hand-written (known issue in HANDOFF). | Low | Defer. |
| 4 | `plan_plate_recorded.jsonl` is synthetic, not a real recording. | Medium | Record a real transcript on the next live run. |
| 5 | Only 1 of 14 live part-chain tests was run on the rebuilt add-in; start-face hole and non-`front` planes (K29) have no live evidence. | Medium | Next step: owner-approved live re-run. |
| 6 | The `sw-mcp-mcp` front-end keeps a dead core connection after a core restart. | Medium | Known. Fix only if it hurts real use. |

## Missing MVP functionality

None. Design goals 1 to 5 and acceptance items 1 to 14 are met and signed off by the owner on 2026-11-06.

## Deferred on purpose

Holes from a face with arcs and patterns, other base planes (K29), `update_part_graph`, reading existing parts, drawings (frozen by ADR-057), and the LLM evaluation run of `score_part_ir.py`.

## Environment note

`uv run` fails while any `sw-mcp-mcp.exe` is running, because uv cannot replace the locked console script. A failed run leaves `.venv` partly synced, which breaks `pyright` and `pytest` imports until `uv sync` succeeds with those processes closed.

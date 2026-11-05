# Drawing Implementation Freeze Record

**Date:** 2026-11-05
**Decision:** [ADR-057](../../adr/ADR-057-freeze-drawings-build-part-chain-first.md)
**Freeze point:** commit `eea9389` on branch `feat/drawing-annotation-pipeline`
**Status:** Frozen, not accepted. Phase 1a and Phase 1b acceptance (section 18) have not been met.

This records what the drawing work is and how far it can be trusted, so it can be resumed without rediscovering it. Findings (`F` numbers) are from the [architecture review](2026-11-05-architecture-review.md).

## Verified at the freeze

Run on 2026-11-05. `apps/`, `packages/`, `schemas/`, `tests/` and `scripts/` had no differences from `eea9389`.

| Check | Result |
| --- | --- |
| `uv run python scripts/generate_contracts.py --check` | Pass |
| `uv run ruff check` | Pass |
| `uv run pyright` | 0 errors, 0 warnings |
| `uv run lint-imports` | 5 contracts kept, 0 broken |
| `uv run pytest -m "not live"` | 2,712 passed, 6 deselected |
| `dotnet test` on `ExecutionServer.Tests` | 241 passed, 0 failed |

**Not re-run at the freeze:**

- **Live suite:** `HANDOFF.md` records an earlier pass (5 passed, 1 skipped) against SOLIDWORKS 2025 SP0.1.
- **`dotnet build` of the solution:** the running SOLIDWORKS locks the add-in DLLs.

## What is frozen

| Area | Location |
| --- | --- |
| Pure drawing logic | `packages/cad-drawing/`: `checks`, `cleanup`, `dimension_scheme`, `placement`, `profiles`, `solidworks`, `view_planning` |
| Drawing operation planning | `packages/cad-application/src/cad_application/drawing/`: `layout_ops.py`, `annotation_ops.py` |
| Drawing check job | `packages/cad-application/src/cad_application/jobs/check_drawing.py` |
| SOLIDWORKS adapters | `apps/execution-server/ExecutionServer.Adapters/Drawings/` |
| Drawing schemas | `schemas/`: `drawing-geometry-snapshot`, `drawing-intent`, `drawing-layout`, `drawing-report`, `drawing-template`, `resolved-scheme` |
| Drawing operation schemas | `schemas/ipc/ops/`: `center_mark.add`, `dimension.hide`, `dimension.move`, `dimension.show`, `dimensions.auto_arrange`, `drawing.create`, `model_items.insert`, `sheet_format.generate`, `view.create`, `view.update` |
| Live tests | `tests/live/`: `test_live_annotation_pipeline.py`, `test_live_sheet_format.py`, `test_live_view_pipeline.py`, `test_live_smoke.py` |

**Not frozen, because the part chain shares them:** the add-in host and dispatch, `ExecutionServer.Core`, the IPC protocol, the job engine, the store and journal, and the `document.*` operations. Changes there must keep the drawing tests passing.

## What works

- Pure checks, planners and report building, under unit and contract tests.
- A live test script that drives sheet format generation, drawing creation, view creation, model item insertion, center marks, auto-arrange, read-back and duplicate hiding.

## What cannot be trusted yet

| Finding | Effect |
| --- | --- |
| F1 | Read-back has no line or text geometry, so a D1, D2, D3 or D7 `pass` is not evidence |
| F2 | Checks pass on data that was never read |
| F3 | The add-in reports a fixed border and title block, not real values |
| F4 | `check_drawing` can close an engineer's open drawing. **Use scratch copies only** |
| F5 | Operations can act on the active document, not the addressed one |
| F6 | An operation can report success without having worked |
| F9, F40 | Annotations have no durable identity, and snapshot keys are random GUIDs today |
| F10 | The Resolved Scheme has known defects |
| F8 | `produce_drawing` and the production entry points do not exist; the sequence lives in a test |

## Fixes that also serve the part chain

F5 and F6 are in the shared add-in, and F7 (connection leak) and F8 (entry points) are in shared runtime code. They may be fixed for the part chain under ADR-057. Update this record when one is.

## Open items waiting for the freeze to lift

- **Owner decisions** ([architecture roadmap](2026-11-05-architecture-roadmap.md)): O1, O3, O5, O6.
- **ADR-056:** stays Proposed. Its [pipeline review](2026-11-05-drawing-execution-pipeline-review.md) is not a verified baseline (review section 7.1).
- **Open decisions** ([register](../../specifications/open-decisions.md)): K3, J11, K8, K9, K10.

## How to resume

1. Read this record and ADR-057, then decide O1.
2. Re-run the checks above and the live suite, with SOLIDWORKS closed for `dotnet build`.
3. Continue from the Phase 1 work order in [section 18](../../specifications/roadmap.md#phase-1-work-order-builders-call): M1 and M4 first, so that checks report honestly and read real geometry before anything else is built on them.

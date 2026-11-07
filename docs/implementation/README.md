# Implementation Checklists

The authoritative, project-wide tracker for **Sketch** and **Part Feature** capabilities: what the product is meant to support, broken into individually trackable configuration options, and how far each one has actually been built and verified. It tracks implementation only. What to build is decided by the [specification](../specifications/README.md) and the [ADRs](../adr/README.md); this tracker never overrides them. See [AGENTS.md §1](../../AGENTS.md).

Audit basis: spec v1.38 and the code at commit `f10cac8`.

## How the documents divide the work (single source of truth)

| Fact | Owned by | Everyone else |
| --- | --- | --- |
| Conventions: status, scope, priority, layers, evidence marks, ID scheme | This file, [Conventions](#conventions) | Link here; never restate |
| Whether an item exists, its scope, priority, status and layer progress | One **row** in one checklist file | Link to the row's ID |
| Feature-level metadata (SOLIDWORKS API, code and test references, dependencies, limitations) | The **feature section** that owns the row | Link to the feature ID |
| Counts and percentages | Nobody: **derived** by [`scripts/check_implementation_checklists.py`](../../scripts/check_implementation_checklists.py) into the [summary](#derived-summary) | Never hand-edit |
| What the product should do and why | The [specification](../specifications/README.md) and [ADRs](../adr/README.md) | Cite the section; do not copy |

Each item is defined **once**. An option with the same name on two features (for example *Mid Plane* on extrude and on revolve) is two items, because each feature supports it independently; its definition is not restated, only its status per feature. Anything shared is owned by one section and linked from the others: the [`SHP-THN`](part-features/shape-modification.md#shp-thn--thin-feature-shared-object) section defines the options of the `thin` object while each host row tracks only that feature's support, mirror is owned by [`PAT-MIR`](part-features/patterns-mirrors.md#pat-mir--mirror-feature-and-mirror-body), equations and parameters by [`CM-EQN`](part-features/common-and-document.md#cm-eqn--parameters-and-equations), post-build checks by [`CM-VER`](part-features/common-and-document.md#cm-ver--result-verification). Status belongs here alone: other documents link to this tracker rather than stating what is supported.

## Documents

The [derived summary](#derived-summary) links every checklist file. Each capability's ID prefix names the file that owns it:

| ID prefix | Owning file |
| --- | --- |
| [`SK-PLN`](sketch/sketch-management.md#sk-pln--sketch-placement-and-coordinate-frames), [`SK-LIF`](sketch/sketch-management.md#sk-lif--sketch-lifecycle-and-state) | [sketch-management](sketch/sketch-management.md) |
| [`SK-ENT`](sketch/sketch-entities.md#sk-ent--sketch-entities) | [sketch-entities](sketch/sketch-entities.md) |
| [`SK-REL`](sketch/sketch-relations.md#sk-rel--sketch-relations) | [sketch-relations](sketch/sketch-relations.md) |
| [`SK-DIM`](sketch/sketch-dimensions.md#sk-dim--sketch-dimensions) | [sketch-dimensions](sketch/sketch-dimensions.md) |
| [`SK-OPS`](sketch/sketch-operations.md#sk-ops--sketch-operations) | [sketch-operations](sketch/sketch-operations.md) |
| [`SK-VAL`](sketch/sketch-validation.md#sk-val--sketch-validation) | [sketch-validation](sketch/sketch-validation.md) |
| `BF-` | [base-features](part-features/base-features.md) |
| `CF-` | [cut-features](part-features/cut-features.md) |
| `SHP-` | [shape-modification](part-features/shape-modification.md) |
| `HT-` | [hole-thread-features](part-features/hole-thread-features.md) |
| `PAT-` | [patterns-mirrors](part-features/patterns-mirrors.md) |
| `RG-` | [reference-geometry](part-features/reference-geometry.md) |
| `SRF-` | [surface-features](part-features/surface-features.md) |
| `SMT-` | [sheet-metal-features](part-features/sheet-metal-features.md) |
| `MBD-` | [multi-body-features](part-features/multi-body-features.md) |
| `CM-` | [common-and-document](part-features/common-and-document.md) |
| `ADV-` | [advanced-and-excluded](part-features/advanced-and-excluded.md) |

Add a capability to the file whose prefix fits. Do not create a new file unless no existing one fits.

## Derived summary

Do not edit this block. Refresh it with `uv run python scripts/check_implementation_checklists.py --write`.

<!-- BEGIN DERIVED SUMMARY (scripts/check_implementation_checklists.py --write) -->
| Category | Capabilities | Items | Not Started | Specified | Partially Implemented | Implemented | Tested | Verified | Deferred | Under Evaluation | Not Applicable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Sketch | 7 | 136 | 0 | 57 | 0 | 5 | 9 | 20 | 1 | 41 | 3 |
| Part Features | 64 | 451 | 0 | 158 | 9 | 4 | 14 | 39 | 32 | 182 | 13 |
| **Total** | **71** | **587** | **0** | **215** | **9** | **9** | **23** | **59** | **33** | **223** | **16** |

| Scope | In Scope | Out of Scope | Under Evaluation |
|---|---:|---:|---:|
| Items | 348 | 16 | 223 |

| Priority | P0 | P1 | P2 | P3 |
|---|---:|---:|---:|---:|
| Items | 65 | 178 | 157 | 187 |

| Document | Capabilities | Items | Verified | Tested | Partially Implemented |
|---|---:|---:|---:|---:|---:|
| [part-features/advanced-and-excluded.md](part-features/advanced-and-excluded.md) | 3 | 17 | 0 | 0 | 0 |
| [part-features/base-features.md](part-features/base-features.md) | 5 | 81 | 8 | 2 | 3 |
| [part-features/common-and-document.md](part-features/common-and-document.md) | 5 | 45 | 13 | 6 | 4 |
| [part-features/cut-features.md](part-features/cut-features.md) | 6 | 56 | 9 | 6 | 2 |
| [part-features/hole-thread-features.md](part-features/hole-thread-features.md) | 3 | 31 | 0 | 0 | 0 |
| [part-features/multi-body-features.md](part-features/multi-body-features.md) | 6 | 18 | 0 | 0 | 0 |
| [part-features/patterns-mirrors.md](part-features/patterns-mirrors.md) | 7 | 33 | 9 | 0 | 0 |
| [part-features/reference-geometry.md](part-features/reference-geometry.md) | 5 | 34 | 0 | 0 | 0 |
| [part-features/shape-modification.md](part-features/shape-modification.md) | 12 | 70 | 0 | 0 | 0 |
| [part-features/sheet-metal-features.md](part-features/sheet-metal-features.md) | 7 | 43 | 0 | 0 | 0 |
| [part-features/surface-features.md](part-features/surface-features.md) | 5 | 23 | 0 | 0 | 0 |
| [sketch/sketch-dimensions.md](sketch/sketch-dimensions.md) | 1 | 11 | 0 | 0 | 0 |
| [sketch/sketch-entities.md](sketch/sketch-entities.md) | 1 | 26 | 8 | 0 | 0 |
| [sketch/sketch-management.md](sketch/sketch-management.md) | 2 | 26 | 11 | 1 | 0 |
| [sketch/sketch-operations.md](sketch/sketch-operations.md) | 1 | 29 | 0 | 0 | 0 |
| [sketch/sketch-relations.md](sketch/sketch-relations.md) | 1 | 22 | 0 | 0 | 0 |
| [sketch/sketch-validation.md](sketch/sketch-validation.md) | 1 | 22 | 1 | 8 | 0 |
<!-- END DERIVED SUMMARY -->

*Capabilities* are the feature sections (`## ID — Title`). *Items* are the checklist rows: one row per configuration option or behaviour. Totals count items, so the Sketch and Part Features rows add up to the Total row.

## Conventions

This is the only place these are defined. The script reads the status, scope, priority, layer and ID prefix tables from this file and holds no copy, so a change here takes effect there. It keeps one rule per status, and fails if a status has no rule or a rule has no status.

### Row format

Each row is `| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |`. IDs look like `BF-EXT-007`: the feature ID ([`BF-EXT`](part-features/base-features.md#bf-ext--extruded-bossbase)) plus a three-digit sequence number. **IDs are permanent.** Never renumber or reuse one; mark a dropped row Out of Scope and Not Applicable with a note saying why, instead of deleting it. Add new rows at the end of their feature section. The script catches a deleted row but not a renumbered one, so reviewers must check for that. Notes are never empty: a Specified row names its spec tier, section or field, and Verified and Tested rows name the `test_*` that proves them. The script enforces this and checks that the test exists.

### Status

The row's Status is authoritative for its progress. The script checks it against the layer cells.

| Status | Meaning | Layer rule enforced |
| --- | --- | --- |
| Not Started | No spec and no code | No layer done |
| Specified | Named in a spec section, as the row's note and feature metadata show (§22 and §8.9 are still Proposed), no code | No layer done |
| Partially Implemented | Some code exists, behaviour incomplete or fixed | At least one layer done or partial |
| Implemented | Code exists across the required layers, but no test covers it or no run is recorded | At least one layer done |
| Tested | Unit or contract tests pass; not run in SOLIDWORKS | Some layers done; Integration Test not done |
| Verified | Run end to end in SOLIDWORKS by a repeatable test, in a run listed in the [live run record](#live-run-record) | Every applicable layer done, Integration Test done |
| Deferred | Intentionally postponed by the spec (Tier 3 / later phase) | No layer done |
| Under Evaluation | Scope or feasibility undecided | No layer done |
| Not Applicable | Out of scope | N/A in every layer |

An IR field, a compiler function or an API call alone never earns more than Partially Implemented.

### Scope and priority (independent)

| Scope | Meaning |
| --- | --- |
| In Scope | Named in a spec tier or an ADR as something the product will build |
| Out of Scope | Excluded by name in the spec (5.3.5, 5.3.1, ADR-015), or a row withdrawn from this tracker |
| Under Evaluation | Not decided by the spec; needs an owner decision |

Out of Scope pairs with Not Applicable, and Under Evaluation scope with Under Evaluation status.

| Priority | Meaning |
| --- | --- |
| P0 | Foundational: the Part Chain MVP cannot work without it |
| P1 | Spec Tier 1 (Phase 1), high priority |
| P2 | Spec Tier 2 (Phase 2), or an option that refines a Tier 1 feature |
| P3 | Tier 3, advanced, future or out of scope |

Priority follows the [spec tiers](../architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage). An Under Evaluation row carries a provisional priority: P2 for an option that refines a Tier 1 feature, otherwise P3.

### Layers

Cells are ✅ done, ◐ partial, ⬜ not done, N/A not applicable. The layers follow the [architecture overview](../architecture/overview.md):

| Layer | Done means |
| --- | --- |
| IR | Representable in the schema and models |
| Compiler | Validated, lowered into the execution plan |
| Adapter | Mapped to SOLIDWORKS API calls in the add-in |
| Execution | Runs in SOLIDWORKS without error |
| Validation | Input is checked and the result is verified against expectations |
| Integration Test | A repeatable live SOLIDWORKS test covers it |

Pure validator rules use N/A for Adapter, Execution and Integration Test, and are capped at Tested.

### Evidence marks for API claims

Taken from [spec 8.9.11](../specifications/solidworks-adapter.md#8911-api-capability-mapping): ✔ measured live, ◐ member and signature read from the installed interop but never run, ? general knowledge and unverified. Where 8.9.11 is silent, ◐ means the member was found by reflecting `SolidWorks.Interop.sldworks.dll` from the local SOLIDWORKS 2025 install: it shows the member exists, not that it is the right route. "No member found by name search" and "Not in 8.9.11; unverified" make no API claim. API names are never invented, and every route must pass a spike before use.

### Scope of the tracker

The checklists track the **Create path** (IR to execution). Reading hand-modelled parts (spec 5.8) is a separate path and is not tracked here. Rows for features that are Read-only in Tier 1 are Under Evaluation for Create. Spec 5.3.2 lists arcs, rectangles, slots, polygons and points as Tier 1 Create while the IR has only lines and circles: that is planned phasing, shown by the Specified rows in [`SK-ENT`](sketch/sketch-entities.md#sk-ent--sketch-entities).

## Maintaining the checklists

1. Change a row only with evidence: name the test in the Notes cell. Feature metadata lists the test files.
2. Do not copy spec text. Cite the section.
3. After any change run `uv run python scripts/check_implementation_checklists.py --write`, then without `--write` to confirm it exits 0. It audits duplicate IDs, malformed rows, status versus layer consistency, note citations and test names, ID prefixes and owning files, shared-section hosts, feature references (which must be links), relative links and anchors, and keeps the summary current.
4. Log spec gaps and disagreements in [open-decisions.md](../specifications/open-decisions.md), not here.
5. Add every live run to the [live run record](#live-run-record).

## Live run record

The durable evidence behind Verified rows, newest first. [`HANDOFF.md`](../../HANDOFF.md) is rewritten each session and only repeats the latest result. Add a row for each live run, with its commit and every skip named.

| Date | Commit | Command | Result | Skips |
| --- | --- | --- | --- | --- |
| 2026-11-07 | Not recorded; first reported in `7c550c2` | `uv run pytest tests/live/test_live_part_chain.py -m live` | 19 passed, 1 skipped | Not named |

## Evidence still needed

Rows held below Verified until a live run is recorded. Run on a throwaway SOLIDWORKS instance and record which test skips:

```bash
uv run pytest tests/live/test_live_part_chain.py tests/live/test_live_part_ops.py -m live -rs
```

- `test_template_with_reordered_planes` can skip, and the recorded run has one unnamed skip: [`CM-DOC`](part-features/common-and-document.md#cm-doc--part-document), [`SK-PLN`](sketch/sketch-management.md#sk-pln--sketch-placement-and-coordinate-frames).
- No run of `test_live_part_ops` is recorded: [`CM-DOC`](part-features/common-and-document.md#cm-doc--part-document), [`CF-EXT`](part-features/cut-features.md#cf-ext--extruded-cut).

## Decisions needed from the owner

- **Spec-silent options.** Under Evaluation rows whose note says "Not named in the spec" or "Not in <section>" list what the UI or API offers beyond what the spec names. Decide which to adopt as each feature's phase comes up.
- **Create scope for Read-only features** (sketch patterns, sketch text, table and fill patterns, thread, forming tools and the other Read-only sheet metal rows, move/copy body, mounting boss, snap hook, lip/groove, vent).
- **Features absent from the spec:** boundary boss/cut ([`BF-BND`](part-features/base-features.md#bf-bnd--boundary-bossbase), [`CF-BND`](part-features/cut-features.md#cf-bnd--boundary-cut)), surface-based cuts ([`CF-SRF`](part-features/cut-features.md#cf-srf--surface-based-cuts)), intersect ([`MBD-INT`](part-features/multi-body-features.md#mbd-int--intersect)), surface creation ([`SRF-CRE`](part-features/surface-features.md#srf-cre--surface-creation)), swept flange and lofted bend, three-point rectangles and circles, arc and centerpoint slots, Advanced Hole.
- **Sketch editing steps** ([`SK-OPS`](sketch/sketch-operations.md#sk-ops--sketch-operations)): 5.3.1 names only trim, extend and split. Confirm that move, copy, rotate, scale, stretch and dynamic mirror are excluded on the same principle.
- **Through All on bosses** ([`BF-EXT`](part-features/base-features.md#bf-ext--extruded-bossbase)): 5.7.3 offers it; SOLIDWORKS support is unverified and needs a spike.
- **Weldments** are Out of Scope under 5.3.5 ([`ADV-WLD`](part-features/advanced-and-excluded.md#adv-wld--weldments)), and **non-ISO hole standards** under ADR-015. Reverse either only through the spec.
- **Spec questions that block whole groups of rows:** K23 reference grammar, K26 selection, K27 sketch solver, K28 persistent references (see [open-decisions.md](../specifications/open-decisions.md)).

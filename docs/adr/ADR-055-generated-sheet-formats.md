# ADR-055: IR-generated sheet formats alongside owner-supplied formats

- **Status:** Proposed
- **Source:** specification v1.24, section 11.12, ADR-050, ADR-054 (principle 1: IR-first)

## Context

In Phase 0, ADR-050 established that drawing sheet formats and title blocks come from the owner's company template supplied as binary `.slddrt` files. However, the core never parses binary CAD files (13.3.4), meaning border boundaries, margin geometries, and title block field locators cannot be inspected or verified without opening the file inside SOLIDWORKS. This left open register item **K3** and required heuristic assumptions in Drawing Geometry Snapshot extraction.

Furthermore, following the core IR-first architectural principle (ADR-054, Spec 1.3), the system needs the ability to treat drawing formats as first-class, verifiable, CAD-neutral structured data.

## Decision

Drawing sheet formats may be authored as pure structured data via the **Drawing Template IR** (`drawing_template`, section 11.12) from which SOLIDWORKS sheet formats can be generated, alongside continuing support for owner-supplied binary `.slddrt` files.

- A drawing sheet in Drawing Layout IR references either `template` (a `DocumentRef` to a `drawing_template` document) or `sheet_format` (a path to a `.slddrt` file), mutually exclusively.
- Generated sheet formats define their own borders, title block zones, lines, text placements, and attribute link sources directly in the IR, requiring no external TOML title-block mapping.
- Hand-made `.slddrt` formats remain fully supported through Section 13.3.4 configuration.
- Generating `.slddrt` files in SOLIDWORKS is tracked in open decision item **K7**.
- This decision extends ADR-050 and does not withdraw it.

## Alternative Rejected

- **Describing existing `.slddrt` files only:** Writing a parser or inspection tool that extracts geometry from binary `.slddrt` files without generating them from IR. Rejected because binary format parsing violates the CAD-neutral and IR-first principles (1.3), creates fragile dependencies on proprietary file structures, and does not provide an authorable format specification.

## Rationale

- Treating sheet formats as authored IR ensures that paper bounds, margins, title block exclusion zones, and required ISO 7200 fields are fully verifiable offline without a running CAD session.
- It directly resolves the title block boundary and field locator problem (K3) for generated drawings.
- It preserves existing engineering workflows by allowing hand-made company templates to remain in use without breaking backwards compatibility.

## Consequences

- `drawing_template` is added as an optional module key in `schemas/common/v0.json` and `cad_ir.core.ids`.
- Multiple `drawing_template` documents are permitted within an IR bundle manifest (3.4.5) to support multi-sheet drawings with varying formats.
- Open register item **K7** is added to track the backend implementation of `sheet_format.generate`.
- Drawing check D8 derives its required fields and revision table checks directly from the template IR for generated drawings.

## Where it applies

- [architecture/drawing-template-ir.md](../architecture/drawing-template-ir.md) — section 11.12
- [architecture/drawing-layout-ir.md](../architecture/drawing-layout-ir.md) — section 11.11
- [architecture/shared-ir-core.md](../architecture/shared-ir-core.md) — section 3.4
- [architecture/production-drawings.md](../architecture/production-drawings.md) — section 11.2, 11.5.3
- [architecture/configuration.md](../architecture/configuration.md) — section 13.3.4
- [ADR-050](ADR-050-phase-0-owner-decisions.md)

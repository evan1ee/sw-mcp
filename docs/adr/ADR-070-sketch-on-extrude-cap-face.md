# ADR-070: A sketch may sit on an extrude's cap face, found by signature at use time

- **Status:** Accepted (owner, 2026-11-06, in the face reference plan)
- **Source:** [plan](../superpowers/plans/2026-11-06-face-reference-sketches.md); [live spike](../superpowers/review/2026-11-06-face-sketch-spike.md); specification v1.37, section 5.7.4. Uses ADR-005; narrows ADR-049 and ADR-067 (both Proposed) for this one case

## Context

The part chain MVP sketches only on the three origin planes, so an agent cannot say "a hole in the top face". IR spec §22 describes face role references (`extrude_base.end_face`) but marks them not built. The full design persists face references (ADR-067, K28), which the spike never measured.

## Decision

- **A `sketch` node's `plane` may be `<extrude_id>.start_face` or `<extrude_id>.end_face`.** Nothing else about faces is accepted: no `side_faces`, no edges, no faces of a cut, no offset planes.
- **Nothing is persisted.** The compiler computes a signature from the IR: the face's outward unit normal and its offset from the model origin along that normal. At execution the add-in finds the extrude by its feature id, takes its planar faces, and picks the one whose normal and offset match. It selects that face with `Entity.Select4` and opens the sketch. Zero or more than one match fails the operation (`REF_NOT_FOUND`, `REF_AMBIGUOUS`).
- **The sketch frame is stated and checked.** The compiler states the expected sketch axes in model space. After the sketch opens, the add-in compares them with `ModelToSketchTransform` and fails the operation on a mismatch, before anything is drawn.
- **A blind cut from a face goes into the body.** The IR needs no `reverse` flag for this. The add-in passes `Flip=false` and `Dir=false` for a sketch on a face, and `Dir=true` for a sketch on an origin plane (the existing rule).

## Rationale

The spike showed the cap faces are unique and planar, that a hole cut in one leaves it one planar face, and that selection and sketching work. A job builds a part inside one plan, so identity never has to outlive it. That removes the need for persisted references, which are unmeasured.

## Consequences

- "Hole in the top face" becomes buildable; side faces, edges and persistence stay for a later phase (K28).
- Frames were measured on `plane:front` only. The rule for other planes is an assumption that the add-in's frame check turns into a safe failure (open decision K29).
- Plan hashes change when a graph uses a face, and the stage versions bump.

## Where it applies

- [architecture/feature-schema-guide.md](../architecture/feature-schema-guide.md) — section 5.7.4
- [specifications/ir-specification.md](../specifications/ir-specification.md) — section 22.4
- [specifications/open-decisions.md](../specifications/open-decisions.md) — K29

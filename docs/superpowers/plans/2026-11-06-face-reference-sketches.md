# Plan: sketches on a face (face references in the part chain)

Status: **approved by the owner (2026-11-06). Phases 0 to 6 done; phase 7's live test is written and not run.** Follows [agent IR authoring](2026-11-06-agent-ir-authoring.md), which makes the agent refuse "a hole in the top face" because the MVP cannot express it.

## Goal

"A 40 x 30 x 10 mm block with a 5 mm hole, 4 mm deep, in the top face" builds and verifies. The agent writes `"plane": "extrude_base.end_face"` and a blind cut, the compiler resolves it, and the add-in sketches on that face.

## What the documents already say

- [IR spec §22](../../specifications/ir-specification.md) (Proposed): an extrude outputs `start_face`, `end_face`, `side_faces`; role references are written `<node>.<role>`; a sketch may use a face. Marked "N, not built".
- The sketch `plane` pattern in the schema already accepts `name.name`. The compiler rejects it (`lowering/lower.py`, standard planes only).
- Open decisions: K23 (reference grammar), K26 (selection without `SelectByID2`), K28 (persistent face references). ADR-049 and ADR-067 are Proposed; ADR-005 is Accepted.
- The part chain MVP design lists face references as out of scope. The roadmap has no phase for sketching on a face.

## Scope (deliberately small)

In: a sketch on `<extrude_node>.start_face` or `<extrude_node>.end_face`; `cut_extrude` from it, blind or through; expected geometry and live verification for it.

Out: `side_faces`, edges, faces of cut features, persistent references across jobs or sessions, offset planes, datums, a hole feature. These stay refused in the guide.

## Proposed design decision (needs an ADR and the owner's approval)

Do not persist face handles. After the extrude exists, the add-in finds the extrude by its feature id (`f<ID>`, proven across reopen), enumerates its faces, and picks the planar face whose normal and offset match the signature the compiler computed from the IR. It selects that face with `Select2` and sketches on it, all within the job. This needs none of K28's persisted-reference evidence, because nothing outlives one plan. K28 stays open for edges and later phases. If this is not acceptable, the alternative is to wait for K28's spike first.

## Phases

0. **Spike (needs SOLIDWORKS; the owner starts it).** On a throwaway instance, with the existing `tests/live/spikes/PartChainSpike`: (a) find the end face of an extrude through `IFeature.GetFaces`; (b) select it with `Select2` and open a sketch; (c) measure the sketch frame with `ModelToSketchTransform` (origin, x and y axes against `plane:front`); (d) cut a Ø5 circle blind and see which way it goes and with which `Dir` and `Flip`. Record the answers in the spike record. Nothing else starts before (c) and (d) are known: the sketch frame on a face decides the coordinates in the IR.
1. **Spec and ADR.** Write the ADR above; accept the parts of §22 that this uses (§22.3 direction, §22.4 plane field, §22.6); close K26 for this route and record why K23 is not needed (two segments suffice); log new gaps in `open-decisions.md`; bump to v1.37 with a changelog entry.
2. **IR and schemas.** Sketch `plane` accepts `<node>.<start_face|end_face>`. Add optional `reverse` to the cut end condition only if the spike shows it is needed. Regenerate contracts. Add `sketch.create` params for a face plane. Valid and invalid fixtures.
3. **Compiler (pure Python).** Validator: the node exists, is the extrude, produces the role, and is built earlier; add the dependency edge. Resolver: compute the face signature (normal, offset = depth, which side) from the IR. Lowering: pass the face and signature into `sketch.create`. Update the golden plans; the plan hash changes by design (stage versions bump).
4. **Verification (pure Python).** `expected_geometry` handles a sketch on a face: the plane origin moves by the depth, the axes follow the spike result, a blind cut from the end face spans `[depth - h, depth]`. Tests first: block 40 x 30 x 10 with a Ø5 x 4 hole is 12,000 - pi x 2.5^2 x 4 = 11,921.5 mm^3, and the cylinder's axis start and extent are correct. Check how `part.measure` matches cylinders when the hole does not start at z = 0.
5. **Add-in (C#).** A face resolver in `ExecutionServer.Adapters` and its signature math in CAD-free `ExecutionServer.Core` with unit tests; `SketchAdapter` takes a face plane; `FeatureAdapter` sets the blind direction from the spike. Release only the temporary face and feature objects (G1); no handles kept between commands. Errors `REF_NOT_FOUND`, `REF_AMBIGUOUS` and `REF_SIGNATURE_MISMATCH` already exist in the catalogue.
6. **Guide and evaluation.** Update `authoring_guide.py` (what is now supported, the face sketch frame, what is still refused) and the tool descriptions. Turn `refuse_blind_hole_on_face` into a build case with facts; add a hole in the start face; keep refusals for side faces and edges.
7. **Verify.** Full Python suite, C# tests, `generate_contracts.py --check`. A live test for the top-face hole, including a reopen check, which the owner runs. Update `HANDOFF.md`.

## Order and gates

0 (owner runs SOLIDWORKS) -> 1 (owner approves the ADR) -> 2 -> 3 -> 4 -> 5 -> 6 -> 7. Phases 2 to 4 are testable without SOLIDWORKS. Phase 5 and the live test need it.

## Risks

- **HIGH:** the sketch axes and origin on a face may differ from the plane's, and the IR's coordinates depend on them. The spike decides; if the frame is not fixed, the add-in must normalise it or the IR must carry the frame.
- **MEDIUM:** blind-cut direction from a face (the earlier spike found the default cut goes the other way).
- **MEDIUM:** signature matching must find exactly one face. For one planar end face the match is unique; a through-hole in it does not split it.
- **MEDIUM:** §22 and ADR-049/067 are Proposed. Using them needs the owner's approval, and changes to them are the owner's call.
- **LOW:** golden plan and hash churn; contract drift is caught by `generate_contracts.py --check`.

## Complexity: HIGH

It touches the spec, schema, compiler, verifier and add-in, and its key facts come from a live spike. The pure-Python phases are lower risk.

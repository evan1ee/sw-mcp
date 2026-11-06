# Sketch on a face: live SOLIDWORKS API spike

Date: 2026-11-06. Phase 0 of [the face reference plan](../plans/2026-11-06-face-reference-sketches.md). SOLIDWORKS 2025, driven out of process by `tests/live/spikes/PartChainSpike` (mode `face`, `FaceSpike.cs`). The spike made new parts only, closed only those, and left the 18 documents already open in the session as they were (the initial and final lists matched). Raw log: `%TEMP%\sw-mcp-spike\spike-output-face.txt` (not committed).

Part under test: a 40 x 30 x 10 mm block, sketch on the first `RefPlane` (front), `FeatureExtrusion3` blind 10 mm, so the block spans z 0 to 0.01 m. Lengths below are in metres unless marked mm.

## Answers

**F1. The extrude reports its faces, and each cap is a unique planar face.** `IFeature.GetFaces()` on the extrude returned 6 faces. Exactly one is planar with outward normal +Z (`end_face`, plane root z = 0.01) and exactly one with outward normal -Z (`start_face`, plane root z = 0). Both selections by `Face2.Normal` found exactly one candidate in every run.

**F2. `Entity.Select4(false, selectData)` selects a face, and `InsertSketch(true)` then opens a sketch on it.** Selected count was 1 each time. The sketch frame, from `ModelToSketchTransform.Inverse()`:

| face | sketch origin (model) | sketch +x | sketch +y | sketch normal |
| --- | --- | --- | --- | --- |
| `end_face` (z = 0.01) | (0, 0, 0.01) | +X | +Y | +Z |
| `start_face` (z = 0) | (0, 0, 0) | **-X** | +Y | -Z |

So on the end face the frame equals the base plane's frame shifted by the depth. On the start face x is mirrored: the sketch is seen from outside the part. A circle at sketch (10, 5) mm cut through all landed at model (0.01, 0.005) on the end face and at model (-0.01, 0.005) on the start face.

**F3 and F4. A blind cut from a face goes into the body with `Flip=false, Dir=false`.** Same on both faces.

| Flip | Dir | Result |
| --- | --- | --- |
| false | false | **Correct.** Removed 7.854e-8 m3 (a 4 mm deep, r 2.5 mm hole, exactly). The hole wall spans z 0.006 to 0.010 from the end face and z 0 to 0.004 from the start face. |
| false | true | `FeatureCut4` returned null, nothing cut. |
| true | false | Wrong: removed 4.721e-6 m3, which is the block's 4 mm layer outside the circle. |
| true | true | Null, nothing cut. |

This is the opposite of a cut from an origin plane, where the earlier spike found `Dir=true` is needed. The add-in must pick `Dir` by the sketch's host: `true` for a standard plane, `false` for a face.

**F5. `through_all_both` from the end face works.** Removed 1.963e-7 m3, which is the full 10 mm hole.

**F6. After a hole is cut in the end face, it is still one planar face with outward normal +Z.** The extrude still reports 6 faces and exactly one +Z planar face, with area 1180.4 mm2 (1200 minus the hole). Finding the face by planar, normal and position is therefore stable across a later cut.

## Design impact

1. **The IR frame on a face is determined.** `end_face`: same axes as the base sketch plane, origin shifted by the depth along the normal. `start_face`: x mirrored, normal reversed. The spec must state this, and the verifier's expected geometry must apply it.
2. **A blind cut from a face goes against the face's outward normal, into the body, with no `reverse` flag.** The IR needs no new field for this case. `reverse` would only be needed to cut away from the body, which makes no cut.
3. **`FeatureAdapter` blind direction depends on the sketch host.** Standard plane: `Dir=true` (existing). Face: `Dir=false`.
4. **Faces are found by signature, not persisted.** Select by feature id, then planar, outward normal and plane root. No persisted reference was needed, so K28 is not on this route's critical path.
5. **Cylinder matching needs no change.** The reported cylinder `point` differs by case (z = 0.006 for a hole cut from the top, z = 0 for through holes from the front plane), but `_cylinder_matches` in `cad_verification/part.py` compares the axis line and radius, not one point on it. Depth is covered by the volume and area checks.

## Not measured

- A face of a cut feature, `side_faces` and edges (out of scope).
- A face sketch after the extrude is suppressed or edited (not needed within one plan).
- Behaviour on a non-planar end face.

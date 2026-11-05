# Part Chain MVP: live SOLIDWORKS API spike

Date: 2026-11-05. Task 1 of the Part Chain MVP plan. Everything below was observed on SOLIDWORKS 2025 (revision 33.0.0, SP0.0) with the Chinese UI, Windows 11, driving the API out of process from `tests/live/spikes/PartChainSpike/` (net48, not in `ExecutionServer.sln`). The spike touched only documents it created in `%TEMP%\sw-mcp-spike\`, changed no application preference, and closed documents only by exact full path under that folder.

Raw logs are written by the spike to `%TEMP%\sw-mcp-spike\spike-output-a.txt`, `-b.txt`, `-c.txt` (not committed).

## Design impact

Assumptions in design sections 3, 5, 7 and 13 that did not hold, or held differently. Nothing here edits the design; each item states the fallback the design already has, or says there is none.

1. **Default template is not usable (section 7, `part.create` `template` optional).** `swDefaultTemplatePart` on this install is `~BLANK_PART_TEMPLATE.prtdot`, which is not a file. `NewDocument` with it, with `""` and with a nonexistent path all return null, with no dialog. So an optional `template` cannot fall back on the user's preference. The design has no fallback for this. Needed: either make `template` required, or resolve the default from the installed template folder (`C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\gb_part.prtdot` here), failing with a catalogued error when none is found. The installed templates are all metric.
2. **`GetOpenDocumentByName` finds a document only by its full path (section 7, "find the document by the batch's path").** By full path it works. By title (`plate1.SLDPRT`), by name without extension, and for an unsaved document by `Part9`, `Part9.SLDPRT` or `Part9.sldprt`, it returns null. The path rule still holds because `part.create` saves at once, but any lookup by title or file name (the add-in's `document.close` uses `Path.GetFileName`) cannot be verified with this call. No design fallback needed for parts; keep to full paths.
3. **`Select4` is not available for features (section 7, rule "selection through `Select4` with explicit marks").** `IFeature` exposes `Select2(bool append, int mark)` only; `Select4(append, ISelectData)` belongs to entities (faces, edges, sketch segments). Planes and sketches were selected with `IFeature.Select2(false, 0)`. `SelectByID2` stays banned. The design's wording should read "`Select2`/`Select4` with explicit marks"; behaviour is otherwise as designed.
4. **A blind cut does not go the way a blind extrude goes (section 5/7 `feature.create` `cut_extrude` with `blind`).** On all three standard planes a default blind `FeatureExtrusion3` goes along the plane normal. A default blind `FeatureCut4` from the same plane goes the other way (against the normal) and, with nothing there to cut, returns null. The flip argument `Flip=true` does not help: it selects which side of the profile to remove, and also returned null. Only the direction argument `Dir=true` cut into the body (volume change equals the circle area times depth). The plate itself is unaffected (it uses `through_all_both`), but the compiler must set `Dir` for blind cuts. No fallback in the design; this is a rule for Task 7b.
5. **`FileCloseNotify` never fires for an API close (section 7, "the add-in forgets table and ledger entries on `FileCloseNotify`").** It did not fire for `CloseDoc` by title, nor by full path, although the same subscription received `DocumentLoadNotify2` and `FileOpenPostNotify`. Whether it fires for a close the engineer does in the UI was not tested. The name format therefore could not be determined (answer 11). Fallback: the per-document `DestroyNotify2` (fired on every API close, answer 13), or checking `GetOpenDocumentByName(path)` lazily before trusting a table entry. The design has no such fallback written; it needs one before Task 8 relies on `FileCloseNotify`.
6. **No `Part.FileSaveNotify` on an API save (section 7, "subscribes to regen, save and destroy").** `SaveAs4` raised `FileSavePostNotify` only (full path, `saveType` 2). Use that one for save, `RegenNotify`/`RegenPostNotify` for regen, `DestroyNotify2` for destroy (answer 13).
7. **Active document is not needed (section 7, "if the spike shows feature calls need the document active").** Sketch, `FeatureExtrusion3`, `FeatureCut4`, measure, `ForceRebuild3` and `SaveAs4` all worked on a document that was not active, and none of them changed the active document. The conditional active-document check in section 7 can be dropped for these calls; the engineer-change detection of rule 13 is a separate matter.
8. **`GetBodyBox` is not looser on this part (section 13 risk).** It equals the true box exactly, but only prismatic planar geometry was tested; the risk stays open for curved bodies.
9. **Confirmed, no impact:** `GetID` is stable across close and reopen (A2), so the `GetPersistReference3` fallback is not needed (its bytes were identical too); `SaveAs4` silent does overwrite (so `part.create` must refuse an existing path itself); no file lock after `CloseDoc`; `CloseDoc` on a dirty document discards without a prompt (F4); reopen reads from disk; A14 and reconnect passed.

## Plate under test

Design section 3 plate: 100 x 60 x 10 mm, four dia 8 mm holes at (+-40, +-20), built on `plane:front` (first `RefPlane`). All API lengths in metres.

## Answers

### 1. Sketch axes and extrude/cut directions

The `RefPlane` features are, in order, Front (`前视基准面`), Top (`上视基准面`), Right (`右视基准面`). Sketch axes in model coordinates, found by applying `ISketch.ModelToSketchTransform.Inverse()` to unit points via `IMathUtility.CreatePoint` and `IMathPoint.MultiplyTransform`:

| Plane | sketch +x | sketch +y | normal (x cross y) | blind extrude goes | blind cut (default) | blind cut with `Dir=true` |
| --- | --- | --- | --- | --- | --- | --- |
| Front | model +X | model +Y | +Z | +Z (box z 0 to 0.01) | -Z, null (nothing to cut) | +Z, removes material |
| Top | model +X | model -Z | +Y | +Y (box y 0 to 0.01) | -Y, null | +Y, removes material |
| Right | model -Z | model +Y | +X | +X (box x 0 to 0.01) | -X, null | +X, removes material |

Calls: `swModel.FeatureManager.FeatureExtrusion3(true, false, false, 0, 0, 0.01, 0.0, false, false, false, false, 0.0, 0.0, false, false, false, false, true, true, true, 0, 0.0, false)` after `sketchFeature.Select2(false, 0)`. Cut: `FeatureManager.FeatureCut4(true, false, dir, 0, 0, 0.004, 0.0, false, false, false, false, 0.0, 0.0, false, false, false, false, false, true, true, false, false, false, 0, 0.0, false, false)` with `dir` the third argument. Probe volumes: r1 mm x 4 mm cut changed the volume by -1.2566370614359217e-08 m3 (exact: 1.2566370614359173e-08).

### 2. Working calls for `sketch.create`, `FeatureExtrusion3`, `FeatureCut4`

Sketch (all worked): `d.ClearSelection2(true)`; `planeFeature.Select2(false, 0)`; `sm.AddToDB = true; sm.AutoInference = false` (both restored in `finally`); `sm.InsertSketch(true)`; `sm.CreateLine(x0, y0, 0, x1, y1, 0)` and `sm.CreateCircleByRadius(cx, cy, 0, r)` (sketch coordinates equal the table above); `sm.InsertSketch(true)` to leave; the new sketch is `d.FeatureByPositionReverse(0)` (type name `ProfileFeature`). Snapping preferences were not changed; `AddToDB` bypasses them.

Extrude: as in answer 1, with the sketch selected by `Select2(false, 0)`; returns the feature (`Boss-Extrude1`). Cut with `through_all_both`: `FeatureCut4(false, false, false, 1, 1, 0.0, 0.0, false, false, false, false, 0.0, 0.0, false, false, false, false, false, true, true, false, false, false, 0, 0.0, false, false)` (Sd=false, T1=T2=`swEndCondThroughAll`=1). It produced `Cut-Extrude1` with the right volume whichever way the normal points. Selection marks: `Select2(false, 0)` was enough for the plane and the sketch; `SelectByID2` was not used. `FeatureExtrusion3` and `FeatureCut4` exist in the 2025 interop with 23 and 27 parameters.

### 3. `RefPlane` order and normal

Order Front, Top, Right holds on this install; names are localized (Chinese), so order is the only usable key. Reading a normal: `((IRefPlane)feature.GetSpecificFeature2()).Transform` is an `IMathTransform`; apply it to the point (0,0,1) and subtract the image of (0,0,0). Results: Front [0,0,1], Top [0,1,0], Right [1,0,0]. Raw `Transform.ArrayData` (rotation 9 values, translation 3, scale, padding): Front `[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]`, Top `[1,0,0,0,0,-1,0,1,0,0,0,0,1,0,0,0]`, Right `[0,0,-1,0,1,0,1,0,0,0,0,0,1,0,0,0]`; the plane's local Z in model space is the third column of the 3x3 block as multiplied by `MultiplyTransform`, which is why the point method is the safe one. Origins are all (0,0,0).

### 4. `NewDocument` and templates

- Preference: `GetUserPreferenceStringValue(swDefaultTemplatePart)` returned `~BLANK_PART_TEMPLATE.prtdot` (file does not exist).
- `NewDocument("~BLANK_PART_TEMPLATE.prtdot", 0, 0, 0)`: null. `NewDocument("", 0, 0, 0)`: null. `NewDocument(<nonexistent path>)`: null. No dialog in any case. The preference was not cleared to test "empty"; passing the empty string is what the API receives.
- `NewDocument(@"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\gb_part.prtdot", 0, 0, 0)`: a part. Its document units: unit system 4 (MMGS), linear unit 0 (mm). Only metric templates are installed (`gb_part.prtdot`, `MBD\*.prtdot`).
- Inch case: no inch template exists, so the new document's unit system was set with `Extension.SetUserPreferenceInteger(swUnitSystem, 0, swUnitSystem_IPS)` (document level; reads back 3, linear units 3). The plate built with the same metre values gave identical geometry: volume 5.798938070170252e-05 m3, area 0.015803185789489239 m2, box and four cylinders unchanged. So a metres-based API is correct in an inch document. `IMassProperty.UseSystemUnits = false` returned 57989.38 (mm3) in that inch document, i.e. it does not follow the document's linear unit; always use `UseSystemUnits = true`.

### 5. A2: `GetID` and `GetPersistReference3` across close and reopen

Before and after close and reopen (`CloseDoc(fullPath)`, `OpenDoc6`): `IFeature.GetID()` identical for all 20 features. Examples: planes 2, 3, 4; origin 5; `Sketch1` 73; `Boss-Extrude1` 79; `Sketch2` 80; `Cut-Extrude1` 86 (its `GetTypeName2()` is `ICE`; the boss is `Extrusion`, sketches `ProfileFeature`, planes `RefPlane`). `Extension.GetPersistReference3(feature)` returns a 20-byte array (prefix `50-46-00-00-01-00-00-00`, "PF") for planes, sketches and features; the bytes were identical after reopen, and `Extension.GetObjectByPersistReference3(oldBytes, out err)` resolved to the same feature for planes, origin, `Sketch1`, `Boss-Extrude1`, `Sketch2` and `Cut-Extrude1`. For several folder features (favourites, history, sensors, design binder, tables, material) it returned null with error 1. **A2 holds; the fallback is not needed.**

### 6. Measurement against the true values

Plate (Front, `through_all_both` cut), `IModelDoc2` built and rebuilt with `ForceRebuild3(false)`:

| Quantity | API call | Observed | Expected | Difference |
| --- | --- | --- | --- | --- |
| Solid bodies | `((IPartDoc)d).GetBodies2(swSolidBody, false)` | 1 | 1 | 0 |
| Body box | `IBody2.GetBodyBox()` | [-0.05,-0.03,0, 0.05,0.03,0.01] | same | 0 (equals the vertex-derived box) |
| Volume | `IMassProperty.Volume` (`UseSystemUnits=true`) | 5.798938070170252e-05 m3 | 5.7989380701702534e-05 | -1.4e-20 |
| Surface area | `IMassProperty.SurfaceArea` | 0.015803185789489239 m2 | 0.015803185789489239 | 0 |
| Center of mass | `IMassProperty.CenterOfMass` | [0, 0, 0.005] | [0, 0, 0.005] | 0 |

Cylindrical faces: `foreach Face2 f in body.GetFaces()`; `ISurface s = (ISurface)f.GetSurface(); s.IsCylinder()`; `s.CylinderParams` returns 7 doubles: a point on the axis (x,y,z), the axis direction (x,y,z), radius. Observed four: point (-0.04,-0.02,-1.2e-8), (0.04,-0.02,-1.2e-8), (0.04,0.02,-1.2e-8), (-0.04,0.02,-1.2e-8); direction (0,0,1); radius 0.0039999999999999966. The point's z is not meaningful (any point on the axis), so compare only the components perpendicular to the axis and give the radius a tolerance.

### 7. `CloseDoc` with unsaved changes (F4)

A document saved to disk and then given another feature (`GetSaveFlag()` true): `CloseDoc(fullPath)` returned after 142 ms, with no prompt, the document was gone, and the file on disk was unchanged (hash equal): **changes are discarded silently**. A never-saved dirty document was not tested in this run, because it has no path and the spike closes only by exact path (an earlier run did close one by title in about 200 ms with no prompt). `QuitDoc`: **not determined, unsafe on a live session** (banned by the owner; never called against the live session).

### 8. File lock after close

`File.Move(path, path + ".renamed")` immediately after `CloseDoc` returned succeeded at once (0 ms, 0 failed attempts), six trials out of six (one on the plate, five on fresh save-close-rename cycles). No lock persists on this install. While a document is open, SOLIDWORKS holds the file such that a default-share read fails (a `FileStream` needs `FileShare.ReadWrite`).

### 9. Calls on a document that is not active

Document A (saved) and then B (new, active). Reacquired A with `GetOpenDocumentByName(fullPath)`; on A: plane `Select2`, `InsertSketch`, `CreateLine`, `FeatureExtrusion3`, `FeatureCut4` (`through_all_both`), `GetBodies2`, `CreateMassProperty`, `ForceRebuild3(false)` and `SaveAs4` all worked, with correct geometry (volume 1.5214601836602556e-05 m3). The active document stayed B throughout.

### 10. `SaveAs4` silent over an existing file

`d.SaveAs4(path, swSaveAsCurrentVersion=0, swSaveAsOptions_Silent=1, ref err, ref warn)`. Saving a different document to a path where a closed file already existed: returned true, err 0, file size 63331 -> 65717 bytes, hash changed: **it overwrites silently**. Saving to a path another open document holds: returned false, err 1 (`swGenericSaveError`), file unchanged.

### 11. Name passed to `FileCloseNotify`

**Not determined: the event never fired.** `((DSldWorksEvents_Event)swApp).FileCloseNotify += (string fileName, int reason) => ...` was subscribed (the add-in subscribes the same way), together with `DocumentLoadNotify2` and `FileOpenPostNotify`, which did fire. `CloseDoc(title)` on saved and unsaved documents (earlier runs) and `CloseDoc(fullPath)` (event stage) raised no `FileCloseNotify`. A close from the SOLIDWORKS UI was not tried (the spike does not drive the UI). For reference, what the other events carry: `DocumentLoadNotify2(title, path)` gives the title and an empty path for a new document, and title plus full path for a saved one; `FileOpenPostNotify(fileName)` gives the full path.

### 12. Reopen after close

After `CloseDoc(fullPath)`, `GetOpenDocumentByName(fullPath)` returned null immediately (reported closed before any reopen). A reopen (`OpenDoc6`, `swOpenDocOptions_Silent`) produced a document with identical features and an identical unrebuilt measurement (volume equal to the last bit). To show it reads from disk, the file was replaced with the no-holes plate while closed; the reopened document had 0 cylinders and volume 6.0e-05 m3, so **reopen reads the file from disk**, not a cache. A read-only reopen (`swOpenDocOptions_ReadOnly`) reported `IsOpenedReadOnly` true and `GetSaveFlag()` false after measuring without a rebuild.

### 13. Part-document events

Subscribed with `((DPartDocEvents_Event)(IPartDoc)d)` after `NewDocument`. Observed order while building and saving the plate (millisecond offsets from the log):

| What happened | Events raised |
| --- | --- |
| Each feature or sketch added (`InsertSketch`, `FeatureExtrusion3`, `FeatureCut4`) | `ModifyNotify` (first only), `RegenNotify`, `RegenPostNotify`, then `AddItemNotify(type 3, name)` after the regen pair |
| `ForceRebuild3(false)` | `RegenNotify`, `RegenPostNotify` |
| `SaveAs4` (silent) | `FileSavePostNotify(saveType 2, fullPath)` only; `FileSaveNotify` did **not** fire |
| `CloseDoc(fullPath)` | `DestroyNotify` then `DestroyNotify2(destroyType 0)`, in the same millisecond, before `CloseDoc` returned |

Because every API call of the job itself raises regen events, the job must mark its own calls (a flag set around each operation) to tell an engineer's edit from its own. Save events came from the job's own `SaveAs4` too. Destroy fired on the job's own close.

## A14 and immediate reconnect (step 3)

`tests/live/test_live_a14.py`, against the registered add-in (session pid 6396), commands `session.ping`, `document.open`, `document.close` only, on the scratch part `a14_scratch.SLDPRT`. 3 passed in 97 s.

- 1,000 sequential pings: median 10.6 ms, p99 21.1 ms, max 104.6 ms; none lost. Then 20 open/close cycles (40 commands plus pings): max 903 ms.
- One command while SOLIDWORKS was busy (the spike's `busy` mode rebuilding a 1,600-hole part back to back): the ping answered in 1 ms (answered by the pipe thread); `document.open` waited 18.2 s and then succeeded; `document.close` 103 ms. No command was dropped or deadlocked, but a command that needs the main thread waits for the whole busy period, so job timeouts must allow for it.
- Reconnect: 10 times open, close, drop the connection, and immediately acquire a new one and ping: every time accepted, 22 to 55 ms. **A14 holds at this load and the register fallback was not needed.**

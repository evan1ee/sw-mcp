using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using ExecutionServer.Adapters.Native;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Parts;
using Newtonsoft.Json.Linq;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace ExecutionServer.Adapters.Parts;

/// <summary>
/// Implements operation feature.create (extrude, cut_extrude, linear_pattern) and document.rebuild (spec 6.5.2, design 7, ADR-059, ADR-064, ADR-074).
/// Selects sketch profile via Select2, invokes FeatureExtrusion3 or FeatureCut4 (with Dir=true for blind cuts),
/// or creates linear patterns via ILinearPatternFeatureData, forces a rebuild, and returns T0 observation.
/// </summary>
public sealed class FeatureAdapter
{
    private readonly ISldWorks _sw;

    public FeatureAdapter(ISldWorks sw)
    {
        _sw = sw ?? throw new ArgumentNullException(nameof(sw));
    }

    public FeatureCreateResult CreateFeature(string document, FeatureCreateParams p, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        var doc = DocumentLocator.FindDocument(_sw, document);

        using var scope = new ComScope();

        IFeature? createdFeature = null;

        try
        {
            if (p.Type == FeatureCreateParamsType.LinearPattern)
            {
                if (p.Seeds == null || p.Seeds.Count == 0)
                {
                    throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Linear pattern requires at least one seed feature.");
                }
                if (p.Direction1 == null)
                {
                    throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Linear pattern requires direction_1.");
                }

                doc.ClearSelection2(true);

                // 1. Select seed features with Mark = 4 (spike / SW API convention)
                bool append = false;
                foreach (var seedId in p.Seeds)
                {
                    var sf = FeatureLookup.FindById(doc, seedId, scope);
                    if (sf == null)
                    {
                        throw new IpcException(ErrorCodes.IR_REFERENCE_UNRESOLVED, $"Seed feature '{seedId}' not found in document.");
                    }
                    sf.Select2(append, 4);
                    append = true;
                }

                var selMgr = (ISelectionMgr)doc.SelectionManager;

                // 2. Select Direction 1 reference edge with Mark = 1
                var (dir1Edge, dir1NeedsRev) = ResolveDirectionEdge(doc, p.Direction1.Direction, scope);
                var selData1 = scope.Track((SelectData?)selMgr.CreateSelectData());
                if (selData1 != null) selData1.Mark = 1;
                ((IEntity)dir1Edge).Select4(true, selData1);

                // 3. Select Direction 2 reference edge with Mark = 2 if present
                bool dir2NeedsRev = false;
                if (p.Direction2 != null)
                {
                    var (dir2Edge, d2Rev) = ResolveDirectionEdge(doc, p.Direction2.Direction, scope);
                    dir2NeedsRev = d2Rev;
                    var selData2 = scope.Track((SelectData?)selMgr.CreateSelectData());
                    if (selData2 != null) selData2.Mark = 2;
                    ((IEntity)dir2Edge).Select4(true, selData2);
                }

                // 4. Create definition (populates references from active selection marks 4, 1, 2)
                var featData = scope.Track((ILinearPatternFeatureData?)doc.FeatureManager.CreateDefinition((int)swFeatureNameID_e.swFmLPattern));
                if (featData == null)
                {
                    throw new IpcException(ErrorCodes.BACKEND_OPERATION_FAILED, "Failed to create linear pattern definition.");
                }

                featData.D1Spacing = PartUnits.MmToMetres(p.Direction1.Spacing);
                featData.D1TotalInstances = (int)p.Direction1.Count;
                featData.D1ReverseDirection = dir1NeedsRev ^ (p.Direction1.Reverse ?? false);

                if (p.Direction2 != null)
                {
                    featData.D2Spacing = PartUnits.MmToMetres(p.Direction2.Spacing);
                    featData.D2TotalInstances = (int)p.Direction2.Count;
                    featData.D2ReverseDirection = dir2NeedsRev ^ (p.Direction2.Reverse ?? false);
                }

                createdFeature = scope.Track((IFeature?)doc.FeatureManager.CreateFeature(featData));
            }
            else if (p.Type == FeatureCreateParamsType.CircularPattern)
            {
                if (p.Seeds == null || p.Seeds.Count == 0)
                {
                    throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Circular pattern requires at least one seed feature.");
                }
                if (string.IsNullOrEmpty(p.Axis))
                {
                    throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Circular pattern requires axis.");
                }
                if (p.Count == null || p.Count < 2)
                {
                    throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Circular pattern requires count >= 2.");
                }
                if (p.Spacing == null || p.Spacing <= 0)
                {
                    throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Circular pattern requires spacing > 0.");
                }

                doc.ClearSelection2(true);

                // 1. Select seed features with Mark = 4 (pattern feature array)
                bool append = false;
                foreach (var seedId in p.Seeds)
                {
                    var sf = FeatureLookup.FindById(doc, seedId, scope);
                    if (sf == null)
                    {
                        throw new IpcException(ErrorCodes.IR_REFERENCE_UNRESOLVED, $"Seed feature '{seedId}' not found in document.");
                    }
                    sf.Select2(append, 4);
                    append = true;
                }

                var selMgr = (ISelectionMgr)doc.SelectionManager;

                // 2. Select rotation axis entity with Mark = 1
                var axisEntity = ResolveCircularPatternAxisEntity(doc, p.Axis!, scope);
                var selData = scope.Track((SelectData?)selMgr.CreateSelectData());
                if (selData != null) selData.Mark = 1;
                axisEntity.Select4(true, selData);

                // 3. Create definition
                var featData = scope.Track((ICircularPatternFeatureData?)doc.FeatureManager.CreateDefinition((int)swFeatureNameID_e.swFmCirPattern));
                if (featData == null)
                {
                    throw new IpcException(ErrorCodes.BACKEND_OPERATION_FAILED, "Failed to create circular pattern definition.");
                }

                featData.TotalInstances = (int)p.Count.Value;
                featData.EqualSpacing = p.EqualSpacing ?? true;
                double angleDeg = p.Spacing.Value;
                featData.Spacing = angleDeg * Math.PI / 180.0;
                featData.ReverseDirection = p.Reverse ?? false;

                createdFeature = scope.Track((IFeature?)doc.FeatureManager.CreateFeature(featData));
            }
            else if (p.Type == FeatureCreateParamsType.Mirror)
            {
                if (p.Seeds == null || p.Seeds.Count == 0)
                {
                    throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Mirror feature requires at least one seed feature.");
                }
                if (string.IsNullOrEmpty(p.Plane))
                {
                    throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Mirror feature requires plane.");
                }

                doc.ClearSelection2(true);

                // 1. Select seed features with Mark = 1 (features to mirror)
                bool append = false;
                foreach (var seedId in p.Seeds)
                {
                    var sf = FeatureLookup.FindById(doc, seedId, scope);
                    if (sf == null)
                    {
                        throw new IpcException(ErrorCodes.IR_REFERENCE_UNRESOLVED, $"Seed feature '{seedId}' not found in document.");
                    }
                    sf.Select2(append, 1);
                    append = true;
                }

                // 2. Select mirror plane with Mark = 2
                var mirrorPlane = ResolveMirrorPlaneFeature(doc, p.Plane!, scope);
                mirrorPlane.Select2(true, 2);

                // 3. Create mirror feature
                createdFeature = scope.Track((IFeature?)doc.FeatureManager.InsertMirrorFeature2(
                    false, // BMirrorBody = false (mirror features, not solid bodies)
                    false, // BGeometryPattern = false (solve features)
                    p.Merge ?? true, // BMerge = true
                    false, // BKnit = false
                    0 // ScopeOptions = 0
                ));
            }
            else
            {
                if (string.IsNullOrEmpty(p.Profile))
                {
                    throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, $"Feature type '{p.Type}' requires profile.");
                }

                // 1. Locate profile sketch by feature_id
                var profileFeature = FeatureLookup.FindById(doc, p.Profile!, scope);
                if (profileFeature == null)
                {
                    throw new IpcException(ErrorCodes.IR_REFERENCE_UNRESOLVED, $"Profile feature '{p.Profile}' not found in document.");
                }

                // 2. Select sketch (Select2 with mark 0, never SelectByID2)
                doc.ClearSelection2(true);
                profileFeature.Select2(false, 0);

                if (p.Type == FeatureCreateParamsType.Extrude)
                {
                    double depthM = PartUnits.MmToMetres(p.EndCondition?.Depth ?? 0.0);

                    createdFeature = scope.Track((IFeature?)doc.FeatureManager.FeatureExtrusion3(
                        true, // Sd
                        false, // Flip
                        false, // Dir
                        (int)swEndConditions_e.swEndCondBlind, // T1
                        0, // T2
                        depthM, // D1
                        0.0, // D2
                        false, false, false, false, 0.0, 0.0, false, false, false, false,
                        true, // Merge
                        true, // UseFeatScope
                        true, // UseAutoSelect
                        0, 0.0, false));
                }
                else if (p.Type == FeatureCreateParamsType.CutExtrude)
                {
                    var endType = p.EndCondition?.Type;
                    if (endType == FeatureCreateEndConditionType.ThroughAllBoth)
                    {
                        // Sd = false, T1 = swEndCondThroughAll (1), T2 = swEndCondThroughAll (1) (spike answer 2)
                        createdFeature = scope.Track((IFeature?)doc.FeatureManager.FeatureCut4(
                            false, // Sd
                            false, // Flip
                            false, // Dir
                            (int)swEndConditions_e.swEndCondThroughAll, // T1
                            (int)swEndConditions_e.swEndCondThroughAll, // T2
                            0.0, // D1
                            0.0, // D2
                            false, false, false, false, 0.0, 0.0, false, false, false, false, false,
                            true, // UseFeatScope
                            true, // UseAutoSelect
                            false, false, false, 0, 0.0, false, false));
                    }
                    else if (endType == FeatureCreateEndConditionType.Blind)
                    {
                        // Blind cut from an origin plane: Dir = true cuts into the body (spike answer 4).
                        // From a cap face the default direction already goes into the body, and Dir = true cuts
                        // nothing (face spike 2026-11-06, ADR-070).
                        double depthM = PartUnits.MmToMetres(p.EndCondition?.Depth ?? 0.0);
                        bool dir = p.Host != FeatureCreateParamsHost.Face;

                        createdFeature = scope.Track((IFeature?)doc.FeatureManager.FeatureCut4(
                            true, // Sd
                            false, // Flip
                            dir, // Dir
                            (int)swEndConditions_e.swEndCondBlind, // T1
                            0, // T2
                            depthM, // D1
                            0.0, // D2
                            false, false, false, false, 0.0, 0.0, false, false, false, false, false,
                            true, // UseFeatScope
                            true, // UseAutoSelect
                            false, false, false, 0, 0.0, false, false));
                    }
                    else
                    {
                        throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, $"Unsupported end condition type '{endType}' for cut_extrude.");
                    }
                }
                else
                {
                    throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, $"Unsupported feature type '{p.Type}'.");
                }
            }
        }
        catch (COMException ex)
        {
            string callName = p.Type switch
            {
                FeatureCreateParamsType.Extrude => "FeatureExtrusion3",
                FeatureCreateParamsType.CutExtrude => "FeatureCut4",
                FeatureCreateParamsType.LinearPattern => "CreateFeature(ILinearPatternFeatureData)",
                FeatureCreateParamsType.CircularPattern => "CreateFeature(ICircularPatternFeatureData)",
                FeatureCreateParamsType.Mirror => "InsertMirrorFeature2",
                _ => "Unknown"
            };
            var details = new JObject
            {
                ["effect"] = "unknown",
                ["stage"] = "invoke",
                ["native"] = new JObject
                {
                    ["call"] = callName,
                    ["hresult"] = $"0x{ex.ErrorCode:X8}"
                }
            };
            throw new IpcException(ErrorCodes.BACKEND_REBUILD_ERROR, $"{p.Type} threw COMException during feature creation: {ex.Message}", details);
        }

        // 3. Check feature creation outcome (null feature fails with BACKEND_REBUILD_ERROR)
        if (createdFeature == null)
        {
            string callName = p.Type switch
            {
                FeatureCreateParamsType.Extrude => "FeatureExtrusion3",
                FeatureCreateParamsType.CutExtrude => "FeatureCut4",
                FeatureCreateParamsType.LinearPattern => "CreateFeature(ILinearPatternFeatureData)",
                FeatureCreateParamsType.CircularPattern => "CreateFeature(ICircularPatternFeatureData)",
                FeatureCreateParamsType.Mirror => "InsertMirrorFeature2",
                _ => "Unknown"
            };
            var details = new JObject
            {
                ["effect"] = "none",
                ["stage"] = "invoke",
                ["native"] = new JObject
                {
                    ["call"] = callName,
                    ["returned"] = "null"
                }
            };
            throw new IpcException(ErrorCodes.BACKEND_REBUILD_ERROR, $"{p.Type} failed to create a feature.", details);
        }

        // 4. Solid features are followed by a forced rebuild before save (design 7)
        try
        {
            doc.ForceRebuild3(false);
        }
        catch (COMException ex)
        {
            var details = new JObject
            {
                ["effect"] = "partial",
                ["stage"] = "rebuild",
                ["native"] = new JObject
                {
                    ["call"] = "ForceRebuild3",
                    ["hresult"] = $"0x{ex.ErrorCode:X8}"
                }
            };
            throw new IpcException(ErrorCodes.BACKEND_REBUILD_ERROR, $"ForceRebuild3 threw COMException after creating {p.Type}: {ex.Message}", details);
        }

        // 5. Read back feature properties and observation
        int nativeId = createdFeature.GetID();
        string featureId = $"f{nativeId}";
        int errCode = createdFeature.GetErrorCode2(out bool isWarning);
        bool suppressed = createdFeature.IsSuppressed();

        FeatureCreateResultStatus status = FeatureCreateResultStatus.Ok;
        if (suppressed)
        {
            status = FeatureCreateResultStatus.Suppressed;
        }
        else if (errCode != 0)
        {
            status = FeatureCreateResultStatus.Error;
        }
        else if (isWarning)
        {
            status = FeatureCreateResultStatus.Warning;
        }

        var parents = new List<string>();
        object[]? parentsObj = (object[]?)createdFeature.GetParents();
        if (parentsObj != null)
        {
            foreach (var pObj in parentsObj)
            {
                var pf = scope.Track(pObj as IFeature);
                if (pf != null)
                {
                    parents.Add($"f{pf.GetID()}");
                }
            }
        }
        if (parents.Count == 0 && !string.IsNullOrEmpty(p.Profile))
        {
            parents.Add(p.Profile!);
        }
        else if (parents.Count == 0 && p.Seeds != null)
        {
            parents.AddRange(p.Seeds);
        }

        string obsType = p.Type switch
        {
            FeatureCreateParamsType.Extrude => "extrude",
            FeatureCreateParamsType.CutExtrude => "cut_extrude",
            FeatureCreateParamsType.LinearPattern => "linear_pattern",
            FeatureCreateParamsType.CircularPattern => "circular_pattern",
            FeatureCreateParamsType.Mirror => "mirror",
            _ => "unknown"
        };

        var observation = new Observation
        {
            NativeType = createdFeature.GetTypeName2(),
            Type = obsType,
            ErrorCode = errCode,
            IsWarning = isWarning,
            Suppressed = suppressed,
            Parents = parents,
            UpdateStamp = createdFeature.GetUpdateStamp(),
            Completeness = new ObservationCompleteness
            {
                Type = CompletenessState.Present,
                ErrorCode = CompletenessState.Present,
                Suppressed = CompletenessState.Present,
                Parents = CompletenessState.Present,
                Parameters = CompletenessState.Unsupported
            }
        };

        return new FeatureCreateResult
        {
            NativeId = nativeId,
            FeatureId = featureId,
            Status = status,
            Observation = observation
        };
    }

    private static (IEdge Edge, bool NeedsReverse) ResolveDirectionEdge(IModelDoc2 doc, string direction, ComScope scope)
    {
        double[] targetDir;
        string lower = direction.ToLowerInvariant();
        if (lower is "plane:right" or "x")
        {
            targetDir = new[] { 1.0, 0.0, 0.0 };
        }
        else if (lower is "plane:top" or "y")
        {
            targetDir = new[] { 0.0, 1.0, 0.0 };
        }
        else if (lower is "plane:front" or "z")
        {
            targetDir = new[] { 0.0, 0.0, 1.0 };
        }
        else if (lower is "-plane:right" or "-x")
        {
            targetDir = new[] { -1.0, 0.0, 0.0 };
        }
        else if (lower is "-plane:top" or "-y")
        {
            targetDir = new[] { 0.0, -1.0, 0.0 };
        }
        else if (lower is "-plane:front" or "-z")
        {
            targetDir = new[] { 0.0, 0.0, -1.0 };
        }
        else
        {
            throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, $"Unsupported direction reference '{direction}'.");
        }

        return FindDirectionEdge(doc, targetDir, scope);
    }

    private static IEntity ResolveCircularPatternAxisEntity(IModelDoc2 doc, string axisRef, ComScope scope)
    {
        double[]? targetAxis = null;
        string lower = axisRef.ToLowerInvariant();
        if (lower is "plane:right" or "x" or "axis:x")
        {
            targetAxis = new[] { 1.0, 0.0, 0.0 };
        }
        else if (lower is "plane:top" or "y" or "axis:y")
        {
            targetAxis = new[] { 0.0, 1.0, 0.0 };
        }
        else if (lower is "plane:front" or "z" or "axis:z")
        {
            targetAxis = new[] { 0.0, 0.0, 1.0 };
        }
        else if (lower is "-plane:right" or "-x" or "-axis:x")
        {
            targetAxis = new[] { -1.0, 0.0, 0.0 };
        }
        else if (lower is "-plane:top" or "-y" or "-axis:y")
        {
            targetAxis = new[] { 0.0, -1.0, 0.0 };
        }
        else if (lower is "-plane:front" or "-z" or "-axis:z")
        {
            targetAxis = new[] { 0.0, 0.0, -1.0 };
        }

        if (targetAxis != null)
        {
            var entity = FindAxisEntity(doc, targetAxis, scope);
            if (entity != null)
            {
                return entity;
            }
        }

        // Try as feature reference (e.g. cylinder/boss)
        var feat = FeatureLookup.FindById(doc, axisRef, scope);
        if (feat != null)
        {
            var faces = (object[]?)feat.GetFaces();
            if (faces != null)
            {
                foreach (object faceObj in faces)
                {
                    var face = (IFace2)faceObj;
                    using var localScope = new ComScope();
                    var surf = localScope.Track((ISurface?)face.GetSurface());
                    if (surf != null && surf.IsCylinder())
                    {
                        return (IEntity)scope.Track(face)!;
                    }
                    if (Marshal.IsComObject(face))
                    {
                        Marshal.ReleaseComObject(face);
                    }
                }
            }
        }

        throw new IpcException(
            ErrorCodes.IR_REFERENCE_UNRESOLVED,
            $"No cylindrical face, circular edge, or axis entity found matching axis reference '{axisRef}'.");
    }

    private static IEntity? FindAxisEntity(IModelDoc2 doc, double[] targetAxis, ComScope callerScope)
    {
        var partDoc = (IPartDoc)doc;
        var bodies = (object[]?)partDoc.GetBodies2((int)swBodyType_e.swSolidBody, false);
        if (bodies == null) return null;

        // 1. Circular edges aligned with axis normal
        foreach (object bodyObj in bodies)
        {
            var body = (IBody2)bodyObj;
            var edges = (object[]?)body.GetEdges();
            if (edges != null)
            {
                foreach (object edgeObj in edges)
                {
                    var edge = (IEdge)edgeObj;
                    using var localScope = new ComScope();
                    var curve = localScope.Track((ICurve?)edge.GetCurve());
                    if (curve != null && curve.IsCircle())
                    {
                        var circleParams = (double[]?)curve.CircleParams;
                        if (circleParams != null && circleParams.Length >= 7)
                        {
                            double nx = circleParams[4];
                            double ny = circleParams[5];
                            double nz = circleParams[6];
                            double dot = nx * targetAxis[0] + ny * targetAxis[1] + nz * targetAxis[2];
                            if (Math.Abs(Math.Abs(dot) - 1.0) < 1e-3)
                            {
                                return (IEntity)callerScope.Track(edge)!;
                            }
                        }
                    }
                    if (Marshal.IsComObject(edge))
                    {
                        Marshal.ReleaseComObject(edge);
                    }
                }
            }
        }

        // 2. Cylindrical faces aligned with axis direction
        foreach (object bodyObj in bodies)
        {
            var body = (IBody2)bodyObj;
            var faces = (object[]?)body.GetFaces();
            if (faces != null)
            {
                foreach (object faceObj in faces)
                {
                    var face = (IFace2)faceObj;
                    using var localScope = new ComScope();
                    var surf = localScope.Track((ISurface?)face.GetSurface());
                    if (surf != null && surf.IsCylinder())
                    {
                        var cylParams = (double[]?)surf.CylinderParams;
                        if (cylParams != null && cylParams.Length >= 6)
                        {
                            double ax = cylParams[3];
                            double ay = cylParams[4];
                            double az = cylParams[5];
                            double dot = ax * targetAxis[0] + ay * targetAxis[1] + az * targetAxis[2];
                            if (Math.Abs(Math.Abs(dot) - 1.0) < 1e-3)
                            {
                                return (IEntity)callerScope.Track(face)!;
                            }
                        }
                    }
                    if (Marshal.IsComObject(face))
                    {
                        Marshal.ReleaseComObject(face);
                    }
                }
            }
        }

        // 3. Linear edge aligned with direction
        var (linearEdge, _) = TryFindDirectionEdge(doc, targetAxis, callerScope);
        if (linearEdge != null)
        {
            return (IEntity)linearEdge;
        }

        return null;
    }

    private static (IEdge? Edge, bool NeedsReverse) TryFindDirectionEdge(IModelDoc2 doc, double[] targetDir, ComScope callerScope)
    {
        var partDoc = (IPartDoc)doc;
        var bodies = (object[]?)partDoc.GetBodies2((int)swBodyType_e.swSolidBody, false);
        if (bodies != null)
        {
            foreach (object bodyObj in bodies)
            {
                var body = (IBody2)bodyObj;
                var edges = (object[]?)body.GetEdges();
                if (edges == null) continue;
                foreach (object edgeObj in edges)
                {
                    var edge = (IEdge)edgeObj;
                    using var localScope = new ComScope();
                    var curve = localScope.Track((ICurve?)edge.GetCurve());
                    if (curve != null && curve.IsLine())
                    {
                        var lineParams = (double[]?)curve.LineParams;
                        if (lineParams != null && lineParams.Length >= 6)
                        {
                            double dx = lineParams[3];
                            double dy = lineParams[4];
                            double dz = lineParams[5];
                            double dot = dx * targetDir[0] + dy * targetDir[1] + dz * targetDir[2];
                            if (Math.Abs(Math.Abs(dot) - 1.0) < 1e-3)
                            {
                                bool reverse = dot < 0;
                                return (callerScope.Track(edge), reverse);
                            }
                        }
                    }
                    if (Marshal.IsComObject(edge))
                    {
                        Marshal.ReleaseComObject(edge);
                    }
                }
            }
        }
        return (null, false);
    }

    private static (IEdge Edge, bool NeedsReverse) FindDirectionEdge(IModelDoc2 doc, double[] targetDir, ComScope callerScope)
    {
        var (edge, needsRev) = TryFindDirectionEdge(doc, targetDir, callerScope);
        if (edge != null)
        {
            return (edge, needsRev);
        }

        throw new IpcException(
            ErrorCodes.IR_REFERENCE_UNRESOLVED,
            $"No linear edge found aligned with direction [{targetDir[0]}, {targetDir[1]}, {targetDir[2]}].");
    }

    public DocumentRebuildResult Rebuild(string document, DocumentRebuildParams p, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        var doc = DocumentLocator.FindDocument(_sw, document);
        bool force = p.Force ?? false;

        bool rebuilt;
        try
        {
            rebuilt = doc.ForceRebuild3(!force);
        }
        catch (COMException ex)
        {
            var details = new JObject
            {
                ["effect"] = "unknown",
                ["stage"] = "invoke",
                ["native"] = new JObject
                {
                    ["call"] = "ForceRebuild3",
                    ["hresult"] = $"0x{ex.ErrorCode:X8}"
                }
            };
            throw new IpcException(ErrorCodes.BACKEND_REBUILD_ERROR, $"ForceRebuild3 threw COMException: {ex.Message}", details);
        }

        using var scope = new ComScope();
        var errors = new List<string>();
        var feat = scope.Track((IFeature?)doc.FirstFeature());
        while (feat != null)
        {
            int err = feat.GetErrorCode2(out _);
            if (err != 0)
            {
                errors.Add($"f{feat.GetID()}");
            }
            feat = scope.Track((IFeature?)feat.GetNextFeature());
        }

        return new DocumentRebuildResult
        {
            Rebuilt = rebuilt,
            Ok = errors.Count == 0,
            Errors = errors
        };
    }
    private static IFeature ResolveMirrorPlaneFeature(IModelDoc2 doc, string planeRef, ComScope scope)
    {
        string lower = planeRef.ToLowerInvariant();
        int planeIndex;
        if (lower is "plane:front" or "front" or "z")
        {
            planeIndex = 0;
        }
        else if (lower is "plane:top" or "top" or "y")
        {
            planeIndex = 1;
        }
        else if (lower is "plane:right" or "right" or "x")
        {
            planeIndex = 2;
        }
        else
        {
            var pf = FeatureLookup.FindById(doc, planeRef, scope);
            if (pf != null) return pf;
            throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, $"Unsupported mirror plane reference '{planeRef}'.");
        }

        var refPlanes = new List<IFeature>();
        var feat = scope.Track((IFeature?)doc.FirstFeature());
        while (feat != null)
        {
            if (string.Equals(feat.GetTypeName2(), "RefPlane", StringComparison.OrdinalIgnoreCase))
            {
                refPlanes.Add(feat);
            }
            feat = scope.Track((IFeature?)feat.GetNextFeature());
        }

        if (refPlanes.Count <= planeIndex)
        {
            throw new IpcException(
                ErrorCodes.BACKEND_OPERATION_FAILED,
                $"Standard plane index {planeIndex} for '{planeRef}' not found in document (found {refPlanes.Count} planes).");
        }

        return refPlanes[planeIndex];
    }
}

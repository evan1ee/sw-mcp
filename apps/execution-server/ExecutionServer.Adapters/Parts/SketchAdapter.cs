using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using ExecutionServer.Adapters.Native;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Parts;
using SolidWorks.Interop.sldworks;

namespace ExecutionServer.Adapters.Parts;

/// <summary>
/// Implements operation sketch.create (spec 6.5.2, design 7, ADR-059, ADR-064).
/// Selects standard plane by RefPlane order, inserts sketch with AddToDB=true and AutoInference=false,
/// creates lines/circles in metres, and reads back T0 observation.
/// </summary>
public sealed class SketchAdapter
{
    private readonly ISldWorks _sw;

    public SketchAdapter(ISldWorks sw)
    {
        _sw = sw ?? throw new ArgumentNullException(nameof(sw));
    }

    public SketchCreateResult CreateSketch(string document, SketchCreateParams p, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        var doc = DocumentLocator.FindDocument(_sw, document);

        if ((p.Plane == null) == (p.Face == null))
        {
            throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "sketch.create needs exactly one of plane or face.");
        }

        if (p.Face != null)
        {
            // 1-2. Find the cap face by signature and select it (ADR-070)
            CapFaceSketch.Select(doc, p.Face);
        }
        else
        {
            // 1. Resolve standard plane by RefPlane order and verify normal (spike answer 3)
            using var planeScope = new ComScope();
            var targetPlane = ResolveAndVerifyPlane(doc, p.Plane!.Value, planeScope);

            // 2. Select plane (Select2 with mark 0, never SelectByID2)
            doc.ClearSelection2(true);
            targetPlane.Select2(false, 0);
        }

        // 3. Create sketch entities with AddToDB=true and AutoInference=false
        var sm = doc.SketchManager;
        bool prevAddToDb = sm.AddToDB;
        bool prevAutoInference = sm.AutoInference;

        bool sketchOpen = false;
        try
        {
            sm.AddToDB = true;
            sm.AutoInference = false;

            sm.InsertSketch(true);
            sketchOpen = true;

            if (p.Face != null)
            {
                CapFaceSketch.VerifyFrame(_sw, sm, p.Face);
            }

            foreach (var entity in p.Entities)
            {
                ct.ThrowIfCancellationRequested();

                if (entity.Type == SketchCreateEntityType.Line)
                {
                    if (entity.Start == null || entity.Start.Count < 2 || entity.End == null || entity.End.Count < 2)
                    {
                        throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Line entity requires start and end points [x, y].");
                    }

                    double x0 = PartUnits.MmToMetres(entity.Start[0]);
                    double y0 = PartUnits.MmToMetres(entity.Start[1]);
                    double x1 = PartUnits.MmToMetres(entity.End[0]);
                    double y1 = PartUnits.MmToMetres(entity.End[1]);

                    var line = sm.CreateLine(x0, y0, 0, x1, y1, 0);
                    if (line != null && Marshal.IsComObject(line))
                    {
                        Marshal.ReleaseComObject(line);
                    }
                }
                else if (entity.Type == SketchCreateEntityType.Circle)
                {
                    if (entity.Center == null || entity.Center.Count < 2 || !entity.Diameter.HasValue)
                    {
                        throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Circle entity requires center [x, y] and diameter.");
                    }

                    double cx = PartUnits.MmToMetres(entity.Center[0]);
                    double cy = PartUnits.MmToMetres(entity.Center[1]);
                    double r = PartUnits.MmToMetres(entity.Diameter.Value / 2.0);

                    var circle = sm.CreateCircleByRadius(cx, cy, 0, r);
                    if (circle != null && Marshal.IsComObject(circle))
                    {
                        Marshal.ReleaseComObject(circle);
                    }
                }
                else if (entity.Type == SketchCreateEntityType.Arc)
                {
                    if (entity.Center == null || entity.Center.Count < 2 ||
                        entity.Start == null || entity.Start.Count < 2 ||
                        entity.End == null || entity.End.Count < 2)
                    {
                        throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Arc entity requires center, start, and end points [x, y].");
                    }

                    double xc = PartUnits.MmToMetres(entity.Center[0]);
                    double yc = PartUnits.MmToMetres(entity.Center[1]);
                    double xp1 = PartUnits.MmToMetres(entity.Start[0]);
                    double yp1 = PartUnits.MmToMetres(entity.Start[1]);
                    double xp2 = PartUnits.MmToMetres(entity.End[0]);
                    double yp2 = PartUnits.MmToMetres(entity.End[1]);
                    short dir = entity.Direction == SketchCreateEntityDirection.Cw ? (short)-1 : (short)1;

                    var arc = sm.CreateArc(xc, yc, 0, xp1, yp1, 0, xp2, yp2, 0, dir);
                    if (arc != null && Marshal.IsComObject(arc))
                    {
                        Marshal.ReleaseComObject(arc);
                    }
                }
                else
                {
                    throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, $"Unsupported sketch entity type '{entity.Type}'.");
                }
            }

            sm.InsertSketch(true); // Close sketch
            sketchOpen = false;
        }
        finally
        {
            if (sketchOpen)
            {
                // Leave edit mode so later commands do not run inside a half-built sketch.
                sm.InsertSketch(true);
            }

            sm.AddToDB = prevAddToDb;
            sm.AutoInference = prevAutoInference;
        }

        // 4. Retrieve created sketch feature (most recent feature in tree)
        using var sketchScope = new ComScope();
        var sketchFeature = sketchScope.Track((IFeature?)doc.FeatureByPositionReverse(0));
        if (sketchFeature == null)
        {
            throw new IpcException(ErrorCodes.BACKEND_REBUILD_ERROR, "Sketch creation failed to produce a feature.");
        }

        int nativeId = sketchFeature.GetID();
        string featureId = $"f{nativeId}";
        int errCode = sketchFeature.GetErrorCode2(out bool isWarning);
        bool suppressed = sketchFeature.IsSuppressed();
        long updateStamp = sketchFeature.GetUpdateStamp();

        var observation = new Observation
        {
            NativeType = sketchFeature.GetTypeName2() ?? "ProfileFeature",
            Type = "sketch",
            ErrorCode = errCode,
            IsWarning = isWarning,
            Suppressed = suppressed,
            Parents = new List<string>(),
            UpdateStamp = updateStamp,
            Completeness = new ObservationCompleteness
            {
                Type = CompletenessState.Present,
                ErrorCode = CompletenessState.Present,
                Suppressed = CompletenessState.Present,
                Parents = CompletenessState.Empty,
                Parameters = CompletenessState.Unsupported
            }
        };

        return new SketchCreateResult
        {
            NativeId = nativeId,
            FeatureId = featureId,
            EntityCount = p.Entities.Count,
            Observation = observation
        };
    }

    private IFeature ResolveAndVerifyPlane(IModelDoc2 doc, SketchCreateParamsPlane planeRole, ComScope callerScope)
    {
        int planeIndex;
        double expNx, expNy, expNz;

        switch (planeRole)
        {
            case SketchCreateParamsPlane.PlaneFront:
                planeIndex = 0;
                expNx = 0; expNy = 0; expNz = 1;
                break;
            case SketchCreateParamsPlane.PlaneTop:
                planeIndex = 1;
                expNx = 0; expNy = 1; expNz = 0;
                break;
            case SketchCreateParamsPlane.PlaneRight:
                planeIndex = 2;
                expNx = 1; expNy = 0; expNz = 0;
                break;
            default:
                throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, $"Unsupported plane role '{planeRole}'.");
        }

        var refPlanes = new List<IFeature>();
        var feat = callerScope.Track((IFeature?)doc.FirstFeature());
        while (feat != null)
        {
            if (string.Equals(feat.GetTypeName2(), "RefPlane", StringComparison.OrdinalIgnoreCase))
            {
                refPlanes.Add(feat);
            }
            feat = callerScope.Track((IFeature?)feat.GetNextFeature());
        }

        if (refPlanes.Count <= planeIndex)
        {
            throw new IpcException(
                ErrorCodes.BACKEND_OPERATION_FAILED,
                $"Standard plane index {planeIndex} for '{planeRole}' not found in document (found {refPlanes.Count} planes).");
        }

        var targetPlane = refPlanes[planeIndex];

        // Verify normal
        using (var scope = new ComScope())
        {
            var refPlane = scope.Track((IRefPlane?)targetPlane.GetSpecificFeature2());
            if (refPlane != null)
            {
                var transform = scope.Track((IMathTransform?)refPlane.Transform);
                if (transform != null)
                {
                    var mathUtil = (IMathUtility)_sw.GetMathUtility();
                    var pt0 = scope.Track((IMathPoint)mathUtil.CreatePoint(new double[] { 0, 0, 0 }));
                    var pt1 = scope.Track((IMathPoint)mathUtil.CreatePoint(new double[] { 0, 0, 1 }));
                    if (pt0 != null && pt1 != null)
                    {
                        var pt0T = scope.Track((IMathPoint)pt0.MultiplyTransform(transform));
                        var pt1T = scope.Track((IMathPoint)pt1.MultiplyTransform(transform));

                        if (pt0T != null && pt1T != null)
                        {
                            double[] arr0 = (double[])pt0T.ArrayData;
                            double[] arr1 = (double[])pt1T.ArrayData;

                            double nx = arr1[0] - arr0[0];
                            double ny = arr1[1] - arr0[1];
                            double nz = arr1[2] - arr0[2];

                            if (Math.Abs(nx - expNx) > 1e-4 || Math.Abs(ny - expNy) > 1e-4 || Math.Abs(nz - expNz) > 1e-4)
                            {
                                throw new IpcException(
                                    ErrorCodes.BACKEND_OPERATION_FAILED,
                                    $"Plane normal mismatch for '{planeRole}': expected [{expNx}, {expNy}, {expNz}], observed [{nx:F4}, {ny:F4}, {nz:F4}].");
                            }
                        }
                    }
                }
            }
        }

        return targetPlane;
    }
}

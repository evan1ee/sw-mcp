using System;
using System.Collections.Generic;
using ExecutionServer.Adapters.Native;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Parts;
using SolidWorks.Interop.sldworks;

namespace ExecutionServer.Adapters.Parts;

/// <summary>
/// Puts a sketch on a cap face of an extrude (ADR-070). The face is found by the signature the compiler computed
/// (outward normal and offset), selected with <c>IEntity.Select4</c>, and the opened sketch's frame is checked.
/// Nothing is kept between commands: faces are read, matched, selected and released inside one call (G1).
/// </summary>
internal static class CapFaceSketch
{
    /// <summary>Selects the cap face; the next <c>InsertSketch(true)</c> opens a sketch on it.</summary>
    public static void Select(IModelDoc2 doc, SketchCreateFace face)
    {
        var extrude = FeatureLookup.FindById(doc, face.Feature);
        if (extrude == null)
        {
            throw new IpcException(ErrorCodes.REF_NOT_FOUND, $"Extrude '{face.Feature}' for the face sketch is not in the document.");
        }

        using var scope = new ComScope();
        var raw = extrude.GetFaces() as object[];
        var candidates = new List<PlanarFace>();
        var faces = new List<IFace2>();
        if (raw != null)
        {
            foreach (var item in raw)
            {
                var candidate = scope.Track(item as IFace2);
                if (candidate == null) continue;
                faces.Add(candidate);

                var surface = scope.Track((ISurface?)candidate.GetSurface());
                if (surface == null || !surface.IsPlane()) continue;
                if (!(candidate.Normal is double[] normal) || !(surface.PlaneParams is double[] plane) || plane.Length < 6) continue;

                candidates.Add(new PlanarFace(faces.Count - 1, normal, new[] { plane[3], plane[4], plane[5] }));
            }
        }

        var hits = FaceSignature.Match(candidates, face.Normal.ToArray(), face.OffsetMm);
        if (hits.Count == 0)
        {
            throw new IpcException(ErrorCodes.REF_NOT_FOUND, $"No planar face of '{face.Feature}' has the {face.Role} normal and offset {face.OffsetMm} mm.");
        }

        if (hits.Count > 1)
        {
            throw new IpcException(ErrorCodes.REF_AMBIGUOUS, $"{hits.Count} planar faces of '{face.Feature}' match the {face.Role} signature.");
        }

        var selectionManager = (ISelectionMgr)doc.SelectionManager;
        var data = scope.Track((SelectData?)selectionManager.CreateSelectData());
        if (data != null) data.Mark = 0;

        doc.ClearSelection2(true);
        if (!((IEntity)faces[hits[0]]).Select4(false, data))
        {
            throw new IpcException(ErrorCodes.BACKEND_OPERATION_FAILED, $"SOLIDWORKS did not select the {face.Role} of '{face.Feature}'.");
        }
    }

    /// <summary>Fails with REF_SIGNATURE_MISMATCH when the opened sketch's axes differ from the stated frame (K29).</summary>
    public static void VerifyFrame(ISldWorks sw, ISketchManager sm, SketchCreateFace face)
    {
        using var scope = new ComScope();
        var sketch = scope.Track((ISketch?)sm.ActiveSketch);
        if (sketch == null)
        {
            throw new IpcException(ErrorCodes.BACKEND_OPERATION_FAILED, "No active sketch after opening one on the face.");
        }

        var toSketch = scope.Track((IMathTransform?)sketch.ModelToSketchTransform);
        var toModel = toSketch == null ? null : scope.Track((IMathTransform?)toSketch.Inverse());
        if (toModel == null)
        {
            throw new IpcException(ErrorCodes.BACKEND_OPERATION_FAILED, "The sketch has no transform to read its frame from.");
        }

        var math = (IMathUtility)sw.GetMathUtility();
        double[] origin = Map(scope, math, toModel, 0, 0, 0);
        double[] x = Subtract(Map(scope, math, toModel, 1, 0, 0), origin);
        double[] y = Subtract(Map(scope, math, toModel, 0, 1, 0), origin);
        double[] normal = Subtract(Map(scope, math, toModel, 0, 0, 1), origin);

        if (!FaceSignature.FrameMatches(face.XAxis.ToArray(), face.YAxis.ToArray(), face.Normal.ToArray(), x, y, normal))
        {
            throw new IpcException(
                ErrorCodes.REF_SIGNATURE_MISMATCH,
                $"The sketch on the {face.Role} has axes x=[{Join(x)}] y=[{Join(y)}] normal=[{Join(normal)}], "
                + $"not the expected x=[{Join(face.XAxis.ToArray())}] y=[{Join(face.YAxis.ToArray())}] normal=[{Join(face.Normal.ToArray())}].");
        }
    }

    private static double[] Map(ComScope scope, IMathUtility math, IMathTransform transform, double x, double y, double z)
    {
        var point = scope.Track((IMathPoint)math.CreatePoint(new[] { x, y, z }));
        var moved = scope.Track((IMathPoint)point!.MultiplyTransform(transform));
        return (double[])moved!.ArrayData;
    }

    private static double[] Subtract(double[] a, double[] b) => new[] { a[0] - b[0], a[1] - b[1], a[2] - b[2] };

    private static string Join(double[] values) => string.Join(", ", Array.ConvertAll(values, v => v.ToString("0.####")));
}

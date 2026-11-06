using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using ExecutionServer.Adapters.Native;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ownership;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace ExecutionServer.Adapters.Parts;

/// <summary>
/// Implements command part.measure (spec 8.7, design 7, ADR-059, ADR-064).
/// Reads raw SI measurements from SOLIDWORKS: IMassProperty with UseSystemUnits=true,
/// body bounding box, cylindrical surfaces, feature tree, and rebuild error status.
/// </summary>
public sealed class PartMeasureAdapter
{
    private readonly ISldWorks _sw;
    private readonly DocumentOwnershipTable? _ownership;

    public PartMeasureAdapter(ISldWorks sw, DocumentOwnershipTable? ownership = null)
    {
        _sw = sw ?? throw new ArgumentNullException(nameof(sw));
        _ownership = ownership;
    }

    public PartMeasureResult Measure(PartMeasureParams p, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        var doc = DocumentLocator.FindDocument(_sw, p.Document);
        var path = p.Document;

        // 1. Instance ID
        string instanceId = _ownership?.GetInstanceId(path, p.Meta?.JobId) ?? Guid.NewGuid().ToString("N");

        // 2. Mass properties in SI units (metres, m^2, m^3, kg)
        double volumeM3 = 0.0;
        double surfaceAreaM2 = 0.0;
        var centerOfMassM = new List<double> { 0.0, 0.0, 0.0 };

        var mass = (IMassProperty?)doc.Extension.CreateMassProperty();
        if (mass != null)
        {
            try
            {
                mass.UseSystemUnits = true; // Spike answer 4 & 6: true ensures SI units (metres)
                volumeM3 = mass.Volume;
                surfaceAreaM2 = mass.SurfaceArea;
                double[]? com = (double[]?)mass.CenterOfMass;
                if (com != null && com.Length >= 3)
                {
                    centerOfMassM = new List<double> { com[0], com[1], com[2] };
                }
            }
            finally
            {
                try { Marshal.ReleaseComObject(mass); } catch { }
            }
        }

        // 3. Bodies and bounding box
        long solidBodyCount = 0;
        var bboxM = new PartBBoxM
        {
            Min = new List<double> { 0.0, 0.0, 0.0 },
            Max = new List<double> { 0.0, 0.0, 0.0 }
        };
        var cylindersM = new List<PartCylinderM>();

        if (doc is IPartDoc partDoc)
        {
            object[]? bodiesObj = (object[]?)partDoc.GetBodies2((int)swBodyType_e.swSolidBody, false);
            if (bodiesObj != null)
            {
                solidBodyCount = bodiesObj.Length;

                double minX = double.MaxValue, minY = double.MaxValue, minZ = double.MaxValue;
                double maxX = double.MinValue, maxY = double.MinValue, maxZ = double.MinValue;

                foreach (var bObj in bodiesObj)
                {
                    ct.ThrowIfCancellationRequested();
                    if (bObj is IBody2 body)
                    {
                        try
                        {
                            double[]? box = (double[]?)body.GetBodyBox();
                            if (box != null && box.Length == 6)
                            {
                                if (box[0] < minX) minX = box[0];
                                if (box[1] < minY) minY = box[1];
                                if (box[2] < minZ) minZ = box[2];
                                if (box[3] > maxX) maxX = box[3];
                                if (box[4] > maxY) maxY = box[4];
                                if (box[5] > maxZ) maxZ = box[5];
                            }

                            // Extract cylindrical faces (spike answer 6)
                            object[]? facesObj = (object[]?)body.GetFaces();
                            if (facesObj != null)
                            {
                                foreach (var fObj in facesObj)
                                {
                                    ct.ThrowIfCancellationRequested();
                                    if (fObj is Face2 face)
                                    {
                                        try
                                        {
                                            var surf = (ISurface?)face.GetSurface();
                                            if (surf != null)
                                            {
                                                try
                                                {
                                                    if (surf.IsCylinder())
                                                    {
                                                        double[]? cp = (double[]?)surf.CylinderParams;
                                                        if (cp != null && cp.Length >= 7)
                                                        {
                                                            cylindersM.Add(new PartCylinderM
                                                            {
                                                                Point = new List<double> { cp[0], cp[1], cp[2] },
                                                                Direction = new List<double> { cp[3], cp[4], cp[5] },
                                                                Radius = cp[6]
                                                            });
                                                        }
                                                    }
                                                }
                                                finally
                                                {
                                                    Marshal.ReleaseComObject(surf);
                                                }
                                            }
                                        }
                                        finally
                                        {
                                            Marshal.ReleaseComObject(face);
                                        }
                                    }
                                }
                            }
                        }
                        finally
                        {
                            Marshal.ReleaseComObject(body);
                        }
                    }
                }

                if (minX != double.MaxValue)
                {
                    bboxM.Min = new List<double> { minX, minY, minZ };
                    bboxM.Max = new List<double> { maxX, maxY, maxZ };
                }
            }
        }

        // 4. Features and rebuild error list
        var features = new List<PartFeatureInfo>();
        var rebuildErrors = new List<string>();

        var feat = (IFeature?)doc.FirstFeature();
        while (feat != null)
        {
            int featId = feat.GetID();
            string featureId = $"f{featId}";
            string typeName = feat.GetTypeName2() ?? string.Empty;
            int errCode = feat.GetErrorCode2(out bool isWarning);
            bool suppressed = feat.IsSuppressed();

            string status = "ok";
            if (suppressed)
            {
                status = "suppressed";
            }
            else if (errCode != 0)
            {
                status = "error";
                rebuildErrors.Add(featureId);
            }
            else if (isWarning)
            {
                status = "warning";
            }

            features.Add(new PartFeatureInfo
            {
                FeatureId = featureId,
                NativeId = featId,
                Type = typeName,
                Status = status
            });

            feat = (IFeature?)feat.GetNextFeature();
        }

        bool dirty = doc.GetSaveFlag();
        bool readOnly = doc.IsOpenedReadOnly();

        return new PartMeasureResult
        {
            Path = path,
            InstanceId = instanceId,
            SolidBodyCount = solidBodyCount,
            BboxM = bboxM,
            VolumeM3 = volumeM3,
            SurfaceAreaM2 = surfaceAreaM2,
            CenterOfMassM = centerOfMassM,
            CylindersM = cylindersM,
            Rebuild = new PartRebuildResult
            {
                Ok = rebuildErrors.Count == 0,
                Errors = rebuildErrors
            },
            Features = features,
            Dirty = dirty,
            ReadOnly = readOnly
        };
    }
}

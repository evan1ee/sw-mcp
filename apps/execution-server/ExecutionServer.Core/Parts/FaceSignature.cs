using System;
using System.Collections.Generic;

namespace ExecutionServer.Core.Parts;

/// <summary>A planar face as read from the model: outward normal and a point on its plane, in metres.</summary>
public readonly struct PlanarFace
{
    public PlanarFace(int index, double[] normal, double[] root)
    {
        Index = index;
        Normal = normal ?? throw new ArgumentNullException(nameof(normal));
        Root = root ?? throw new ArgumentNullException(nameof(root));
    }

    public int Index { get; }

    public double[] Normal { get; }

    public double[] Root { get; }
}

/// <summary>
/// CAD-free matching of an extrude's cap face by signature: outward unit normal and offset of its plane from the
/// model origin (ADR-070). Nothing is persisted; the add-in reads the faces, calls this, and selects the match.
/// </summary>
public static class FaceSignature
{
    public const double NormalTolerance = 1e-6;
    public const double OffsetToleranceMm = 1e-3;
    public const double AxisTolerance = 1e-4;

    /// <summary>Indexes of the faces whose normal equals <paramref name="normal"/> and whose plane lies at <paramref name="offsetMm"/>.</summary>
    public static IReadOnlyList<int> Match(IReadOnlyList<PlanarFace> faces, double[] normal, double offsetMm)
    {
        if (faces == null) throw new ArgumentNullException(nameof(faces));
        var wanted = Unit(normal);
        var hits = new List<int>();
        foreach (var face in faces)
        {
            var n = Unit(face.Normal);
            if (Math.Abs(n[0] - wanted[0]) > NormalTolerance
                || Math.Abs(n[1] - wanted[1]) > NormalTolerance
                || Math.Abs(n[2] - wanted[2]) > NormalTolerance)
            {
                continue;
            }

            double offsetM = n[0] * face.Root[0] + n[1] * face.Root[1] + n[2] * face.Root[2];
            if (Math.Abs(PartUnits.MetresToMm(offsetM) - offsetMm) <= OffsetToleranceMm)
            {
                hits.Add(face.Index);
            }
        }

        return hits;
    }

    /// <summary>True when the opened sketch's axes equal the frame the compiler stated.</summary>
    public static bool FrameMatches(
        double[] expectedX, double[] expectedY, double[] expectedNormal,
        double[] actualX, double[] actualY, double[] actualNormal)
    {
        return Close(expectedX, actualX) && Close(expectedY, actualY) && Close(expectedNormal, actualNormal);
    }

    private static bool Close(double[] a, double[] b)
    {
        if (a.Length != 3 || b.Length != 3) return false;
        for (int i = 0; i < 3; i++)
        {
            if (Math.Abs(a[i] - b[i]) > AxisTolerance) return false;
        }

        return true;
    }

    private static double[] Unit(double[] v)
    {
        if (v == null || v.Length != 3) throw new ArgumentException("A normal needs three components.", nameof(v));
        double length = Math.Sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
        if (length == 0.0) throw new ArgumentException("A normal cannot have zero length.", nameof(v));
        return new[] { v[0] / length, v[1] / length, v[2] / length };
    }
}

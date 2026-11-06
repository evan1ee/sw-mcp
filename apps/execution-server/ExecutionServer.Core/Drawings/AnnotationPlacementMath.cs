using System;

namespace ExecutionServer.Core.Drawings;

/// <summary>
/// CAD-free mathematical operations for drawing annotation spacing, clearance, and bounds (spec 11.4).
/// Completely decoupled from SOLIDWORKS APIs (ADR-038).
/// </summary>
public static class AnnotationPlacementMath
{
    private const double MmPerMeter = 1000.0;

    /// <summary>
    /// Calculates the target position for stacked dimension lines.
    /// </summary>
    public static double CalculateOffset(double baselineMm, int rank, double spacingMm)
    {
        return baselineMm + (rank * spacingMm);
    }

    /// <summary>
    /// Determines whether two 2D axis-aligned bounding boxes overlap, accounting for an optional clearance margin.
    /// </summary>
    public static bool IsOverlapping(
        double minX1, double minY1, double maxX1, double maxY1,
        double minX2, double minY2, double maxX2, double maxY2,
        double marginMm = 0.0)
    {
        // Expand the first box by margin
        double expMinX1 = minX1 - marginMm;
        double expMinY1 = minY1 - marginMm;
        double expMaxX1 = maxX1 + marginMm;
        double expMaxY1 = maxY1 + marginMm;

        // No overlap if one box is completely to the left, right, above, or below the other
        if (expMaxX1 < minX2 || expMinX1 > maxX2) return false;
        if (expMaxY1 < minY2 || expMinY1 > maxY2) return false;

        return true;
    }

    /// <summary>
    /// Calculates the 2D centroid of a set of coordinate pairs [x0, y0, x1, y1, ...].
    /// </summary>
    public static (double x, double y) CalculateCentroid(double[] coordinates)
    {
        if (coordinates == null || coordinates.Length < 2)
        {
            return (0.0, 0.0);
        }

        double sumX = 0.0;
        double sumY = 0.0;
        int pointCount = coordinates.Length / 2;

        for (int i = 0; i < pointCount; i++)
        {
            sumX += coordinates[i * 2];
            sumY += coordinates[i * 2 + 1];
        }

        return (sumX / pointCount, sumY / pointCount);
    }

    /// <summary>
    /// Converts millimeters to meters.
    /// </summary>
    public static double MmToMeters(double mm)
    {
        return mm / MmPerMeter;
    }

    /// <summary>
    /// Converts meters to millimeters.
    /// </summary>
    public static double MetersToMm(double m)
    {
        return m * MmPerMeter;
    }
}

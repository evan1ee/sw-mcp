using System;

namespace ExecutionServer.Core.Drawings;

/// <summary>
/// Pure mathematical calculations for drawing view layout, scale parsing, and coordinate conversions (spec 11.2, 11.11).
/// Adheres strictly to ADR-038 (ExecutionServer.Core CAD-free).
/// </summary>
public static class ViewLayoutGeometry
{
    /// <summary>
    /// Convert coordinates from drawing sheet millimetres to SOLIDWORKS metres.
    /// </summary>
    public static (double xMeters, double yMeters) MmToMeters(double xMm, double yMm)
    {
        return (xMm / 1000.0, yMm / 1000.0);
    }

    /// <summary>
    /// Convert coordinates from SOLIDWORKS metres to drawing sheet millimetres.
    /// </summary>
    public static (double xMm, double yMm) MetersToMm(double xM, double yM)
    {
        return (xM * 1000.0, yM * 1000.0);
    }

    /// <summary>
    /// Parse an ISO scale string such as "1:1", "1:2", or "2:1" into a floating-point ratio.
    /// </summary>
    public static double ParseScaleRatio(string scaleStr)
    {
        if (string.IsNullOrWhiteSpace(scaleStr))
        {
            throw new ArgumentException("Scale string cannot be empty", nameof(scaleStr));
        }

        var parts = scaleStr.Trim().Split(':');
        if (parts.Length != 2)
        {
            throw new ArgumentException($"Invalid scale format '{scaleStr}' (expected 'num:den')", nameof(scaleStr));
        }

        if (!double.TryParse(parts[0], out var num) || !double.TryParse(parts[1], out var den) || num <= 0 || den <= 0)
        {
            throw new ArgumentException($"Invalid scale values '{scaleStr}'", nameof(scaleStr));
        }

        return num / den;
    }

    /// <summary>
    /// Checks whether an axis-aligned bounding box lies strictly within the drawing sheet borders.
    /// </summary>
    public static bool IsWithinSheet(
        double minX, double minY, double maxX, double maxY,
        double sheetWidthMm, double sheetHeightMm, double marginMm = 0.0)
    {
        if (minX < marginMm || minY < marginMm)
        {
            return false;
        }

        if (maxX > (sheetWidthMm - marginMm) || maxY > (sheetHeightMm - marginMm))
        {
            return false;
        }

        return true;
    }
}

using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Drawings;

public readonly struct LineSegment
{
    public double X1 { get; }
    public double Y1 { get; }
    public double X2 { get; }
    public double Y2 { get; }
    public double LineWidthMm { get; }

    public LineSegment(double x1, double y1, double x2, double y2, double lineWidthMm = 0.0)
    {
        X1 = x1;
        Y1 = y1;
        X2 = x2;
        Y2 = y2;
        LineWidthMm = lineWidthMm;
    }
}

public static class SheetFormatGeometry
{
    public static (double widthMm, double heightMm) GetPaperDimensions(string size, string orientation)
    {
        if (string.IsNullOrEmpty(size)) throw new ArgumentException("Paper size must not be empty.", nameof(size));

        double shortSide;
        double longSide;

        switch (size.Trim().ToUpperInvariant())
        {
            case "A4":
                shortSide = 210.0;
                longSide = 297.0;
                break;
            case "A3":
                shortSide = 297.0;
                longSide = 420.0;
                break;
            case "A2":
                shortSide = 420.0;
                longSide = 594.0;
                break;
            case "A1":
                shortSide = 594.0;
                longSide = 841.0;
                break;
            case "A0":
                shortSide = 841.0;
                longSide = 1189.0;
                break;
            default:
                throw new ArgumentException($"Unsupported paper size '{size}'.", nameof(size));
        }

        var isLandscape = string.Equals(orientation, "landscape", StringComparison.OrdinalIgnoreCase);
        return isLandscape ? (longSide, shortSide) : (shortSide, longSide);
    }

    public static List<LineSegment> ComputeBorderLines(
        double widthMm,
        double heightMm,
        double left,
        double right,
        double top,
        double bottom,
        double lineWidthMm = 0.5)
    {
        var xMin = left;
        var xMax = widthMm - right;
        var yMin = bottom;
        var yMax = heightMm - top;

        return new List<LineSegment>
        {
            new LineSegment(xMin, yMin, xMax, yMin, lineWidthMm), // Bottom: left -> right
            new LineSegment(xMax, yMin, xMax, yMax, lineWidthMm), // Right: bottom -> top
            new LineSegment(xMax, yMax, xMin, yMax, lineWidthMm), // Top: right -> left
            new LineSegment(xMin, yMax, xMin, yMin, lineWidthMm), // Left: top -> bottom
        };
    }

    public static string? FormatFieldNoteText(string fieldName, JArray? sourceCandidates)
    {
        if (sourceCandidates == null || sourceCandidates.Count == 0)
        {
            return string.Empty;
        }

        foreach (var candidateToken in sourceCandidates)
        {
            var candidate = candidateToken?.Value<string>();
            if (candidate == null || candidate.Length == 0) continue;

            if (candidate.StartsWith("part_property:", StringComparison.OrdinalIgnoreCase))
            {
                var propName = candidate.Substring("part_property:".Length);
                return $"$PRPSHEET:\"{propName}\"";
            }

            if (string.Equals(candidate, "part_material", StringComparison.OrdinalIgnoreCase))
            {
                return "$PRPSHEET:\"Material\"";
            }

            if (candidate.StartsWith("drawing_property:", StringComparison.OrdinalIgnoreCase))
            {
                var propName = candidate.Substring("drawing_property:".Length);
                return $"$PRP:\"{propName}\"";
            }

            if (string.Equals(candidate, "sheet:scale", StringComparison.OrdinalIgnoreCase))
            {
                return "$PRP:\"SW-Sheet Scale\"";
            }

            if (string.Equals(candidate, "sheet:units", StringComparison.OrdinalIgnoreCase))
            {
                return "mm";
            }

            if (string.Equals(candidate, "sheet:projection", StringComparison.OrdinalIgnoreCase))
            {
                // Projection symbol is geometric, not text note
                return null;
            }

            if (candidate.StartsWith("design_intent:", StringComparison.OrdinalIgnoreCase) ||
                candidate.StartsWith("drawing_intent:", StringComparison.OrdinalIgnoreCase))
            {
                // Property link format or fallback
                var propName = candidate.Substring(candidate.IndexOf(':') + 1);
                return $"$PRP:\"{propName}\"";
            }
        }

        return string.Empty;
    }
}

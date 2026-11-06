using System;
using ExecutionServer.Core.Drawings;
using Xunit;

namespace ExecutionServer.Tests.Drawings;

public class AnnotationPlacementMathTests
{
    [Theory]
    [InlineData(100.0, 1, 10.0, 110.0)]
    [InlineData(100.0, 2, 10.0, 120.0)]
    [InlineData(100.0, 0, 10.0, 100.0)]
    [InlineData(50.0, 3, 8.0, 74.0)]
    public void CalculateOffset_ComputesStackedPositions(double baselineMm, int rank, double spacingMm, double expected)
    {
        var result = AnnotationPlacementMath.CalculateOffset(baselineMm, rank, spacingMm);
        Assert.Equal(expected, result, 4);
    }

    [Theory]
    [InlineData(0, 0, 10, 10, 5, 5, 15, 15, 0.0, true)] // overlapping
    [InlineData(0, 0, 10, 10, 20, 20, 30, 30, 0.0, false)] // clearly separate
    [InlineData(0, 0, 10, 10, 11, 11, 20, 20, 0.0, false)] // separated by 1mm
    [InlineData(0, 0, 10, 10, 11, 11, 20, 20, 2.0, true)] // overlapping with 2mm margin
    public void IsOverlapping_AabbOverlapCheck(
        double minX1, double minY1, double maxX1, double maxY1,
        double minX2, double minY2, double maxX2, double maxY2,
        double marginMm, bool expected)
    {
        var result = AnnotationPlacementMath.IsOverlapping(
            minX1, minY1, maxX1, maxY1,
            minX2, minY2, maxX2, maxY2,
            marginMm);
        Assert.Equal(expected, result);
    }

    [Fact]
    public void CalculateCentroid_ComputesAverage()
    {
        // 4 corners of a 20x10 rectangle centered at (50, 60)
        double[] corners = new double[]
        {
            40.0, 55.0, // bottom-left
            60.0, 55.0, // bottom-right
            60.0, 65.0, // top-right
            40.0, 65.0  // top-left
        };
        var (x, y) = AnnotationPlacementMath.CalculateCentroid(corners);
        Assert.Equal(50.0, x, 4);
        Assert.Equal(60.0, y, 4);
    }

    [Theory]
    [InlineData(10.0, 0.010)]
    [InlineData(250.0, 0.250)]
    [InlineData(0.0, 0.0)]
    public void MmToMeters_Converts(double mm, double expectedM)
    {
        Assert.Equal(expectedM, AnnotationPlacementMath.MmToMeters(mm), 6);
    }

    [Theory]
    [InlineData(0.010, 10.0)]
    [InlineData(0.250, 250.0)]
    [InlineData(0.0, 0.0)]
    public void MetersToMm_Converts(double m, double expectedMm)
    {
        Assert.Equal(expectedMm, AnnotationPlacementMath.MetersToMm(m), 6);
    }
}

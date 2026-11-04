using System;
using ExecutionServer.Core.Drawings;
using Xunit;

namespace ExecutionServer.Tests.Drawings;

public class ViewLayoutGeometryTests
{
    [Theory]
    [InlineData(150.0, 200.0, 0.150, 0.200)]
    [InlineData(0.0, 0.0, 0.0, 0.0)]
    [InlineData(420.0, 297.0, 0.420, 0.297)]
    public void MmToMeters_ConvertsAccurately(double xMm, double yMm, double expectedX, double expectedY)
    {
        var (xM, yM) = ViewLayoutGeometry.MmToMeters(xMm, yMm);
        Assert.Equal(expectedX, xM, 6);
        Assert.Equal(expectedY, yM, 6);
    }

    [Theory]
    [InlineData(0.150, 0.200, 150.0, 200.0)]
    [InlineData(0.0, 0.0, 0.0, 0.0)]
    [InlineData(0.420, 0.297, 420.0, 297.0)]
    public void MetersToMm_ConvertsAccurately(double xM, double yM, double expectedX, double expectedY)
    {
        var (xMm, yMm) = ViewLayoutGeometry.MetersToMm(xM, yM);
        Assert.Equal(expectedX, xMm, 6);
        Assert.Equal(expectedY, yMm, 6);
    }

    [Theory]
    [InlineData("1:1", 1.0)]
    [InlineData("1:2", 0.5)]
    [InlineData("2:1", 2.0)]
    [InlineData("5:1", 5.0)]
    [InlineData("1:10", 0.1)]
    public void ParseScaleRatio_ParsesValidIsoScales(string scaleStr, double expectedRatio)
    {
        var ratio = ViewLayoutGeometry.ParseScaleRatio(scaleStr);
        Assert.Equal(expectedRatio, ratio, 6);
    }

    [Fact]
    public void ParseScaleRatio_InvalidThrows()
    {
        Assert.Throws<ArgumentException>(() => ViewLayoutGeometry.ParseScaleRatio("invalid"));
        Assert.Throws<ArgumentException>(() => ViewLayoutGeometry.ParseScaleRatio("0:1"));
    }

    [Theory]
    [InlineData(25.0, 15.0, 400.0, 280.0, 420.0, 297.0, 10.0, true)]
    [InlineData(5.0, 15.0, 400.0, 280.0, 420.0, 297.0, 10.0, false)] // Exceeds left margin
    [InlineData(25.0, 5.0, 400.0, 280.0, 420.0, 297.0, 10.0, false)] // Exceeds bottom margin
    [InlineData(25.0, 15.0, 415.0, 280.0, 420.0, 297.0, 10.0, false)] // Exceeds right margin
    [InlineData(25.0, 15.0, 400.0, 290.0, 420.0, 297.0, 10.0, false)] // Exceeds top margin
    public void IsWithinSheet_ValidatesBoundaryContainment(
        double minX, double minY, double maxX, double maxY,
        double sheetW, double sheetH, double marginMm, bool expected)
    {
        var result = ViewLayoutGeometry.IsWithinSheet(minX, minY, maxX, maxY, sheetW, sheetH, marginMm);
        Assert.Equal(expected, result);
    }
}

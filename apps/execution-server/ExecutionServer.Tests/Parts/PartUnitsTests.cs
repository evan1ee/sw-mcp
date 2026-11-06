using System;
using ExecutionServer.Core.Parts;
using Xunit;

namespace ExecutionServer.Tests.Parts;

public sealed class PartUnitsTests
{
    [Fact]
    public void Length_MmToMetres_ConvertsAccurately()
    {
        Assert.Equal(0.0, PartUnits.MmToMetres(0.0));
        Assert.Equal(0.1, PartUnits.MmToMetres(100.0), 9);
        Assert.Equal(0.06, PartUnits.MmToMetres(60.0), 9);
        Assert.Equal(0.01, PartUnits.MmToMetres(10.0), 9);
        Assert.Equal(0.004, PartUnits.MmToMetres(4.0), 9);
        Assert.Equal(-0.05, PartUnits.MmToMetres(-50.0), 9);
    }

    [Fact]
    public void Length_MetresToMm_ConvertsAccurately()
    {
        Assert.Equal(0.0, PartUnits.MetresToMm(0.0));
        Assert.Equal(100.0, PartUnits.MetresToMm(0.1), 6);
        Assert.Equal(60.0, PartUnits.MetresToMm(0.06), 6);
        Assert.Equal(10.0, PartUnits.MetresToMm(0.01), 6);
        Assert.Equal(-50.0, PartUnits.MetresToMm(-0.05), 6);
    }

    [Fact]
    public void Area_Mm2ToM2_ConvertsAccurately()
    {
        // 1 m2 = 1,000,000 mm2
        Assert.Equal(0.0, PartUnits.Mm2ToM2(0.0));
        Assert.Equal(1.0, PartUnits.Mm2ToM2(1_000_000.0), 9);
        Assert.Equal(0.015803185789489239, PartUnits.Mm2ToM2(15803.185789489239), 12);
    }

    [Fact]
    public void Area_M2ToMm2_ConvertsAccurately()
    {
        Assert.Equal(0.0, PartUnits.M2ToMm2(0.0));
        Assert.Equal(1_000_000.0, PartUnits.M2ToMm2(1.0), 6);
        Assert.Equal(15803.185789489239, PartUnits.M2ToMm2(0.015803185789489239), 6);
    }

    [Fact]
    public void Volume_Mm3ToM3_ConvertsAccurately()
    {
        // 1 m3 = 1,000,000,000 mm3
        Assert.Equal(0.0, PartUnits.Mm3ToM3(0.0));
        Assert.Equal(1.0, PartUnits.Mm3ToM3(1_000_000_000.0), 12);
        // Plate volume: 57989.38070170252 mm3 = 5.798938070170252e-05 m3
        Assert.Equal(5.798938070170252e-05, PartUnits.Mm3ToM3(57989.38070170252), 15);
    }

    [Fact]
    public void Volume_M3ToMm3_ConvertsAccurately()
    {
        Assert.Equal(0.0, PartUnits.M3ToMm3(0.0));
        Assert.Equal(1_000_000_000.0, PartUnits.M3ToMm3(1.0), 3);
        Assert.Equal(57989.38070170252, PartUnits.M3ToMm3(5.798938070170252e-05), 6);
    }

    [Fact]
    public void Angle_DegreesToRadians_ConvertsAccurately()
    {
        Assert.Equal(0.0, PartUnits.DegreesToRadians(0.0));
        Assert.Equal(Math.PI / 2.0, PartUnits.DegreesToRadians(90.0), 9);
        Assert.Equal(Math.PI, PartUnits.DegreesToRadians(180.0), 9);
        Assert.Equal(2.0 * Math.PI, PartUnits.DegreesToRadians(360.0), 9);
    }

    [Fact]
    public void Angle_RadiansToDegrees_ConvertsAccurately()
    {
        Assert.Equal(0.0, PartUnits.RadiansToDegrees(0.0));
        Assert.Equal(90.0, PartUnits.RadiansToDegrees(Math.PI / 2.0), 9);
        Assert.Equal(180.0, PartUnits.RadiansToDegrees(Math.PI), 9);
        Assert.Equal(360.0, PartUnits.RadiansToDegrees(2.0 * Math.PI), 9);
    }

    [Fact]
    public void Quantization_RoundToQuantum()
    {
        // 3.4.3: length quantum is 1e-6 mm
        Assert.Equal(1.000000, PartUnits.QuantizeLength(1.0000004), 9);
        Assert.Equal(1.000001, PartUnits.QuantizeLength(1.0000006), 9);
        Assert.Equal(-1.000001, PartUnits.QuantizeLength(-1.0000006), 9);

        // Angle quantum is 1e-6 degrees
        Assert.Equal(45.000000, PartUnits.QuantizeAngle(45.0000004), 9);
        Assert.Equal(45.000001, PartUnits.QuantizeAngle(45.0000006), 9);
    }

    [Fact]
    public void Equality_WithinTolerance()
    {
        Assert.True(PartUnits.NearlyEqual(10.0, 10.00000005, 1e-6));
        Assert.False(PartUnits.NearlyEqual(10.0, 10.001, 1e-6));

        Assert.True(PartUnits.LengthEquals(50.0, 50.0000005));
        Assert.False(PartUnits.LengthEquals(50.0, 50.00001));

        Assert.True(PartUnits.AngleEquals(90.0, 90.0000005));
        Assert.False(PartUnits.AngleEquals(90.0, 90.00001));
    }
}

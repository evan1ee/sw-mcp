using System.Collections.Generic;
using ExecutionServer.Core.Parts;
using Xunit;

namespace ExecutionServer.Tests.Parts;

public sealed class FaceSignatureTests
{
    // A 40 x 30 x 10 mm block on the front plane: caps at z = 0 and z = 0.01 m, in metres.
    private static List<PlanarFace> Block() => new List<PlanarFace>
    {
        new PlanarFace(0, new[] { 0.0, 0.0, -1.0 }, new[] { 0.0, 0.0, 0.0 }),
        new PlanarFace(1, new[] { 0.0, 0.0, 1.0 }, new[] { 0.0, 0.0, 0.01 }),
        new PlanarFace(2, new[] { 0.0, 1.0, 0.0 }, new[] { 0.0, 0.015, 0.0 }),
        new PlanarFace(3, new[] { 0.0, -1.0, 0.0 }, new[] { 0.0, -0.015, 0.0 }),
        new PlanarFace(4, new[] { 1.0, 0.0, 0.0 }, new[] { 0.02, 0.0, 0.0 }),
        new PlanarFace(5, new[] { -1.0, 0.0, 0.0 }, new[] { -0.02, 0.0, 0.0 }),
    };

    [Fact]
    public void Match_FindsTheEndFaceByNormalAndOffset()
    {
        var hits = FaceSignature.Match(Block(), new[] { 0.0, 0.0, 1.0 }, 10.0);
        Assert.Equal(new[] { 1 }, hits);
    }

    [Fact]
    public void Match_FindsTheStartFace()
    {
        var hits = FaceSignature.Match(Block(), new[] { 0.0, 0.0, -1.0 }, 0.0);
        Assert.Equal(new[] { 0 }, hits);
    }

    [Fact]
    public void Match_ReturnsNothingWhenTheOffsetIsWrong()
    {
        Assert.Empty(FaceSignature.Match(Block(), new[] { 0.0, 0.0, 1.0 }, 12.0));
    }

    [Fact]
    public void Match_ReturnsNothingWhenTheNormalPointsInward()
    {
        Assert.Empty(FaceSignature.Match(Block(), new[] { 0.0, 0.0, -1.0 }, 10.0));
    }

    [Fact]
    public void Match_ReturnsEveryFaceThatFits()
    {
        var twice = Block();
        twice.Add(new PlanarFace(6, new[] { 0.0, 0.0, 1.0 }, new[] { 0.0, 0.0, 0.01 }));
        Assert.Equal(new[] { 1, 6 }, FaceSignature.Match(twice, new[] { 0.0, 0.0, 1.0 }, 10.0));
    }

    [Fact]
    public void Match_NormalisesTheNormalsItCompares()
    {
        var scaled = new List<PlanarFace> { new PlanarFace(3, new[] { 0.0, 0.0, 2.0 }, new[] { 0.0, 0.0, 0.01 }) };
        Assert.Equal(new[] { 3 }, FaceSignature.Match(scaled, new[] { 0.0, 0.0, 1.0 }, 10.0));
    }

    [Fact]
    public void FrameMatches_AcceptsTheExpectedAxes()
    {
        var x = new[] { 1.0, 0.0, 0.0 };
        var y = new[] { 0.0, 1.0, 0.0 };
        var z = new[] { 0.0, 0.0, 1.0 };
        Assert.True(FaceSignature.FrameMatches(x, y, z, x, y, z));
    }

    [Fact]
    public void FrameMatches_RejectsAMirroredX()
    {
        var x = new[] { 1.0, 0.0, 0.0 };
        var mirrored = new[] { -1.0, 0.0, 0.0 };
        var y = new[] { 0.0, 1.0, 0.0 };
        var z = new[] { 0.0, 0.0, 1.0 };
        Assert.False(FaceSignature.FrameMatches(x, y, z, mirrored, y, z));
    }
}

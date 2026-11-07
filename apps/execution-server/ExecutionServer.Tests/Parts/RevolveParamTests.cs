using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json;
using Xunit;

namespace ExecutionServer.Tests.Parts;

public sealed class RevolveParamTests
{
    [Fact]
    public void FeatureCreateParams_Deserializes_Revolve_Defaults()
    {
        var json = """
        {
            "node_id": "shaft_body",
            "type": "revolve",
            "profile": "sketch_shaft"
        }
        """;

        var p = JsonConvert.DeserializeObject<FeatureCreateParams>(json);
        Assert.NotNull(p);
        Assert.Equal("shaft_body", p.NodeId);
        Assert.Equal(FeatureCreateParamsType.Revolve, p.Type);
        Assert.Equal("sketch_shaft", p.Profile);
        Assert.Null(p.Angle);
        Assert.Null(p.Axis);
        Assert.Null(p.MidPlane);
        Assert.Null(p.Reverse);
        Assert.Null(p.Merge);
    }

    [Fact]
    public void FeatureCreateParams_Deserializes_Revolve_Full()
    {
        var json = """
        {
            "node_id": "shaft_body",
            "type": "revolve",
            "profile": "sketch_shaft",
            "axis": "sketch_shaft.cl",
            "angle": 180.0,
            "mid_plane": true,
            "reverse": true,
            "merge": true
        }
        """;

        var p = JsonConvert.DeserializeObject<FeatureCreateParams>(json);
        Assert.NotNull(p);
        Assert.Equal("shaft_body", p.NodeId);
        Assert.Equal(FeatureCreateParamsType.Revolve, p.Type);
        Assert.Equal("sketch_shaft", p.Profile);
        Assert.Equal("sketch_shaft.cl", p.Axis);
        Assert.Equal(180.0, p.Angle);
        Assert.True(p.MidPlane ?? false);
        Assert.True(p.Reverse ?? false);
        Assert.True(p.Merge ?? false);
    }

    [Fact]
    public void FeatureCreateParams_Deserializes_CutRevolve()
    {
        var json = """
        {
            "node_id": "cut_groove",
            "type": "cut_revolve",
            "profile": "sketch_groove",
            "axis": "sketch_groove.cl",
            "angle": 360.0
        }
        """;

        var p = JsonConvert.DeserializeObject<FeatureCreateParams>(json);
        Assert.NotNull(p);
        Assert.Equal("cut_groove", p.NodeId);
        Assert.Equal(FeatureCreateParamsType.CutRevolve, p.Type);
        Assert.Equal("sketch_groove", p.Profile);
        Assert.Equal("sketch_groove.cl", p.Axis);
        Assert.Equal(360.0, p.Angle);
    }

    [Fact]
    public void SketchCreateEntity_Deserializes_Construction_Line()
    {
        var json = """
        {
            "type": "line",
            "start": [0.0, 0.0],
            "end": [0.0, 50.0],
            "construction": true
        }
        """;

        var entity = JsonConvert.DeserializeObject<SketchCreateEntity>(json);
        Assert.NotNull(entity);
        Assert.Equal(SketchCreateEntityType.Line, entity.Type);
        Assert.NotNull(entity.Start);
        Assert.Equal(new[] { 0.0, 0.0 }, entity.Start);
        Assert.NotNull(entity.End);
        Assert.Equal(new[] { 0.0, 50.0 }, entity.End);
        Assert.True(entity.Construction ?? false);
    }
}

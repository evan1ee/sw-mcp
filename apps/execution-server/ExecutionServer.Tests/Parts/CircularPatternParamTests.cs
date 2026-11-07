using System.Collections.Generic;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json;
using Xunit;

namespace ExecutionServer.Tests.Parts;

public sealed class CircularPatternParamTests
{
    [Fact]
    public void FeatureCreateParams_Deserializes_CircularPattern_EqualSpacing()
    {
        var json = """
        {
            "node_id": "pattern_holes",
            "type": "circular_pattern",
            "seeds": ["cut_hole"],
            "axis": "plane:front",
            "count": 6,
            "spacing": 360.0,
            "equal_spacing": true,
            "reverse": false
        }
        """;

        var p = JsonConvert.DeserializeObject<FeatureCreateParams>(json);
        Assert.NotNull(p);
        Assert.Equal("pattern_holes", p.NodeId);
        Assert.Equal(FeatureCreateParamsType.CircularPattern, p.Type);
        Assert.NotNull(p.Seeds);
        Assert.Single(p.Seeds);
        Assert.Equal("cut_hole", p.Seeds[0]);
        Assert.Equal("plane:front", p.Axis);
        Assert.Equal(6, p.Count);
        Assert.Equal(360.0, p.Spacing);
        Assert.True(p.EqualSpacing ?? false);
        Assert.False(p.Reverse ?? false);
    }

    [Fact]
    public void FeatureCreateParams_Deserializes_CircularPattern_InstanceSpacing()
    {
        var json = """
        {
            "node_id": "pattern_holes_step",
            "type": "circular_pattern",
            "seeds": ["cut_hole1", "cut_hole2"],
            "axis": "extrude_base",
            "count": 4,
            "spacing": 45.0,
            "equal_spacing": false,
            "reverse": true
        }
        """;

        var p = JsonConvert.DeserializeObject<FeatureCreateParams>(json);
        Assert.NotNull(p);
        Assert.Equal("pattern_holes_step", p.NodeId);
        Assert.Equal(FeatureCreateParamsType.CircularPattern, p.Type);
        Assert.NotNull(p.Seeds);
        Assert.Equal(2, p.Seeds.Count);
        Assert.Equal(new[] { "cut_hole1", "cut_hole2" }, p.Seeds);
        Assert.Equal("extrude_base", p.Axis);
        Assert.Equal(4, p.Count);
        Assert.Equal(45.0, p.Spacing);
        Assert.False(p.EqualSpacing ?? true);
        Assert.True(p.Reverse ?? false);
    }
}

using System.Collections.Generic;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json;
using Xunit;

namespace ExecutionServer.Tests.Parts;

public sealed class LinearPatternParamTests
{
    [Fact]
    public void FeatureCreateParams_Deserializes_LinearPattern_1D()
    {
        var json = """
        {
            "node_id": "pattern_holes",
            "type": "linear_pattern",
            "seeds": ["cut_hole"],
            "direction_1": {
                "direction": "plane:right",
                "spacing": 20.0,
                "count": 4,
                "reverse": false
            }
        }
        """;

        var p = JsonConvert.DeserializeObject<FeatureCreateParams>(json);
        Assert.NotNull(p);
        Assert.Equal("pattern_holes", p.NodeId);
        Assert.Equal(FeatureCreateParamsType.LinearPattern, p.Type);
        Assert.NotNull(p.Seeds);
        Assert.Single(p.Seeds);
        Assert.Equal("cut_hole", p.Seeds[0]);
        Assert.NotNull(p.Direction1);
        Assert.Equal("plane:right", p.Direction1.Direction);
        Assert.Equal(20.0, p.Direction1.Spacing);
        Assert.Equal(4, p.Direction1.Count);
        Assert.False(p.Direction1.Reverse ?? false);
        Assert.Null(p.Direction2);
    }

    [Fact]
    public void FeatureCreateParams_Deserializes_LinearPattern_2D()
    {
        var json = """
        {
            "node_id": "pattern_grid",
            "type": "linear_pattern",
            "seeds": ["cut_hole", "cut_slot"],
            "direction_1": {
                "direction": "plane:right",
                "spacing": 20.0,
                "count": 4
            },
            "direction_2": {
                "direction": "plane:top",
                "spacing": 15.0,
                "count": 2,
                "reverse": true
            }
        }
        """;

        var p = JsonConvert.DeserializeObject<FeatureCreateParams>(json);
        Assert.NotNull(p);
        Assert.Equal("pattern_grid", p.NodeId);
        Assert.Equal(FeatureCreateParamsType.LinearPattern, p.Type);
        Assert.NotNull(p.Seeds);
        Assert.Equal(2, p.Seeds.Count);
        Assert.Equal(new[] { "cut_hole", "cut_slot" }, p.Seeds);
        Assert.NotNull(p.Direction1);
        Assert.Equal("plane:right", p.Direction1.Direction);
        Assert.NotNull(p.Direction2);
        Assert.Equal("plane:top", p.Direction2.Direction);
        Assert.Equal(15.0, p.Direction2.Spacing);
        Assert.Equal(2, p.Direction2.Count);
        Assert.True(p.Direction2.Reverse ?? false);
    }
}

using System.Collections.Generic;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json;
using Xunit;

namespace ExecutionServer.Tests.Parts;

public sealed class MirrorParamTests
{
    [Fact]
    public void FeatureCreateParams_Deserializes_Mirror_DefaultMerge()
    {
        var json = """
        {
            "node_id": "mirror_hole",
            "type": "mirror",
            "seeds": ["cut_hole"],
            "plane": "plane:right"
        }
        """;

        var p = JsonConvert.DeserializeObject<FeatureCreateParams>(json);
        Assert.NotNull(p);
        Assert.Equal("mirror_hole", p.NodeId);
        Assert.Equal(FeatureCreateParamsType.Mirror, p.Type);
        Assert.NotNull(p.Seeds);
        Assert.Single(p.Seeds);
        Assert.Equal("cut_hole", p.Seeds[0]);
        Assert.Equal("plane:right", p.Plane);
        Assert.Null(p.Merge);
    }

    [Fact]
    public void FeatureCreateParams_Deserializes_Mirror_ExplicitMerge()
    {
        var json = """
        {
            "node_id": "mirror_features",
            "type": "mirror",
            "seeds": ["cut_hole1", "cut_hole2"],
            "plane": "plane:front",
            "merge": true
        }
        """;

        var p = JsonConvert.DeserializeObject<FeatureCreateParams>(json);
        Assert.NotNull(p);
        Assert.Equal("mirror_features", p.NodeId);
        Assert.Equal(FeatureCreateParamsType.Mirror, p.Type);
        Assert.NotNull(p.Seeds);
        Assert.Equal(2, p.Seeds.Count);
        Assert.Equal(new[] { "cut_hole1", "cut_hole2" }, p.Seeds);
        Assert.Equal("plane:front", p.Plane);
        Assert.True(p.Merge ?? false);
    }
}

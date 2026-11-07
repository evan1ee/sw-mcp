using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json;
using Xunit;

namespace ExecutionServer.Tests.Parts;

public sealed class SketchEntityTests
{
    [Fact]
    public void StraightSlot_Deserializes_Correctly()
    {
        var json = """
        {
            "type": "straight_slot",
            "start_point": [-20.0, 0.0],
            "end_point": [20.0, 0.0],
            "width": 15.0
        }
        """;

        var entity = JsonConvert.DeserializeObject<SketchCreateEntity>(json);
        Assert.NotNull(entity);
        Assert.Equal(SketchCreateEntityType.StraightSlot, entity.Type);
        Assert.NotNull(entity.StartPoint);
        Assert.Equal(new[] { -20.0, 0.0 }, entity.StartPoint);
        Assert.NotNull(entity.EndPoint);
        Assert.Equal(new[] { 20.0, 0.0 }, entity.EndPoint);
        Assert.Equal(15.0, entity.Width);
    }
}

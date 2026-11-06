using System.Collections.Generic;
using ExecutionServer.Core.Drawings;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests.Drawings;

public class ViewCreationAdapterContractTests
{
    [Fact]
    public void ViewCreateParams_DeserializesCorrectly()
    {
        var json = new JObject
        {
            ["model_path"] = "C:/parts/bracket.sldprt",
            ["sheet"] = "Sheet1",
            ["view_type"] = "base",
            ["orientation"] = "front",
            ["position"] = new JArray { 150.0, 100.0 },
            ["scale"] = 1.0,
            ["configuration"] = "Default",
            ["display_mode"] = "hlr",
            ["tangent_edges"] = "removed",
            ["view_name"] = "Front"
        };

        var p = json.ToObject<ViewCreateParams>();
        Assert.NotNull(p);
        Assert.Equal("C:/parts/bracket.sldprt", p.ModelPath);
        Assert.Equal("Sheet1", p.Sheet);
        Assert.Equal(ViewCreateParamsViewType.Base, p.ViewType);
        Assert.Equal(ViewCreateParamsOrientation.Front, p.Orientation);
        Assert.Equal(2, p.Position.Count);
        Assert.Equal(150.0, p.Position[0]);
        Assert.Equal(100.0, p.Position[1]);
        Assert.Equal(1.0, p.Scale);
        Assert.Equal("Default", p.Configuration);
        Assert.Equal(ViewCreateParamsDisplayMode.Hlr, p.DisplayMode);
        Assert.Equal(ViewCreateParamsTangentEdges.Removed, p.TangentEdges);
        Assert.Equal("Front", p.ViewName);
    }

    [Fact]
    public void ViewCreateResult_SerializesCorrectly()
    {
        var res = new ViewCreateResult
        {
            ViewId = "v_front",
            NativeId = "Drawing View1",
            PositionMm = new List<double> { 150.0, 100.0 },
            Scale = 1.0,
            OutlineMm = new ViewOutline
            {
                Min = new List<double> { 100.0, 75.0 },
                Max = new List<double> { 200.0, 125.0 }
            },
            WidthMm = 100.0,
            HeightMm = 50.0
        };

        var jsonStr = JsonConvert.SerializeObject(res);
        var jObj = JObject.Parse(jsonStr);

        Assert.Equal("v_front", jObj["view_id"]?.Value<string>());
        Assert.Equal("Drawing View1", jObj["native_id"]?.Value<string>());
        Assert.Equal(1.0, jObj["scale"]?.Value<double>());
        Assert.Equal(100.0, jObj["width_mm"]?.Value<double>());
        Assert.Equal(50.0, jObj["height_mm"]?.Value<double>());

        var outline = jObj["outline_mm"] as JObject;
        Assert.NotNull(outline);
        var min = outline["min"] as JArray;
        var max = outline["max"] as JArray;
        Assert.NotNull(min);
        Assert.NotNull(max);
        Assert.Equal(100.0, min[0].Value<double>());
        Assert.Equal(75.0, min[1].Value<double>());
        Assert.Equal(200.0, max[0].Value<double>());
        Assert.Equal(125.0, max[1].Value<double>());
    }

    [Fact]
    public void ViewUpdateParams_DeserializesCorrectly()
    {
        var json = new JObject
        {
            ["view_name"] = "Drawing View1",
            ["position"] = new JArray { 160.0, 110.0 },
            ["scale"] = 0.5,
            ["display_mode"] = "shaded"
        };

        var p = json.ToObject<ViewUpdateParams>();
        Assert.NotNull(p);
        Assert.Equal("Drawing View1", p.ViewName);
        Assert.NotNull(p.Position);
        Assert.Equal(160.0, p.Position[0]);
        Assert.Equal(110.0, p.Position[1]);
        Assert.Equal(0.5, p.Scale);
        Assert.Equal(ViewUpdateParamsDisplayMode.Shaded, p.DisplayMode);
    }

    [Fact]
    public void ViewUpdateResult_SerializesCorrectly()
    {
        var res = new ViewUpdateResult
        {
            NativeId = "Drawing View1",
            PositionMm = new List<double> { 160.0, 110.0 },
            Scale = 0.5,
            OutlineMm = new ViewOutline
            {
                Min = new List<double> { 110.0, 85.0 },
                Max = new List<double> { 210.0, 135.0 }
            }
        };

        var jsonStr = JsonConvert.SerializeObject(res);
        var jObj = JObject.Parse(jsonStr);

        Assert.Equal("Drawing View1", jObj["native_id"]?.Value<string>());
        Assert.Equal(0.5, jObj["scale"]?.Value<double>());
        var pos = jObj["position_mm"] as JArray;
        Assert.NotNull(pos);
        Assert.Equal(160.0, pos[0].Value<double>());
        Assert.Equal(110.0, pos[1].Value<double>());
    }
}

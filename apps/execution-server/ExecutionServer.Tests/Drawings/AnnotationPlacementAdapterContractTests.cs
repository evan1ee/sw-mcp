using System.Collections.Generic;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests.Drawings;

public class AnnotationPlacementAdapterContractTests
{
    [Fact]
    public void ModelItemsInsertParams_Roundtrips()
    {
        var json = new JObject
        {
            ["view"] = "Drawing View1",
            ["source"] = "entire_model",
            ["marked_for_drawing"] = true,
            ["not_marked_for_drawing"] = false,
            ["hole_callouts"] = true,
            ["duplicate_dims"] = false
        };

        var p = json.ToObject<ModelItemsInsertParams>();
        Assert.NotNull(p);
        Assert.Equal("Drawing View1", p.View);
        Assert.Equal(ModelItemsInsertParamsSource.EntireModel, p.Source);
        Assert.True(p.MarkedForDrawing);
        Assert.False(p.NotMarkedForDrawing);
        Assert.True(p.HoleCallouts);
        Assert.False(p.DuplicateDims);

        var res = new ModelItemsInsertResult
        {
            Count = 5,
            Annotations = new List<string> { "D1@Sketch1", "D2@Sketch1" }
        };
        var resJson = JObject.FromObject(res);
        Assert.Equal(5, (int)resJson["count"]!);
        Assert.Equal(2, ((JArray)resJson["annotations"]!).Count);
    }

    [Fact]
    public void DimensionsAutoArrangeParams_Roundtrips()
    {
        var json = new JObject
        {
            ["view"] = "Drawing View1",
            ["spacing_mm"] = 12.5
        };

        var p = json.ToObject<DimensionsAutoArrangeParams>();
        Assert.NotNull(p);
        Assert.Equal("Drawing View1", p.View);
        Assert.Equal(12.5, p.SpacingMm);

        var res = new DimensionsAutoArrangeResult
        {
            Success = true,
            View = "Drawing View1"
        };
        var resJson = JObject.FromObject(res);
        Assert.True((bool)resJson["success"]!);
        Assert.Equal("Drawing View1", (string)resJson["view"]!);
    }

    [Fact]
    public void CenterMarkAddParams_Roundtrips()
    {
        var json = new JObject
        {
            ["view"] = "Drawing View1",
            ["hole_centers"] = true,
            ["slot_centers"] = true,
            ["use_doc_defaults"] = true,
            ["size_mm"] = 5.0,
            ["gap_mm"] = 2.5
        };

        var p = json.ToObject<CenterMarkAddParams>();
        Assert.NotNull(p);
        Assert.Equal("Drawing View1", p.View);
        Assert.True(p.HoleCenters);
        Assert.True(p.SlotCenters);
        Assert.True(p.UseDocDefaults);
        Assert.Equal(5.0, p.SizeMm);
        Assert.Equal(2.5, p.GapMm);

        var res = new CenterMarkAddResult
        {
            Count = 4,
            View = "Drawing View1"
        };
        var resJson = JObject.FromObject(res);
        Assert.Equal(4, (int)resJson["count"]!);
        Assert.Equal("Drawing View1", (string)resJson["view"]!);
    }

    [Fact]
    public void DimensionHideParams_Roundtrips()
    {
        var json = new JObject
        {
            ["annotation"] = "D1@Sketch1",
            ["reason"] = "duplicate"
        };

        var p = json.ToObject<DimensionHideParams>();
        Assert.NotNull(p);
        Assert.Equal("D1@Sketch1", p.Annotation);
        Assert.Equal("duplicate", p.Reason);

        var res = new DimensionHideResult
        {
            Annotation = "D1@Sketch1",
            Hidden = true
        };
        var resJson = JObject.FromObject(res);
        Assert.Equal("D1@Sketch1", (string)resJson["annotation"]!);
        Assert.True((bool)resJson["hidden"]!);
    }

    [Fact]
    public void DimensionShowParams_Roundtrips()
    {
        var json = new JObject
        {
            ["annotation"] = "D1@Sketch1"
        };

        var p = json.ToObject<DimensionShowParams>();
        Assert.NotNull(p);
        Assert.Equal("D1@Sketch1", p.Annotation);

        var res = new DimensionShowResult
        {
            Annotation = "D1@Sketch1",
            Shown = true
        };
        var resJson = JObject.FromObject(res);
        Assert.Equal("D1@Sketch1", (string)resJson["annotation"]!);
        Assert.True((bool)resJson["shown"]!);
    }

    [Fact]
    public void DimensionMoveParams_Roundtrips()
    {
        var json = new JObject
        {
            ["annotation"] = "D1@Sketch1",
            ["position"] = new JArray { 150.0, 120.0 },
            ["center_text"] = true
        };

        var p = json.ToObject<DimensionMoveParams>();
        Assert.NotNull(p);
        Assert.Equal("D1@Sketch1", p.Annotation);
        Assert.Equal(2, p.Position.Count);
        Assert.Equal(150.0, p.Position[0]);
        Assert.Equal(120.0, p.Position[1]);
        Assert.True(p.CenterText);

        var res = new DimensionMoveResult
        {
            Annotation = "D1@Sketch1",
            Position = new List<double> { 150.0, 120.0 }
        };
        var resJson = JObject.FromObject(res);
        Assert.Equal("D1@Sketch1", (string)resJson["annotation"]!);
        Assert.Equal(150.0, (double)((JArray)resJson["position"]!)[0]);
        Assert.Equal(120.0, (double)((JArray)resJson["position"]!)[1]);
    }
}

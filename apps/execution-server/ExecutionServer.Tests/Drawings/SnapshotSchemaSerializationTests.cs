using System;
using System.Collections.Generic;
using System.IO;
using ExecutionServer.Adapters.Drawings;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests.Drawings;

public sealed class SnapshotSchemaSerializationTests
{
    [Fact]
    public void FilterSheets_ReturnsAllSheetsWhenNoFilterGiven()
    {
        var available = new List<string> { "Sheet1", "Sheet2" };
        var filtered = DrawingSnapshotAdapter.FilterSheets(available, null);
        Assert.Equal(2, filtered.Count);
        Assert.Equal("Sheet1", filtered[0]);
        Assert.Equal("Sheet2", filtered[1]);
    }

    [Fact]
    public void FilterSheets_ReturnsFilteredSheetsWhenValid()
    {
        var available = new List<string> { "Sheet1", "Sheet2", "Sheet3" };
        var filtered = DrawingSnapshotAdapter.FilterSheets(available, new List<string> { "Sheet2" });
        Assert.Single(filtered);
        Assert.Equal("Sheet2", filtered[0]);
    }

    [Fact]
    public void FilterSheets_ThrowsIrReferenceUnresolvedWhenSheetDoesNotExist()
    {
        var available = new List<string> { "Sheet1", "Sheet2" };
        var ex = Assert.Throws<IpcException>(() =>
            DrawingSnapshotAdapter.FilterSheets(available, new List<string> { "Nope" }));

        Assert.Equal(ErrorCodes.IR_REFERENCE_UNRESOLVED, ex.Code);
        Assert.Contains("Nope", ex.Message);
        Assert.NotNull(ex.Details);
        var missingSheets = ex.Details["sheets"] as JArray;
        Assert.NotNull(missingSheets);
        Assert.Contains("Nope", missingSheets.Values<string>());
    }

    [Fact]
    public void SnapshotJson_CompliesWithDrawingGeometrySnapshotSchema()
    {
        var snapshot = DrawingSnapshotAdapter.BuildSnapshotJson(
            document: "C:/Work/bracket.slddrw",
            revision: 3,
            version: "2025",
            servicePack: "SP3.0",
            capturedAt: DateTime.UtcNow,
            sheets: new Dictionary<string, JObject>
            {
                ["s_0123456789"] = new JObject
                {
                    ["index"] = 0,
                    ["native_id"] = "Sheet1",
                    ["size_mm"] = new JArray { 297.0, 210.0 },
                    ["border"] = new JObject
                    {
                        ["min"] = new JArray { 10.0, 5.0 },
                        ["max"] = new JArray { 292.0, 205.0 }
                    },
                    ["title_block"] = new JArray
                    {
                        new JObject
                        {
                            ["min"] = new JArray { 212.0, 5.0 },
                            ["max"] = new JArray { 292.0, 45.0 }
                        }
                    },
                    ["views"] = new JObject
                    {
                        ["v_0123456789"] = new JObject
                        {
                            ["native_id"] = "Drawing View1",
                            ["scale"] = 1.0,
                            ["outline"] = new JObject
                            {
                                ["min"] = new JArray { 50.0, 50.0 },
                                ["max"] = new JArray { 150.0, 150.0 }
                            },
                            ["edges"] = new JArray()
                        }
                    },
                    ["annotations"] = new JObject
                    {
                        ["ann_0123456789"] = new JObject
                        {
                            ["kind"] = "dimension",
                            ["native_id"] = "D1@Drawing View1",
                            ["view"] = "v_0123456789",
                            ["parenthesized"] = false,
                            ["parameters"] = new JArray { "D1@Sketch1" }
                        }
                    }
                }
            });

        Assert.Equal("0.1", snapshot["schema_version"]?.Value<string>());
        Assert.Equal("C:/Work/bracket.slddrw", snapshot["drawing"]?["document"]?.Value<string>());
        Assert.Equal(3, snapshot["drawing"]?["revision"]?.Value<int>());
        Assert.Equal("2025", snapshot["solidworks"]?["version"]?.Value<string>());
        Assert.Equal("SP3.0", snapshot["solidworks"]?["service_pack"]?.Value<string>());
        Assert.NotNull(snapshot["captured_at"]);

        var sheets = snapshot["sheets"] as JObject;
        Assert.NotNull(sheets);
        var sheet = sheets["s_0123456789"] as JObject;
        Assert.NotNull(sheet);
        Assert.Equal(0, sheet["index"]?.Value<int>());
        Assert.Equal("Sheet1", sheet["native_id"]?.Value<string>());

        var size = sheet["size_mm"] as JArray;
        Assert.NotNull(size);
        Assert.Equal(2, size.Count);

        var views = sheet["views"] as JObject;
        Assert.NotNull(views);
        var view = views["v_0123456789"] as JObject;
        Assert.NotNull(view);
        Assert.Equal("Drawing View1", view["native_id"]?.Value<string>());
        Assert.Equal(1.0, view["scale"]?.Value<double>());

        var annotations = sheet["annotations"] as JObject;
        Assert.NotNull(annotations);
        var ann = annotations["ann_0123456789"] as JObject;
        Assert.NotNull(ann);
        Assert.Equal("dimension", ann["kind"]?.Value<string>());
        Assert.Equal("v_0123456789", ann["view"]?.Value<string>());
        Assert.False(ann["parenthesized"]?.Value<bool>());
        var parameters = ann["parameters"] as JArray;
        Assert.NotNull(parameters);
        Assert.Contains("D1@Sketch1", parameters.Values<string>());
    }
}

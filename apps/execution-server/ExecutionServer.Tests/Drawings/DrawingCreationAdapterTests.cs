using System;
using ExecutionServer.Core.Drawings;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests.Drawings;

public class DrawingCreationAdapterTests
{
    [Fact]
    public void DrawingCreateParams_DeserializesCorrectly()
    {
        var json = new JObject
        {
            ["destination_path"] = "C:/temp/drawing.slddrw",
            ["sheet_format_path"] = "C:/temp/format.slddrt",
            ["paper_size"] = "A3",
            ["width_mm"] = 420.0,
            ["height_mm"] = 297.0
        };

        var p = json.ToObject<DrawingCreateParams>();
        Assert.NotNull(p);
        Assert.Equal("C:/temp/drawing.slddrw", p.DestinationPath);
        Assert.Equal("C:/temp/format.slddrt", p.SheetFormatPath);
        Assert.Equal("A3", p.PaperSize);
        Assert.Equal(420.0, p.WidthMm);
        Assert.Equal(297.0, p.HeightMm);
    }

    [Fact]
    public void DocumentSaveParams_DeserializesCorrectly()
    {
        var json = new JObject
        {
            ["path"] = "C:/temp/drawing.slddrw",
            ["target_path"] = "C:/temp/saved.slddrw"
        };

        var p = json.ToObject<DocumentSaveParams>();
        Assert.NotNull(p);
        Assert.Equal("C:/temp/drawing.slddrw", p.Path);
        Assert.Equal("C:/temp/saved.slddrw", p.TargetPath);
    }
}

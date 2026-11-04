using System;
using System.Collections.Generic;
using ExecutionServer.Core.Drawings;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests.Drawings;

public class SheetFormatGeneratorTests
{
    [Theory]
    [InlineData("A4", "portrait", 210.0, 297.0)]
    [InlineData("A4", "landscape", 297.0, 210.0)]
    [InlineData("A3", "landscape", 420.0, 297.0)]
    [InlineData("A2", "landscape", 594.0, 420.0)]
    [InlineData("A1", "landscape", 841.0, 594.0)]
    [InlineData("A0", "landscape", 1189.0, 841.0)]
    public void GetPaperDimensions_ReturnsCorrectMillimeters(string size, string orientation, double expectedW, double expectedH)
    {
        var (width, height) = SheetFormatGeometry.GetPaperDimensions(size, orientation);
        Assert.Equal(expectedW, width);
        Assert.Equal(expectedH, height);
    }

    [Fact]
    public void ComputeBorderLines_CalculatesFourClosedSegments()
    {
        // A3 paper with 20mm left margin, 10mm right, top, bottom
        var segments = SheetFormatGeometry.ComputeBorderLines(420.0, 297.0, 20.0, 10.0, 10.0, 10.0);
        Assert.Equal(4, segments.Count);

        // Bottom segment: (20, 10) -> (410, 10)
        Assert.Equal(20.0, segments[0].X1);
        Assert.Equal(10.0, segments[0].Y1);
        Assert.Equal(410.0, segments[0].X2);
        Assert.Equal(10.0, segments[0].Y2);

        // Right segment: (410, 10) -> (410, 287)
        Assert.Equal(410.0, segments[1].X1);
        Assert.Equal(10.0, segments[1].Y1);
        Assert.Equal(410.0, segments[1].X2);
        Assert.Equal(287.0, segments[1].Y2);

        // Top segment: (410, 287) -> (20, 287)
        Assert.Equal(410.0, segments[2].X1);
        Assert.Equal(287.0, segments[2].Y1);
        Assert.Equal(20.0, segments[2].X2);
        Assert.Equal(287.0, segments[2].Y2);

        // Left segment: (20, 287) -> (20, 10)
        Assert.Equal(20.0, segments[3].X1);
        Assert.Equal(287.0, segments[3].Y1);
        Assert.Equal(20.0, segments[3].X2);
        Assert.Equal(10.0, segments[3].Y2);
    }

    [Theory]
    [InlineData("part_number", "part_property:PartNo", "$PRPSHEET:\"PartNo\"")]
    [InlineData("material", "part_material", "$PRPSHEET:\"Material\"")]
    [InlineData("revision", "drawing_property:Revision", "$PRP:\"Revision\"")]
    [InlineData("scale", "sheet:scale", "$PRP:\"SW-Sheet Scale\"")]
    [InlineData("units", "sheet:units", "mm")]
    public void FormatFieldNoteText_GeneratesCorrectSolidWorksSyntax(string fieldName, string sourceCandidate, string expectedText)
    {
        var candidates = new JArray { sourceCandidate };
        var text = SheetFormatGeometry.FormatFieldNoteText(fieldName, candidates);
        Assert.Equal(expectedText, text);
    }

    [Fact]
    public void FormatFieldNoteText_ProjectionSymbol_ReturnsNull()
    {
        var candidates = new JArray { "sheet:projection" };
        var text = SheetFormatGeometry.FormatFieldNoteText("projection_symbol", candidates);
        Assert.Null(text);
    }
}

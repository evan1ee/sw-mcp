using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using ExecutionServer.Core.Drawings;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace ExecutionServer.Adapters.Drawings;

/// <summary>
/// Generates SOLIDWORKS .slddrt sheet format files from Drawing Template IR (spec 11.12, ADR-055, K7).
/// Adheres strictly to Guideline G1 (Marshal.ReleaseComObject in finally blocks).
/// </summary>
public sealed class SheetFormatGenerator
{
    private readonly ISldWorks _sw;

    public SheetFormatGenerator(ISldWorks sw)
    {
        _sw = sw ?? throw new ArgumentNullException(nameof(sw));
    }

    public SheetFormatGenerateResult Generate(SheetFormatGenerateParams p, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        if (string.IsNullOrEmpty(p.DestinationPath))
        {
            throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "destination_path must not be empty.");
        }

        var templateObj = p.Template as JObject;
        if (templateObj == null)
        {
            throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "template must be a DrawingTemplate JSON object.");
        }

        var paper = templateObj["paper"] as JObject;
        var border = templateObj["border"] as JObject;
        if (paper == null || border == null)
        {
            throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "template must contain 'paper' and 'border'.");
        }

        var paperSize = paper["size"]?.Value<string>() ?? "A3";
        var orientation = paper["orientation"]?.Value<string>() ?? "landscape";
        var (widthMm, heightMm) = SheetFormatGeometry.GetPaperDimensions(paperSize, orientation);

        var margins = border["margins"] as JObject;
        var leftMargin = margins?["left"]?.Value<double>() ?? 20.0;
        var rightMargin = margins?["right"]?.Value<double>() ?? 10.0;
        var topMargin = margins?["top"]?.Value<double>() ?? 10.0;
        var bottomMargin = margins?["bottom"]?.Value<double>() ?? 10.0;
        var lineWidth = border["line_width"]?.Value<double>() ?? 0.5;

        var destDir = Path.GetDirectoryName(p.DestinationPath);
        if (!string.IsNullOrEmpty(destDir) && !Directory.Exists(destDir))
        {
            Directory.CreateDirectory(destDir);
        }

        double widthMeters = widthMm / 1000.0;
        double heightMeters = heightMm / 1000.0;

        var templatePath = ResolveDrawingTemplatePath(_sw);
        if (string.IsNullOrEmpty(templatePath))
        {
            throw new IpcException(ErrorCodes.FILE_NOT_FOUND, "No valid SOLIDWORKS drawing template (.drwdot) found to create drawing.");
        }

        IModelDoc2? modelDoc = null;
        IDrawingDoc? drawing = null;
        string? tempDocTitle = null;

        try
        {
            ct.ThrowIfCancellationRequested();

            try
            {
                modelDoc = (IModelDoc2)_sw.NewDocument(
                    templatePath,
                    (int)swDwgPaperSizes_e.swDwgPapersUserDefined,
                    widthMeters,
                    heightMeters);
            }
            catch
            {
                modelDoc = (IModelDoc2)_sw.INewDocument2(
                    templatePath,
                    (int)swDwgPaperSizes_e.swDwgPapersUserDefined,
                    widthMeters,
                    heightMeters);
            }

            if (modelDoc == null)
            {
                throw new IpcException(ErrorCodes.BACKEND_LOST, "Failed to create temporary drawing in SOLIDWORKS for sheet format generation.");
            }

            tempDocTitle = modelDoc.GetTitle();
            drawing = (IDrawingDoc)modelDoc;

            // Enter sheet format edit mode
            drawing.EditTemplate();
            try
            {
                ct.ThrowIfCancellationRequested();

                // Clear any pre-existing entities from the base template
                modelDoc.Extension.SelectAll();
                modelDoc.EditDelete();
                modelDoc.ClearSelection2(true);

                // 1. Draw outer border lines
                var borderSegments = SheetFormatGeometry.ComputeBorderLines(
                    widthMm, heightMm, leftMargin, rightMargin, topMargin, bottomMargin, lineWidth);

                foreach (var seg in borderSegments)
                {
                    modelDoc.CreateLine2(
                        seg.X1 / 1000.0, seg.Y1 / 1000.0, 0,
                        seg.X2 / 1000.0, seg.Y2 / 1000.0, 0);
                }

                // 2. Draw title block divider lines
                if (templateObj["title_block"]?["lines"] is JObject tbLines)
                {
                    foreach (var prop in tbLines.Properties())
                    {
                        if (prop.Value is JObject lineObj &&
                            lineObj["from"] is JArray fromArr && fromArr.Count >= 2 &&
                            lineObj["to"] is JArray toArr && toArr.Count >= 2)
                        {
                            var x1 = (fromArr[0]?.Value<double>() ?? 0) / 1000.0;
                            var y1 = (fromArr[1]?.Value<double>() ?? 0) / 1000.0;
                            var x2 = (toArr[0]?.Value<double>() ?? 0) / 1000.0;
                            var y2 = (toArr[1]?.Value<double>() ?? 0) / 1000.0;

                            modelDoc.CreateLine2(x1, y1, 0, x2, y2, 0);
                        }
                    }
                }

                // 3. Draw static texts
                if (templateObj["texts"] is JObject textsObj)
                {
                    foreach (var prop in textsObj.Properties())
                    {
                        if (prop.Value is JObject textObj)
                        {
                            var text = textObj["text"]?.Value<string>() ?? string.Empty;
                            var height = (textObj["height"]?.Value<double>() ?? 3.5) / 1000.0;
                            var align = textObj["align"]?.Value<string>() ?? "left";

                            if (!string.IsNullOrEmpty(text) && textObj["box"] is JObject box)
                            {
                                var (insX, insY) = ComputeNoteInsertion(box, align);
                                InsertTextNote(modelDoc, text, insX, insY, height, align);
                            }
                        }
                    }
                }

                // 4. Draw attribute link fields
                if (templateObj["fields"] is JObject fieldsObj)
                {
                    foreach (var prop in fieldsObj.Properties())
                    {
                        var fieldName = prop.Name;
                        if (prop.Value is JObject fieldItem)
                        {
                            var sources = fieldItem["source"] as JArray;
                            var noteText = SheetFormatGeometry.FormatFieldNoteText(fieldName, sources);

                            if (string.Equals(fieldName, "projection_symbol", StringComparison.OrdinalIgnoreCase) &&
                                fieldItem["box"] is JObject projBox)
                            {
                                DrawFirstAngleProjectionSymbol(modelDoc, projBox);
                            }
                            else if (!string.IsNullOrEmpty(noteText) && fieldItem["box"] is JObject box)
                            {
                                var height = (fieldItem["height"]?.Value<double>() ?? 3.5) / 1000.0;
                                var align = fieldItem["align"]?.Value<string>() ?? "left";
                                var (insX, insY) = ComputeNoteInsertion(box, align);
                                InsertTextNote(modelDoc, noteText!, insX, insY, height, align);
                            }
                        }
                    }
                }

            }
            finally
            {
                // Always exit template edit mode back to normal sheet
                drawing.EditSheet();
            }

            // Save sheet format to destination path
            ISheet? sheet = null;
            try
            {
                sheet = (ISheet)drawing.GetCurrentSheet();
                if (sheet == null)
                {
                    throw new IpcException(ErrorCodes.BACKEND_LOST, "Failed to get current sheet for sheet format persistence.");
                }

                bool saved = sheet.SaveFormat(p.DestinationPath);
                if (!saved)
                {
                    throw new IpcException(ErrorCodes.FILE_NOT_FOUND, $"SOLIDWORKS SaveFormat failed for '{p.DestinationPath}'.");
                }
            }
            finally
            {
                if (sheet != null)
                {
                    Marshal.ReleaseComObject(sheet);
                }
            }

            return new SheetFormatGenerateResult
            {
                Path = p.DestinationPath,
                SizeMm = new System.Collections.Generic.List<double> { widthMm, heightMm }
            };
        }
        finally
        {
            if (drawing != null)
            {
                Marshal.ReleaseComObject(drawing);
                drawing = null;
            }

            if (modelDoc != null)
            {
                Marshal.ReleaseComObject(modelDoc);
                modelDoc = null;
            }

            if (!string.IsNullOrEmpty(tempDocTitle))
            {
                try
                {
                    _sw.CloseDoc(tempDocTitle);
                }
                catch
                {
                }
            }
        }
    }

    private static (double insX, double insY) ComputeNoteInsertion(JObject box, string align)
    {
        var minArr = box["min"] as JArray;
        var maxArr = box["max"] as JArray;

        var x1 = (minArr?[0]?.Value<double>() ?? 0) / 1000.0;
        var y1 = (minArr?[1]?.Value<double>() ?? 0) / 1000.0;
        var x2 = (maxArr?[0]?.Value<double>() ?? 0) / 1000.0;

        double insX;
        if (string.Equals(align, "center", StringComparison.OrdinalIgnoreCase))
        {
            insX = (x1 + x2) / 2.0;
        }
        else if (string.Equals(align, "right", StringComparison.OrdinalIgnoreCase))
        {
            insX = x2;
        }
        else
        {
            insX = x1;
        }

        return (insX, y1);
    }

    private static void InsertTextNote(IModelDoc2 modelDoc, string text, double xMeters, double yMeters, double heightMeters, string align)
    {
        INote? note = null;
        try
        {
            note = (INote?)modelDoc.InsertNote(text);
            if (note != null)
            {
                IAnnotation? ann = null;
                try
                {
                    ann = (IAnnotation?)note.GetAnnotation();
                    if (ann != null)
                    {
                        ann.SetPosition(xMeters, yMeters, 0);
                    }
                }
                finally
                {
                    if (ann != null)
                    {
                        Marshal.ReleaseComObject(ann);
                    }
                }
            }
        }
        catch
        {
        }
        finally
        {
            if (note != null)
            {
                Marshal.ReleaseComObject(note);
            }
        }
    }

    private static void DrawFirstAngleProjectionSymbol(IModelDoc2 modelDoc, JObject box)
    {
        var minArr = box["min"] as JArray;
        var maxArr = box["max"] as JArray;
        if (minArr == null || maxArr == null || minArr.Count < 2 || maxArr.Count < 2) return;

        var x1 = (minArr[0]?.Value<double>() ?? 0) / 1000.0;
        var y1 = (minArr[1]?.Value<double>() ?? 0) / 1000.0;
        var x2 = (maxArr[0]?.Value<double>() ?? 0) / 1000.0;
        var y2 = (maxArr[1]?.Value<double>() ?? 0) / 1000.0;

        var bw = x2 - x1;
        var bh = y2 - y1;
        var cx = (x1 + x2) / 2.0;
        var cy = (y1 + y2) / 2.0;

        var r = Math.Min(bw, bh) / 6.0;
        if (r <= 0) return;

        try
        {
            // Truncated cone (trapezoid at left)
            var coneLeftX = cx - (1.8 * r);
            var coneRightX = cx - (0.4 * r);
            var largeH = 1.6 * r;
            var smallH = 0.8 * r;

            // Left vertical
            modelDoc.CreateLine2(coneLeftX, cy - largeH, 0, coneLeftX, cy + largeH, 0);
            // Right vertical
            modelDoc.CreateLine2(coneRightX, cy - smallH, 0, coneRightX, cy + smallH, 0);
            // Top slanted
            modelDoc.CreateLine2(coneLeftX, cy + largeH, 0, coneRightX, cy + smallH, 0);
            // Bottom slanted
            modelDoc.CreateLine2(coneLeftX, cy - largeH, 0, coneRightX, cy - smallH, 0);

            // Concentric circles at right
            var circleCx = cx + (1.2 * r);
            modelDoc.CreateCircleByRadius2(circleCx, cy, 0, smallH);
            modelDoc.CreateCircleByRadius2(circleCx, cy, 0, largeH);

            // Centerline
            modelDoc.CreateLine2(cx - (2.2 * r), cy, 0, cx + (2.2 * r), cy, 0);
        }
        catch
        {
        }
    }

    public static string ResolveDrawingTemplatePath(ISldWorks sw, string? preferredPath = null)
    {
        if (!string.IsNullOrEmpty(preferredPath) && File.Exists(preferredPath))
        {
            return preferredPath!;
        }

        try
        {
            var userPref = sw.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplateDrawing);
            if (!string.IsNullOrEmpty(userPref) && File.Exists(userPref))
            {
                return userPref!;
            }
        }
        catch
        {
        }

        try
        {
            var docTmpl = sw.GetDocumentTemplate((int)swDocumentTypes_e.swDocDRAWING, string.Empty, 0, 0, 0);
            if (!string.IsNullOrEmpty(docTmpl) && File.Exists(docTmpl))
            {
                return docTmpl!;
            }
        }
        catch
        {
        }

        var candidates = new[]
        {
            @"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\Drawing.drwdot",
            @"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\data\templates\Drawing.drwdot",
            @"C:\ProgramData\SolidWorks\templates\Drawing.drwdot"
        };
        foreach (var candidate in candidates)
        {
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return string.Empty;
    }
}

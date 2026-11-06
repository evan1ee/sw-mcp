using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using Newtonsoft.Json.Linq;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace ExecutionServer.Adapters.Drawings;

/// <summary>
/// Extracts view geometry, scale, bounding outline, and polylines from a SOLIDWORKS drawing sheet (spec 11.5.1).
/// Adheres strictly to Guideline G1 (Marshal.ReleaseComObject in finally blocks).
/// </summary>
public static class ViewExtractor
{
    public static (Dictionary<string, JObject> views, Dictionary<string, JObject> annotations) ExtractViewsAndAnnotations(
        ISheet sheet, CancellationToken ct)
    {
        var viewsResult = new Dictionary<string, JObject>();
        var annotationsResult = new Dictionary<string, JObject>();
        if (sheet == null) return (viewsResult, annotationsResult);

        object[]? views = null;
        try
        {
            var raw = sheet.GetViews();
            if (raw is object[] arr)
            {
                views = arr;
            }
        }
        catch
        {
        }

        if (views == null || views.Length == 0)
        {
            return (viewsResult, annotationsResult);
        }

        int viewIndex = 0;
        foreach (var viewObj in views)
        {
            ct.ThrowIfCancellationRequested();
            if (!(viewObj is IView view))
            {
                continue;
            }

            try
            {
                var viewType = (swDrawingViewTypes_e)view.Type;
                var isSheetView = viewType == swDrawingViewTypes_e.swDrawingSheet;
                string? viewKey = null;

                if (!isSheetView)
                {
                    var nativeId = view.GetName2() ?? $"View{viewIndex}";
                    var scale = view.ScaleDecimal;
                    if (scale <= 0) scale = 1.0;

                    double minX = 0, minY = 0, maxX = 0, maxY = 0;
                    double[]? outline = (double[]?)view.GetOutline();
                    if (outline != null && outline.Length >= 4)
                    {
                        minX = outline[0] * 1000.0;
                        minY = outline[1] * 1000.0;
                        maxX = outline[2] * 1000.0;
                        maxY = outline[3] * 1000.0;
                    }

                    var edges = new JArray();
                    var viewObjJson = new JObject
                    {
                        ["native_id"] = nativeId,
                        ["scale"] = scale,
                        ["outline"] = new JObject
                        {
                            ["min"] = new JArray { minX, minY },
                            ["max"] = new JArray { maxX, maxY }
                        },
                        ["edges"] = edges
                    };

                    viewKey = "v_" + Guid.NewGuid().ToString("N").Substring(0, 10);
                    viewsResult[viewKey] = viewObjJson;
                    viewIndex++;
                }

                var anns = AnnotationExtractor.ExtractAnnotations(view, ct, viewKey);
                foreach (var kvp in anns)
                {
                    annotationsResult[kvp.Key] = kvp.Value;
                }
            }
            finally
            {
                Marshal.ReleaseComObject(view);
            }
        }

        return (viewsResult, annotationsResult);
    }

    public static Dictionary<string, JObject> ExtractViews(IDrawingDoc drawing, ISheet sheet, CancellationToken ct)
    {
        return ExtractViewsAndAnnotations(sheet, ct).views;
    }
}

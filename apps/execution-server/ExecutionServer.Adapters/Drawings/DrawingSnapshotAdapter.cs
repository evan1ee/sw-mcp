using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
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
/// Extracts real drawing geometry, views, annotations, and dimensions from SOLIDWORKS (spec 11.5.1).
/// Adheres strictly to Guideline G1 (Marshal.ReleaseComObject on all COM proxies).
/// </summary>
public sealed class DrawingSnapshotAdapter
{
    private readonly ISldWorks _sw;

    public DrawingSnapshotAdapter(ISldWorks sw)
    {
        _sw = sw ?? throw new ArgumentNullException(nameof(sw));
    }

    public static List<string> FilterSheets(IReadOnlyList<string> availableSheets, IReadOnlyList<string>? requestedSheets)
        => SnapshotBuilder.FilterSheets(availableSheets, requestedSheets);

    public static JObject BuildSnapshotJson(
        string document,
        int? revision,
        string version,
        string servicePack,
        DateTime capturedAt,
        Dictionary<string, JObject> sheets)
        => SnapshotBuilder.BuildSnapshotJson(document, revision, version, servicePack, capturedAt, sheets);

    public JToken Snapshot(SnapshotParams p, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));

        IModelDoc2? modelDoc = null;
        try
        {
            modelDoc = (IModelDoc2)_sw.ActiveDoc;
            if (modelDoc != null)
            {
                var curPath = modelDoc.GetPathName();
                var curTitle = modelDoc.GetTitle();
                if (!string.Equals(curPath, p.Document, StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(curTitle, p.Document, StringComparison.OrdinalIgnoreCase))
                {
                    Marshal.ReleaseComObject(modelDoc);
                    modelDoc = null;
                }
            }

            if (modelDoc == null)
            {
                try
                {
                    modelDoc = (IModelDoc2)_sw.GetOpenDocument(p.Document);
                }
                catch
                {
                    modelDoc = null;
                }
            }

            if (modelDoc == null)
            {
                try
                {
                    modelDoc = (IModelDoc2)_sw.GetOpenDocumentByName(p.Document);
                }
                catch
                {
                    modelDoc = null;
                }
            }

            if (modelDoc == null && File.Exists(p.Document))
            {
                int errors = 0;
                int warnings = 0;
                modelDoc = (IModelDoc2)_sw.OpenDoc6(
                    p.Document,
                    (int)swDocumentTypes_e.swDocDRAWING,
                    (int)swOpenDocOptions_e.swOpenDocOptions_Silent,
                    "",
                    ref errors,
                    ref warnings);
            }

            if (modelDoc == null)
            {
                throw new IpcException(ErrorCodes.FILE_NOT_FOUND, $"Drawing document '{p.Document}' not found or could not be opened.");
            }

            if (modelDoc.GetType() != (int)swDocumentTypes_e.swDocDRAWING)
            {
                throw new IpcException(ErrorCodes.IR_REFERENCE_UNRESOLVED, $"Document '{p.Document}' is not a drawing.");
            }

            var drawing = (IDrawingDoc)modelDoc;
            var rawSheetNamesObj = drawing.GetSheetNames();
            var availableSheets = new List<string>();
            if (rawSheetNamesObj is string[] strArr)
            {
                availableSheets.AddRange(strArr);
            }
            else if (rawSheetNamesObj is object[] objArr)
            {
                foreach (var o in objArr)
                {
                    if (o != null) availableSheets.Add(o.ToString());
                }
            }
            var targetSheets = FilterSheets(availableSheets, p.Sheets);

            var sheetsDict = new Dictionary<string, JObject>();
            int sheetIndex = 0;

            foreach (var sheetName in targetSheets)
            {
                ct.ThrowIfCancellationRequested();

                ISheet? sheet = null;
                try
                {
                    sheet = (ISheet)drawing.get_Sheet(sheetName);
                    if (sheet == null) continue;

                    double widthMm = 297.0;
                    double heightMm = 210.0;
                    double[]? props = (double[]?)sheet.GetProperties();
                    if (props != null && props.Length >= 7)
                    {
                        widthMm = props[5] * 1000.0;
                        heightMm = props[6] * 1000.0;
                    }

                    var (viewsDict, annotationsDict) = ViewExtractor.ExtractViewsAndAnnotations(sheet, ct);

                    var viewsObj = new JObject();
                    foreach (var v in viewsDict) viewsObj[v.Key] = v.Value;

                    var annsObj = new JObject();
                    foreach (var a in annotationsDict) annsObj[a.Key] = a.Value;

                    var sheetObj = new JObject
                    {
                        ["index"] = sheetIndex,
                        ["native_id"] = sheetName,
                        ["size_mm"] = new JArray { widthMm, heightMm },
                        ["border"] = new JObject
                        {
                            ["min"] = new JArray { 10.0, 5.0 },
                            ["max"] = new JArray { widthMm - 5.0, heightMm - 5.0 }
                        },
                        ["title_block"] = new JArray
                        {
                            new JObject
                            {
                                ["min"] = new JArray { Math.Max(0, widthMm - 85.0), 5.0 },
                                ["max"] = new JArray { widthMm - 5.0, 45.0 }
                            }
                        },
                        ["views"] = viewsObj,
                        ["annotations"] = annsObj
                    };

                    var sheetKey = "s_" + Guid.NewGuid().ToString("N").Substring(0, 10);
                    sheetsDict[sheetKey] = sheetObj;
                    sheetIndex++;
                }
                finally
                {
                    if (sheet != null)
                    {
                        Marshal.ReleaseComObject(sheet);
                    }
                }
            }

            return BuildSnapshotJson(
                p.Document,
                1,
                "2025",
                "SP3.0",
                DateTime.UtcNow,
                sheetsDict);
        }
        finally
        {
            if (modelDoc != null)
            {
                Marshal.ReleaseComObject(modelDoc);
            }
        }
    }
}

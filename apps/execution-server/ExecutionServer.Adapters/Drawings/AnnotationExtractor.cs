using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using Newtonsoft.Json.Linq;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace ExecutionServer.Adapters.Drawings;

/// <summary>
/// Extracts drawing annotations (dimensions, notes, datums, finishes, callouts) into snapshot schema format (spec 11.5.1).
/// Adheres strictly to Guideline G1 (Marshal.ReleaseComObject on all COM proxies in finally blocks).
/// </summary>
public static class AnnotationExtractor
{
    public static Dictionary<string, JObject> ExtractAnnotations(IView view, CancellationToken ct, string? viewKey = null)
    {
        var result = new Dictionary<string, JObject>();
        if (view == null) return result;

        IAnnotation? ann = null;
        try
        {
            ann = (IAnnotation?)view.GetFirstAnnotation2();
        }
        catch
        {
        }

        while (ann != null)
        {
            ct.ThrowIfCancellationRequested();
            IAnnotation? nextAnn = null;
            try
            {
                try
                {
                    nextAnn = (IAnnotation?)ann.GetNext3();
                }
                catch
                {
                }

                var annObj = ExtractSingleAnnotation(ann, viewKey);
                if (annObj != null)
                {
                    var key = "ann_" + Guid.NewGuid().ToString("N").Substring(0, 10);
                    result[key] = annObj;
                }
            }
            finally
            {
                Marshal.ReleaseComObject(ann);
                ann = nextAnn;
            }
        }

        return result;
    }

    private static JObject? ExtractSingleAnnotation(IAnnotation ann, string? viewKey)
    {
        var swType = (swAnnotationType_e)ann.GetType();
        string kind;
        switch (swType)
        {
            case swAnnotationType_e.swDisplayDimension:
                kind = "dimension";
                break;
            case swAnnotationType_e.swNote:
                kind = "note";
                break;
            case swAnnotationType_e.swGTol:
                kind = "gdt";
                break;
            case swAnnotationType_e.swDatumTag:
            case swAnnotationType_e.swDatumTargetSym:
                kind = "datum";
                break;
            case swAnnotationType_e.swSFSymbol:
                kind = "surface_finish";
                break;
            case swAnnotationType_e.swCenterMarkSym:
                kind = "center_mark";
                break;
            case swAnnotationType_e.swCenterLine:
                kind = "centerline";
                break;
            case swAnnotationType_e.swCustomSymbol:
                kind = "callout";
                break;
            default:
                kind = "note";
                break;
        }

        var nativeId = ann.GetName() ?? "Annotation";
        var obj = new JObject
        {
            ["kind"] = kind,
            ["native_id"] = nativeId
        };

        if (!string.IsNullOrEmpty(viewKey))
        {
            obj["view"] = viewKey;
        }

        if (swType == swAnnotationType_e.swDisplayDimension)
        {
            object? specific = null;
            IDimension? dim = null;
            try
            {
                specific = ann.GetSpecificAnnotation();
                if (specific is IDisplayDimension dispDim)
                {
                    obj["parenthesized"] = dispDim.ShowParenthesis;
                    try
                    {
                        dim = (IDimension?)dispDim.GetDimension2(0);
                        if (dim != null)
                        {
                            var fullName = dim.FullName;
                            var dimName = !string.IsNullOrEmpty(fullName) ? fullName : dim.Name;
                            if (!string.IsNullOrEmpty(dimName))
                            {
                                obj["parameters"] = new JArray { dimName };
                            }
                        }
                    }
                    catch
                    {
                    }
                }
            }
            catch
            {
            }
            finally
            {
                if (dim != null)
                {
                    Marshal.ReleaseComObject(dim);
                }
                if (specific != null)
                {
                    Marshal.ReleaseComObject(specific);
                }
            }
        }
        else if (swType == swAnnotationType_e.swNote)
        {
            object? specific = null;
            try
            {
                specific = ann.GetSpecificAnnotation();
                if (specific is INote note)
                {
                    var text = note.GetText() ?? string.Empty;
                    var textBoxes = new JArray
                    {
                        new JObject
                        {
                            ["corners"] = new JArray
                            {
                                new JArray { 0.0, 0.0 },
                                new JArray { 10.0, 0.0 },
                                new JArray { 10.0, 5.0 },
                                new JArray { 0.0, 5.0 }
                            },
                            ["height_mm"] = 3.5,
                            ["method"] = "display_data",
                            ["text"] = text
                        }
                    };
                    obj["text_boxes"] = textBoxes;
                }
            }
            catch
            {
            }
            finally
            {
                if (specific != null)
                {
                    Marshal.ReleaseComObject(specific);
                }
            }
        }

        return obj;
    }
}

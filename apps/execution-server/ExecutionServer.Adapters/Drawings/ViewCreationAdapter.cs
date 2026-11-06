using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using ExecutionServer.Core.Drawings;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace ExecutionServer.Adapters.Drawings;

/// <summary>
/// Handles view creation (view.create) and updates (view.update) on SOLIDWORKS drawing sheets.
/// Adheres strictly to Guideline G1 (Marshal.ReleaseComObject in finally blocks).
/// </summary>
public sealed class ViewCreationAdapter
{
    private readonly ISldWorks _sw;

    public ViewCreationAdapter(ISldWorks sw)
    {
        _sw = sw ?? throw new ArgumentNullException(nameof(sw));
    }

    public static string MapOrientationName(ViewCreateParamsOrientation orientation)
    {
        return orientation switch
        {
            ViewCreateParamsOrientation.Front => "*Front",
            ViewCreateParamsOrientation.Top => "*Top",
            ViewCreateParamsOrientation.Right => "*Right",
            ViewCreateParamsOrientation.Back => "*Back",
            ViewCreateParamsOrientation.Bottom => "*Bottom",
            ViewCreateParamsOrientation.Left => "*Left",
            ViewCreateParamsOrientation.Isometric => "*Isometric",
            _ => "*Front"
        };
    }

    public static swDisplayMode_e MapDisplayMode(ViewCreateParamsDisplayMode mode)
    {
        return mode switch
        {
            ViewCreateParamsDisplayMode.Hlr => swDisplayMode_e.swHIDDEN,
            ViewCreateParamsDisplayMode.Hlv => swDisplayMode_e.swHIDDEN_GREYED,
            ViewCreateParamsDisplayMode.Wireframe => swDisplayMode_e.swWIREFRAME,
            ViewCreateParamsDisplayMode.Shaded => swDisplayMode_e.swSHADED,
            ViewCreateParamsDisplayMode.ShadedEdges => swDisplayMode_e.swSHADED_EDGES,
            ViewCreateParamsDisplayMode.Default => swDisplayMode_e.swDisplayModeDEFAULT,
            _ => swDisplayMode_e.swHIDDEN
        };
    }

    public static swDisplayMode_e MapUpdateDisplayMode(ViewUpdateParamsDisplayMode mode)
    {
        return mode switch
        {
            ViewUpdateParamsDisplayMode.Hlr => swDisplayMode_e.swHIDDEN,
            ViewUpdateParamsDisplayMode.Hlv => swDisplayMode_e.swHIDDEN_GREYED,
            ViewUpdateParamsDisplayMode.Wireframe => swDisplayMode_e.swWIREFRAME,
            ViewUpdateParamsDisplayMode.Shaded => swDisplayMode_e.swSHADED,
            ViewUpdateParamsDisplayMode.ShadedEdges => swDisplayMode_e.swSHADED_EDGES,
            ViewUpdateParamsDisplayMode.Default => swDisplayMode_e.swDisplayModeDEFAULT,
            _ => swDisplayMode_e.swHIDDEN
        };
    }

    public static swDisplayTangentEdges_e MapTangentEdges(ViewCreateParamsTangentEdges edges)
    {
        return edges switch
        {
            ViewCreateParamsTangentEdges.Removed => swDisplayTangentEdges_e.swTangentEdgesHidden,
            ViewCreateParamsTangentEdges.Phantom => swDisplayTangentEdges_e.swTangentEdgesVisibleAndFonted,
            ViewCreateParamsTangentEdges.Visible => swDisplayTangentEdges_e.swTangentEdgesVisible,
            _ => swDisplayTangentEdges_e.swTangentEdgesHidden
        };
    }

    public ViewCreateResult CreateView(ViewCreateParams p, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        IModelDoc2? modelDoc = null;
        try
        {
            modelDoc = (IModelDoc2?)_sw.IActiveDoc2;
            if (modelDoc == null || modelDoc.GetType() != (int)swDocumentTypes_e.swDocDRAWING)
            {
                throw new IpcException(ErrorCodes.IR_RULE_VIOLATED, "Active document is not a drawing.");
            }

            var drawing = (IDrawingDoc)modelDoc;

            if (!string.IsNullOrEmpty(p.Sheet))
            {
                drawing.ActivateSheet(p.Sheet);
            }

            var modelPath = p.ModelPath;
            if (string.IsNullOrEmpty(modelPath))
            {
                modelPath = ResolveModelPathFromDrawing(drawing);
            }

            if (string.IsNullOrEmpty(modelPath))
            {
                throw new IpcException(ErrorCodes.FILE_NOT_FOUND, "Model path is required to create a drawing view.");
            }

            var orientationName = MapOrientationName(p.Orientation);

            var xMm = p.Position.Count > 0 ? p.Position[0] : 100.0;
            var yMm = p.Position.Count > 1 ? p.Position[1] : 100.0;
            var (xM, yM) = ViewLayoutGeometry.MmToMeters(xMm, yMm);

            IView? view = null;
            try
            {
                view = (IView?)drawing.CreateDrawViewFromModelView3(modelPath, orientationName, xM, yM, 0.0);
                if (view == null)
                {
                    throw new IpcException(ErrorCodes.BACKEND_LOST,
                        $"Failed to create drawing view for model '{modelPath}' with orientation '{orientationName}'.");
                }

                if (p.Scale > 0)
                {
                    view.UseSheetScale = 0;
                    view.ScaleDecimal = p.Scale;
                }

                if (!string.IsNullOrEmpty(p.Configuration))
                {
                    view.ReferencedConfiguration = p.Configuration;
                }

                if (p.DisplayMode.HasValue)
                {
                    var swMode = MapDisplayMode(p.DisplayMode.Value);
                    view.SetDisplayMode3(false, (int)swMode, false, false);
                }

                if (p.TangentEdges.HasValue)
                {
                    var swTangent = MapTangentEdges(p.TangentEdges.Value);
                    view.SetDisplayTangentEdges2((int)swTangent);
                }

                view.Position = new double[] { xM, yM };

                if (!string.IsNullOrEmpty(p.ViewName))
                {
                    view.SetName2(p.ViewName);
                }

                var nativeId = view.GetName2() ?? p.ViewName ?? "Drawing View";
                var actualScale = view.ScaleDecimal;
                if (actualScale <= 0)
                {
                    actualScale = p.Scale > 0 ? p.Scale : 1.0;
                }

                double minX = 0, minY = 0, maxX = 0, maxY = 0;
                var outline = (double[]?)view.GetOutline();
                if (outline != null && outline.Length >= 4)
                {
                    minX = outline[0] * 1000.0;
                    minY = outline[1] * 1000.0;
                    maxX = outline[2] * 1000.0;
                    maxY = outline[3] * 1000.0;
                }

                var widthMm = maxX > minX ? maxX - minX : 0.0;
                var heightMm = maxY > minY ? maxY - minY : 0.0;

                return new ViewCreateResult
                {
                    ViewId = p.ViewName,
                    NativeId = nativeId,
                    PositionMm = new List<double> { xMm, yMm },
                    Scale = actualScale,
                    OutlineMm = new ViewOutline
                    {
                        Min = new List<double> { minX, minY },
                        Max = new List<double> { maxX, maxY }
                    },
                    WidthMm = widthMm,
                    HeightMm = heightMm
                };
            }
            finally
            {
                if (view != null)
                {
                    Marshal.ReleaseComObject(view);
                }
            }
        }
        finally
        {
            if (modelDoc != null)
            {
                Marshal.ReleaseComObject(modelDoc);
            }
        }
    }

    public ViewUpdateResult UpdateView(ViewUpdateParams p, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        IModelDoc2? modelDoc = null;
        try
        {
            modelDoc = (IModelDoc2?)_sw.IActiveDoc2;
            if (modelDoc == null || modelDoc.GetType() != (int)swDocumentTypes_e.swDocDRAWING)
            {
                throw new IpcException(ErrorCodes.IR_RULE_VIOLATED, "Active document is not a drawing.");
            }

            var drawing = (IDrawingDoc)modelDoc;

            var foundView = FindViewByName(drawing, p.ViewName);
            if (foundView == null)
            {
                throw new IpcException(ErrorCodes.EXEC_NOT_FOUND,
                    $"Drawing view '{p.ViewName}' not found in active drawing.");
            }

            try
            {
                if (p.Scale.HasValue && p.Scale.Value > 0)
                {
                    foundView.UseSheetScale = 0;
                    foundView.ScaleDecimal = p.Scale.Value;
                }

                if (p.Position != null && p.Position.Count >= 2)
                {
                    var (xM, yM) = ViewLayoutGeometry.MmToMeters(p.Position[0], p.Position[1]);
                    foundView.Position = new double[] { xM, yM };
                }

                if (p.DisplayMode.HasValue)
                {
                    var swMode = MapUpdateDisplayMode(p.DisplayMode.Value);
                    foundView.SetDisplayMode3(false, (int)swMode, false, false);
                }

                modelDoc.EditRebuild3();

                var nativeId = foundView.GetName2() ?? p.ViewName;
                double? actualScale = p.Scale.HasValue ? foundView.ScaleDecimal : null;

                ViewOutline? outlineMm = null;
                var outline = (double[]?)foundView.GetOutline();
                if (outline != null && outline.Length >= 4)
                {
                    outlineMm = new ViewOutline
                    {
                        Min = new List<double> { outline[0] * 1000.0, outline[1] * 1000.0 },
                        Max = new List<double> { outline[2] * 1000.0, outline[3] * 1000.0 }
                    };
                }

                return new ViewUpdateResult
                {
                    NativeId = nativeId,
                    PositionMm = p.Position,
                    Scale = actualScale,
                    OutlineMm = outlineMm
                };
            }
            finally
            {
                Marshal.ReleaseComObject(foundView);
            }
        }
        finally
        {
            if (modelDoc != null)
            {
                Marshal.ReleaseComObject(modelDoc);
            }
        }
    }

    private static string? ResolveModelPathFromDrawing(IDrawingDoc drawing)
    {
        IView? firstView = null;
        try
        {
            firstView = (IView?)drawing.GetFirstView();
            if (firstView == null) return null;

            var cur = (IView?)firstView.GetNextView();
            while (cur != null)
            {
                try
                {
                    var model = cur.GetReferencedModelName();
                    if (!string.IsNullOrEmpty(model))
                    {
                        return model;
                    }
                }
                finally
                {
                    var next = (IView?)cur.GetNextView();
                    Marshal.ReleaseComObject(cur);
                    cur = next;
                }
            }
            return null;
        }
        finally
        {
            if (firstView != null)
            {
                Marshal.ReleaseComObject(firstView);
            }
        }
    }

    private static IView? FindViewByName(IDrawingDoc drawing, string viewName)
    {
        IView? firstView = null;
        try
        {
            firstView = (IView?)drawing.GetFirstView();
            if (firstView == null) return null;

            var cur = (IView?)firstView.GetNextView();
            while (cur != null)
            {
                var name = cur.GetName2();
                if (string.Equals(name, viewName, StringComparison.OrdinalIgnoreCase))
                {
                    return cur; // Caller must release found view
                }

                var next = (IView?)cur.GetNextView();
                Marshal.ReleaseComObject(cur);
                cur = next;
            }
            return null;
        }
        finally
        {
            if (firstView != null)
            {
                Marshal.ReleaseComObject(firstView);
            }
        }
    }
}

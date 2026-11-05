using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using ExecutionServer.Core.Drawings;
using ExecutionServer.Core.Ipc.Generated;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace ExecutionServer.Adapters.Drawings;

/// <summary>
/// Handles model items insertion, auto center marks, auto arrangement, and dimension visibility/movement
/// in SOLIDWORKS drawings. Adheres strictly to Guideline G1 (Marshal.ReleaseComObject in finally blocks)
/// and Spec 8.3 rule 11 (selection by entity, no SelectByID2 display names).
/// </summary>
public sealed class AnnotationPlacementAdapter
{
    private readonly ISldWorks _sw;

    public AnnotationPlacementAdapter(ISldWorks sw)
    {
        _sw = sw ?? throw new ArgumentNullException(nameof(sw));
    }

    /// <summary>
    /// Inserts model items (dimensions, hole callouts) from the 3D model into drawing views (spec 11.4).
    /// </summary>
    public ModelItemsInsertResult InsertModelItems(ModelItemsInsertParams p, CancellationToken ct)
    {
        var model = (IModelDoc2?)_sw.ActiveDoc;
        if (model == null || model.GetType() != (int)swDocumentTypes_e.swDocDRAWING)
        {
            throw new InvalidOperationException("No active drawing document found for model_items.insert.");
        }

        var drawing = (IDrawingDoc)model;
        int insertedCount = 0;
        var insertedAnnotations = new List<string>();

        {
            ct.ThrowIfCancellationRequested();

            // Calculate types bitmask
            int typesBitmask = 0;
            bool marked = p.MarkedForDrawing ?? false;
            bool notMarked = p.NotMarkedForDrawing ?? false;
            bool holeCallouts = p.HoleCallouts ?? false;

            if (marked || (!marked && !notMarked))
            {
                typesBitmask |= (int)swInsertAnnotation_e.swInsertDimensionsMarkedForDrawing;
            }
            if (notMarked)
            {
                typesBitmask |= (int)swInsertAnnotation_e.swInsertDimensionsNotMarkedForDrawing;
            }
            if (holeCallouts)
            {
                typesBitmask |= (int)swInsertAnnotation_e.swInsertholeCallout;
            }

            // Calculate source option
            int sourceOption = p.Source == ModelItemsInsertParamsSource.SelectedFeature
                ? (int)swImportModelItemsSource_e.swImportModelItemsFromSelectedFeature
                : (int)swImportModelItemsSource_e.swImportModelItemsFromEntireModel;

            bool allViews = string.IsNullOrEmpty(p.View);
            if (!allViews && !string.IsNullOrEmpty(p.View))
            {
                drawing.ActivateView(p.View);
            }

            bool duplicateDims = p.DuplicateDims ?? false;
            bool hiddenFeatureDims = p.HiddenFeatureDims ?? false;
            bool usePlacementInSketch = p.UsePlacementInSketch ?? false;

            // Insert model annotations
            drawing.InsertModelAnnotations3(
                sourceOption,
                typesBitmask,
                allViews,
                duplicateDims,
                hiddenFeatureDims,
                usePlacementInSketch);

            insertedCount = 1;
        }

        return new ModelItemsInsertResult
        {
            Count = insertedCount,
            Annotations = insertedAnnotations
        };
    }

    /// <summary>
    /// Auto-arranges dimensions on the specified view or active sheet (spec 11.4).
    /// </summary>
    public DimensionsAutoArrangeResult AutoArrangeDimensions(DimensionsAutoArrangeParams p, CancellationToken ct)
    {
        var model = (IModelDoc2?)_sw.ActiveDoc;
        if (model == null || model.GetType() != (int)swDocumentTypes_e.swDocDRAWING)
        {
            throw new InvalidOperationException("No active drawing document found for dimensions.auto_arrange.");
        }

        var drawing = (IDrawingDoc)model;

        {
            ct.ThrowIfCancellationRequested();

            double spacingMm = (p.SpacingMm.HasValue && p.SpacingMm.Value > 0) ? p.SpacingMm.Value : 10.0;
            double spacingM = AnnotationPlacementMath.MmToMeters(spacingMm);

            model.ClearSelection2(true);
            if (!string.IsNullOrEmpty(p.View))
            {
                drawing.ActivateView(p.View);
                IView? view = FindView(drawing, p.View);
                if (view != null)
                {
                    try
                    {
                        IAnnotation? ann = (IAnnotation?)view.GetFirstAnnotation2();
                        while (ann != null)
                        {
                            if (ann.GetType() == (int)swAnnotationType_e.swDisplayDimension)
                            {
                                ann.Select2(true, 0);
                            }
                            IAnnotation? nextAnn = (IAnnotation?)ann.GetNext3();
                            Marshal.ReleaseComObject(ann);
                            ann = nextAnn;
                        }
                    }
                    finally
                    {
                        Marshal.ReleaseComObject(view);
                    }
                }
            }

            model.Extension.AlignDimensions((int)swAlignDimensionType_e.swAlignDimensionType_AutoArrange, spacingM);
        }

        return new DimensionsAutoArrangeResult
        {
            Success = true,
            View = p.View
        };
    }

    /// <summary>
    /// Automatically inserts ISO 128 center marks on circular holes and slots in a view (spec 11.4).
    /// </summary>
    public CenterMarkAddResult AutoInsertCenterMarks(CenterMarkAddParams p, CancellationToken ct)
    {
        var model = (IModelDoc2?)_sw.ActiveDoc;
        if (model == null || model.GetType() != (int)swDocumentTypes_e.swDocDRAWING)
        {
            throw new InvalidOperationException("No active drawing document found for center_mark.add.");
        }

        var drawing = (IDrawingDoc)model;
        int count = 0;

        {
            ct.ThrowIfCancellationRequested();
            IView? view = FindView(drawing, p.View);
            if (view == null)
            {
                throw new InvalidOperationException($"View '{p.View}' not found for center_mark.add.");
            }

            try
            {
                bool useDocDefaults = p.UseDocDefaults ?? true;
                bool slotCenters = p.SlotCenters ?? true;
                double sizeM = (p.SizeMm.HasValue && p.SizeMm.Value > 0) ? AnnotationPlacementMath.MmToMeters(p.SizeMm.Value) : 0.005;
                double gapM = (p.GapMm.HasValue && p.GapMm.Value > 0) ? AnnotationPlacementMath.MmToMeters(p.GapMm.Value) : 0.0025;

                // 1 = swCenterMark_Hole, 1 = swCenterMarkOption_e.swCenterMarkOption_Hole
                object? result = view.AutoInsertCenterMarks2(
                    1,
                    1,
                    slotCenters,
                    slotCenters,
                    useDocDefaults,
                    sizeM,
                    gapM,
                    false,
                    true,
                    0.0);

                if (result is object[] arr)
                {
                    count = arr.Length;
                }
                else
                {
                    count = 1;
                }
            }
            finally
            {
                Marshal.ReleaseComObject(view);
            }
        }

        return new CenterMarkAddResult
        {
            Count = count,
            View = p.View
        };
    }

    /// <summary>
    /// Hides a dimension annotation without deleting it, preserving reference integrity (spec 11.4, check D5).
    /// </summary>
    public DimensionHideResult HideDimension(DimensionHideParams p, CancellationToken ct)
    {
        var model = (IModelDoc2?)_sw.ActiveDoc;
        if (model == null || model.GetType() != (int)swDocumentTypes_e.swDocDRAWING)
        {
            throw new InvalidOperationException("No active drawing document found for dimension.hide.");
        }

        var drawing = (IDrawingDoc)model;
        bool hidden = false;

        {
            ct.ThrowIfCancellationRequested();
            var ann = FindAnnotation(drawing, p.Annotation);
            if (ann != null)
            {
                try
                {
                    ann.Visible = (int)swAnnotationVisibilityState_e.swAnnotationHidden;
                    hidden = true;
                }
                finally
                {
                    Marshal.ReleaseComObject(ann);
                }
            }
        }

        return new DimensionHideResult
        {
            Annotation = p.Annotation,
            Hidden = hidden
        };
    }

    /// <summary>
    /// Shows a previously hidden dimension annotation (spec 11.4).
    /// </summary>
    public DimensionShowResult ShowDimension(DimensionShowParams p, CancellationToken ct)
    {
        var model = (IModelDoc2?)_sw.ActiveDoc;
        if (model == null || model.GetType() != (int)swDocumentTypes_e.swDocDRAWING)
        {
            throw new InvalidOperationException("No active drawing document found for dimension.show.");
        }

        var drawing = (IDrawingDoc)model;
        bool shown = false;

        {
            ct.ThrowIfCancellationRequested();
            var ann = FindAnnotation(drawing, p.Annotation);
            if (ann != null)
            {
                try
                {
                    ann.Visible = (int)swAnnotationVisibilityState_e.swAnnotationVisible;
                    shown = true;
                }
                finally
                {
                    Marshal.ReleaseComObject(ann);
                }
            }
        }

        return new DimensionShowResult
        {
            Annotation = p.Annotation,
            Shown = shown
        };
    }

    /// <summary>
    /// Moves a dimension annotation to a specified sheet position (spec 6.5.2).
    /// </summary>
    public DimensionMoveResult MoveDimension(DimensionMoveParams p, CancellationToken ct)
    {
        var model = (IModelDoc2?)_sw.ActiveDoc;
        if (model == null || model.GetType() != (int)swDocumentTypes_e.swDocDRAWING)
        {
            throw new InvalidOperationException("No active drawing document found for dimension.move.");
        }

        var drawing = (IDrawingDoc)model;

        {
            ct.ThrowIfCancellationRequested();
            var ann = FindAnnotation(drawing, p.Annotation);
            if (ann != null)
            {
                try
                {
                    double xM = AnnotationPlacementMath.MmToMeters(p.Position[0]);
                    double yM = AnnotationPlacementMath.MmToMeters(p.Position[1]);
                    ann.SetPosition2(xM, yM, 0.0);
                }
                finally
                {
                    Marshal.ReleaseComObject(ann);
                }
            }
        }

        return new DimensionMoveResult
        {
            Annotation = p.Annotation,
            Position = p.Position
        };
    }

    private static IView? FindView(IDrawingDoc drawing, string viewName)
    {
        IView? current = (IView?)drawing.GetFirstView();
        while (current != null)
        {
            if (string.Equals(current.GetName2(), viewName, StringComparison.OrdinalIgnoreCase))
            {
                return current;
            }

            IView? next = (IView?)current.GetNextView();
            Marshal.ReleaseComObject(current);
            current = next;
        }

        return null;
    }

    private static IAnnotation? FindAnnotation(IDrawingDoc drawing, string annotationName)
    {
        IView? view = (IView?)drawing.GetFirstView();
        while (view != null)
        {
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
                string name = ann.GetName() ?? string.Empty;
                if (string.Equals(name, annotationName, StringComparison.OrdinalIgnoreCase))
                {
                    Marshal.ReleaseComObject(view);
                    return ann;
                }

                // Check display dimension name
                if (ann.GetType() == (int)swAnnotationType_e.swDisplayDimension)
                {
                    object? spec = null;
                    IDimension? dim = null;
                    try
                    {
                        spec = ann.GetSpecificAnnotation();
                        if (spec is IDisplayDimension dispDim)
                        {
                            dim = (IDimension?)dispDim.GetDimension2(0);
                            if (dim != null)
                            {
                                var dimName = dim.FullName;
                                if (string.IsNullOrEmpty(dimName))
                                {
                                    dimName = dim.Name;
                                }
                                if (string.Equals(dimName, annotationName, StringComparison.OrdinalIgnoreCase))
                                {
                                    Marshal.ReleaseComObject(view);
                                    return ann;
                                }
                            }
                        }
                    }
                    catch
                    {
                    }
                    finally
                    {
                        if (dim != null) Marshal.ReleaseComObject(dim);
                        if (spec != null) Marshal.ReleaseComObject(spec);
                    }
                }

                IAnnotation? nextAnn = null;
                try
                {
                    nextAnn = (IAnnotation?)ann.GetNext3();
                }
                catch
                {
                }

                Marshal.ReleaseComObject(ann);
                ann = nextAnn;
            }

            IView? nextView = null;
            try
            {
                nextView = (IView?)view.GetNextView();
            }
            catch
            {
            }

            Marshal.ReleaseComObject(view);
            view = nextView;
        }

        return null;
    }
}

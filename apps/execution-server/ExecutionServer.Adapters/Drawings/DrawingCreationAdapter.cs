using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using ExecutionServer.Core.Drawings;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace ExecutionServer.Adapters.Drawings;

/// <summary>
/// Handles drawing document creation (drawing.create) and document persistence (document.save) in SOLIDWORKS.
/// Adheres strictly to Guideline G1 (Marshal.ReleaseComObject in finally blocks).
/// </summary>
public sealed class DrawingCreationAdapter
{
    private readonly ISldWorks _sw;

    public DrawingCreationAdapter(ISldWorks sw)
    {
        _sw = sw ?? throw new ArgumentNullException(nameof(sw));
    }

    public DrawingCreateResult CreateDrawing(DrawingCreateParams p, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        double widthM;
        double heightM;

        if (p.WidthMm.HasValue && p.HeightMm.HasValue && p.WidthMm.Value > 0 && p.HeightMm.Value > 0)
        {
            widthM = p.WidthMm.Value / 1000.0;
            heightM = p.HeightMm.Value / 1000.0;
        }
        else if (!string.IsNullOrEmpty(p.PaperSize))
        {
            var (wMm, hMm) = SheetFormatGeometry.GetPaperDimensions(p.PaperSize!, "landscape");
            widthM = wMm / 1000.0;
            heightM = hMm / 1000.0;
        }
        else
        {
            widthM = 0.420;
            heightM = 0.297;
        }

        var templatePath = SheetFormatGenerator.ResolveDrawingTemplatePath(_sw, p.TemplatePath);
        if (string.IsNullOrEmpty(templatePath))
        {
            throw new IpcException(ErrorCodes.FILE_NOT_FOUND, $"Drawing template file not found: '{p.TemplatePath}'.");
        }

        IModelDoc2? modelDoc = null;
        try
        {
            try
            {
                modelDoc = (IModelDoc2)_sw.NewDocument(
                    templatePath,
                    (int)swDwgPaperSizes_e.swDwgPapersUserDefined,
                    widthM,
                    heightM);
            }
            catch
            {
                modelDoc = (IModelDoc2)_sw.INewDocument2(
                    templatePath,
                    (int)swDwgPaperSizes_e.swDwgPapersUserDefined,
                    widthM,
                    heightM);
            }

            if (modelDoc == null)
            {
                throw new IpcException(ErrorCodes.BACKEND_LOST, "Failed to create drawing document in SOLIDWORKS.");
            }

            var drawing = (IDrawingDoc)modelDoc;
            ISheet? sheet = null;
            string sheetName = "Sheet1";

            try
            {
                sheet = (ISheet)drawing.GetCurrentSheet();
                if (sheet != null)
                {
                    sheetName = sheet.GetName() ?? "Sheet1";
                    if (!string.IsNullOrEmpty(p.SheetFormatPath))
                    {
                        sheet.SetSheetFormatName(p.SheetFormatPath);
                        sheet.SetTemplateName(p.SheetFormatPath);
                        sheet.ReloadTemplate(false);
                    }
                }
            }
            finally
            {
                if (sheet != null)
                {
                    Marshal.ReleaseComObject(sheet);
                }
            }

            var docPath = modelDoc.GetPathName();
            if (string.IsNullOrEmpty(docPath))
            {
                docPath = modelDoc.GetTitle();
            }

            if (!string.IsNullOrEmpty(p.DestinationPath))
            {
                int errors = 0;
                int warnings = 0;
                bool saved = modelDoc.SaveAs4(
                    p.DestinationPath,
                    (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                    ref errors,
                    ref warnings);

                if (saved)
                {
                    docPath = p.DestinationPath;
                }
            }

            return new DrawingCreateResult
            {
                Document = docPath ?? string.Empty,
                SheetName = sheetName
            };
        }
        finally
        {
            if (modelDoc != null)
            {
                Marshal.ReleaseComObject(modelDoc);
            }
        }
    }

    public DocumentSaveResult SaveDocument(DocumentSaveParams p, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        IModelDoc2? modelDoc = null;
        try
        {
            modelDoc = (IModelDoc2)_sw.ActiveDoc;
            if (modelDoc != null)
            {
                var curPath = modelDoc.GetPathName();
                var curTitle = modelDoc.GetTitle();
                if (!string.Equals(curPath, p.Path, StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(curTitle, p.Path, StringComparison.OrdinalIgnoreCase))
                {
                    Marshal.ReleaseComObject(modelDoc);
                    modelDoc = null;
                }
            }

            if (modelDoc == null)
            {
                try
                {
                    modelDoc = (IModelDoc2)_sw.GetOpenDocument(p.Path);
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
                    modelDoc = (IModelDoc2)_sw.GetOpenDocumentByName(p.Path);
                }
                catch
                {
                    modelDoc = null;
                }
            }

            if (modelDoc == null)
            {
                throw new IpcException(ErrorCodes.FILE_NOT_FOUND, $"Document '{p.Path}' not found or not active.");
            }

            var targetPath = !string.IsNullOrEmpty(p.TargetPath) ? p.TargetPath : p.Path;
            int errors = 0;
            int warnings = 0;
            bool saved = modelDoc.SaveAs4(
                targetPath,
                (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                ref errors,
                ref warnings);

            if (!saved)
            {
                throw new IpcException(ErrorCodes.FILE_NOT_FOUND, $"SaveAs failed for '{targetPath}', errors: {errors}, warnings: {warnings}.");
            }

            return new DocumentSaveResult
            {
                SavedPath = targetPath ?? string.Empty
            };
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

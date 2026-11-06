using System;
using System.IO;
using System.Threading;
using ExecutionServer.Adapters.Drawings;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ownership;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace ExecutionServer.Adapters.Documents;

/// <summary>
/// Document lifecycle operations (open, close, save) with ownership enforcement (spec 8.3, 8.7; ADR-022, ADR-046, ADR-059).
/// </summary>
public sealed class DocumentOps
{
    private readonly ISldWorks _sw;
    private readonly DocumentOwnershipTable _ownership;

    public DocumentOps(ISldWorks sw, DocumentOwnershipTable ownership)
    {
        _sw = sw ?? throw new ArgumentNullException(nameof(sw));
        _ownership = ownership ?? throw new ArgumentNullException(nameof(ownership));
    }

    public DocumentOpenResult Open(string document, DocumentOpenParams p, string? jobId, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        var path = !string.IsNullOrWhiteSpace(p.Path) ? p.Path : document;
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new IpcException(ErrorCodes.FILE_NOT_FOUND, "Document path required for document.open.");
        }

        // 1. Check whether document is already open (ADR-059: do not release IModelDoc2)
        var existing = (IModelDoc2?)_sw.GetOpenDocumentByName(path);
        bool alreadyOpen = existing != null;

        string? previousActive = null;
        var active = (IModelDoc2?)_sw.ActiveDoc;
        if (active != null)
        {
            previousActive = active.GetPathName();
            if (string.IsNullOrEmpty(previousActive))
            {
                previousActive = active.GetTitle();
            }
        }

        bool owned = !alreadyOpen;
        if (!alreadyOpen)
        {
            int errors = 0;
            int warnings = 0;
            var docType = (int)swDocumentTypes_e.swDocDRAWING;
            if (path.EndsWith(".sldprt", StringComparison.OrdinalIgnoreCase))
            {
                docType = (int)swDocumentTypes_e.swDocPART;
            }
            else if (path.EndsWith(".sldasm", StringComparison.OrdinalIgnoreCase))
            {
                docType = (int)swDocumentTypes_e.swDocASSEMBLY;
            }

            int options = (int)swOpenDocOptions_e.swOpenDocOptions_Silent;
            if (p.ReadOnly)
            {
                options |= (int)swOpenDocOptions_e.swOpenDocOptions_ReadOnly;
            }

            var modelDoc = (IModelDoc2?)_sw.OpenDoc6(
                path,
                docType,
                options,
                p.Configuration ?? "",
                ref errors,
                ref warnings);

            if (modelDoc == null)
            {
                throw new IpcException(ErrorCodes.FILE_NOT_FOUND, $"Failed to open document '{path}', errors: {errors}");
            }
        }

        var instanceId = Guid.NewGuid().ToString("N");
        if (!string.IsNullOrEmpty(jobId))
        {
            _ownership.Record(path, jobId!, owned, instanceId, previousActive);
        }

        return new DocumentOpenResult
        {
            Owned = owned,
            InstanceId = instanceId,
        };
    }

    public DocumentCloseResult Close(string document, DocumentCloseParams p, string? jobId, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        var path = !string.IsNullOrWhiteSpace(p.Path) ? p.Path : document;
        var decision = _ownership.CheckClose(path, jobId);
        if (!decision.Allowed)
        {
            throw new IpcException(
                decision.ErrorCode ?? ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED,
                decision.Reason ?? "Close refused by ownership check.");
        }

        string? prevActive = !string.IsNullOrEmpty(jobId) ? _ownership.PreviousActive(path, jobId!) : null;

        var isPart = path.EndsWith(".sldprt", StringComparison.OrdinalIgnoreCase);
        if (isPart)
        {
            // Spike answer 7: CloseDoc(fullPath) closes without prompt
            _sw.CloseDoc(path);
        }
        else
        {
            // Drawings keep today's lookup: title
            var title = Path.GetFileName(path);
            _sw.CloseDoc(title);
        }

        _ownership.Forget(path);

        // Restore previous active if present
        if (!string.IsNullOrEmpty(prevActive))
        {
            try
            {
                int errors = 0;
                _sw.ActivateDoc3(prevActive, false, (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref errors);
            }
            catch
            {
                // Best effort activation
            }
        }

        return new DocumentCloseResult { Closed = true };
    }

    public DocumentSaveResult Save(string document, DocumentSaveParams p, string? jobId, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        var path = !string.IsNullOrWhiteSpace(p.Path) ? p.Path : document;
        var decision = _ownership.CheckSave(path, p.TargetPath, jobId);
        if (!decision.Allowed)
        {
            throw new IpcException(
                decision.ErrorCode ?? ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED,
                decision.Reason ?? "Save refused by ownership check.");
        }

        var isPart = path.EndsWith(".sldprt", StringComparison.OrdinalIgnoreCase);
        if (!isPart)
        {
            // Frozen flow: calls DrawingCreationAdapter.SaveDocument unchanged for drawings
            return new DrawingCreationAdapter(_sw).SaveDocument(p, ct);
        }

        // Part saves: find document by full path, never ActiveDoc (F5)
        var modelDoc = (IModelDoc2?)_sw.GetOpenDocumentByName(path);
        if (modelDoc == null)
        {
            throw new IpcException(ErrorCodes.FILE_NOT_FOUND, $"Part document '{path}' not found.");
        }

        var targetPath = !string.IsNullOrEmpty(p.TargetPath) ? p.TargetPath : path;
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

        return new DocumentSaveResult { SavedPath = targetPath ?? string.Empty };
    }
}

using System;
using System.IO;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using SolidWorks.Interop.sldworks;

namespace ExecutionServer.Adapters.Native;

/// <summary>
/// Finds open SOLIDWORKS documents by full normalized path only (F5, R2, ADR-059).
/// Adheres strictly to Guideline G1: never releases IModelDoc2.
/// </summary>
public static class DocumentLocator
{
    public static IModelDoc2 FindDocument(ISldWorks sw, string path)
    {
        if (sw == null) throw new ArgumentNullException(nameof(sw));
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new IpcException(ErrorCodes.FILE_NOT_FOUND, "Document path cannot be empty.");
        }

        string fullPath = path;
        try
        {
            fullPath = Path.GetFullPath(path);
        }
        catch
        {
            // Use path as provided if GetFullPath fails
        }

        var doc = (IModelDoc2?)sw.GetOpenDocumentByName(fullPath);
        if (doc == null && !string.Equals(fullPath, path, StringComparison.OrdinalIgnoreCase))
        {
            doc = (IModelDoc2?)sw.GetOpenDocumentByName(path);
        }

        if (doc == null)
        {
            throw new IpcException(ErrorCodes.FILE_NOT_FOUND, $"Document '{path}' is not open in SOLIDWORKS.");
        }

        return doc;
    }
}

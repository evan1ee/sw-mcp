using System;
using System.IO;
using System.Security.Cryptography;
using System.Threading;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ownership;
using Newtonsoft.Json.Linq;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace ExecutionServer.Adapters.Parts;

/// <summary>
/// Implements operation part.create (spec 6.5.2, design 7, ADR-022, ADR-046, ADR-059).
/// Creates a new part from a template, saves immediately to the working path, and records ownership.
/// </summary>
public sealed class PartCreationAdapter
{
    private readonly ISldWorks _sw;
    private readonly DocumentOwnershipTable _ownership;

    public PartCreationAdapter(ISldWorks sw, DocumentOwnershipTable ownership)
    {
        _sw = sw ?? throw new ArgumentNullException(nameof(sw));
        _ownership = ownership ?? throw new ArgumentNullException(nameof(ownership));
    }

    public PartCreateResult CreatePart(string document, PartCreateParams p, string? jobId, CancellationToken ct)
    {
        if (p == null) throw new ArgumentNullException(nameof(p));
        ct.ThrowIfCancellationRequested();

        var workingPath = document;
        if (string.IsNullOrWhiteSpace(workingPath))
        {
            throw new IpcException(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, "Working path required for part.create.");
        }

        // 1. Refuse existing file before calling SaveAs4 (which overwrites silently)
        if (File.Exists(workingPath))
        {
            throw new IpcException(
                ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED,
                $"File already exists at '{workingPath}'. Refusing to overwrite.");
        }

        // 2. Validate template path
        if (string.IsNullOrWhiteSpace(p.Template))
        {
            var details = new JObject { ["setting"] = "part.template" };
            throw new IpcException(ErrorCodes.CONFIG_INVALID, "Template is required for part.create.", details);
        }

        if (!File.Exists(p.Template))
        {
            var details = new JObject { ["setting"] = "part.template" };
            throw new IpcException(ErrorCodes.FILE_NOT_FOUND, $"Template file '{p.Template}' was not found.", details);
        }

        // 3. Compute SHA256 of template
        string sha256;
        using (var sha = SHA256.Create())
        using (var stream = File.OpenRead(p.Template))
        {
            var hashBytes = sha.ComputeHash(stream);
            sha256 = BitConverter.ToString(hashBytes).Replace("-", "").ToLowerInvariant();
        }

        // 4. Record previous active document
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

        // 5. Create new document
        var modelDoc = (IModelDoc2?)_sw.NewDocument(p.Template, 0, 0, 0);
        if (modelDoc == null)
        {
            throw new IpcException(ErrorCodes.BACKEND_OPERATION_FAILED, $"NewDocument returned null for template '{p.Template}'.");
        }

        // 6. Save immediately to working path
        int errors = 0;
        int warnings = 0;
        bool saved = false;
        try
        {
            saved = modelDoc.SaveAs4(
                workingPath,
                (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                ref errors,
                ref warnings);
        }
        catch
        {
            try
            {
                string title = modelDoc.GetTitle();
                if (!string.IsNullOrEmpty(title))
                {
                    _sw.CloseDoc(title);
                }
            }
            catch
            {
                // Best-effort cleanup of untitled document handle
            }
            throw;
        }

        if (!saved || errors != 0)
        {
            try
            {
                string title = modelDoc.GetTitle();
                if (!string.IsNullOrEmpty(title))
                {
                    _sw.CloseDoc(title);
                }
            }
            catch
            {
                // Best-effort cleanup of untitled document handle
            }

            throw new IpcException(
                ErrorCodes.BACKEND_OPERATION_FAILED,
                $"SaveAs4 failed for '{workingPath}', errors: {errors}, warnings: {warnings}");
        }

        // 7. Record ownership
        var instanceId = Guid.NewGuid().ToString("N");
        if (!string.IsNullOrEmpty(jobId))
        {
            _ownership.Record(workingPath, jobId!, true, instanceId, previousActive);
        }

        return new PartCreateResult
        {
            NativeId = 1,
            Path = workingPath,
            InstanceId = instanceId,
            PreviousActive = previousActive,
            Template = new PartCreateTemplateInfo
            {
                Path = p.Template,
                Sha256 = sha256
            }
        };
    }
}

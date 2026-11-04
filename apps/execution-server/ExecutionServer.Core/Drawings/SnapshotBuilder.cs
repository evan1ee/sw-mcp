using System;
using System.Collections.Generic;
using System.Linq;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Drawings;

public static class SnapshotBuilder
{
    public static List<string> FilterSheets(IReadOnlyList<string> availableSheets, IReadOnlyList<string>? requestedSheets)
    {
        if (availableSheets == null)
        {
            throw new ArgumentNullException(nameof(availableSheets));
        }

        if (requestedSheets == null || requestedSheets.Count == 0)
        {
            return availableSheets.ToList();
        }

        var availableSet = new HashSet<string>(availableSheets, StringComparer.OrdinalIgnoreCase);
        var missing = requestedSheets.Where(s => !availableSet.Contains(s)).ToList();

        if (missing.Count > 0)
        {
            var missingArray = new JArray(missing);
            var details = new JObject { ["sheets"] = missingArray };
            throw new IpcException(
                ErrorCodes.IR_REFERENCE_UNRESOLVED,
                $"Sheet {string.Join(", ", missing)} does not exist.",
                details);
        }

        return requestedSheets.ToList();
    }

    public static JObject BuildSnapshotJson(
        string document,
        int? revision,
        string version,
        string servicePack,
        DateTime capturedAt,
        Dictionary<string, JObject> sheets)
    {
        var sheetsObj = new JObject();
        foreach (var kvp in sheets)
        {
            sheetsObj[kvp.Key] = kvp.Value;
        }

        var drawingObj = new JObject
        {
            ["document"] = document
        };
        if (revision.HasValue)
        {
            drawingObj["revision"] = revision.Value;
        }

        return new JObject
        {
            ["schema_version"] = "0.1",
            ["drawing"] = drawingObj,
            ["solidworks"] = new JObject
            {
                ["version"] = version,
                ["service_pack"] = servicePack
            },
            ["captured_at"] = capturedAt.ToString("yyyy-MM-ddTHH:mm:ssZ"),
            ["sheets"] = sheetsObj
        };
    }
}

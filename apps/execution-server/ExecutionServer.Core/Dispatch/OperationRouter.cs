using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Dispatch;

public delegate JToken OperationHandler(string document, Operation operation, CancellationToken ct);

/// <summary>
/// Table-driven operation dispatcher (spec 6.5.1, 8.7; ADR-038 CAD-free).
/// Routes operations to registered handlers or fails with BACKEND_CAPABILITY_MISSING.
/// </summary>
public sealed class OperationRouter
{
    public static readonly IReadOnlyList<string> CurrentOperations = new[]
    {
        "document.open",
        "document.close",
        "sheet_format.generate",
        "drawing.create",
        "view.create",
        "view.update",
        "model_items.insert",
        "dimensions.auto_arrange",
        "center_mark.add",
        "dimension.hide",
        "dimension.show",
        "dimension.move",
        "document.save"
    };

    private readonly Dictionary<string, (OperationHandler Handler, OperationInfo Info)> _handlers =
        new Dictionary<string, (OperationHandler, OperationInfo)>(StringComparer.Ordinal);

    public void Register(string op, OperationHandler handler, string schemaVersion = "0.1")
    {
        if (string.IsNullOrWhiteSpace(op)) throw new ArgumentException("Operation name required", nameof(op));
        if (handler == null) throw new ArgumentNullException(nameof(handler));

        var info = new OperationInfo { Op = op, SchemaVersion = schemaVersion };
        _handlers[op] = (handler, info);
    }

    public JToken Route(string document, Operation operation, CancellationToken ct)
    {
        if (operation == null) throw new ArgumentNullException(nameof(operation));

        if (operation.Op != null && _handlers.TryGetValue(operation.Op, out var entry))
        {
            return entry.Handler(document, operation, ct);
        }

        throw new IpcException(
            ErrorCodes.BACKEND_CAPABILITY_MISSING,
            $"Unknown operation '{operation?.Op}'.");
    }

    public IReadOnlyList<OperationInfo> Operations =>
        _handlers.Values.Select(v => v.Info).ToList();
}

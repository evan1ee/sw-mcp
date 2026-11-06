using System;
using System.Collections.Generic;
using System.Threading;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ledger;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ipc;

/// <summary>Runs an <c>ops.apply</c> batch in order, stopping at the first error (spec 8.7).</summary>
public static class OpsBatchRunner
{
    public static OpsApplyResult Run(OpsApplyParams p, OperationLedger ledger, ICommandHandler handler, CancellationToken ct)
    {
        var outcomes = new List<OperationOutcome>();
        foreach (var group in p.Groups)
        {
            foreach (var op in group.Operations)
            {
                outcomes.Add(RunOne(group.Document, op, ledger, handler, ct, out var succeeded));
                if (!succeeded)
                {
                    return new OpsApplyResult { Outcomes = outcomes };
                }
            }
        }

        return new OpsApplyResult { Outcomes = outcomes };
    }

    private static OperationOutcome RunOne(
        string document, Operation op, OperationLedger ledger, ICommandHandler handler, CancellationToken ct, out bool succeeded)
    {
        succeeded = false;
        if (ct.IsCancellationRequested)
        {
            return new OperationOutcome { OperationId = op.OperationId, Error = RpcFrames.Cancelled() };
        }

        if (ledger.TryGet(op.OperationId, out var original))
        {
            return new OperationOutcome
            {
                OperationId = op.OperationId,
                Result = original,
                Error = RpcFrames.MakeError(ErrorCodes.DUPLICATE_OPERATION, "Operation " + op.OperationId + " already completed."),
            };
        }

        if (ledger.TryGetFailure(op.OperationId, out var originalError))
        {
            var details = new JObject();
            if (originalError != null)
            {
                details["original_error"] = originalError;
            }

            return new OperationOutcome
            {
                OperationId = op.OperationId,
                Error = RpcFrames.MakeError(ErrorCodes.DUPLICATE_OPERATION, "Operation " + op.OperationId + " already failed.", details),
            };
        }

        JToken result;
        try
        {
            result = handler.Execute(document, op, ct);
        }
        catch (OperationCanceledException)
        {
            return new OperationOutcome { OperationId = op.OperationId, Error = RpcFrames.Cancelled() };
        }
        catch (IpcException e)
        {
            var err = RpcFrames.FromException(e);
            var effect = ExtractEffect(e.Details);
            if (string.Equals(effect, "applied", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(effect, "unknown", StringComparison.OrdinalIgnoreCase))
            {
                var normEffect = effect?.ToLowerInvariant() ?? "unknown";
                ledger.RecordFailure(document, op.OperationId, e.Code, normEffect, JToken.FromObject(err));
            }

            return new OperationOutcome { OperationId = op.OperationId, Error = err };
        }
        catch (Exception ex) when (!(ex is OutOfMemoryException))
        {
            var err = RpcFrames.MakeError("-32603", "Internal error: " + ex.Message, new JObject { ["effect"] = "unknown" });
            ledger.RecordFailure(document, op.OperationId, "-32603", "unknown", JToken.FromObject(err));
            throw;
        }

        ledger.Record(document, op.OperationId, result);
        succeeded = true;
        return new OperationOutcome { OperationId = op.OperationId, Result = result };
    }

    private static string? ExtractEffect(JToken? details)
    {
        if (details is JObject obj && obj.TryGetValue("effect", StringComparison.OrdinalIgnoreCase, out var val))
        {
            return val?.ToString();
        }
        return null;
    }
}

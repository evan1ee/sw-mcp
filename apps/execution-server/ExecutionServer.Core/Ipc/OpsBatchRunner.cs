using System;
using System.Collections.Generic;
using System.Threading;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ledger;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ipc;

/// <summary>Runs an <c>ops.apply</c> batch in order, stopping at the first error (spec 8.7).</summary>
internal static class OpsBatchRunner
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
            return new OperationOutcome { OperationId = op.OperationId, Error = RpcFrames.FromException(e) };
        }

        ledger.Record(document, op.OperationId, result);
        succeeded = true;
        return new OperationOutcome { OperationId = op.OperationId, Result = result };
    }
}

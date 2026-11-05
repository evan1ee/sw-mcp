using System;
using System.Threading;
using ExecutionServer.Core.Ledger;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ipc;

/// <summary>Runs one command and turns every outcome into the response frame (spec 8.7).</summary>
internal static class CommandExecutor
{
    public static byte[] Execute(QueuedCommand command, OperationLedger ledger, ICommandHandler handler, CancellationToken ct, Action<Exception>? onUnexpected)
    {
        try
        {
            if (command.Snapshot != null)
            {
                return RpcFrames.Result(command.Id, handler.Snapshot(command.Snapshot, ct));
            }

            if (command.Measure != null)
            {
                return RpcFrames.Result(command.Id, handler.MeasurePart(command.Measure, ct));
            }

            var result = OpsBatchRunner.Run(command.Ops!, ledger, handler, ct);
            return RpcFrames.Result(command.Id, JToken.FromObject(result));
        }
        catch (OperationCanceledException)
        {
            return RpcFrames.CatalogueError(command.Id, RpcFrames.Cancelled());
        }
        catch (IpcException e)
        {
            return RpcFrames.CatalogueError(command.Id, RpcFrames.FromException(e));
        }
        catch (Exception ex) when (!(ex is OutOfMemoryException))
        {
            onUnexpected?.Invoke(ex);
            return RpcFrames.Fault(command.Id, RpcFrames.InternalError, "Internal error");
        }
    }
}

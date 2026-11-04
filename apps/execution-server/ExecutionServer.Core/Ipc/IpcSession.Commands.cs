using System.Collections.Generic;
using System.Linq;
using System.Threading;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ipc;

// The command half of the session: queue, UI-thread run loop, cancel (spec 8.7).
public sealed partial class IpcSession
{
    /// <summary>
    /// UI thread: runs one queued command to completion. Returns false if there is none, or if one is
    /// already running. A command already taken finishes even if the session closes meanwhile.
    /// </summary>
    public bool RunNext()
    {
        QueuedCommand command;
        RunningCommand running;
        lock (_gate)
        {
            if (_running != null || _queue.Count == 0)
            {
                return false;
            }

            command = _queue.Dequeue();
            running = new RunningCommand();
            _running = running;
        }

        try
        {
            WriteWhole(command.Id, Execute(command, running.Cancel.Token));
        }
        finally
        {
            List<long> cancels;
            lock (_gate)
            {
                cancels = running.PendingCancels.ToList();
                _running = null;
            }

            // The source is not disposed: it has no timer or wait handle, and Cancel() may still race with this point.
            foreach (var id in cancels)
            {
                WriteWhole(id, RpcFrames.Result(id, new JObject { ["cancelled"] = true }));
            }
        }

        return true;
    }

    // --- commands ---------------------------------------------------------------------------

    private void Enqueue(QueuedCommand command)
    {
        lock (_gate)
        {
            if (_closed)
            {
                return;
            }

            _queue.Enqueue(command);
        }
    }

    private void Cancel(long id)
    {
        List<QueuedCommand> dropped;
        CancellationTokenSource? toCancel = null;
        lock (_gate)
        {
            dropped = _queue.ToList();
            _queue.Clear();
            if (_running != null)
            {
                _running.PendingCancels.Add(id);
                toCancel = _running.Cancel;
            }
        }

        foreach (var command in dropped)
        {
            WriteWhole(command.Id, RpcFrames.CatalogueError(command.Id, RpcFrames.Cancelled()));
        }

        if (toCancel != null)
        {
            toCancel.Cancel(); // the answer follows the running command's own
        }
        else
        {
            WriteWhole(id, RpcFrames.Result(id, new JObject { ["cancelled"] = dropped.Count > 0 }));
        }
    }

    private byte[] Execute(QueuedCommand command, CancellationToken ct) =>
        CommandExecutor.Execute(command, _ledger, _handler, ct, _onUnexpected);
}

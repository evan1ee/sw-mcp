using ExecutionServer.Core.Ipc.Generated;

namespace ExecutionServer.Core.Ipc;

/// <summary>A snapshot, part measure, or ops.apply request waiting for the UI thread.</summary>
internal sealed class QueuedCommand
{
    public QueuedCommand(long id, SnapshotParams? snapshot, OpsApplyParams? ops, PartMeasureParams? measure = null)
    {
        Id = id;
        Snapshot = snapshot;
        Ops = ops;
        Measure = measure;
    }

    public long Id { get; }

    public SnapshotParams? Snapshot { get; }

    public OpsApplyParams? Ops { get; }

    public PartMeasureParams? Measure { get; }
}

/// <summary>The command the UI thread is running.</summary>
internal sealed class RunningCommand
{
    public System.Threading.CancellationTokenSource Cancel { get; } = new System.Threading.CancellationTokenSource();

    /// <summary>job.cancel requests to answer once this command has answered.</summary>
    public System.Collections.Generic.List<long> PendingCancels { get; } = new System.Collections.Generic.List<long>();
}

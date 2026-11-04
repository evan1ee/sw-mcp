using System.Threading;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ipc;

/// <summary>Runs commands on the UI thread. The real one lives in the add-in; Core never sees SOLIDWORKS.</summary>
public interface ICommandHandler
{
    JToken Snapshot(SnapshotParams p, CancellationToken ct);

    /// <summary>Runs one operation. Throws <see cref="IpcException"/> for a failure the core can act on.</summary>
    JToken Execute(string document, Operation op, CancellationToken ct);
}

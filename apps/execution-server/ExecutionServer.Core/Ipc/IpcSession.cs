using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ledger;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ipc;

/// <summary>
/// One pipe connection's protocol state (spec 8.7). Has no threads of its own: the pipe thread calls
/// <see cref="Receive"/>, the UI thread calls <see cref="RunNext"/>. One lock guards the state and is never
/// held while the handler runs or a frame is written.
/// </summary>
public sealed partial class IpcSession
{
    private readonly SessionConfig _config;
    private readonly OperationLedger _ledger;
    private readonly ICommandHandler _handler;
    private readonly IFrameSink _sink;
    private readonly Action<Exception>? _onUnexpected;
    private readonly object _gate = new object();
    private readonly Queue<QueuedCommand> _queue = new Queue<QueuedCommand>();
    private RunningCommand? _running;
    private bool _authenticated;
    private bool _closed;

    /// <param name="onUnexpected">Receives unexpected handler exceptions so the add-in can log the stack trace (G3).</param>
    public IpcSession(SessionConfig config, OperationLedger ledger, ICommandHandler handler, IFrameSink sink, Action<Exception>? onUnexpected = null)
    {
        _config = config ?? throw new ArgumentNullException(nameof(config));
        _ledger = ledger ?? throw new ArgumentNullException(nameof(ledger));
        _handler = handler ?? throw new ArgumentNullException(nameof(handler));
        _sink = sink ?? throw new ArgumentNullException(nameof(sink));
        _onUnexpected = onUnexpected;
    }

    public bool IsClosed
    {
        get
        {
            lock (_gate)
            {
                return _closed;
            }
        }
    }

    /// <summary>Pipe thread: handles one received frame. Never blocks on the UI thread.</summary>
    public void Receive(byte[] payload)
    {
        if (IsClosed)
        {
            return;
        }

        try
        {
            Dispatch(payload);
        }
        catch (Exception ex) when (!(ex is OutOfMemoryException))
        {
            _onUnexpected?.Invoke(ex);
            if (IsAuthenticated())
            {
                WriteWhole(null, RpcFrames.Fault(null, RpcFrames.InternalError, "Internal error"));
            }
            else
            {
                Close(); // an unauthenticated client learns nothing, not even that we failed
            }
        }
    }

    /// <summary>Either thread: sends a notification. Ignored before the handshake and after close.</summary>
    public void Notify(string method, JToken? p)
    {
        lock (_gate)
        {
            if (_closed || !_authenticated)
            {
                return;
            }
        }

        var frame = RpcFrames.Notification(method, p);
        if (frame.Length > _config.MaxFrameBytes)
        {
            throw new InvalidOperationException("Notification " + method + " of " + frame.Length + " bytes is over the frame limit.");
        }

        WriteRaw(frame);
    }

    /// <summary>Pipe thread: the pipe ended or the session must stop. Queued commands are dropped; a running one finishes.</summary>
    public void Close()
    {
        lock (_gate)
        {
            if (_closed)
            {
                return;
            }

            _closed = true;
            _queue.Clear();
        }

        try
        {
            _sink.Close();
        }
        catch (Exception ex) when (ex is IOException || ex is ObjectDisposedException)
        {
            // The pipe is already gone, which is what Close wanted.
        }
    }

    public override string ToString()
    {
        lock (_gate)
        {
            return "IpcSession(authenticated=" + _authenticated + ", closed=" + _closed + ", queued=" + _queue.Count + ")";
        }
    }

    // --- dispatch ---------------------------------------------------------------------------

    private void Dispatch(byte[] payload)
    {
        JToken frame;
        try
        {
            frame = RpcFrames.Parse(payload);
        }
        catch (Exception ex) when (ex is JsonException || ex is ArgumentException)
        {
            RejectUnreadable();
            return;
        }

        var id = RpcFrames.IdOf(frame);
        var method = IsRequest(frame, id) ? frame["method"]!.Value<string>()! : null;
        if (!IsAuthenticated())
        {
            if (method == "session.hello")
            {
                Handshake(id!.Value, frame["params"]);
            }
            else
            {
                Close(); // an unauthenticated client learns nothing
            }

            return;
        }

        if (method == null)
        {
            WriteWhole(id, RpcFrames.Fault(id, RpcFrames.InvalidRequest, "Invalid Request"));
            return;
        }

        Route(id!.Value, method, frame["params"]);
    }

    private void RejectUnreadable()
    {
        if (IsAuthenticated())
        {
            WriteWhole(null, RpcFrames.Fault(null, RpcFrames.ParseError, "Parse error"));
        }
        else
        {
            Close();
        }
    }

    private static bool IsRequest(JToken frame, long? id) =>
        id != null
        && frame is JObject o
        && o["jsonrpc"] is JValue v && v.Type == JTokenType.String && (string?)v.Value == "2.0"
        && o["method"] is JValue m && m.Type == JTokenType.String;

    private bool IsAuthenticated()
    {
        lock (_gate)
        {
            return _authenticated;
        }
    }

    private void Route(long id, string method, JToken? p)
    {
        switch (method)
        {
            case "session.hello":
                Handshake(id, p);
                break;
            case "session.ping":
                if (TryParams<PingParams>(id, p, required: false, out _))
                {
                    WriteWhole(id, RpcFrames.Result(id, new JObject { ["pong"] = true }));
                }

                break;
            case "session.completed_operations":
                if (TryParams<CompletedOperationsParams>(id, p, required: false, out _))
                {
                    WriteWhole(id, RpcFrames.Result(id, new JObject { ["operation_ids"] = new JArray(_ledger.CompletedIds()) }));
                }

                break;
            case "job.cancel":
                if (TryParams<JobCancelParams>(id, p, required: false, out _))
                {
                    Cancel(id);
                }

                break;
            case "drawing.snapshot":
                if (TryParams<SnapshotParams>(id, p, required: true, out var snapshot))
                {
                    Enqueue(new QueuedCommand(id, snapshot, null));
                }

                break;
            case "ops.apply":
                if (TryParams<OpsApplyParams>(id, p, required: true, out var ops) && RpcParams.HasValidShape(ops!))
                {
                    Enqueue(new QueuedCommand(id, null, ops));
                }
                else if (ops != null)
                {
                    WriteWhole(id, RpcFrames.Fault(id, RpcFrames.InvalidParams, "Invalid params"));
                }

                break;
            default:
                WriteWhole(id, RpcFrames.Fault(id, RpcFrames.MethodNotFound, "Method not found"));
                break;
        }
    }

    private bool TryParams<T>(long id, JToken? p, bool required, out T? result)
        where T : class, new()
    {
        if (RpcParams.TryRead(p, required, out result))
        {
            return true;
        }

        WriteWhole(id, RpcFrames.Fault(id, RpcFrames.InvalidParams, "Invalid params"));
        return false;
    }

    // --- handshake --------------------------------------------------------------------------

    private void Handshake(long id, JToken? p)
    {
        HelloParams? hello = null;
        try
        {
            hello = p is JObject ? p.ToObject<HelloParams>(RpcFrames.Serializer) : null;
        }
        catch (Exception ex) when (!(ex is OutOfMemoryException))
        {
            // Any failure reading hello is treated like a wrong token below.
        }

        if (hello == null || !ConstantTime.TextEquals(_config.Token, hello.Token))
        {
            Close();
            return;
        }

        if (RpcFrames.MajorOf(hello.Protocol) != RpcFrames.MajorOf(ProtocolVersion.Current))
        {
            var message = "Protocol " + hello.Protocol + " is not supported; this add-in speaks " + RpcFrames.MajorOf(ProtocolVersion.Current) + ".x.";
            WriteWhole(id, RpcFrames.CatalogueError(id, RpcFrames.MakeError(ErrorCodes.BACKEND_VERSION_UNSUPPORTED, message)));
            Close();
            return;
        }

        if (!_config.VersionSupported)
        {
            WriteWhole(id, RpcFrames.CatalogueError(id, RpcFrames.MakeError(ErrorCodes.BACKEND_VERSION_UNSUPPORTED, _config.UnsupportedMessage)));
            return;
        }

        lock (_gate)
        {
            _authenticated = true;
        }

        WriteWhole(id, RpcFrames.Result(id, _config.HelloResultJson.DeepClone()));
    }

    // --- output -----------------------------------------------------------------------------

    /// <summary>Writes a response as one frame, or as chunks when it is over the limit.</summary>
    private void WriteWhole(long? id, byte[] response)
    {
        if (response.Length <= _config.MaxFrameBytes || id == null)
        {
            WriteRaw(response);
            return;
        }

        foreach (var chunk in ChunkWriter.Split(id.Value, response, _config.MaxFrameBytes))
        {
            WriteRaw(chunk);
        }
    }

    private void WriteRaw(byte[] frame)
    {
        if (IsClosed)
        {
            return;
        }

        try
        {
            _sink.Write(frame);
        }
        catch (Exception ex) when (ex is IOException || ex is ObjectDisposedException)
        {
            Close(); // the pipe broke under us
        }
    }
}

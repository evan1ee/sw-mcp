using System.Collections.Generic;
using System.Text;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ledger;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Tests.Support;

/// <summary>Builders shared by the session tests.</summary>
public static class Rpc
{
    public const string Token = "tok-unit-test-9c41";

    public static byte[] Bytes(JToken frame) => Encoding.UTF8.GetBytes(frame.ToString(Newtonsoft.Json.Formatting.None));

    public static byte[] Request(long id, string method, JToken? p = null)
    {
        var o = new JObject { ["jsonrpc"] = "2.0", ["id"] = id, ["method"] = method };
        if (p != null)
        {
            o["params"] = p;
        }

        return Bytes(o);
    }

    public static byte[] Hello(long id = 1, string token = Token, string protocol = "0.1") =>
        Request(id, "session.hello", new JObject { ["token"] = token, ["protocol"] = protocol });

    public static HelloResult HelloResult() => new HelloResult
    {
        Protocol = "0.1",
        AddinVersion = "0.1.0",
        Solidworks = new SolidWorksInfo { Version = "2025", ServicePack = "SP3.0", UiLanguage = "en-US" },
        Capabilities = new List<string> { "drawing.snapshot", "ops.apply" },
        Operations = new List<OperationInfo> { new OperationInfo { Op = "document.open", SchemaVersion = "0.1" } },
    };

    public static SessionConfig Config(int maxFrameBytes = 64 * 1024 * 1024, string token = Token) =>
        new SessionConfig(token, HelloResult(), true, "unsupported", maxFrameBytes);

    public static JObject SnapshotParams(string document = "C:/d/x.slddrw") => new JObject { ["document"] = document };
    public static JObject PartMeasureParams(string document = "C:/d/plate.sldprt") => new JObject { ["document"] = document };

    public static JObject OpsParams(string document, params string[] operationIds)
    {
        var ops = new JArray();
        foreach (var id in operationIds)
        {
            ops.Add(new JObject
            {
                ["operation_id"] = id,
                ["op"] = "document.open",
                ["params"] = new JObject { ["path"] = document, ["read_only"] = false, ["fully_resolved"] = true },
            });
        }

        return new JObject
        {
            ["groups"] = new JArray(new JObject { ["document"] = document, ["operations"] = ops }),
        };
    }
}

/// <summary>A session already past the handshake, with its collaborators.</summary>
public sealed class Harness
{
    public Harness(int maxFrameBytes = 64 * 1024 * 1024, OperationLedger? ledger = null, ScriptedHandler? handler = null)
    {
        Ledger = ledger ?? new OperationLedger();
        Handler = handler ?? new ScriptedHandler();
        Sink = new RecordingSink();
        Session = new IpcSession(Rpc.Config(maxFrameBytes), Ledger, Handler, Sink, ex => Unexpected.Add(ex));
        Handler.Session = Session;
        Session.Receive(Rpc.Hello());
    }

    public OperationLedger Ledger { get; }

    public ScriptedHandler Handler { get; }

    public RecordingSink Sink { get; }

    public IpcSession Session { get; }

    public List<System.Exception> Unexpected { get; } = new List<System.Exception>();

    public JToken Last => Sink.Frames[Sink.Frames.Count - 1];
}

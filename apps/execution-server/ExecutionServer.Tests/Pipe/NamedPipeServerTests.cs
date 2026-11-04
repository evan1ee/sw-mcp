using System;
using System.Collections.Concurrent;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using ExecutionServer.AddIn.Dispatch;
using ExecutionServer.AddIn.Pipe;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ledger;
using ExecutionServer.Tests.Support;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests.Pipe;

public sealed class NamedPipeServerTests
{
    private const string SecretToken = "test-token-12345";

    private sealed class TrackingSyncContext : SynchronizationContext
    {
        public ConcurrentQueue<Action> PostedActions { get; } = new ConcurrentQueue<Action>();
        public int PostCount => PostedActions.Count;
        public bool AutoExecute { get; set; }

        public override void Post(SendOrPostCallback d, object? state)
        {
            Action action = () => d(state);
            PostedActions.Enqueue(action);
            if (AutoExecute)
            {
                action();
            }
        }
    }

    private static (NamedPipeServer server, TrackingSyncContext syncContext, string pipeName) CreateServer(TimeSpan? uiTimeout = null, bool autoExecute = true)
    {
        var syncContext = new TrackingSyncContext { AutoExecute = autoExecute };
        var dispatcher = new UIThreadDispatcher(syncContext, uiTimeout);
        var pipeName = "test-pipe-" + Guid.NewGuid().ToString("N");
        var config = Rpc.Config(token: SecretToken);
        var ledger = new OperationLedger();
        var handler = new ScriptedHandler();
        handler.OnSnapshot = (p, ct) => new JObject { ["schema_version"] = "0.1", ["sheets"] = new JObject() };

        var server = new NamedPipeServer(pipeName, config, ledger, handler, dispatcher);
        return (server, syncContext, pipeName);
    }

    private static byte[] SendAndReceiveFrame(NamedPipeClientStream client, byte[] payload)
    {
        var encoded = FrameCodec.Encode(payload, 64 * 1024 * 1024);
        client.Write(encoded, 0, encoded.Length);
        client.Flush();
        return FrameCodec.Read(client, 64 * 1024 * 1024)!;
    }

    [Fact]
    public void PipeServer_RejectsFirstFrameIfNotHello()
    {
        var (server, _, pipeName) = CreateServer();
        using (server)
        using (var client = new NamedPipeClientStream(".", pipeName, PipeDirection.InOut))
        {
            client.Connect(5000);

            // Send ping instead of hello as first frame
            var ping = Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(new
            {
                jsonrpc = "2.0",
                id = 1,
                method = "session.ping"
            }));

            var encoded = FrameCodec.Encode(ping, 64 * 1024 * 1024);
            client.Write(encoded, 0, encoded.Length);
            client.Flush();

            // Client should read EOF because server closes pipe immediately
            var reply = FrameCodec.Read(client, 64 * 1024 * 1024);
            Assert.Null(reply);
        }
    }

    [Fact]
    public void PipeServer_HandlesPingOnPipeThread()
    {
        var (server, syncContext, pipeName) = CreateServer(autoExecute: false);
        using (server)
        using (var client = new NamedPipeClientStream(".", pipeName, PipeDirection.InOut))
        {
            client.Connect(5000);

            // 1. Handshake
            var helloPayload = Rpc.Hello(1, SecretToken);
            var helloReply = SendAndReceiveFrame(client, helloPayload);
            var helloJson = JObject.Parse(Encoding.UTF8.GetString(helloReply));
            Assert.NotNull(helloJson["result"]);

            // 2. Ping
            var pingPayload = Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(new
            {
                jsonrpc = "2.0",
                id = 2,
                method = "session.ping"
            }));
            var pingReply = SendAndReceiveFrame(client, pingPayload);
            var pingJson = JObject.Parse(Encoding.UTF8.GetString(pingReply));
            Assert.True(pingJson["result"]?["pong"]?.Value<bool>());

            // Ping should NOT post to the UI thread
            Assert.Equal(0, syncContext.PostCount);
        }
    }

    [Fact]
    public void PipeServer_DispatchesCommandsToSynchronizationContext()
    {
        var (server, syncContext, pipeName) = CreateServer(autoExecute: false);
        using (server)
        using (var client = new NamedPipeClientStream(".", pipeName, PipeDirection.InOut))
        {
            client.Connect(5000);

            // 1. Handshake
            SendAndReceiveFrame(client, Rpc.Hello(1, SecretToken));

            // 2. Send snapshot command (must be dispatched to UI thread)
            var cmdPayload = Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(new
            {
                jsonrpc = "2.0",
                id = 2,
                method = "drawing.snapshot",
                @params = new { document = "doc1" }
            }));
            var encoded = FrameCodec.Encode(cmdPayload, 64 * 1024 * 1024);
            client.Write(encoded, 0, encoded.Length);
            client.Flush();

            // Wait for command to be posted to TrackingSyncContext
            var deadline = DateTime.UtcNow.AddSeconds(5);
            while (syncContext.PostCount == 0 && DateTime.UtcNow < deadline)
            {
                Thread.Sleep(10);
            }
            Assert.Equal(1, syncContext.PostCount);

            // Execute the posted UI thread callback
            Assert.True(syncContext.PostedActions.TryDequeue(out var action));
            action();

            // Read the snapshot reply
            var reply = FrameCodec.Read(client, 64 * 1024 * 1024);
            Assert.NotNull(reply);
            var json = JObject.Parse(Encoding.UTF8.GetString(reply));
            Assert.Equal(2, json["id"]?.Value<long>());
            Assert.Equal("0.1", json["result"]?["schema_version"]?.Value<string>());
        }
    }

    [Fact]
    public void PipeServer_EnforcesUiBlockedTimeout()
    {
        // 100 ms timeout for UI blocked
        var (server, syncContext, pipeName) = CreateServer(uiTimeout: TimeSpan.FromMilliseconds(100), autoExecute: false);
        using (server)
        using (var client = new NamedPipeClientStream(".", pipeName, PipeDirection.InOut))
        {
            client.Connect(5000);

            // 1. Handshake
            SendAndReceiveFrame(client, Rpc.Hello(1, SecretToken));

            // 2. Send snapshot command without running the posted UI action immediately
            var cmdPayload = Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(new
            {
                jsonrpc = "2.0",
                id = 2,
                method = "drawing.snapshot",
                @params = new { document = "doc1" }
            }));
            var encoded = FrameCodec.Encode(cmdPayload, 64 * 1024 * 1024);
            client.Write(encoded, 0, encoded.Length);
            client.Flush();

            // Wait for ui_blocked notification before executing the UI action
            var firstFrame = FrameCodec.Read(client, 64 * 1024 * 1024);
            Assert.NotNull(firstFrame);
            var notificationJson = JObject.Parse(Encoding.UTF8.GetString(firstFrame));
            Assert.Equal("session.ui_blocked", notificationJson["method"]?.Value<string>());
            Assert.True(notificationJson["params"]?["waited_ms"]?.Value<long>() >= 100);

            // Now run the posted UI callback
            Assert.True(syncContext.PostedActions.TryDequeue(out var action));
            action();

            // Now read the command result
            var resultFrame = FrameCodec.Read(client, 64 * 1024 * 1024);
            Assert.NotNull(resultFrame);
            var resultJson = JObject.Parse(Encoding.UTF8.GetString(resultFrame));
            Assert.Equal(2, resultJson["id"]?.Value<long>());
            Assert.Equal("0.1", resultJson["result"]?["schema_version"]?.Value<string>());
        }
    }
}

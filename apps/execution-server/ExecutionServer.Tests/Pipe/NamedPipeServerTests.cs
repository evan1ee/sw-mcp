using System;
using System.Collections.Concurrent;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using ExecutionServer.Core.Dispatch;
using ExecutionServer.Core.Pipe;
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

    private sealed class BlockingStream : Stream
    {
        public ManualResetEventSlim WriteStarted { get; } = new ManualResetEventSlim(false);
        public ManualResetEventSlim AllowWriteToComplete { get; } = new ManualResetEventSlim(false);

        public override bool CanRead => false;
        public override bool CanSeek => false;
        public override bool CanWrite => true;
        public override long Length => 0;
        public override long Position { get => 0; set { } }
        public override void Flush() { }
        public override int Read(byte[] buffer, int offset, int count) => 0;
        public override long Seek(long offset, SeekOrigin origin) => 0;
        public override void SetLength(long value) { }

        public override void Write(byte[] buffer, int offset, int count)
        {
            WriteStarted.Set();
            AllowWriteToComplete.Wait(5000);
        }
    }

    [Fact]
    public void PartMeasure_RunsThroughSession()
    {
        var sink = new RecordingSink();
        var config = Rpc.Config();
        var ledger = new OperationLedger();
        var handler = new ScriptedHandler();
        handler.OnMeasure = (p, ct) => new JObject { ["path"] = p.Document, ["volume_m3"] = 1.0 };
        var session = new IpcSession(config, ledger, handler, sink);

        session.Receive(Rpc.Hello(1, config.Token));
        session.Receive(Rpc.Request(2, "part.measure", Rpc.PartMeasureParams("D:/work/plate.sldprt")));

        Assert.True(session.HasQueuedCommands);
        var ran = session.RunNext();
        Assert.True(ran);
        Assert.Single(handler.MeasureCalls);
        Assert.Equal("D:/work/plate.sldprt", handler.MeasureCalls[0]);
    }

    [Fact]
    public void ResponseWrite_DoesNotBlockTheCommandThread()
    {
        var blockingStream = new BlockingStream();
        using var sink = new PipeFrameSink(blockingStream, 64 * 1024 * 1024);

        var config = Rpc.Config();
        var ledger = new OperationLedger();
        var handler = new ScriptedHandler();
        handler.OnSnapshot = (p, ct) => new JObject { ["schema_version"] = "0.1" };
        var session = new IpcSession(config, ledger, handler, sink);

        session.Receive(Rpc.Hello(1, config.Token));
        session.Receive(Rpc.Request(2, "drawing.snapshot", Rpc.SnapshotParams()));

        var sw = System.Diagnostics.Stopwatch.StartNew();
        // RunNext on the command thread
        var ran = session.RunNext();
        sw.Stop();

        Assert.True(ran);
        // Command thread should NOT be blocked by the stalled stream write
        Assert.True(sw.ElapsedMilliseconds < 500, $"RunNext took {sw.ElapsedMilliseconds}ms, should be < 500ms");

        // Allow writer to exit cleanly
        blockingStream.AllowWriteToComplete.Set();
    }

    [Fact]
    public void Frames_KeepTheirOrder()
    {
        using var ms = new MemoryStream();
        using (var sink = new PipeFrameSink(ms, 64 * 1024 * 1024, leaveOpen: true))
        {
            for (int i = 1; i <= 5; i++)
            {
                var payload = Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(new { seq = i }));
                sink.Write(payload);
            }
            sink.Close();
        }

        ms.Position = 0;
        for (int i = 1; i <= 5; i++)
        {
            var frame = FrameCodec.Read(ms, 64 * 1024 * 1024);
            Assert.NotNull(frame);
            var json = JObject.Parse(Encoding.UTF8.GetString(frame));
            Assert.Equal(i, json["seq"]?.Value<int>());
        }
        Assert.Null(FrameCodec.Read(ms, 64 * 1024 * 1024));
    }

    [Fact]
    public void Close_FlushesOrFailsQueuedFrames()
    {
        using var ms = new MemoryStream();
        var sink = new PipeFrameSink(ms, 64 * 1024 * 1024, leaveOpen: true);

        var payload1 = Encoding.UTF8.GetBytes("frame-1");
        var payload2 = Encoding.UTF8.GetBytes("frame-2");
        sink.Write(payload1);
        sink.Write(payload2);

        // Close flushes queued frames
        sink.Close();

        ms.Position = 0;
        var r1 = FrameCodec.Read(ms, 64 * 1024 * 1024);
        var r2 = FrameCodec.Read(ms, 64 * 1024 * 1024);
        Assert.NotNull(r1);
        Assert.NotNull(r2);
        Assert.Equal("frame-1", Encoding.UTF8.GetString(r1));
        Assert.Equal("frame-2", Encoding.UTF8.GetString(r2));

        // Additional writes after Close should fail/be dropped without throwing
        sink.Write(Encoding.UTF8.GetBytes("frame-3"));
        Assert.Null(FrameCodec.Read(ms, 64 * 1024 * 1024));
    }
}

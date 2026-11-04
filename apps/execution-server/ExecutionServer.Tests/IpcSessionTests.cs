using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ledger;
using ExecutionServer.Tests.Support;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests;

public sealed class IpcSessionTests
{
    private const string Secret = "SECRET-TOKEN-do-not-leak-7731";

    [Fact]
    public void Token_never_appears_in_exception_or_ToString()
    {
        var texts = new List<string>();
        var config = Rpc.Config(token: Secret);
        var sink = new RecordingSink();
        var handler = new ScriptedHandler();
        var session = new IpcSession(config, new OperationLedger(), handler, sink, ex => texts.Add(ex.ToString()));
        handler.Session = session;
        texts.Add(config.ToString());
        texts.Add(session.ToString());

        Assert.ThrowsAny<Exception>(() => new SessionConfig(Secret, Rpc.HelloResult(), true, "m", 3));
        try
        {
            _ = new SessionConfig(Secret, Rpc.HelloResult(), true, "m", 3);
        }
        catch (Exception ex)
        {
            texts.Add(ex.ToString());
        }

        session.Receive(Rpc.Hello(1, Secret));
        session.Receive(Rpc.Request(2, "drawing.snapshot", Rpc.SnapshotParams()));
        handler.OnSnapshot = (p, ct) => throw new InvalidOperationException("handler failed");
        session.RunNext();
        session.Receive(Encoding.UTF8.GetBytes("{\"token\":\"" + Secret + "\" nope"));
        session.Receive(Rpc.Request(3, "session.hello", new JObject { ["token"] = Secret + "x", ["protocol"] = "0.1" }));
        texts.AddRange(sink.Payloads.Select(p => Encoding.UTF8.GetString(p)).Where(t => !t.Contains("\"result\":{\"protocol\"")));
        texts.Add(config.ToString());
        texts.Add(session.ToString());

        Assert.All(texts, t => Assert.DoesNotContain(Secret, t));
    }

    [Fact]
    public void Constant_time_compare_handles_length_mismatch()
    {
        Assert.True(ConstantTime.TextEquals("abc", "abc"));
        Assert.True(ConstantTime.TextEquals(string.Empty, string.Empty));
        Assert.False(ConstantTime.TextEquals("abc", "abcd"));
        Assert.False(ConstantTime.TextEquals("abcd", "abc"));
        Assert.False(ConstantTime.TextEquals(string.Empty, "a"));
        Assert.False(ConstantTime.TextEquals("a", string.Empty));
        Assert.False(ConstantTime.TextEquals("abc", "abd"));
    }

    [Fact]
    public void Wrong_token_closes_without_a_reply_and_session_stays_closed()
    {
        var sink = new RecordingSink();
        var session = new IpcSession(Rpc.Config(), new OperationLedger(), new ScriptedHandler(), sink);

        session.Receive(Rpc.Hello(1, "wrong"));
        session.Receive(Rpc.Hello(2));

        Assert.True(session.IsClosed);
        Assert.Empty(sink.Payloads);
        Assert.Equal(1, sink.CloseCount);
    }

    private sealed class ThrowingSink : IFrameSink
    {
        public int Writes { get; private set; }

        public int Closes { get; private set; }

        public void Write(byte[] payload)
        {
            Writes++;
            throw new InvalidOperationException("sink failed");
        }

        public void Close() => Closes++;
    }

    [Fact]
    public void Unexpected_exception_before_auth_closes_without_a_reply()
    {
        var sink = new ThrowingSink();
        var seen = new List<Exception>();
        var session = new IpcSession(Rpc.Config(), new OperationLedger(), new ScriptedHandler(), sink, seen.Add);

        session.Receive(Rpc.Hello(1, protocol: "9.0")); // writes a mismatch error, which throws

        Assert.Single(seen);
        Assert.Equal(1, sink.Writes); // the one attempt; no -32603 fault followed
        Assert.True(session.IsClosed);
        Assert.Equal(1, sink.Closes);
    }

    [Fact]
    public void Unparsable_first_frame_closes_without_a_reply()
    {
        var sink = new RecordingSink();
        var session = new IpcSession(Rpc.Config(), new OperationLedger(), new ScriptedHandler(), sink);

        session.Receive(Encoding.UTF8.GetBytes("{oops"));

        Assert.True(session.IsClosed);
        Assert.Empty(sink.Payloads);
    }

    [Fact]
    public void Repeated_hello_after_ready_is_answered_again()
    {
        var h = new Harness();

        h.Session.Receive(Rpc.Hello(5));

        Assert.Equal(5, h.Last.Value<long>("id"));
        Assert.Equal("0.1", h.Last["result"]!.Value<string>("protocol"));
    }

    [Fact]
    public void Requests_after_close_ignored()
    {
        var h = new Harness();
        var before = h.Sink.Payloads.Count;

        h.Session.Close();
        h.Session.Close();
        h.Session.Receive(Rpc.Request(2, "session.ping"));

        Assert.True(h.Session.IsClosed);
        Assert.Equal(before, h.Sink.Payloads.Count);
        Assert.Equal(1, h.Sink.CloseCount);
    }

    [Fact]
    public void Parse_failure_answers_minus_32700_with_null_id()
    {
        var h = new Harness();

        h.Session.Receive(Encoding.UTF8.GetBytes("{not json"));

        Assert.Equal(JTokenType.Null, h.Last["id"]!.Type);
        Assert.Equal(-32700, h.Last["error"]!.Value<int>("code"));
        Assert.Null(h.Last["error"]!["data"]);
    }

    [Theory]
    [InlineData("[]", null)]
    [InlineData("\"text\"", null)]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":7}", 7L)]
    [InlineData("{\"jsonrpc\":\"2.0\",\"method\":\"session.ping\"}", null)]
    [InlineData("{\"jsonrpc\":\"1.0\",\"id\":3,\"method\":\"session.ping\"}", 3L)]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1.5,\"method\":\"session.ping\"}", null)]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":\"a\",\"method\":\"session.ping\"}", null)]
    public void Non_request_shape_answers_minus_32600(string json, long? expectedId)
    {
        var h = new Harness();

        h.Session.Receive(Encoding.UTF8.GetBytes(json));

        Assert.Equal(-32600, h.Last["error"]!.Value<int>("code"));
        if (expectedId == null)
        {
            Assert.Equal(JTokenType.Null, h.Last["id"]!.Type);
        }
        else
        {
            Assert.Equal(expectedId, h.Last.Value<long>("id"));
        }
    }

    [Theory]
    [InlineData("drawing.snapshot", "{}")]
    [InlineData("drawing.snapshot", "[]")]
    [InlineData("ops.apply", "{\"groups\":[]}")]
    [InlineData("ops.apply", "{\"groups\":[{\"document\":\"d\",\"operations\":[]}]}")]
    [InlineData("session.ping", "[]")]
    public void Invalid_params_answer_minus_32602(string method, string paramsJson)
    {
        var h = new Harness();

        h.Session.Receive(Rpc.Request(2, method, Fixtures.Parse(paramsJson)));

        Assert.Equal(-32602, h.Last["error"]!.Value<int>("code"));
        Assert.False(h.Session.RunNext());
    }

    [Fact]
    public void Unknown_method_answers_minus_32601()
    {
        var h = new Harness();

        h.Session.Receive(Rpc.Request(2, "nope.nope"));

        Assert.Equal(-32601, h.Last["error"]!.Value<int>("code"));
    }

    [Fact]
    public void Ping_answered_without_RunNext()
    {
        var h = new Harness();

        h.Session.Receive(Rpc.Request(2, "session.ping", new JObject()));

        Assert.True(h.Last["result"]!.Value<bool>("pong"));
    }

    [Fact]
    public void Completed_operations_answered_without_RunNext()
    {
        var h = new Harness();
        h.Ledger.Record("d", "a:1", null);
        h.Ledger.Record("d", "a:2", null);

        h.Session.Receive(Rpc.Request(2, "session.completed_operations"));

        Assert.Equal(new[] { "a:1", "a:2" }, h.Last["result"]!["operation_ids"]!.Select(t => t.Value<string>()).ToArray());
    }

    [Fact]
    public void Commands_run_one_at_a_time_in_order()
    {
        var h = new Harness();
        var running = 0;
        var overlap = false;
        h.Handler.OnSnapshot = (p, ct) =>
        {
            overlap |= Interlocked.Increment(ref running) > 1;
            Interlocked.Decrement(ref running);
            return new JObject { ["document"] = p.Document };
        };
        var baseline = h.Sink.Payloads.Count;

        foreach (var id in new long[] { 2, 3, 4 })
        {
            h.Session.Receive(Rpc.Request(id, "drawing.snapshot", Rpc.SnapshotParams("doc" + id)));
        }

        Assert.Equal(baseline, h.Sink.Payloads.Count);
        Assert.True(h.Session.RunNext());
        Assert.True(h.Session.RunNext());
        Assert.True(h.Session.RunNext());
        Assert.False(h.Session.RunNext());
        Assert.False(overlap);
        Assert.Equal(new[] { "doc2", "doc3", "doc4" }, h.Handler.SnapshotCalls);
        Assert.Equal(new long[] { 2, 3, 4 }, h.Sink.Frames.Skip(1).Select(f => f.Value<long>("id")).ToArray());
    }

    [Fact]
    public void Parallel_receive_and_runnext_answer_each_once()
    {
        const int Count = 300;
        var h = new Harness();
        var producer = new Thread(() =>
        {
            for (var id = 2; id < 2 + Count; id++)
            {
                h.Session.Receive(Rpc.Request(id, "drawing.snapshot", Rpc.SnapshotParams("d" + id)));
                h.Session.Receive(Rpc.Request(1000 + id, "session.ping"));
            }
        });

        producer.Start();
        while (true)
        {
            if (h.Session.RunNext())
            {
                continue;
            }

            if (!producer.IsAlive && !h.Session.RunNext())
            {
                break;
            }

            Thread.Yield();
        }

        producer.Join();

        var ids = h.Sink.Frames.Skip(1).Select(f => f.Value<long>("id")).ToList();
        Assert.Equal(Count * 2, ids.Count);
        Assert.Equal(ids.Count, ids.Distinct().Count());
        Assert.Equal(Count, h.Handler.SnapshotCalls.Count);
        var order = ids.Where(i => i < 1000).ToList();
        Assert.Equal(order.OrderBy(x => x).ToList(), order);
    }

    [Fact]
    public void Cancel_when_idle_answers_false()
    {
        var h = new Harness();

        h.Session.Receive(Rpc.Request(2, "job.cancel", new JObject()));

        Assert.False(h.Last["result"]!.Value<bool>("cancelled"));
    }

    [Fact]
    public void Cancel_of_queued_command_answers_it_first_then_true()
    {
        var h = new Harness();
        h.Session.Receive(Rpc.Request(2, "drawing.snapshot", Rpc.SnapshotParams()));

        h.Session.Receive(Rpc.Request(3, "job.cancel"));

        var frames = h.Sink.Frames.Skip(1).ToList();
        Assert.Equal(2, frames[0].Value<long>("id"));
        Assert.Equal("EXEC_CANCELLED", frames[0]["error"]!["data"]!.Value<string>("code"));
        Assert.Equal(3, frames[1].Value<long>("id"));
        Assert.True(frames[1]["result"]!.Value<bool>("cancelled"));
        Assert.False(h.Session.RunNext());
    }

    [Fact]
    public void Cancel_stops_batch_with_exec_cancelled_outcome()
    {
        var h = new Harness();
        h.Handler.OnExecute = (doc, op, ct) =>
        {
            h.Session.Receive(Rpc.Request(9, "job.cancel"));
            return new JObject { ["owned"] = true };
        };
        h.Session.Receive(Rpc.Request(2, "ops.apply", Rpc.OpsParams("d", "j:1", "j:2", "j:3")));

        h.Session.RunNext();

        var frames = h.Sink.Frames.Skip(1).ToList();
        Assert.Equal(2, frames.Count);
        Assert.Equal(2, frames[0].Value<long>("id"));
        var outcomes = (JArray)frames[0]["result"]!["outcomes"]!;
        Assert.Equal(2, outcomes.Count);
        Assert.Equal("EXEC_CANCELLED", outcomes[1]["error"]!.Value<string>("code"));
        Assert.Equal("j:2", outcomes[1].Value<string>("operation_id"));
        Assert.Equal(9, frames[1].Value<long>("id"));
        Assert.True(frames[1]["result"]!.Value<bool>("cancelled"));
        Assert.Equal(new[] { "j:1" }, h.Ledger.CompletedIds());
        Assert.Single(h.Handler.ExecuteCalls);
    }

    [Fact]
    public void Handler_exception_answers_minus_32603_without_stack_trace()
    {
        var h = new Harness();
        h.Handler.OnSnapshot = (p, ct) => throw new InvalidOperationException("boom at C:/secret/path");
        h.Session.Receive(Rpc.Request(2, "drawing.snapshot", Rpc.SnapshotParams()));

        h.Session.RunNext();

        var text = h.Last.ToString();
        Assert.Equal(-32603, h.Last["error"]!.Value<int>("code"));
        Assert.Null(h.Last["error"]!["data"]);
        Assert.DoesNotContain("boom", text);
        Assert.DoesNotContain("   at ", text);
        Assert.Single(h.Unexpected);
    }

    [Fact]
    public void Handler_ipc_exception_answers_catalogue_error()
    {
        var h = new Harness();
        h.Handler.OnSnapshot = (p, ct) => throw new IpcException("EXEC_NOT_FOUND", "no such sheet", new JObject { ["sheet"] = "S9" });
        h.Session.Receive(Rpc.Request(2, "drawing.snapshot", Rpc.SnapshotParams()));

        h.Session.RunNext();

        var error = h.Last["error"]!;
        Assert.Equal(-32000, error.Value<int>("code"));
        Assert.Equal("EXEC_NOT_FOUND", error["data"]!.Value<string>("code"));
        Assert.Equal("S9", error["data"]!["details"]!.Value<string>("sheet"));
    }

    [Fact]
    public void Completed_ops_survive_unexpected_exception()
    {
        var h = new Harness();
        h.Handler.OnExecute = (doc, op, ct) =>
            op.OperationId == "j:2" ? throw new InvalidOperationException("boom") : new JObject();
        h.Session.Receive(Rpc.Request(2, "ops.apply", Rpc.OpsParams("d", "j:1", "j:2", "j:3")));

        h.Session.RunNext();
        h.Session.Receive(Rpc.Request(3, "session.completed_operations"));

        Assert.Equal(-32603, h.Sink.Frames[1]["error"]!.Value<int>("code"));
        Assert.Equal(new[] { "j:1" }, h.Last["result"]!["operation_ids"]!.Select(t => t.Value<string>()).ToArray());
    }

    [Fact]
    public void Duplicate_does_not_call_handler()
    {
        var h = new Harness();
        h.Ledger.Record("d", "j:1", new JObject { ["owned"] = true });
        h.Session.Receive(Rpc.Request(2, "ops.apply", Rpc.OpsParams("d", "j:1", "j:2")));

        h.Session.RunNext();

        var outcomes = (JArray)h.Last["result"]!["outcomes"]!;
        Assert.Single(outcomes);
        Assert.Equal("DUPLICATE_OPERATION", outcomes[0]["error"]!.Value<string>("code"));
        Assert.True(outcomes[0]["result"]!.Value<bool>("owned"));
        Assert.Empty(h.Handler.ExecuteCalls);
    }

    [Fact]
    public void Failed_operation_is_not_recorded_and_stops_the_batch()
    {
        var h = new Harness();
        h.Handler.OnExecute = (doc, op, ct) =>
            op.OperationId == "j:2" ? throw new IpcException("AUTH_PATH_DENIED", "denied") : new JObject();
        h.Session.Receive(Rpc.Request(2, "ops.apply", Rpc.OpsParams("d", "j:1", "j:2", "j:3")));

        h.Session.RunNext();

        Assert.Equal(2, ((JArray)h.Last["result"]!["outcomes"]!).Count);
        Assert.Equal(new[] { "j:1" }, h.Ledger.CompletedIds());
    }

    [Fact]
    public void Command_running_at_close_records_in_ledger()
    {
        var h = new Harness();
        h.Handler.OnExecute = (doc, op, ct) =>
        {
            h.Session.Close(); // the pipe drops while the command is running
            return new JObject { ["owned"] = true };
        };
        h.Session.Receive(Rpc.Request(2, "ops.apply", Rpc.OpsParams("d", "j:1")));
        h.Session.Receive(Rpc.Request(3, "drawing.snapshot", Rpc.SnapshotParams()));
        var written = h.Sink.Payloads.Count;

        var ran = h.Session.RunNext();

        Assert.True(ran);
        Assert.Equal(new[] { "j:1" }, h.Ledger.CompletedIds());
        Assert.Equal(written, h.Sink.Payloads.Count);
        Assert.False(h.Session.RunNext()); // the queued snapshot was dropped
        Assert.Empty(h.Handler.SnapshotCalls);
    }

    [Fact]
    public void New_session_sees_ledger()
    {
        var ledger = new OperationLedger();
        var first = new Harness(ledger: ledger);
        first.Session.Receive(Rpc.Request(2, "ops.apply", Rpc.OpsParams("d", "j:1")));
        first.Session.RunNext();
        first.Session.Close();

        var second = new Harness(ledger: ledger);
        second.Session.Receive(Rpc.Request(2, "session.completed_operations"));
        second.Session.Receive(Rpc.Request(3, "ops.apply", Rpc.OpsParams("d", "j:1")));
        second.Session.RunNext();

        Assert.Equal(new[] { "j:1" }, second.Sink.Frames[1]["result"]!["operation_ids"]!.Select(t => t.Value<string>()).ToArray());
        Assert.Equal("DUPLICATE_OPERATION", second.Last["result"]!["outcomes"]![0]!["error"]!.Value<string>("code"));
        Assert.Empty(second.Handler.ExecuteCalls);
    }

    [Fact]
    public void Chunked_response_frames_stay_within_limit()
    {
        const int Limit = 400;
        var h = new Harness(Limit);
        var big = new JObject { ["text"] = new string('草', 500) + "tail" };
        h.Handler.OnSnapshot = (p, ct) => big;
        h.Session.Receive(Rpc.Request(2, "drawing.snapshot", Rpc.SnapshotParams()));

        h.Session.RunNext();

        var payloads = h.Sink.Payloads.Skip(1).ToList();
        Assert.True(payloads.Count > 2);
        Assert.All(payloads, p => Assert.True(p.Length <= Limit, "frame of " + p.Length + " bytes"));
        var chunks = payloads.Select(p => Fixtures.Parse(Encoding.UTF8.GetString(p))).ToList();
        Assert.All(chunks, c => Assert.Equal("response.chunk", c.Value<string>("method")));
        Assert.Equal(Enumerable.Range(0, chunks.Count).Select(i => (long)i), chunks.Select(c => c["params"]!.Value<long>("index")));
        Assert.All(chunks, c => Assert.Equal(chunks.Count, c["params"]!.Value<int>("count")));
        var joined = TranscriptNormalizer.Normalize(h.Sink.Events.Skip(1).ToList()).Single();
        Assert.Equal(big.ToString(), ((JObject)joined)["result"]!.ToString());
    }

    [Fact]
    public void Small_response_is_one_frame()
    {
        var h = new Harness();
        h.Session.Receive(Rpc.Request(2, "drawing.snapshot", Rpc.SnapshotParams()));

        h.Session.RunNext();

        Assert.Equal(2, h.Sink.Payloads.Count);
        Assert.Null(h.Last["method"]);
    }

    [Fact]
    public void Notify_writes_a_notification_once_ready()
    {
        var h = new Harness();

        h.Session.Notify("job.progress", new JObject { ["done"] = 1 });

        Assert.Equal("job.progress", h.Last.Value<string>("method"));
        Assert.Null(h.Last["id"]);
    }

    [Fact]
    public void Notify_before_hello_ignored()
    {
        var sink = new RecordingSink();
        var session = new IpcSession(Rpc.Config(), new OperationLedger(), new ScriptedHandler(), sink);

        session.Notify("document.event", new JObject());

        Assert.Empty(sink.Payloads);
    }

    [Fact]
    public void Notify_after_close_ignored()
    {
        var h = new Harness();
        h.Session.Close();
        var before = h.Sink.Payloads.Count;

        h.Session.Notify("job.progress", new JObject());

        Assert.Equal(before, h.Sink.Payloads.Count);
    }

    [Fact]
    public void Oversize_notification_is_rejected_loudly()
    {
        var h = new Harness(400);

        Assert.Throws<InvalidOperationException>(() =>
            h.Session.Notify("job.progress", new JObject { ["message"] = new string('x', 1000) }));
    }
}

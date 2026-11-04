using System.Collections.Generic;
using System.Linq;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ledger;
using ExecutionServer.Tests.Support;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests;

/// <summary>Replays each transcript whose sides include csharp against a session (15.5, spec 8.7).</summary>
public sealed class TranscriptReplayTests
{
    public static IEnumerable<object[]> CsharpScenarios() => Fixtures.ScenariosFor("csharp").Select(s => new object[] { s });

    [Fact]
    public void Scenario_list_covers_the_core_behaviours()
    {
        var names = Fixtures.ScenariosFor("csharp");

        Assert.NotEmpty(names);
        foreach (var required in new[] { "handshake", "cancel_running", "snapshot_chunked", "ops_duplicate" })
        {
            Assert.Contains(required, names);
        }
    }

    [Theory]
    [MemberData(nameof(CsharpScenarios))]
    public void Replays_to_the_end(string scenario)
    {
        var transcript = Transcript.LoadScenario(scenario);
        var config = BuildConfig(transcript.Config);
        var sink = new RecordingSink();
        var handler = ScriptedHandler.FromTranscript(transcript);
        var session = new IpcSession(config, new OperationLedger(), handler, sink);
        handler.Session = session;

        var expected = new List<object>();
        var unrun = 0;
        foreach (var entry in transcript.Entries)
        {
            if (entry.CoreToAddin)
            {
                var bytes = Rpc.Bytes(entry.Frame!);
                if (entry.Method == "job.cancel" && unrun > 0)
                {
                    handler.InjectDuringNextCommand(bytes); // arrives while the first command runs
                    continue;
                }

                session.Receive(bytes);
                if (entry.Method == "drawing.snapshot" || entry.Method == "ops.apply")
                {
                    unrun++;
                }

                continue;
            }

            if (entry.IsClose)
            {
                expected.Add(RecordingSink.CloseMarker);
            }
            else if (entry.Method != null && entry.Method != "response.chunk")
            {
                session.Notify(entry.Method, entry.Frame!["params"]);
                expected.Add(entry.Frame!);
            }
            else
            {
                RunAll(session);
                unrun = 0;
                expected.Add(entry.Frame!);
            }
        }

        RunAll(session);

        var actual = TranscriptNormalizer.Normalize(sink.Events.ToList()).Select(TranscriptNormalizer.Describe).ToList();
        var wanted = TranscriptNormalizer.Normalize(expected).Select(TranscriptNormalizer.Describe).ToList();
        Assert.Equal(wanted, actual);
        Assert.All(sink.Payloads, p => Assert.True(p.Length <= config.MaxFrameBytes));
    }

    private static void RunAll(IpcSession session)
    {
        while (session.RunNext())
        {
        }
    }

    private static SessionConfig BuildConfig(JObject c)
    {
        var hello = c["backend"]?.ToObject<HelloResult>() ?? Rpc.HelloResult();
        return new SessionConfig(
            Transcript.RequireString(c, "token"),
            hello,
            c.Value<bool?>("version_supported") ?? true,
            c.Value<string>("unsupported_message") ?? "SOLIDWORKS version is not supported.",
            c.Value<int?>("max_frame_bytes") ?? 64 * 1024 * 1024);
    }
}

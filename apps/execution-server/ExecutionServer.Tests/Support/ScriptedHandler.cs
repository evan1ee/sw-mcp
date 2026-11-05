using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Tests.Support;

/// <summary>
/// A command handler whose behaviour a test (or a transcript) scripts. Records every call so a test
/// can assert the handler was not reached.
/// </summary>
public sealed class ScriptedHandler : ICommandHandler
{
    private readonly ConcurrentQueue<string> _snapshotCalls = new ConcurrentQueue<string>();
    private readonly ConcurrentQueue<string> _measureCalls = new ConcurrentQueue<string>();
    private readonly ConcurrentQueue<string> _executeCalls = new ConcurrentQueue<string>();
    private readonly ConcurrentQueue<byte[]> _injectOnNextRun = new ConcurrentQueue<byte[]>();

    public IpcSession? Session { get; set; }

    public Func<SnapshotParams, CancellationToken, JToken> OnSnapshot { get; set; } =
        (p, ct) => new JObject { ["document"] = p.Document };

    public Func<PartMeasureParams, CancellationToken, JToken> OnMeasure { get; set; } =
        (p, ct) => new JObject { ["path"] = p.Document };

    public Func<string, Operation, CancellationToken, JToken> OnExecute { get; set; } =
        (doc, op, ct) => new JObject { ["done"] = op.OperationId };

    public IReadOnlyList<string> SnapshotCalls => _snapshotCalls.ToList();

    public IReadOnlyList<string> MeasureCalls => _measureCalls.ToList();

    public IReadOnlyList<string> ExecuteCalls => _executeCalls.ToList();

    /// <summary>Frames to deliver to the session from inside the next command (a job.cancel while running).</summary>
    public void InjectDuringNextCommand(byte[] frame) => _injectOnNextRun.Enqueue(frame);

    public JToken Snapshot(SnapshotParams p, CancellationToken ct)
    {
        _snapshotCalls.Enqueue(p.Document);
        DeliverInjected();
        return OnSnapshot(p, ct);
    }

    public JToken MeasurePart(PartMeasureParams p, CancellationToken ct)
    {
        _measureCalls.Enqueue(p.Document);
        DeliverInjected();
        return OnMeasure(p, ct);
    }

    public JToken Execute(string document, Operation op, CancellationToken ct)
    {
        _executeCalls.Enqueue(op.OperationId);
        DeliverInjected();
        return OnExecute(document, op, ct);
    }

    /// <summary>Takes snapshot results and per-operation outcomes from what the transcript's add-in answered.</summary>
    public static ScriptedHandler FromTranscript(Transcript t)
    {
        var responses = TranscriptNormalizer.WholeResponses(t.Entries.Where(e => !e.CoreToAddin).ToList());
        var snapshotIds = t.Entries
            .Where(e => e.CoreToAddin && e.Method == "drawing.snapshot")
            .Select(e => e.Frame!.Value<long>("id")).ToList();
        var measureIds = t.Entries
            .Where(e => e.CoreToAddin && e.Method == "part.measure")
            .Select(e => e.Frame!.Value<long>("id")).ToList();
        var outcomes = new Dictionary<string, JToken>();
        foreach (var kv in responses)
        {
            var list = kv.Value["result"]?["outcomes"] as JArray;
            if (list == null)
            {
                continue;
            }

            foreach (var o in list)
            {
                if (o["error"]?["code"]?.Value<string>() == "DUPLICATE_OPERATION")
                {
                    continue;
                }

                var key = o.Value<string>("operation_id")!;
                if (!outcomes.ContainsKey(key))
                {
                    outcomes[key] = o;
                }
            }
        }

        var handler = new ScriptedHandler();
        var snapshotCall = 0;
        var measureCall = 0;
        handler.OnMeasure = (p, ct) =>
        {
            if (measureCall >= measureIds.Count)
            {
                throw new InvalidOperationException("transcript has no more part.measure entries");
            }
            var id = measureIds[measureCall++];
            ct.ThrowIfCancellationRequested();
            if (responses.TryGetValue(id, out var r))
            {
                var error = r["error"];
                if (error != null)
                {
                    var data = error["data"];
                    var code = data?["code"]?.Value<string>() ?? error.Value<string>("code") ?? "IR_REFERENCE_UNRESOLVED";
                    var msg = data?["message"]?.Value<string>() ?? error.Value<string>("message") ?? string.Empty;
                    throw new IpcException(code, msg, data?["details"]);
                }

                if (r["result"] != null)
                {
                    return r["result"]!;
                }
            }

            throw new InvalidOperationException("transcript has no measure result or error for id " + id);
        };
        handler.OnSnapshot = (p, ct) =>
        {
            var id = snapshotIds[snapshotCall++];
            ct.ThrowIfCancellationRequested();
            if (responses.TryGetValue(id, out var r))
            {
                var error = r["error"];
                if (error != null)
                {
                    var data = error["data"];
                    var code = data?["code"]?.Value<string>() ?? error.Value<string>("code") ?? "IR_REFERENCE_UNRESOLVED";
                    var msg = data?["message"]?.Value<string>() ?? error.Value<string>("message") ?? string.Empty;
                    throw new IpcException(code, msg, data?["details"]);
                }

                if (r["result"] != null)
                {
                    return r["result"]!;
                }
            }

            throw new InvalidOperationException("transcript has no snapshot result or error for id " + id);
        };
        handler.OnExecute = (doc, op, ct) =>
        {
            if (!outcomes.TryGetValue(op.OperationId, out var outcome))
            {
                throw new InvalidOperationException("transcript never attempts " + op.OperationId);
            }

            var error = outcome["error"];
            if (error != null)
            {
                throw new IpcException(error.Value<string>("code")!, error.Value<string>("message") ?? string.Empty, error["details"]);
            }

            return outcome["result"] ?? new JObject();
        };
        return handler;
    }

    private void DeliverInjected()
    {
        while (_injectOnNextRun.TryDequeue(out var frame))
        {
            (Session ?? throw new InvalidOperationException("Session not set")).Receive(frame);
        }
    }
}

/// <summary>Turns a transcript's frames into comparable form: chunks joined, _meta and error messages masked (spec 8.7).</summary>
public static class TranscriptNormalizer
{
    /// <summary>Whole responses by request id, with chunked ones reassembled.</summary>
    public static Dictionary<long, JToken> WholeResponses(IReadOnlyList<TranscriptEntry> addinEntries)
    {
        var frames = addinEntries.Where(e => !e.IsClose).Select(e => e.Frame!).ToList();
        var result = new Dictionary<long, JToken>();
        foreach (var item in Normalize(frames.Cast<object>().ToList()))
        {
            if (item is JObject o && o["id"]?.Type == JTokenType.Integer)
            {
                result[o.Value<long>("id")] = o;
            }
        }

        return result;
    }

    /// <summary>Joins chunk runs at the position of their first chunk, then masks and canonicalises.</summary>
    public static List<object> Normalize(IReadOnlyList<object> events)
    {
        var chunks = new Dictionary<long, SortedDictionary<long, byte[]>>();
        foreach (var e in events)
        {
            if (e is JToken t && t["method"]?.Value<string>() == "response.chunk")
            {
                var p = t["params"]!;
                var id = p.Value<long>("id");
                if (!chunks.TryGetValue(id, out var parts))
                {
                    chunks[id] = parts = new SortedDictionary<long, byte[]>();
                }

                parts[p.Value<long>("index")] = Convert.FromBase64String(p.Value<string>("data")!);
            }
        }

        var output = new List<object>();
        var emitted = new HashSet<long>();
        foreach (var e in events)
        {
            if (e is JToken t && t["method"]?.Value<string>() == "response.chunk")
            {
                var id = t["params"]!.Value<long>("id");
                if (emitted.Add(id))
                {
                    var bytes = chunks[id].Values.SelectMany(b => b).ToArray();
                    output.Add(Canonical(Fixtures.Parse(Encoding.UTF8.GetString(bytes))));
                }
            }
            else if (e is JToken whole)
            {
                output.Add(Canonical(whole));
            }
            else
            {
                output.Add(e);
            }
        }

        return output;
    }

    public static string Describe(object item) => item is JToken t ? t.ToString(Newtonsoft.Json.Formatting.None) : item.ToString()!;

    private static JToken Canonical(JToken token)
    {
        var copy = token.DeepClone();
        Mask(copy);
        return Sort(copy);
    }

    private static void Mask(JToken token)
    {
        if (token is JObject o)
        {
            o.Remove("_meta");
            if (o["error"] is JObject err)
            {
                err.Remove("message");
                (err["data"] as JObject)?.Remove("message");
            }

            foreach (var p in o.Properties().ToList())
            {
                Mask(p.Value);
            }
        }
        else if (token is JArray a)
        {
            foreach (var item in a)
            {
                Mask(item);
            }
        }
    }

    private static JToken Sort(JToken token)
    {
        if (token is JObject o)
        {
            var sorted = new JObject();
            foreach (var p in o.Properties().OrderBy(p => p.Name, StringComparer.Ordinal))
            {
                sorted[p.Name] = Sort(p.Value);
            }

            return sorted;
        }

        if (token is JArray a)
        {
            return new JArray(a.Select(Sort));
        }

        if (token is JValue v && v.Type == JTokenType.Float && v.Value is double d && d == Math.Floor(d) && Math.Abs(d) < 1e15)
        {
            return new JValue((long)d);
        }

        return token.DeepClone();
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Tests.Support;

public sealed class TranscriptEntry
{
    public TranscriptEntry(bool coreToAddin, long tMs, JToken? frame)
    {
        CoreToAddin = coreToAddin;
        TMs = tMs;
        Frame = frame;
    }

    public bool CoreToAddin { get; }

    public long TMs { get; }

    /// <summary>The frame, or null for a <c>close</c> entry.</summary>
    public JToken? Frame { get; }

    public bool IsClose => Frame == null;

    public string? Method => Frame?["method"]?.Value<string>();
}

/// <summary>A transcript (spec 8.7): a header line, then one JSON object per frame.</summary>
public sealed class Transcript
{
    private Transcript(string scenario, IReadOnlyList<string> sides, JObject config, IReadOnlyList<TranscriptEntry> entries)
    {
        Scenario = scenario;
        Sides = sides;
        Config = config;
        Entries = entries;
    }

    public string Scenario { get; }

    public IReadOnlyList<string> Sides { get; }

    public JObject Config { get; }

    public IReadOnlyList<TranscriptEntry> Entries { get; }

    public static Transcript Load(string path)
    {
        var lines = File.ReadAllLines(path).Where(l => l.Trim().Length > 0).ToList();
        var header = (JObject)Fixtures.Parse(lines[0]);
        var entries = new List<TranscriptEntry>();
        foreach (var line in lines.Skip(1))
        {
            var obj = (JObject)Fixtures.Parse(line);
            var coreToAddin = obj.Value<string>("dir") == "core_to_addin";
            entries.Add(new TranscriptEntry(coreToAddin, obj.Value<long>("t_ms"), obj["close"] != null ? null : obj["frame"]));
        }

        var sides = header["sides"]!.Select(t => t.Value<string>()!).ToList();
        return new Transcript(header.Value<string>("scenario")!, sides, (JObject)header["config"]!, entries);
    }

    public static Transcript LoadScenario(string scenario) =>
        Load(Path.Combine(Fixtures.IpcTranscriptDir, scenario + ".jsonl"));

    public static string RequireString(JObject o, string name) =>
        o.Value<string>(name) ?? throw new InvalidOperationException("transcript config lacks " + name);
}

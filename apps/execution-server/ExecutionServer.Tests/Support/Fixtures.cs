using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Tests.Support;

/// <summary>Finds the repository's fixtures and parses JSON the way the session does (strings stay strings).</summary>
public static class Fixtures
{
    private static readonly Lazy<string> Root = new Lazy<string>(FindRoot);

    public static string RepoRoot => Root.Value;

    public static string IpcTranscriptDir => Path.Combine(RepoRoot, "tests", "fixtures", "ipc");

    public static string IpcSchemaFixtureDir => Path.Combine(RepoRoot, "tests", "fixtures", "schemas", "ipc");

    public static JToken Parse(string text)
    {
        using var reader = new JsonTextReader(new StringReader(text)) { DateParseHandling = DateParseHandling.None };
        return JToken.ReadFrom(reader);
    }

    public static JToken ReadJson(string path) => Parse(File.ReadAllText(path));

    /// <summary>Names of the transcripts whose header <c>sides</c> include <paramref name="side"/>.</summary>
    public static IReadOnlyList<string> ScenariosFor(string side)
    {
        var names = new List<string>();
        foreach (var path in Directory.GetFiles(IpcTranscriptDir, "*.jsonl").OrderBy(p => p, StringComparer.Ordinal))
        {
            var transcript = Transcript.Load(path);
            if (transcript.Sides.Contains(side))
            {
                names.Add(transcript.Scenario);
            }
        }

        return names;
    }

    private static string FindRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir != null)
        {
            if (Directory.Exists(Path.Combine(dir.FullName, "schemas")) && Directory.Exists(Path.Combine(dir.FullName, "tests")))
            {
                return dir.FullName;
            }

            dir = dir.Parent;
        }

        throw new DirectoryNotFoundException("Repository root (a folder holding schemas/ and tests/) not found above the test binaries.");
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Tests.Support;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests;

public sealed class GeneratedTypesTests
{
    private const string Namespace = "ExecutionServer.Core.Ipc.Generated.";

    public static IEnumerable<object[]> ValidDefs() => Defs("valid", "*.json");

    public static IEnumerable<object[]> StructuralDefs() => Defs("invalid", "structural_*.json");

    [Theory]
    [MemberData(nameof(ValidDefs))]
    public void Valid_instances_deserialize(string def)
    {
        if (def == "SnapshotResult")
        {
            return; // opaque to the generator (3.4.8): C# carries it as a JToken
        }

        var type = TypeOf(def);
        foreach (var instance in Instances("valid", def + ".json"))
        {
            Assert.NotNull(Deserialize(instance, type));
        }
    }

    [Theory]
    [MemberData(nameof(StructuralDefs))]
    public void Structurally_invalid_instances_throw(string def)
    {
        var type = TypeOf(def);
        foreach (var instance in Instances("invalid", "structural_" + def + ".json"))
        {
            Assert.ThrowsAny<Exception>(() => Deserialize(instance, type));
        }
    }

    [Fact]
    public void Unknown_input_enum_rejected()
    {
        var json = new JObject { ["document"] = "d", ["event"] = "explode" };

        Assert.ThrowsAny<JsonException>(() => Deserialize(json, typeof(DocumentEventParams)));
    }

    [Fact]
    public void Unknown_fields_ignored()
    {
        var json = new JObject
        {
            ["document"] = "C:/d/x.slddrw",
            ["sheets"] = new JArray("Sheet1"),
            ["future_field"] = new JObject { ["a"] = 1 },
        };

        var p = (SnapshotParams)Deserialize(json, typeof(SnapshotParams));

        Assert.Equal("C:/d/x.slddrw", p.Document);
        Assert.Equal(new[] { "Sheet1" }, p.Sheets);
    }

    [Fact]
    public void Error_codes_match_catalogue()
    {
        var catalogue = (JObject)Fixtures.ReadJson(Path.Combine(Fixtures.RepoRoot, "schemas", "common", "errors.json"));
        var branches = ((JArray)catalogue["oneOf"]!).Cast<JObject>().ToList();
        var constants = typeof(ErrorCodes).GetFields(BindingFlags.Public | BindingFlags.Static)
            .Where(f => f.IsLiteral).ToDictionary(f => f.Name, f => (string)f.GetRawConstantValue()!);

        Assert.Equal(branches.Count, constants.Count);
        foreach (var branch in branches)
        {
            var code = branch.Value<string>("const")!;
            Assert.Equal(code, constants[code]);
            var expected = branch.Value<string>("x-retryable")!.Replace("_", string.Empty);
            Assert.Equal(expected, ErrorCodes.DefaultRetryable(code).ToString().ToLowerInvariant());
        }

        Assert.Equal(ErrorRetryable.AfterFix, ErrorCodes.DefaultRetryable("NOT_A_CODE"));
    }

    private static IEnumerable<object[]> Defs(string kind, string pattern) =>
        Directory.GetFiles(Path.Combine(Fixtures.IpcSchemaFixtureDir, kind), pattern)
            .Select(p => Path.GetFileNameWithoutExtension(p))
            .Select(n => n.StartsWith("structural_", StringComparison.Ordinal) ? n.Substring("structural_".Length) : n)
            .OrderBy(n => n, StringComparer.Ordinal)
            .Select(n => new object[] { n });

    private static IEnumerable<JToken> Instances(string kind, string file) =>
        ((JArray)Fixtures.ReadJson(Path.Combine(Fixtures.IpcSchemaFixtureDir, kind, file))).ToList();

    private static Type TypeOf(string def) =>
        typeof(Meta).Assembly.GetType(Namespace + def) ?? throw new InvalidOperationException("no generated type " + def);

    private static object Deserialize(JToken json, Type type) =>
        JsonConvert.DeserializeObject(
            json.ToString(Formatting.None),
            type,
            new JsonSerializerSettings { DateParseHandling = DateParseHandling.None })
        ?? throw new JsonSerializationException("null");
}

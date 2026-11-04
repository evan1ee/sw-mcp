using System;
using System.Collections.Generic;
using System.IO;
using ExecutionServer.AddIn.Diagnostics;
using ExecutionServer.AddIn.Events;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests.Diagnostics;

public sealed class SettingsGuardTests
{
    private sealed class MockSettingsTarget : ISettingsTarget
    {
        public Dictionary<int, bool> Toggles { get; } = new Dictionary<int, bool>();
        public Dictionary<int, int> Integers { get; } = new Dictionary<int, int>();
        public Dictionary<int, double> Doubles { get; } = new Dictionary<int, double>();
        public Dictionary<int, string> Strings { get; } = new Dictionary<int, string>();

        public bool GetToggle(int pref) => Toggles.TryGetValue(pref, out var v) && v;
        public void SetToggle(int pref, bool value) => Toggles[pref] = value;

        public int GetInteger(int pref) => Integers.TryGetValue(pref, out var v) ? v : 0;
        public void SetInteger(int pref, int value) => Integers[pref] = value;

        public double GetDouble(int pref) => Doubles.TryGetValue(pref, out var v) ? v : 0.0;
        public void SetDouble(int pref, double value) => Doubles[pref] = value;

        public string GetString(int pref) => Strings.TryGetValue(pref, out var v) ? v : string.Empty;
        public void SetString(int pref, string value) => Strings[pref] = value;
    }

    [Fact]
    public void SettingsGuard_SnapshotsAndRestoresPreferences()
    {
        var target = new MockSettingsTarget();
        target.SetToggle(10, false);
        target.SetInteger(20, 100);
        target.SetString(30, "original");

        var restorePath = Path.Combine(Path.GetTempPath(), "test-restore-" + Guid.NewGuid().ToString("N") + ".json");
        try
        {
            var guard = new SettingsGuard(target, restorePath);

            guard.SetToggle(10, true);
            guard.SetInteger(20, 200);
            guard.SetString(30, "modified");

            Assert.True(target.GetToggle(10));
            Assert.Equal(200, target.GetInteger(20));
            Assert.Equal("modified", target.GetString(30));
            Assert.True(File.Exists(restorePath));

            guard.RestoreAll();

            Assert.False(target.GetToggle(10));
            Assert.Equal(100, target.GetInteger(20));
            Assert.Equal("original", target.GetString(30));
            Assert.False(File.Exists(restorePath));
        }
        finally
        {
            if (File.Exists(restorePath)) File.Delete(restorePath);
        }
    }

    [Fact]
    public void SettingsGuard_RecoversFromCrashFile()
    {
        var target = new MockSettingsTarget();
        target.SetToggle(10, true);
        target.SetInteger(20, 999);

        var restorePath = Path.Combine(Path.GetTempPath(), "test-crash-" + Guid.NewGuid().ToString("N") + ".json");
        try
        {
            var crashJson = new JObject
            {
                ["pid"] = 1234,
                ["saved_at"] = DateTime.UtcNow.ToString("o"),
                ["toggles"] = new JObject { ["10"] = false },
                ["integers"] = new JObject { ["20"] = 100 },
                ["doubles"] = new JObject(),
                ["strings"] = new JObject()
            };
            File.WriteAllText(restorePath, crashJson.ToString());

            Assert.True(File.Exists(restorePath));
            SettingsGuard.RecoverFromCrashFile(target, restorePath);

            Assert.False(target.GetToggle(10));
            Assert.Equal(100, target.GetInteger(20));
            Assert.False(File.Exists(restorePath));
        }
        finally
        {
            if (File.Exists(restorePath)) File.Delete(restorePath);
        }
    }

    [Fact]
    public void SettingsGuard_RecoversAllCrashFilesFromDirectory()
    {
        var target = new MockSettingsTarget();
        target.SetToggle(10, true);
        target.SetInteger(20, 999);
        target.SetString(30, "changed");

        var tempDir = Path.Combine(Path.GetTempPath(), "test-crash-dir-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDir);
        try
        {
            var crash1 = Path.Combine(tempDir, "settings-restore-1111.json");
            var crash2 = Path.Combine(tempDir, "settings-restore-2222.json");

            var json1 = new JObject
            {
                ["pid"] = 1111,
                ["saved_at"] = DateTime.UtcNow.ToString("o"),
                ["toggles"] = new JObject { ["10"] = false },
                ["integers"] = new JObject { ["20"] = 100 },
                ["doubles"] = new JObject(),
                ["strings"] = new JObject()
            };
            File.WriteAllText(crash1, json1.ToString());

            var json2 = new JObject
            {
                ["pid"] = 2222,
                ["saved_at"] = DateTime.UtcNow.ToString("o"),
                ["toggles"] = new JObject(),
                ["integers"] = new JObject(),
                ["doubles"] = new JObject(),
                ["strings"] = new JObject { ["30"] = "original" }
            };
            File.WriteAllText(crash2, json2.ToString());

            SettingsGuard.RecoverAllCrashFiles(target, tempDir);

            Assert.False(target.GetToggle(10));
            Assert.Equal(100, target.GetInteger(20));
            Assert.Equal("original", target.GetString(30));
            Assert.False(File.Exists(crash1));
            Assert.False(File.Exists(crash2));
        }
        finally
        {
            if (Directory.Exists(tempDir)) Directory.Delete(tempDir, true);
        }
    }

    [Fact]
    public void DocumentEventMonitor_TagsJobEvents()
    {
        var received = new List<(string method, JToken payload)>();
        var monitor = new DocumentEventMonitor((method, payload) => received.Add((method, payload)));

        // Event without active job (user interaction)
        monitor.CurrentJobId = null;
        monitor.OnDocumentEvent("bracket.slddrw", DocumentEventParamsEvent.Save);

        Assert.Single(received);
        Assert.Equal("document.event", received[0].method);
        var meta0 = received[0].payload["_meta"];
        Assert.True(meta0 == null || meta0["job_id"] == null);

        // Event during active job
        monitor.CurrentJobId = "job_01JXYZ";
        monitor.OnDocumentEvent("bracket.slddrw", DocumentEventParamsEvent.Regen);

        Assert.Equal(2, received.Count);
        Assert.Equal("document.event", received[1].method);
        var meta1 = received[1].payload["_meta"];
        Assert.NotNull(meta1);
        Assert.Equal("job_01JXYZ", meta1["job_id"]?.Value<string>());
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using SolidWorks.Interop.sldworks;

namespace ExecutionServer.AddIn.Diagnostics;

public interface ISettingsTarget
{
    bool GetToggle(int pref);
    void SetToggle(int pref, bool value);
    int GetInteger(int pref);
    void SetInteger(int pref, int value);
    double GetDouble(int pref);
    void SetDouble(int pref, double value);
    string GetString(int pref);
    void SetString(int pref, string value);
}

public sealed class SldWorksSettingsTarget : ISettingsTarget
{
    private readonly ISldWorks _sw;

    public SldWorksSettingsTarget(ISldWorks sw)
    {
        _sw = sw ?? throw new ArgumentNullException(nameof(sw));
    }

    public bool GetToggle(int pref) => _sw.GetUserPreferenceToggle(pref);
    public void SetToggle(int pref, bool value) => _sw.SetUserPreferenceToggle(pref, value);
    public int GetInteger(int pref) => _sw.GetUserPreferenceIntegerValue(pref);
    public void SetInteger(int pref, int value) => _sw.SetUserPreferenceIntegerValue(pref, value);
    public double GetDouble(int pref) => _sw.GetUserPreferenceDoubleValue(pref);
    public void SetDouble(int pref, double value) => _sw.SetUserPreferenceDoubleValue(pref, value);
    public string GetString(int pref) => _sw.GetUserPreferenceStringValue(pref);
    public void SetString(int pref, string value) => _sw.SetUserPreferenceStringValue(pref, value);
}

/// <summary>
/// Isolates and tracks SOLIDWORKS engineer settings modified during a job (spec 8.6.4).
/// Persists originals to %LOCALAPPDATA%\sw-mcp\settings-restore-<pid>.json and restores them
/// on job completion or upon crash recovery at startup.
/// </summary>
public sealed class SettingsGuard
{
    private readonly ISettingsTarget _target;
    private readonly string _restoreFilePath;
    private readonly object _gate = new object();

    private readonly Dictionary<int, bool> _originalToggles = new Dictionary<int, bool>();
    private readonly Dictionary<int, int> _originalIntegers = new Dictionary<int, int>();
    private readonly Dictionary<int, double> _originalDoubles = new Dictionary<int, double>();
    private readonly Dictionary<int, string> _originalStrings = new Dictionary<int, string>();

    public SettingsGuard(ISettingsTarget target, string? restoreFilePath = null)
    {
        _target = target ?? throw new ArgumentNullException(nameof(target));
        _restoreFilePath = restoreFilePath ?? GetDefaultRestorePath();
    }

    public static string GetDefaultRestoreDir()
    {
        var localAppData = System.Environment.GetFolderPath(System.Environment.SpecialFolder.LocalApplicationData);
        var dir = Path.Combine(localAppData, "sw-mcp");
        Directory.CreateDirectory(dir);
        return dir;
    }

    public static string GetDefaultRestorePath()
    {
        var dir = GetDefaultRestoreDir();
        var pid = System.Diagnostics.Process.GetCurrentProcess().Id;
        return Path.Combine(dir, $"settings-restore-{pid}.json");
    }

    public static void RecoverAllCrashFiles(ISettingsTarget target, string? directory = null)
    {
        if (target == null) return;
        var dir = directory ?? GetDefaultRestoreDir();
        if (!Directory.Exists(dir)) return;

        var files = Directory.GetFiles(dir, "settings-restore-*.json");
        foreach (var file in files)
        {
            RecoverFromCrashFile(target, file);
        }
    }

    public void SetToggle(int pref, bool value)
    {
        lock (_gate)
        {
            if (!_originalToggles.ContainsKey(pref))
            {
                _originalToggles[pref] = _target.GetToggle(pref);
                SaveRestoreFile();
            }
            _target.SetToggle(pref, value);
        }
    }

    public void SetInteger(int pref, int value)
    {
        lock (_gate)
        {
            if (!_originalIntegers.ContainsKey(pref))
            {
                _originalIntegers[pref] = _target.GetInteger(pref);
                SaveRestoreFile();
            }
            _target.SetInteger(pref, value);
        }
    }

    public void SetDouble(int pref, double value)
    {
        lock (_gate)
        {
            if (!_originalDoubles.ContainsKey(pref))
            {
                _originalDoubles[pref] = _target.GetDouble(pref);
                SaveRestoreFile();
            }
            _target.SetDouble(pref, value);
        }
    }

    public void SetString(int pref, string value)
    {
        lock (_gate)
        {
            if (!_originalStrings.ContainsKey(pref))
            {
                _originalStrings[pref] = _target.GetString(pref);
                SaveRestoreFile();
            }
            _target.SetString(pref, value);
        }
    }

    public void RestoreAll()
    {
        lock (_gate)
        {
            foreach (var kvp in _originalToggles)
            {
                try { _target.SetToggle(kvp.Key, kvp.Value); } catch { }
            }
            foreach (var kvp in _originalIntegers)
            {
                try { _target.SetInteger(kvp.Key, kvp.Value); } catch { }
            }
            foreach (var kvp in _originalDoubles)
            {
                try { _target.SetDouble(kvp.Key, kvp.Value); } catch { }
            }
            foreach (var kvp in _originalStrings)
            {
                try { _target.SetString(kvp.Key, kvp.Value); } catch { }
            }

            _originalToggles.Clear();
            _originalIntegers.Clear();
            _originalDoubles.Clear();
            _originalStrings.Clear();

            DeleteRestoreFile();
        }
    }

    private void SaveRestoreFile()
    {
        try
        {
            var dir = Path.GetDirectoryName(_restoreFilePath);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
            {
                Directory.CreateDirectory(dir);
            }

            var togglesObj = new JObject();
            foreach (var kvp in _originalToggles) togglesObj[kvp.Key.ToString()] = kvp.Value;

            var integersObj = new JObject();
            foreach (var kvp in _originalIntegers) integersObj[kvp.Key.ToString()] = kvp.Value;

            var doublesObj = new JObject();
            foreach (var kvp in _originalDoubles) doublesObj[kvp.Key.ToString()] = kvp.Value;

            var stringsObj = new JObject();
            foreach (var kvp in _originalStrings) stringsObj[kvp.Key.ToString()] = kvp.Value;

            var root = new JObject
            {
                ["pid"] = System.Diagnostics.Process.GetCurrentProcess().Id,
                ["saved_at"] = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                ["toggles"] = togglesObj,
                ["integers"] = integersObj,
                ["doubles"] = doublesObj,
                ["strings"] = stringsObj
            };

            File.WriteAllText(_restoreFilePath, root.ToString(Formatting.Indented), Encoding.UTF8);
        }
        catch
        {
        }
    }

    private void DeleteRestoreFile()
    {
        try
        {
            if (File.Exists(_restoreFilePath))
            {
                File.Delete(_restoreFilePath);
            }
        }
        catch
        {
        }
    }

    public static void RecoverFromCrashFile(ISettingsTarget target, string restoreFilePath)
    {
        if (target == null || string.IsNullOrEmpty(restoreFilePath) || !File.Exists(restoreFilePath))
        {
            return;
        }

        try
        {
            var text = File.ReadAllText(restoreFilePath, Encoding.UTF8);
            var root = JObject.Parse(text);

            if (root["toggles"] is JObject toggles)
            {
                foreach (var prop in toggles.Properties())
                {
                    if (int.TryParse(prop.Name, out var pref) && prop.Value.Type == JTokenType.Boolean)
                    {
                        try { target.SetToggle(pref, prop.Value.Value<bool>()); } catch { }
                    }
                }
            }

            if (root["integers"] is JObject integers)
            {
                foreach (var prop in integers.Properties())
                {
                    if (int.TryParse(prop.Name, out var pref) && prop.Value.Type == JTokenType.Integer)
                    {
                        try { target.SetInteger(pref, prop.Value.Value<int>()); } catch { }
                    }
                }
            }

            if (root["doubles"] is JObject doubles)
            {
                foreach (var prop in doubles.Properties())
                {
                    if (int.TryParse(prop.Name, out var pref) && (prop.Value.Type == JTokenType.Float || prop.Value.Type == JTokenType.Integer))
                    {
                        try { target.SetDouble(pref, prop.Value.Value<double>()); } catch { }
                    }
                }
            }

            if (root["strings"] is JObject strings)
            {
                foreach (var prop in strings.Properties())
                {
                    if (int.TryParse(prop.Name, out var pref) && prop.Value.Type == JTokenType.String)
                    {
                        try { target.SetString(pref, prop.Value.Value<string>() ?? string.Empty); } catch { }
                    }
                }
            }

            File.Delete(restoreFilePath);
        }
        catch
        {
        }
    }
}

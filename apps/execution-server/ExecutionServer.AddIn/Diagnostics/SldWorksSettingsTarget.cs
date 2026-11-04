using System;
using ExecutionServer.Core.Diagnostics;
using SolidWorks.Interop.sldworks;

namespace ExecutionServer.AddIn.Diagnostics;

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

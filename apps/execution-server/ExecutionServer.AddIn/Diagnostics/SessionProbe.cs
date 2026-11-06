using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using ExecutionServer.Core.Versions;
using SolidWorks.Interop.sldworks;

namespace ExecutionServer.AddIn.Diagnostics;

/// <summary>
/// Probes the running SOLIDWORKS session for version, language, and threading diagnostics (ADR-059, ADR-062).
/// This is the sole CAD-aware reader of version and language; handlers read capabilities from CapabilityTable.
/// </summary>
public static class SessionProbe
{
    private static readonly Dictionary<string, string> LanguageMap = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
    {
        ["english"] = "en-US",
        ["chinese-simplified"] = "zh-CN",
        ["chinese-traditional"] = "zh-TW",
        ["french"] = "fr-FR",
        ["german"] = "de-DE",
        ["italian"] = "it-IT",
        ["japanese"] = "ja-JP",
        ["korean"] = "ko-KR",
        ["polish"] = "pl-PL",
        ["portuguese-brazilian"] = "pt-BR",
        ["russian"] = "ru-RU",
        ["spanish"] = "es-ES",
        ["czech"] = "cs-CZ",
        ["turkish"] = "tr-TR"
    };

    public static SolidWorksVersion? ProbeVersion(ISldWorks swApp, out string? failureReason)
    {
        failureReason = null;
        if (swApp == null)
        {
            failureReason = "SOLIDWORKS application instance is null.";
            return null;
        }

        string? revision;
        try
        {
            revision = swApp.RevisionNumber();
        }
        catch (Exception ex)
        {
            failureReason = $"Failed to query RevisionNumber: {ex.Message}";
            return null;
        }

        if (string.IsNullOrWhiteSpace(revision))
        {
            failureReason = "SOLIDWORKS RevisionNumber() returned empty or null.";
            return null;
        }

        try
        {
            return SolidWorksVersion.Parse(revision);
        }
        catch (Exception ex)
        {
            failureReason = $"Failed to parse revision '{revision}': {ex.Message}";
            return null;
        }
    }

    public static string? ProbeUiLanguage(ISldWorks swApp, out string? failureReason)
    {
        failureReason = null;
        if (swApp == null)
        {
            failureReason = "SOLIDWORKS application instance is null.";
            return null;
        }

        string? lang;
        try
        {
            lang = swApp.GetCurrentLanguage();
        }
        catch (Exception ex)
        {
            failureReason = $"Failed to query GetCurrentLanguage: {ex.Message}";
            return null;
        }

        if (string.IsNullOrWhiteSpace(lang))
        {
            failureReason = "SOLIDWORKS GetCurrentLanguage() returned empty or null.";
            return null;
        }

        lang = lang.Trim();
        if (LanguageMap.TryGetValue(lang, out var tag))
        {
            return tag;
        }

        return lang;
    }

    public static void LogSessionDiagnostics(int pid, int threadId, ApartmentState apartmentState, string dispatchPath)
    {
        try
        {
            var localAppData = System.Environment.GetFolderPath(System.Environment.SpecialFolder.LocalApplicationData);
            var logDir = Path.Combine(localAppData, "sw-mcp");
            Directory.CreateDirectory(logDir);
            var logPath = Path.Combine(logDir, "addin-load.log");
            var line = $"[{DateTime.UtcNow:O}] Session probe: PID {pid}, Thread ID {threadId}, ApartmentState {apartmentState}, DispatchPath {dispatchPath}\n";
            File.AppendAllText(logPath, line);
        }
        catch
        {
        }
    }
}

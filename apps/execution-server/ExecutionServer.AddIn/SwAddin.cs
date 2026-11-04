using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using ExecutionServer.Core.Diagnostics;
using ExecutionServer.Core.Dispatch;
using ExecutionServer.AddIn.Events;
using ExecutionServer.Core.Pipe;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ledger;
using Microsoft.Win32;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swpublished;

namespace ExecutionServer.AddIn;

[Guid(SwAddin.AddinGuid)]
[ComVisible(true)]
public class SwAddin : ISwAddin
{
    public const string AddinGuid = "4A137B34-3A9B-4A73-BE94-0E37C0F4A0A1";
    public const string AddinTitle = "sw-mcp Add-In";
    public const string AddinDescription = "sw-mcp execution server add-in for SOLIDWORKS";

    private ISldWorks? _swApp;
    private int _addinCookie;
    private NamedPipeServer? _pipeServer;
    private UIThreadDispatcher? _dispatcher;
    private string? _sessionFilePath;
    private OperationLedger? _ledger;
    private SldWorksDocumentEventMonitor? _eventMonitor;
    private SettingsGuard? _settingsGuard;

    public ISldWorks? SwApp => _swApp;

    public bool ConnectToSW(object ThisSW, int cookie)
    {
        _swApp = (ISldWorks)ThisSW;
        _addinCookie = cookie;

        try
        {
            // 0. Recover any crashed settings from previous sessions
            SettingsGuard.RecoverAllCrashFiles(new Diagnostics.SldWorksSettingsTarget(_swApp));
            _settingsGuard = new SettingsGuard(new Diagnostics.SldWorksSettingsTarget(_swApp));

            // 1. Capture UI-thread SynchronizationContext
            var syncContext = SynchronizationContext.Current;
            if (syncContext == null)
            {
                syncContext = new SynchronizationContext();
                SynchronizationContext.SetSynchronizationContext(syncContext);
            }
            _dispatcher = new UIThreadDispatcher(syncContext);

            // 2. Query SOLIDWORKS version info
            var revision = _swApp.RevisionNumber() ?? "33.0.0";
            var (version, sp) = ParseRevision(revision);
            var isSupported = version == "2025";
            var unsupportedMessage = isSupported ? string.Empty : $"SOLIDWORKS version {version} ({revision}) is unsupported; sw-mcp requires 2025.";

            // 3. Generate 32-byte cryptographic session token (base64url)
            var tokenBytes = new byte[32];
            using (var rng = RandomNumberGenerator.Create())
            {
                rng.GetBytes(tokenBytes);
            }
            var token = Convert.ToBase64String(tokenBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_');

            // 4. Pipe name and HelloResult configuration
            var pid = Process.GetCurrentProcess().Id;
            var pipeName = NamedPipeServer.GeneratePipeName(pid);

            var helloResult = new HelloResult
            {
                Protocol = ProtocolVersion.Current,
                AddinVersion = "0.1.0",
                Solidworks = new SolidWorksInfo
                {
                    Version = version,
                    ServicePack = sp,
                    UiLanguage = "en-US"
                },
                Capabilities = new List<string> { "drawing.snapshot", "ops.apply" },
                Operations = new List<OperationInfo>
                {
                    new OperationInfo { Op = "document.open", SchemaVersion = "0.1" },
                    new OperationInfo { Op = "document.close", SchemaVersion = "0.1" }
                },
                LicensedModules = new List<string>(),
                Warnings = new List<string>()
            };

            var sessionConfig = new SessionConfig(token, helloResult, isSupported, unsupportedMessage);
            _ledger = new OperationLedger();

            // 5a. Start DocumentEventMonitor
            _eventMonitor = new SldWorksDocumentEventMonitor((method, payload) => _pipeServer?.ActiveSession?.Notify(method, payload));
            _eventMonitor.Attach(_swApp);

            var handler = new DefaultAddinCommandHandler(_swApp, _eventMonitor, _settingsGuard);

            // 5b. Start NamedPipeServer
            _pipeServer = new NamedPipeServer(pipeName, sessionConfig, _ledger, handler, _dispatcher);

            // 6. Write session file to %LOCALAPPDATA%\sw-mcp\sessions\<pid>.json
            WriteSessionFile(pid, pipeName, token, version, sp);

            return true;
        }
        catch (Exception)
        {
            DisconnectFromSW();
            return false;
        }
    }

    public bool DisconnectFromSW()
    {
        // 0. Detach event monitor and restore settings
        if (_eventMonitor != null)
        {
            try
            {
                _eventMonitor.Detach();
                _eventMonitor.Dispose();
            }
            catch
            {
            }
            _eventMonitor = null;
        }

        if (_settingsGuard != null)
        {
            try
            {
                _settingsGuard.RestoreAll();
            }
            catch
            {
            }
            _settingsGuard = null;
        }

        // 1. Delete session file
        if (_sessionFilePath != null && File.Exists(_sessionFilePath))
        {
            try
            {
                File.Delete(_sessionFilePath);
            }
            catch
            {
            }
            _sessionFilePath = null;
        }

        // 2. Shut down pipe server & dispatcher
        if (_pipeServer != null)
        {
            try
            {
                _pipeServer.Dispose();
            }
            catch
            {
            }
            _pipeServer = null;
        }

        if (_dispatcher != null)
        {
            try
            {
                _dispatcher.Dispose();
            }
            catch
            {
            }
            _dispatcher = null;
        }

        // 3. Release SOLIDWORKS COM proxy per G1
        if (_swApp != null)
        {
            try
            {
                Marshal.ReleaseComObject(_swApp);
            }
            catch
            {
            }
            _swApp = null;
        }

        GC.Collect();
        GC.WaitForPendingFinalizers();

        return true;
    }

    private void WriteSessionFile(int pid, string pipeName, string token, string version, string sp)
    {
        var localAppData = System.Environment.GetFolderPath(System.Environment.SpecialFolder.LocalApplicationData);
        var sessionDir = Path.Combine(localAppData, "sw-mcp", "sessions");
        Directory.CreateDirectory(sessionDir);

        _sessionFilePath = Path.Combine(sessionDir, $"{pid}.json");
        var sessionObj = new JObject
        {
            ["pipe"] = pipeName,
            ["token"] = token,
            ["pid"] = pid,
            ["solidworks"] = new JObject
            {
                ["version"] = version,
                ["service_pack"] = sp
            },
            ["addin_version"] = "0.1.0",
            ["protocol"] = ProtocolVersion.Current,
            ["started_at"] = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
        };

        File.WriteAllText(_sessionFilePath, sessionObj.ToString(Formatting.Indented), Encoding.UTF8);
    }

    private static (string version, string sp) ParseRevision(string revision)
    {
        // SOLIDWORKS 2025 is internal version 33.x
        // format usually "33.0.0" (SP0) or "33.3.0" (SP3.0)
        var parts = revision.Split('.');
        string version = "2025";
        string sp = "SP0.0";

        if (parts.Length > 0 && int.TryParse(parts[0], out var major))
        {
            if (major == 33) version = "2025";
            else if (major == 32) version = "2024";
            else if (major == 34) version = "2026";
            else version = (1992 + major).ToString();
        }

        if (parts.Length > 1 && int.TryParse(parts[1], out var spNum))
        {
            sp = $"SP{spNum}.0";
        }

        return (version, sp);
    }

    [ComRegisterFunction]
    public static void RegisterFunction(Type t)
    {
        try
        {
            using (var key = Registry.CurrentUser.CreateSubKey($@"Software\SolidWorks\Addins\{{{AddinGuid}}}"))
            {
                key?.SetValue(null, 1, RegistryValueKind.DWord);
                key?.SetValue("Title", AddinTitle, RegistryValueKind.String);
                key?.SetValue("Description", AddinDescription, RegistryValueKind.String);
            }

            using (var key = Registry.CurrentUser.CreateSubKey($@"Software\SolidWorks\AddInsStartup\{{{AddinGuid}}}"))
            {
                key?.SetValue(null, 1, RegistryValueKind.DWord);
            }
        }
        catch
        {
        }
    }

    [ComUnregisterFunction]
    public static void UnregisterFunction(Type t)
    {
        try
        {
            Registry.CurrentUser.DeleteSubKeyTree($@"Software\SolidWorks\Addins\{{{AddinGuid}}}", false);
            Registry.CurrentUser.DeleteSubKeyTree($@"Software\SolidWorks\AddInsStartup\{{{AddinGuid}}}", false);
        }
        catch
        {
        }
    }

    private sealed class DefaultAddinCommandHandler : ICommandHandler
    {
        private readonly ISldWorks _sw;
        private readonly ExecutionServer.Core.Events.DocumentEventMonitor? _eventMonitor;
        private readonly SettingsGuard? _settingsGuard;
        private readonly Adapters.Drawings.DrawingSnapshotAdapter _snapshotAdapter;

        public DefaultAddinCommandHandler(
            ISldWorks sw,
            ExecutionServer.Core.Events.DocumentEventMonitor? eventMonitor = null,
            SettingsGuard? settingsGuard = null)
        {
            _sw = sw;
            _eventMonitor = eventMonitor;
            _settingsGuard = settingsGuard;
            _snapshotAdapter = new Adapters.Drawings.DrawingSnapshotAdapter(sw);
        }

        public JToken Snapshot(SnapshotParams p, CancellationToken ct)
        {
            if (_eventMonitor != null)
            {
                _eventMonitor.CurrentJobId = p.Meta?.JobId;
            }
            try
            {
                return _snapshotAdapter.Snapshot(p, ct);
            }
            finally
            {
                if (_eventMonitor != null)
                {
                    _eventMonitor.CurrentJobId = null;
                }
                _settingsGuard?.RestoreAll();
            }
        }

        public JToken Execute(string document, Operation op, CancellationToken ct)
        {
            if (_eventMonitor != null)
            {
                string? jobId = null;
                if (op.Params is JObject pObj && pObj["_meta"]?["job_id"] is JValue jv)
                {
                    jobId = jv.Value<string>();
                }
                if (string.IsNullOrEmpty(jobId) && !string.IsNullOrEmpty(op.OperationId))
                {
                    var colonIdx = op.OperationId.IndexOf(':');
                    jobId = colonIdx > 0 ? op.OperationId.Substring(0, colonIdx) : op.OperationId;
                }
                _eventMonitor.CurrentJobId = jobId;
            }
            try
            {
                if (op.Op == "document.open")
                {
                    int errors = 0;
                    int warnings = 0;
                    var docType = (int)SolidWorks.Interop.swconst.swDocumentTypes_e.swDocDRAWING;
                    if (document.EndsWith(".sldprt", StringComparison.OrdinalIgnoreCase))
                    {
                        docType = (int)SolidWorks.Interop.swconst.swDocumentTypes_e.swDocPART;
                    }
                    else if (document.EndsWith(".sldasm", StringComparison.OrdinalIgnoreCase))
                    {
                        docType = (int)SolidWorks.Interop.swconst.swDocumentTypes_e.swDocASSEMBLY;
                    }

                    var modelDoc = _sw.OpenDoc6(
                        document,
                        docType,
                        (int)SolidWorks.Interop.swconst.swOpenDocOptions_e.swOpenDocOptions_Silent,
                        "",
                        ref errors,
                        ref warnings);
                    if (modelDoc == null)
                    {
                        throw new IpcException(ErrorCodes.FILE_NOT_FOUND, $"Failed to open document '{document}', errors: {errors}");
                    }
                    Marshal.ReleaseComObject(modelDoc);
                    return new JObject { ["owned"] = true };
                }

                if (op.Op == "document.close")
                {
                    var title = Path.GetFileName(document);
                    _sw.CloseDoc(title);
                    return new JObject { ["closed"] = true };
                }

                return new JObject { ["op"] = op.Op, ["operation_id"] = op.OperationId, ["status"] = "applied" };
            }
            finally
            {
                if (_eventMonitor != null)
                {
                    _eventMonitor.CurrentJobId = null;
                }
                _settingsGuard?.RestoreAll();
            }
        }
    }
}

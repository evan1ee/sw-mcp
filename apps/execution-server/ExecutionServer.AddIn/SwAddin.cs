using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using ExecutionServer.Adapters.Documents;
using ExecutionServer.Adapters.Drawings;
using ExecutionServer.AddIn.Events;
using ExecutionServer.Core.Diagnostics;
using ExecutionServer.Core.Dispatch;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ledger;
using ExecutionServer.Core.Ownership;
using ExecutionServer.Core.Pipe;
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
    private DocumentOwnershipTable? _ownershipTable;
    private OperationRouter? _router;
    private SldWorksDocumentEventMonitor? _eventMonitor;
    private SettingsGuard? _settingsGuard;

    static SwAddin()
    {
        AppDomain.CurrentDomain.AssemblyResolve += OnAssemblyResolve;
    }

    private static Assembly? OnAssemblyResolve(object? sender, ResolveEventArgs args)
    {
        try
        {
            var assemblyName = new AssemblyName(args.Name).Name;
            if (string.IsNullOrEmpty(assemblyName))
            {
                return null;
            }
            var executingAssemblyDir = Path.GetDirectoryName(typeof(SwAddin).Assembly.Location);
            if (!string.IsNullOrEmpty(executingAssemblyDir))
            {
                var candidatePath = Path.Combine(executingAssemblyDir, assemblyName + ".dll");
                if (File.Exists(candidatePath))
                {
                    return Assembly.LoadFrom(candidatePath);
                }
            }
        }
        catch
        {
        }
        return null;
    }

    public ISldWorks? SwApp => _swApp;

    public bool ConnectToSW(object ThisSW, int cookie)
    {
        _swApp = (ISldWorks)ThisSW;
        _addinCookie = cookie;

        try
        {
            try
            {
                var localAppData = System.Environment.GetFolderPath(System.Environment.SpecialFolder.LocalApplicationData);
                var logDir = Path.Combine(localAppData, "sw-mcp");
                Directory.CreateDirectory(logDir);
                File.AppendAllText(Path.Combine(logDir, "addin-load.log"), $"[{DateTime.UtcNow:O}] ConnectToSW started for PID {Process.GetCurrentProcess().Id}\n");
            }
            catch {}
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

            _ownershipTable = new DocumentOwnershipTable();
            _router = CreateRouter(_swApp, _ownershipTable);

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
                Operations = _router.Operations.ToList(),
                LicensedModules = new List<string>(),
                Warnings = new List<string>()
            };

            var sessionConfig = new SessionConfig(token, helloResult, isSupported, unsupportedMessage);
            _ledger = new OperationLedger();

            // 5a. Start DocumentEventMonitor
            _eventMonitor = new SldWorksDocumentEventMonitor((method, payload) => _pipeServer?.ActiveSession?.Notify(method, payload));
            _eventMonitor.Attach(_swApp);

            var handler = new DefaultAddinCommandHandler(_swApp, _router, _eventMonitor, _settingsGuard);

            // 5b. Start NamedPipeServer
            _pipeServer = new NamedPipeServer(pipeName, sessionConfig, _ledger, handler, _dispatcher);

            // 6. Write session file to %LOCALAPPDATA%\sw-mcp\sessions\<pid>.json
            WriteSessionFile(pid, pipeName, token, version, sp);

            return true;
        }
        catch (Exception ex)
        {
            try
            {
                var localAppData = System.Environment.GetFolderPath(System.Environment.SpecialFolder.LocalApplicationData);
                var logDir = Path.Combine(localAppData, "sw-mcp");
                Directory.CreateDirectory(logDir);
                File.AppendAllText(Path.Combine(logDir, "addin-load.log"), $"[{DateTime.UtcNow:O}] ConnectToSW error: {ex}\n");
            }
            catch {}
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

        _ownershipTable = null;
        _router = null;

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

        File.WriteAllText(_sessionFilePath, sessionObj.ToString(Formatting.Indented), new UTF8Encoding(false));
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

    private static OperationRouter CreateRouter(ISldWorks sw, DocumentOwnershipTable ownership)
    {
        var router = new OperationRouter();
        var docOps = new DocumentOps(sw, ownership);

        router.Register("document.open", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<DocumentOpenParams>()
                : throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for document.open");
            var res = docOps.Open(doc, p!, ExtractJobId(op), ct);
            return JObject.FromObject(res);
        });

        router.Register("document.close", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<DocumentCloseParams>()
                : new DocumentCloseParams();
            var res = docOps.Close(doc, p ?? new DocumentCloseParams(), ExtractJobId(op), ct);
            return JObject.FromObject(res);
        });

        router.Register("sheet_format.generate", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<SheetFormatGenerateParams>()
                : throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for sheet_format.generate");
            var res = new SheetFormatGenerator(sw).Generate(p!, ct);
            return JObject.FromObject(res);
        });

        router.Register("drawing.create", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<DrawingCreateParams>()
                : new DrawingCreateParams();
            var res = new DrawingCreationAdapter(sw).CreateDrawing(p ?? new DrawingCreateParams(), ct);
            return JObject.FromObject(res);
        });

        router.Register("view.create", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<ViewCreateParams>()
                : throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for view.create");
            var res = new ViewCreationAdapter(sw).CreateView(p!, ct);
            return JObject.FromObject(res);
        });

        router.Register("view.update", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<ViewUpdateParams>()
                : throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for view.update");
            var res = new ViewCreationAdapter(sw).UpdateView(p!, ct);
            return JObject.FromObject(res);
        });

        router.Register("model_items.insert", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<ModelItemsInsertParams>()
                : throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for model_items.insert");
            var res = new AnnotationPlacementAdapter(sw).InsertModelItems(p!, ct);
            return JObject.FromObject(res);
        });

        router.Register("dimensions.auto_arrange", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<DimensionsAutoArrangeParams>()
                : throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for dimensions.auto_arrange");
            var res = new AnnotationPlacementAdapter(sw).AutoArrangeDimensions(p!, ct);
            return JObject.FromObject(res);
        });

        router.Register("center_mark.add", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<CenterMarkAddParams>()
                : throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for center_mark.add");
            var res = new AnnotationPlacementAdapter(sw).AutoInsertCenterMarks(p!, ct);
            return JObject.FromObject(res);
        });

        router.Register("dimension.hide", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<DimensionHideParams>()
                : throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for dimension.hide");
            var res = new AnnotationPlacementAdapter(sw).HideDimension(p!, ct);
            return JObject.FromObject(res);
        });

        router.Register("dimension.show", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<DimensionShowParams>()
                : throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for dimension.show");
            var res = new AnnotationPlacementAdapter(sw).ShowDimension(p!, ct);
            return JObject.FromObject(res);
        });

        router.Register("dimension.move", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<DimensionMoveParams>()
                : throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for dimension.move");
            var res = new AnnotationPlacementAdapter(sw).MoveDimension(p!, ct);
            return JObject.FromObject(res);
        });

        router.Register("document.save", (doc, op, ct) =>
        {
            var p = op.Params is JObject pObj
                ? pObj.ToObject<DocumentSaveParams>()
                : throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for document.save");
            var res = docOps.Save(doc, p!, ExtractJobId(op), ct);
            return JObject.FromObject(res);
        });

        return router;
    }

    private static string? ExtractJobId(Operation op)
    {
        if (op == null) return null;
        if (op.Params is JObject pObj && pObj["_meta"]?["job_id"] is JValue jv)
        {
            var id = jv.Value<string>();
            if (!string.IsNullOrEmpty(id)) return id;
        }
        if (!string.IsNullOrEmpty(op.OperationId))
        {
            var colonIdx = op.OperationId.IndexOf(':');
            return colonIdx > 0 ? op.OperationId.Substring(0, colonIdx) : op.OperationId;
        }
        return null;
    }

    private sealed class DefaultAddinCommandHandler : ICommandHandler
    {
        private readonly ISldWorks _sw;
        private readonly OperationRouter _router;
        private readonly ExecutionServer.Core.Events.DocumentEventMonitor? _eventMonitor;
        private readonly SettingsGuard? _settingsGuard;
        private readonly DrawingSnapshotAdapter _snapshotAdapter;

        public DefaultAddinCommandHandler(
            ISldWorks sw,
            OperationRouter router,
            ExecutionServer.Core.Events.DocumentEventMonitor? eventMonitor = null,
            SettingsGuard? settingsGuard = null)
        {
            _sw = sw ?? throw new ArgumentNullException(nameof(sw));
            _router = router ?? throw new ArgumentNullException(nameof(router));
            _eventMonitor = eventMonitor;
            _settingsGuard = settingsGuard;
            _snapshotAdapter = new DrawingSnapshotAdapter(sw);
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
                _eventMonitor.CurrentJobId = ExtractJobId(op);
            }
            try
            {
                return _router.Route(document, op, ct);
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

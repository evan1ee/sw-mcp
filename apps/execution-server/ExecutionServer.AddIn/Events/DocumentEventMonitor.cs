using System;
using System.Collections.Concurrent;
using ExecutionServer.Core.Events;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ledger;
using ExecutionServer.Core.Ownership;
using Newtonsoft.Json.Linq;
using SolidWorks.Interop.sldworks;

namespace ExecutionServer.AddIn.Events;

/// <summary>
/// Monitors SOLIDWORKS document lifecycle events and forwards them as document.event JSON-RPC notifications (spec 8.6.5).
/// Subscribes per-document part events on PartDoc (DestroyNotify2, FileSavePostNotify, RegenNotify/RegenPostNotify).
/// Adheres strictly to Guideline G1: never releases ISldWorks or IModelDoc2 COM wrappers.
/// </summary>
public sealed class SldWorksDocumentEventMonitor : DocumentEventMonitor
{
    private sealed class PartSubscription
    {
        public PartSubscription(
            DPartDocEvents_Event events,
            DPartDocEvents_RegenNotifyEventHandler? regen,
            DPartDocEvents_RegenPostNotifyEventHandler regenPost,
            DPartDocEvents_FileSavePostNotifyEventHandler savePost,
            DPartDocEvents_DestroyNotify2EventHandler destroy)
        {
            Events = events;
            Regen = regen;
            RegenPost = regenPost;
            SavePost = savePost;
            Destroy = destroy;
        }

        public DPartDocEvents_Event Events { get; }
        public DPartDocEvents_RegenNotifyEventHandler? Regen { get; }
        public DPartDocEvents_RegenPostNotifyEventHandler RegenPost { get; }
        public DPartDocEvents_FileSavePostNotifyEventHandler SavePost { get; }
        public DPartDocEvents_DestroyNotify2EventHandler Destroy { get; }

        public void Detach(bool isDestroying = false)
        {
            try
            {
                if (Regen != null) Events.RegenNotify -= Regen;
                Events.RegenPostNotify -= RegenPost;
                Events.FileSavePostNotify -= SavePost;
                if (!isDestroying)
                {
                    Events.DestroyNotify2 -= Destroy;
                }
            }
            catch
            {
            }
        }
    }

    private ISldWorks? _sw;
    private DSldWorksEvents_ActiveDocChangeNotifyEventHandler? _activeDocHandler;
    private DSldWorksEvents_FileCloseNotifyEventHandler? _fileCloseHandler;
    private readonly ConcurrentDictionary<string, PartSubscription> _partSubscriptions =
        new ConcurrentDictionary<string, PartSubscription>(StringComparer.OrdinalIgnoreCase);

    public SldWorksDocumentEventMonitor(Action<string, JToken> notificationSink)
        : this(notificationSink, null, null)
    {
    }

    public SldWorksDocumentEventMonitor(
        Action<string, JToken> notificationSink,
        DocumentOwnershipTable? ownershipTable = null,
        OperationLedger? ledger = null)
        : base(notificationSink, ownershipTable, ledger)
    {
    }

    public void Attach(ISldWorks sw)
    {
        if (sw == null) return;
        _sw = sw;

        if (OwnershipTable != null)
        {
            OwnershipTable.DocumentRecorded += OnDocumentRecorded;
        }

        _activeDocHandler = () =>
        {
            try
            {
                var doc = (IModelDoc2)_sw.ActiveDoc;
                if (doc != null)
                {
                    // Guideline G1: Never release ISldWorks or IModelDoc2 wrappers
                    var path = doc.GetPathName();
                    var title = doc.GetTitle();
                    var name = !string.IsNullOrEmpty(path) ? path : title;
                    OnDocumentEvent(name, DocumentEventParamsEvent.ActiveChanged);
                }
            }
            catch
            {
            }
            return 0;
        };

        _fileCloseHandler = (string docName, int reason) =>
        {
            try
            {
                // Spike answer 11: FileCloseNotify never fires for API close; parts rely on DestroyNotify2.
                // Forward only if non-part (drawing / title).
                if (!DocumentOwnershipTable.IsPart(docName))
                {
                    OnDocumentEvent(docName, DocumentEventParamsEvent.Close);
                }
            }
            catch
            {
            }
            return 0;
        };

        var appEvents = _sw as DSldWorksEvents_Event;
        if (appEvents != null)
        {
            appEvents.ActiveDocChangeNotify += _activeDocHandler;
            appEvents.FileCloseNotify += _fileCloseHandler;
        }
    }

    private void OnDocumentRecorded(string path)
    {
        TrackDocument(path);
    }

    public void TrackDocument(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || _sw == null) return;
        var normalized = DocumentOwnershipTable.NormalizePath(path);
        if (!DocumentOwnershipTable.IsPart(normalized)) return;

        if (_partSubscriptions.ContainsKey(normalized)) return;

        try
        {
            var doc = _sw.GetOpenDocumentByName(normalized) as IModelDoc2;
            if (doc != null)
            {
                TrackDocument(doc, normalized);
            }
        }
        catch
        {
        }
    }

    public void TrackDocument(IModelDoc2 doc, string? path = null)
    {
        if (doc == null) return;

        try
        {
            var docPath = !string.IsNullOrEmpty(path) ? path : doc.GetPathName();
            if (string.IsNullOrEmpty(docPath)) return;

            var normalized = DocumentOwnershipTable.NormalizePath(docPath);
            if (!DocumentOwnershipTable.IsPart(normalized)) return;

            if (_partSubscriptions.ContainsKey(normalized)) return;

            var partDoc = doc as PartDoc;
            var pe = partDoc as DPartDocEvents_Event;
            if (pe == null) return;

            DPartDocEvents_RegenPostNotifyEventHandler r2 = () =>
            {
                try
                {
                    OnDocumentEvent(normalized, DocumentEventParamsEvent.Regen);
                }
                catch
                {
                }
                return 0;
            };

            DPartDocEvents_FileSavePostNotifyEventHandler s2 = (saveType, fileName) =>
            {
                try
                {
                    OnDocumentEvent(normalized, DocumentEventParamsEvent.Save);
                }
                catch
                {
                }
                return 0;
            };

            DPartDocEvents_DestroyNotify2EventHandler d2 = destroyType =>
            {
                try
                {
                    if (_partSubscriptions.TryRemove(normalized, out var sub))
                    {
                        sub.Detach(isDestroying: true);
                    }
                    OnDocumentEvent(normalized, DocumentEventParamsEvent.Close);
                }
                catch
                {
                }
                return 0;
            };

            pe.RegenPostNotify += r2;
            pe.FileSavePostNotify += s2;
            pe.DestroyNotify2 += d2;

            var subscription = new PartSubscription(pe, null, r2, s2, d2);
            _partSubscriptions.TryAdd(normalized, subscription);
        }
        catch
        {
        }
    }

    public void Detach()
    {
        if (OwnershipTable != null)
        {
            OwnershipTable.DocumentRecorded -= OnDocumentRecorded;
        }

        foreach (var sub in _partSubscriptions.Values)
        {
            sub.Detach();
        }
        _partSubscriptions.Clear();

        if (_sw != null)
        {
            var appEvents = _sw as DSldWorksEvents_Event;
            if (appEvents != null)
            {
                if (_activeDocHandler != null) appEvents.ActiveDocChangeNotify -= _activeDocHandler;
                if (_fileCloseHandler != null) appEvents.FileCloseNotify -= _fileCloseHandler;
            }
            _sw = null;
        }
    }

    public override void Dispose()
    {
        base.Dispose();
        Detach();
    }
}

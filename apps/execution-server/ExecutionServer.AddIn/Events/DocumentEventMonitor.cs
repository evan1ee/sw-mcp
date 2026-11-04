using System;
using System.Runtime.InteropServices;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;
using SolidWorks.Interop.sldworks;

namespace ExecutionServer.AddIn.Events;

/// <summary>
/// Monitors SOLIDWORKS document lifecycle events and forwards them as document.event JSON-RPC notifications (spec 8.6.5).
/// Tags events that occur during an active AI job with _meta.job_id.
/// </summary>
public sealed class DocumentEventMonitor : IDisposable
{
    private readonly Action<string, JToken> _notificationSink;
    private ISldWorks? _sw;
    private DSldWorksEvents_ActiveDocChangeNotifyEventHandler? _activeDocHandler;
    private DSldWorksEvents_FileCloseNotifyEventHandler? _fileCloseHandler;
    private readonly object _gate = new object();
    private string? _currentJobId;
    private bool _disposed;

    public DocumentEventMonitor(Action<string, JToken> notificationSink)
    {
        _notificationSink = notificationSink ?? throw new ArgumentNullException(nameof(notificationSink));
    }

    public string? CurrentJobId
    {
        get
        {
            lock (_gate)
            {
                return _currentJobId;
            }
        }
        set
        {
            lock (_gate)
            {
                _currentJobId = value;
            }
        }
    }

    public void OnDocumentEvent(string document, DocumentEventParamsEvent evt)
    {
        string? jobId;
        lock (_gate)
        {
            if (_disposed)
            {
                return;
            }
            jobId = _currentJobId;
        }

        var p = new DocumentEventParams
        {
            Document = document,
            Event = evt,
            Meta = jobId != null ? new Meta { JobId = jobId } : null
        };

        try
        {
            _notificationSink("document.event", JObject.FromObject(p));
        }
        catch
        {
            // Sink might be closed
        }
    }

    public void Attach(ISldWorks sw)
    {
        if (sw == null) return;
        _sw = sw;

        _activeDocHandler = () =>
        {
            try
            {
                var doc = (IModelDoc2)_sw.ActiveDoc;
                if (doc != null)
                {
                    try
                    {
                        var path = doc.GetPathName();
                        var title = doc.GetTitle();
                        var name = !string.IsNullOrEmpty(path) ? path : title;
                        OnDocumentEvent(name, DocumentEventParamsEvent.ActiveChanged);
                    }
                    finally
                    {
                        Marshal.ReleaseComObject(doc);
                    }
                }
            }
            catch
            {
            }
            return 0;
        };

        _fileCloseHandler = (string docName, int reason) =>
        {
            OnDocumentEvent(docName, DocumentEventParamsEvent.Close);
            return 0;
        };

        var appEvents = _sw as DSldWorksEvents_Event;
        if (appEvents != null)
        {
            appEvents.ActiveDocChangeNotify += _activeDocHandler;
            appEvents.FileCloseNotify += _fileCloseHandler;
        }
    }

    public void Detach()
    {
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

    public void Dispose()
    {
        lock (_gate)
        {
            _disposed = true;
        }
        Detach();
    }
}

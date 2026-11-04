using System;
using System.Runtime.InteropServices;
using ExecutionServer.Core.Events;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;
using SolidWorks.Interop.sldworks;

namespace ExecutionServer.AddIn.Events;

/// <summary>
/// Monitors SOLIDWORKS document lifecycle events and forwards them as document.event JSON-RPC notifications (spec 8.6.5).
/// </summary>
public sealed class SldWorksDocumentEventMonitor : DocumentEventMonitor
{
    private ISldWorks? _sw;
    private DSldWorksEvents_ActiveDocChangeNotifyEventHandler? _activeDocHandler;
    private DSldWorksEvents_FileCloseNotifyEventHandler? _fileCloseHandler;

    public SldWorksDocumentEventMonitor(Action<string, JToken> notificationSink)
        : base(notificationSink)
    {
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

    public override void Dispose()
    {
        base.Dispose();
        Detach();
    }
}

using System;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Events;

/// <summary>
/// Monitors document lifecycle events and forwards them as document.event JSON-RPC notifications (spec 8.6.5).
/// Tags events that occur during an active AI job with _meta.job_id.
/// </summary>
public class DocumentEventMonitor : IDisposable
{
    private readonly Action<string, JToken> _notificationSink;
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

    public virtual void Dispose()
    {
        lock (_gate)
        {
            _disposed = true;
        }
    }
}

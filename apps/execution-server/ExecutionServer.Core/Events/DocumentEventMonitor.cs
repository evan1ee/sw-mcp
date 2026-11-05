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
    private readonly Ownership.DocumentOwnershipTable? _ownershipTable;
    private readonly Ledger.OperationLedger? _ledger;
    private readonly object _gate = new object();
    private string? _currentJobId;
    private bool _disposed;

    public DocumentEventMonitor(Action<string, JToken> notificationSink)
        : this(notificationSink, null, null)
    {
    }

    public DocumentEventMonitor(
        Action<string, JToken> notificationSink,
        Ownership.DocumentOwnershipTable? ownershipTable = null,
        Ledger.OperationLedger? ledger = null)
    {
        _notificationSink = notificationSink ?? throw new ArgumentNullException(nameof(notificationSink));
        _ownershipTable = ownershipTable;
        _ledger = ledger;
    }

    public Ownership.DocumentOwnershipTable? OwnershipTable => _ownershipTable;
    public Ledger.OperationLedger? Ledger => _ledger;

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
        if (string.IsNullOrWhiteSpace(document))
        {
            return;
        }

        var normalizedDoc = Ownership.DocumentOwnershipTable.NormalizePath(document);
        bool isPart = Ownership.DocumentOwnershipTable.IsPart(normalizedDoc);

        // If an ownership table is present, part events are filtered to documents the table lists (spec 8.6.5).
        if (_ownershipTable != null && isPart)
        {
            bool tracked = evt == DocumentEventParamsEvent.Close
                ? _ownershipTable.HasEntry(normalizedDoc)
                : _ownershipTable.IsTracked(normalizedDoc);

            if (!tracked)
            {
                return;
            }
        }

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
            Document = normalizedDoc,
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

        if (evt == DocumentEventParamsEvent.Close)
        {
            _ownershipTable?.Forget(normalizedDoc);
            _ledger?.ForgetDocument(normalizedDoc);
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

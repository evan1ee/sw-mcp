using System;
using System.Threading;
using ExecutionServer.Core.Ipc;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Dispatch;

/// <summary>
/// Dispatches IPC commands to the captured UI thread SynchronizationContext (spec 8.6.2, ADR-059).
/// Enforces single-command serialization, thread-affinity assertions, re-entrant drain protection,
/// and monitors the 30-second UI-blocked timeout (spec 8.6.3).
/// </summary>
public sealed class UIThreadDispatcher : IDisposable
{
    private readonly SynchronizationContext _syncContext;
    private readonly TimeSpan _uiBlockedTimeout;
    private readonly int _targetThreadId;
    private readonly Action<Exception>? _onUnexpected;
    private readonly object _gate = new object();
    private readonly object _drainGate = new object();
    private bool _draining;
    private bool _disposed;

    public UIThreadDispatcher(
        SynchronizationContext syncContext,
        TimeSpan? uiBlockedTimeout = null,
        int? targetThreadId = null,
        Action<Exception>? onUnexpected = null)
    {
        _syncContext = syncContext ?? throw new ArgumentNullException(nameof(syncContext));
        _uiBlockedTimeout = uiBlockedTimeout ?? TimeSpan.FromSeconds(30);
        _targetThreadId = targetThreadId ?? Thread.CurrentThread.ManagedThreadId;
        _onUnexpected = onUnexpected;
    }

    public int TargetThreadId => _targetThreadId;

    public void Drain(IpcSession session)
    {
        if (session == null)
        {
            throw new ArgumentNullException(nameof(session));
        }

        if (Thread.CurrentThread.ManagedThreadId != _targetThreadId)
        {
            _onUnexpected?.Invoke(new InvalidOperationException(
                $"Drain called on wrong thread: expected {_targetThreadId}, current is {Thread.CurrentThread.ManagedThreadId}"));
            return;
        }

        lock (_drainGate)
        {
            if (_draining)
            {
                // Reentrant drain refused; relying on re-post when outer command ends
                return;
            }
            _draining = true;
        }

        try
        {
            if (!session.IsClosed)
            {
                session.RunNext();
            }
        }
        finally
        {
            lock (_drainGate)
            {
                _draining = false;
            }

            // When a command ends, re-post if the queue is not empty
            if (!session.IsClosed && session.HasQueuedCommands)
            {
                Dispatch(session);
            }
        }
    }

    public void Dispatch(IpcSession session)
    {
        if (session == null)
        {
            throw new ArgumentNullException(nameof(session));
        }

        lock (_gate)
        {
            if (_disposed)
            {
                return;
            }
        }

        Timer? timer = null;
        int executed = 0;

        timer = new Timer(_ =>
        {
            if (Interlocked.CompareExchange(ref executed, 0, 0) == 0)
            {
                try
                {
                    session.Notify("session.ui_blocked", new JObject
                    {
                        ["waited_ms"] = (long)_uiBlockedTimeout.TotalMilliseconds
                    });
                }
                catch
                {
                    // Session might be closed or disposed
                }
            }
        }, null, (int)_uiBlockedTimeout.TotalMilliseconds, Timeout.Infinite);

        _syncContext.Post(_ =>
        {
            try
            {
                Interlocked.Exchange(ref executed, 1);
                timer?.Dispose();

                lock (_gate)
                {
                    if (_disposed)
                    {
                        return;
                    }
                }

                Drain(session);
            }
            catch (Exception ex)
            {
                _onUnexpected?.Invoke(ex);
            }
        }, null);
    }

    public void Dispose()
    {
        lock (_gate)
        {
            _disposed = true;
        }
    }
}

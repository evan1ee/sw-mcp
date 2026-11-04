using System;
using System.Threading;
using ExecutionServer.Core.Ipc;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Dispatch;

/// <summary>
/// Dispatches IPC commands to the captured UI thread SynchronizationContext (spec 8.6.2).
/// Enforces single-command serialization and monitors the 30-second UI-blocked timeout (spec 8.6.3).
/// </summary>
public sealed class UIThreadDispatcher : IDisposable
{
    private readonly SynchronizationContext _syncContext;
    private readonly TimeSpan _uiBlockedTimeout;
    private readonly object _gate = new object();
    private bool _disposed;

    public UIThreadDispatcher(SynchronizationContext syncContext, TimeSpan? uiBlockedTimeout = null)
    {
        _syncContext = syncContext ?? throw new ArgumentNullException(nameof(syncContext));
        _uiBlockedTimeout = uiBlockedTimeout ?? TimeSpan.FromSeconds(30);
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

                if (!session.IsClosed)
                {
                    session.RunNext();
                }
            }
            catch (Exception)
            {
                // Uncaught UI-thread command exceptions are logged via onUnexpected in IpcSession
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

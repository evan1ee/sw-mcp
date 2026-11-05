using System;
using System.Threading;
using System.Windows.Forms;

namespace ExecutionServer.AddIn.Dispatch;

/// <summary>
/// SynchronizationContext backed by a hidden WinForms Control on the STA UI thread (ADR-059, spec 8.6.2).
/// Uses BeginInvoke to dispatch work without blocking the caller.
/// </summary>
public sealed class ControlSynchronizationContext : SynchronizationContext, IDisposable
{
    private readonly Control _control;
    private readonly int _uiThreadId;
    private bool _disposed;

    public ControlSynchronizationContext()
    {
        _uiThreadId = Thread.CurrentThread.ManagedThreadId;
        _control = new Control();
        // Force Win32 window handle creation on the STA UI thread
        var _ = _control.Handle;
    }

    public int UIThreadId => _uiThreadId;

    public override SynchronizationContext CreateCopy() => this;

    public override void Post(SendOrPostCallback d, object? state)
    {
        if (d == null) throw new ArgumentNullException(nameof(d));
        if (_disposed || _control.IsDisposed) return;

        try
        {
            _control.BeginInvoke(d, state);
        }
        catch (ObjectDisposedException)
        {
        }
        catch (InvalidOperationException)
        {
            // Host or control handle may be shutting down
        }
    }

    public override void Send(SendOrPostCallback d, object? state)
    {
        if (d == null) throw new ArgumentNullException(nameof(d));
        if (_disposed || _control.IsDisposed) return;

        try
        {
            _control.Invoke(d, state);
        }
        catch (ObjectDisposedException)
        {
        }
        catch (InvalidOperationException)
        {
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        try
        {
            if (!_control.IsDisposed)
            {
                if (_control.InvokeRequired)
                {
                    _control.BeginInvoke((Action)(() => _control.Dispose()));
                }
                else
                {
                    _control.Dispose();
                }
            }
        }
        catch
        {
        }
    }
}

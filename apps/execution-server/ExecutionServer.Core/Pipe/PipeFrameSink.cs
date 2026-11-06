using System;
using System.Collections.Concurrent;
using System.IO;
using System.Threading;
using ExecutionServer.Core.Ipc;

namespace ExecutionServer.Core.Pipe;

/// <summary>
/// Thread-safe outgoing frame queue for named-pipe IPC (ADR-059, spec 8.6.2).
/// The caller (e.g. UI thread) enqueues encoded frames without blocking on pipe I/O.
/// A dedicated background thread flushes frames sequentially to the stream.
/// </summary>
public sealed class PipeFrameSink : IFrameSink, IDisposable
{
    private readonly Stream _stream;
    private readonly int _maxFrameBytes;
    private readonly bool _leaveOpen;
    private readonly BlockingCollection<byte[]> _queue = new BlockingCollection<byte[]>();
    private readonly Thread _writerThread;
    private readonly CancellationTokenSource _cts = new CancellationTokenSource();
    private readonly ManualResetEventSlim _flushedEvent = new ManualResetEventSlim(false);
    private int _closed;
    private bool _disposed;

    public PipeFrameSink(Stream stream, int maxFrameBytes, bool leaveOpen = false)
    {
        _stream = stream ?? throw new ArgumentNullException(nameof(stream));
        _maxFrameBytes = maxFrameBytes;
        _leaveOpen = leaveOpen;
        _writerThread = new Thread(WriteLoop)
        {
            IsBackground = true,
            Name = "sw-mcp-pipe-writer"
        };
        _writerThread.Start();
    }

    public void Write(byte[] payload)
    {
        if (payload == null) throw new ArgumentNullException(nameof(payload));
        if (Volatile.Read(ref _closed) != 0 || _queue.IsAddingCompleted)
        {
            return;
        }

        var frame = FrameCodec.Encode(payload, _maxFrameBytes);
        try
        {
            _queue.Add(frame);
        }
        catch (InvalidOperationException)
        {
            // Adding was marked completed concurrent with this call
        }
    }

    private void WriteLoop()
    {
        try
        {
            foreach (var frame in _queue.GetConsumingEnumerable(_cts.Token))
            {
                try
                {
                    _stream.Write(frame, 0, frame.Length);
                    _stream.Flush();
                }
                catch
                {
                    // Stream closed or pipe broken under us
                    break;
                }
            }
        }
        catch (OperationCanceledException)
        {
        }
        catch (Exception)
        {
            // ADR-059: Catch and survive unexpected exceptions on background thread
        }
        finally
        {
            try
            {
                _flushedEvent.Set();
            }
            catch (ObjectDisposedException)
            {
            }
        }
    }

    public void Close()
    {
        if (Interlocked.Exchange(ref _closed, 1) != 0)
        {
            return;
        }

        try
        {
            _queue.CompleteAdding();
            // Wait briefly for queued frames to flush before closing the stream
            _flushedEvent.Wait(1000);
        }
        catch
        {
        }

        try
        {
            _cts.Cancel();
        }
        catch
        {
        }

        if (!_leaveOpen)
        {
            try
            {
                _stream.Close();
            }
            catch
            {
            }
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        Close();

        if (_writerThread.IsAlive)
        {
            _writerThread.Join(500);
        }

        _cts.Dispose();
        _flushedEvent.Dispose();
        _queue.Dispose();
    }
}

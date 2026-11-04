using System;
using System.IO;
using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Threading;
using ExecutionServer.Core.Dispatch;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ledger;

namespace ExecutionServer.Core.Pipe;

/// <summary>
/// In-process named-pipe server for the SOLIDWORKS add-in (spec 8.6.1).
/// Uses length-prefixed framing and restricts access to the current Windows user.
/// </summary>
public sealed class NamedPipeServer : IDisposable
{
    private readonly string _pipeName;
    private readonly SessionConfig _config;
    private readonly OperationLedger _ledger;
    private readonly ICommandHandler _handler;
    private readonly UIThreadDispatcher _dispatcher;
    private readonly Action<Exception>? _onUnexpected;
    private readonly CancellationTokenSource _cts = new CancellationTokenSource();
    private readonly Thread _serverThread;
    private readonly ManualResetEventSlim _startedEvent = new ManualResetEventSlim(false);
    private NamedPipeServerStream? _activeStream;
    private IpcSession? _activeSession;
    private readonly object _gate = new object();
    private bool _disposed;

    public NamedPipeServer(
        string pipeName,
        SessionConfig config,
        OperationLedger ledger,
        ICommandHandler handler,
        UIThreadDispatcher dispatcher,
        Action<Exception>? onUnexpected = null)
    {
        _pipeName = pipeName ?? throw new ArgumentNullException(nameof(pipeName));
        _config = config ?? throw new ArgumentNullException(nameof(config));
        _ledger = ledger ?? throw new ArgumentNullException(nameof(ledger));
        _handler = handler ?? throw new ArgumentNullException(nameof(handler));
        _dispatcher = dispatcher ?? throw new ArgumentNullException(nameof(dispatcher));
        _onUnexpected = onUnexpected;

        _serverThread = new Thread(ListenLoop)
        {
            IsBackground = true,
            Name = "sw-mcp-pipe-server"
        };
        _serverThread.Start();
        _startedEvent.Wait(5000);
    }

    public string PipeName => _pipeName;

    public IpcSession? ActiveSession
    {
        get
        {
            lock (_gate)
            {
                return _activeSession;
            }
        }
    }

    public static PipeSecurity CreateCurrentUserSecurity()
    {
        var security = new PipeSecurity();
        var user = WindowsIdentity.GetCurrent().User;
        if (user != null)
        {
            security.SetOwner(user);
            security.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);
            security.AddAccessRule(new PipeAccessRule(user, PipeAccessRights.ReadWrite, AccessControlType.Allow));
        }
        return security;
    }

    public static string GeneratePipeName(int pid)
    {
        var randomBytes = new byte[4];
        using (var rng = System.Security.Cryptography.RandomNumberGenerator.Create())
        {
            rng.GetBytes(randomBytes);
        }
        var hex = BitConverter.ToString(randomBytes).Replace("-", "").ToLowerInvariant();
        return $"sw-mcp-addin-{pid}-{hex}";
    }

    private void ListenLoop()
    {
        _startedEvent.Set();

        while (!_cts.IsCancellationRequested)
        {
            NamedPipeServerStream? stream = null;
            try
            {
                var security = CreateCurrentUserSecurity();
                stream = new NamedPipeServerStream(
                    _pipeName,
                    PipeDirection.InOut,
                    NamedPipeServerStream.MaxAllowedServerInstances,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous,
                    65536,
                    65536,
                    security);

                lock (_gate)
                {
                    if (_disposed)
                    {
                        stream.Dispose();
                        break;
                    }
                    _activeStream = stream;
                }

                var connectTask = stream.WaitForConnectionAsync(_cts.Token);
                connectTask.GetAwaiter().GetResult();

                var sink = new PipeFrameSink(stream, _config.MaxFrameBytes);
                var session = new IpcSession(
                    _config,
                    _ledger,
                    _handler,
                    sink,
                    _onUnexpected,
                    onCommandEnqueued: s => _dispatcher.Dispatch(s));

                lock (_gate)
                {
                    _activeSession = session;
                }

                while (!_cts.IsCancellationRequested && stream.IsConnected && !session.IsClosed)
                {
                    byte[]? payload;
                    try
                    {
                        payload = FrameCodec.Read(stream, _config.MaxFrameBytes);
                    }
                    catch (Exception)
                    {
                        break;
                    }

                    if (payload == null)
                    {
                        break;
                    }

                    session.Receive(payload);
                }

                session.Close();
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                if (!_cts.IsCancellationRequested)
                {
                    _onUnexpected?.Invoke(ex);
                }
            }
            finally
            {
                lock (_gate)
                {
                    _activeSession = null;
                    _activeStream = null;
                }
                if (stream != null)
                {
                    try
                    {
                        stream.Dispose();
                    }
                    catch
                    {
                    }
                }
            }
        }
    }

    public void Dispose()
    {
        lock (_gate)
        {
            if (_disposed)
            {
                return;
            }
            _disposed = true;
        }

        _cts.Cancel();

        lock (_gate)
        {
            try
            {
                _activeSession?.Close();
            }
            catch
            {
            }
            try
            {
                _activeStream?.Dispose();
            }
            catch
            {
            }
        }

        if (_serverThread.IsAlive)
        {
            _serverThread.Join(2000);
        }
        _cts.Dispose();
        _startedEvent.Dispose();
    }

    private sealed class PipeFrameSink : IFrameSink
    {
        private readonly Stream _stream;
        private readonly int _maxFrameBytes;
        private readonly object _writeLock = new object();
        private bool _closed;

        public PipeFrameSink(Stream stream, int maxFrameBytes)
        {
            _stream = stream;
            _maxFrameBytes = maxFrameBytes;
        }

        public void Write(byte[] payload)
        {
            lock (_writeLock)
            {
                if (_closed)
                {
                    return;
                }
                var frame = FrameCodec.Encode(payload, _maxFrameBytes);
                _stream.Write(frame, 0, frame.Length);
                _stream.Flush();
            }
        }

        public void Close()
        {
            lock (_writeLock)
            {
                if (_closed)
                {
                    return;
                }
                _closed = true;
                try
                {
                    _stream.Close();
                }
                catch
                {
                }
            }
        }
    }
}

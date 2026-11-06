using System.Collections.Generic;
using System.Linq;
using System.Text;
using ExecutionServer.Core.Ipc;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Tests.Support;

/// <summary>Records frames and close events in order. Thread-safe.</summary>
public sealed class RecordingSink : IFrameSink
{
    public const string CloseMarker = "<close>";

    private readonly object _gate = new object();
    private readonly List<object> _events = new List<object>();

    public int CloseCount { get; private set; }

    /// <summary>Raw payloads, for size checks.</summary>
    public IReadOnlyList<byte[]> Payloads
    {
        get
        {
            lock (_gate)
            {
                return _events.OfType<byte[]>().ToList();
            }
        }
    }

    /// <summary>Parsed frames in write order (close events omitted).</summary>
    public IReadOnlyList<JToken> Frames => Payloads.Select(p => Fixtures.Parse(Encoding.UTF8.GetString(p))).ToList();

    /// <summary>Frames as parsed JSON and the close marker, in order.</summary>
    public IReadOnlyList<object> Events
    {
        get
        {
            lock (_gate)
            {
                return _events
                    .Select(e => e is byte[] b ? (object)Fixtures.Parse(Encoding.UTF8.GetString(b)) : e)
                    .ToList();
            }
        }
    }

    public void Write(byte[] payload)
    {
        lock (_gate)
        {
            _events.Add(payload);
        }
    }

    public void Close()
    {
        lock (_gate)
        {
            CloseCount++;
            _events.Add(CloseMarker);
        }
    }
}

using System;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ipc;

/// <summary>Immutable settings of a session. The token never appears in <see cref="ToString"/> or an exception.</summary>
public sealed class SessionConfig
{
    /// <summary>Smallest frame limit that still leaves room for a chunk frame's envelope.</summary>
    public const int MinFrameBytes = 256;

    public SessionConfig(string token, HelloResult hello, bool versionSupported, string unsupportedMessage, int maxFrameBytes = 64 * 1024 * 1024)
    {
        if (string.IsNullOrEmpty(token))
        {
            throw new ArgumentException("A session token is required.", nameof(token));
        }

        if (hello == null)
        {
            throw new ArgumentNullException(nameof(hello));
        }

        if (maxFrameBytes < MinFrameBytes)
        {
            throw new ArgumentOutOfRangeException(nameof(maxFrameBytes), maxFrameBytes, "The frame limit must be at least " + MinFrameBytes + " bytes.");
        }

        Token = token;
        HelloResultJson = JObject.FromObject(hello);
        Hello = hello;
        VersionSupported = versionSupported;
        UnsupportedMessage = unsupportedMessage ?? string.Empty;
        MaxFrameBytes = maxFrameBytes;
    }

    public string Token { get; }

    public HelloResult Hello { get; }

    public bool VersionSupported { get; }

    public string UnsupportedMessage { get; }

    public int MaxFrameBytes { get; }

    /// <summary>The hello result as captured at construction, so later edits to <see cref="Hello"/> do not change replies.</summary>
    internal JObject HelloResultJson { get; }

    public override string ToString() =>
        "SessionConfig(versionSupported=" + VersionSupported + ", maxFrameBytes=" + MaxFrameBytes + ")";
}

using System;

namespace ExecutionServer.Core.Ipc;

/// <summary>A frame that is truncated or over the size limit.</summary>
public sealed class FrameException : Exception
{
    public FrameException(string message)
        : base(message)
    {
    }
}

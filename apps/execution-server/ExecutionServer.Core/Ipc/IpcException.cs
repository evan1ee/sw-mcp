using System;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ipc;

/// <summary>A failure with an ADR-037 catalogue code, raised by a command handler.</summary>
public sealed class IpcException : Exception
{
    public IpcException(string code, string message, JToken? details = null)
        : base(message)
    {
        Code = code;
        Details = details;
    }

    public string Code { get; }

    public JToken? Details { get; }
}

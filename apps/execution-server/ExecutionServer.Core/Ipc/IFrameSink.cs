namespace ExecutionServer.Core.Ipc;

/// <summary>Where a session writes its payloads. Implementations are thread-safe and never interleave two frames.</summary>
public interface IFrameSink
{
    void Write(byte[] payload);

    void Close();
}

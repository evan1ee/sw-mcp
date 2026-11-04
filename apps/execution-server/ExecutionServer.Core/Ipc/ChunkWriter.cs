using System;
using System.Collections.Generic;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ipc;

/// <summary>Splits an over-limit response frame into <c>response.chunk</c> notifications (spec 8.7).</summary>
internal static class ChunkWriter
{
    /// <summary>
    /// Chunk frames, each at most <paramref name="maxBytes"/> long. The split is on bytes of the encoded
    /// response, so a multi-byte character may straddle two chunks; the client joins before decoding.
    /// </summary>
    public static IReadOnlyList<byte[]> Split(long id, byte[] response, int maxBytes)
    {
        // Worst-case envelope: 19-digit numbers for id, index and count.
        var envelope = RpcFrames.Notification("response.chunk", ParamsOf(long.MaxValue, long.MaxValue, long.MaxValue, string.Empty));
        var rawPerChunk = (maxBytes - envelope.Length) / 4 * 3;
        if (rawPerChunk < 1)
        {
            throw new InvalidOperationException("Frame limit " + maxBytes + " is too small for a chunk frame.");
        }

        var count = (response.Length + rawPerChunk - 1) / rawPerChunk;
        var frames = new List<byte[]>(count);
        for (var index = 0; index < count; index++)
        {
            var start = index * rawPerChunk;
            var length = Math.Min(rawPerChunk, response.Length - start);
            var data = Convert.ToBase64String(response, start, length);
            frames.Add(RpcFrames.Notification("response.chunk", ParamsOf(id, index, count, data)));
        }

        return frames;
    }

    private static JToken ParamsOf(long id, long index, long count, string data) =>
        JObject.FromObject(new ResponseChunkParams { Id = id, Index = index, Count = count, Data = data });
}

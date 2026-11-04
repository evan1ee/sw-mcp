using System;
using System.IO;

namespace ExecutionServer.Core.Ipc;

/// <summary>Length-prefixed frames (ADR-036): a 4-byte little-endian length, then the payload.</summary>
public static class FrameCodec
{
    private const int HeaderBytes = 4;

    public static byte[] Encode(byte[] payload, int maxBytes)
    {
        if (payload == null)
        {
            throw new ArgumentNullException(nameof(payload));
        }

        if (payload.Length > maxBytes)
        {
            throw new FrameException("frame of " + payload.Length + " bytes is over the " + maxBytes + "-byte limit");
        }

        var frame = new byte[HeaderBytes + payload.Length];
        var length = (uint)payload.Length;
        frame[0] = (byte)(length & 0xFF);
        frame[1] = (byte)((length >> 8) & 0xFF);
        frame[2] = (byte)((length >> 16) & 0xFF);
        frame[3] = (byte)((length >> 24) & 0xFF);
        Buffer.BlockCopy(payload, 0, frame, HeaderBytes, payload.Length);
        return frame;
    }

    /// <summary>The next payload, or null at a clean end of stream. The length is checked before the body is allocated.</summary>
    public static byte[]? Read(Stream stream, int maxBytes)
    {
        if (stream == null)
        {
            throw new ArgumentNullException(nameof(stream));
        }

        var header = new byte[HeaderBytes];
        var got = ReadExactly(stream, header, HeaderBytes);
        if (got == 0)
        {
            return null;
        }

        if (got < HeaderBytes)
        {
            throw new FrameException("truncated frame header");
        }

        var length = (uint)header[0] | ((uint)header[1] << 8) | ((uint)header[2] << 16) | ((uint)header[3] << 24);
        if (length > (uint)maxBytes)
        {
            throw new FrameException("frame of " + length + " bytes is over the " + maxBytes + "-byte limit");
        }

        var body = new byte[length];
        if (ReadExactly(stream, body, (int)length) < (int)length)
        {
            throw new FrameException("truncated frame body");
        }

        return body;
    }

    /// <summary>Reads until <paramref name="count"/> bytes arrive; fewer only at the end of the stream.</summary>
    private static int ReadExactly(Stream stream, byte[] buffer, int count)
    {
        var total = 0;
        while (total < count)
        {
            var n = stream.Read(buffer, total, count - total);
            if (n <= 0)
            {
                break;
            }

            total += n;
        }

        return total;
    }
}

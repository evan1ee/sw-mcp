using System;
using System.IO;
using System.Text;
using ExecutionServer.Core.Ipc;
using Xunit;

namespace ExecutionServer.Tests;

public sealed class FrameCodecTests
{
    private const int Limit = 1024;

    [Fact]
    public void Golden_bytes()
    {
        var payload = Encoding.UTF8.GetBytes("{\"id\":1}");

        var frame = FrameCodec.Encode(payload, Limit);

        Assert.Equal(new byte[] { 0x08, 0, 0, 0 }, frame.AsSpanlessHead());
        Assert.Equal(payload, frame.AsSpanlessTail());
    }

    [Fact]
    public void Round_trip()
    {
        var first = Encoding.UTF8.GetBytes("{\"a\":\"草\"}");
        var second = Array.Empty<byte>();
        var stream = new MemoryStream();
        foreach (var f in new[] { first, second })
        {
            var encoded = FrameCodec.Encode(f, Limit);
            stream.Write(encoded, 0, encoded.Length);
        }

        stream.Position = 0;

        Assert.Equal(first, FrameCodec.Read(new OneByteStream(stream), Limit));
        Assert.Equal(second, FrameCodec.Read(new OneByteStream(stream), Limit));
        Assert.Null(FrameCodec.Read(stream, Limit));
    }

    [Theory]
    [InlineData(new byte[] { 0x08, 0x00 })]
    [InlineData(new byte[] { 0x08, 0x00, 0x00, 0x00, 0x41, 0x42 })]
    public void Truncated_header_and_body_throw(byte[] bytes)
    {
        Assert.Throws<FrameException>(() => FrameCodec.Read(new MemoryStream(bytes), Limit));
    }

    [Fact]
    public void Oversize_rejected_before_body()
    {
        var header = new byte[] { 0x40, 0x42, 0x0F, 0x00 }; // 1,000,000
        var stream = new CountingStream(new MemoryStream(header));

        Assert.Throws<FrameException>(() => FrameCodec.Read(stream, 100));

        Assert.Equal(4, stream.BytesRead);
    }

    [Fact]
    public void Encode_rejects_oversize_payload()
    {
        Assert.Throws<FrameException>(() => FrameCodec.Encode(new byte[Limit + 1], Limit));
    }

    [Fact]
    public void Clean_end_returns_null()
    {
        Assert.Null(FrameCodec.Read(new MemoryStream(Array.Empty<byte>()), Limit));
    }

    private sealed class OneByteStream : Stream
    {
        private readonly Stream _inner;

        public OneByteStream(Stream inner) => _inner = inner;

        public override bool CanRead => true;

        public override bool CanSeek => false;

        public override bool CanWrite => false;

        public override long Length => throw new NotSupportedException();

        public override long Position
        {
            get => throw new NotSupportedException();
            set => throw new NotSupportedException();
        }

        public override void Flush()
        {
        }

        public override int Read(byte[] buffer, int offset, int count) => _inner.Read(buffer, offset, Math.Min(count, 1));

        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();

        public override void SetLength(long value) => throw new NotSupportedException();

        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }

    private sealed class CountingStream : Stream
    {
        private readonly Stream _inner;

        public CountingStream(Stream inner) => _inner = inner;

        public int BytesRead { get; private set; }

        public override bool CanRead => true;

        public override bool CanSeek => false;

        public override bool CanWrite => false;

        public override long Length => throw new NotSupportedException();

        public override long Position
        {
            get => throw new NotSupportedException();
            set => throw new NotSupportedException();
        }

        public override void Flush()
        {
        }

        public override int Read(byte[] buffer, int offset, int count)
        {
            var n = _inner.Read(buffer, offset, count);
            BytesRead += n;
            return n;
        }

        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();

        public override void SetLength(long value) => throw new NotSupportedException();

        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }
}

internal static class ByteArrayExtensions
{
    public static byte[] AsSpanlessHead(this byte[] bytes)
    {
        var head = new byte[4];
        Array.Copy(bytes, head, 4);
        return head;
    }

    public static byte[] AsSpanlessTail(this byte[] bytes)
    {
        var tail = new byte[bytes.Length - 4];
        Array.Copy(bytes, 4, tail, 0, tail.Length);
        return tail;
    }
}

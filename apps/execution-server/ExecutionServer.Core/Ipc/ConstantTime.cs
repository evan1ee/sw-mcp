using System.Text;

namespace ExecutionServer.Core.Ipc;

public static class ConstantTime
{
    /// <summary>
    /// Compares two strings without an early exit on the first difference. The loop runs over the length of
    /// <paramref name="expected"/>, so timing reveals nothing about where the strings differ.
    /// </summary>
    public static bool TextEquals(string expected, string supplied)
    {
        var a = Encoding.UTF8.GetBytes(expected);
        var b = Encoding.UTF8.GetBytes(supplied);
        var diff = a.Length ^ b.Length;
        for (var i = 0; i < a.Length; i++)
        {
            var other = b.Length == 0 ? 0 : b[i % b.Length];
            diff |= a[i] ^ other;
        }

        return diff == 0;
    }
}

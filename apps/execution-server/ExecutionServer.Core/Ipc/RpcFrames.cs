using System.IO;
using System.Text;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ipc;

/// <summary>Builds and parses JSON-RPC frames (spec 8.7).</summary>
internal static class RpcFrames
{
    public const int CatalogueFault = -32000;
    public const int ParseError = -32700;
    public const int InvalidRequest = -32600;
    public const int MethodNotFound = -32601;
    public const int InvalidParams = -32602;
    public const int InternalError = -32603;

    private static readonly UTF8Encoding StrictUtf8 = new UTF8Encoding(false, true);
    private static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);

    public static JsonSerializer Serializer { get; } =
        JsonSerializer.Create(new JsonSerializerSettings { DateParseHandling = DateParseHandling.None });

    /// <summary>Parses one JSON value; dates stay strings. Throws JsonException or ArgumentException on bad input.</summary>
    public static JToken Parse(byte[] payload)
    {
        using var reader = new JsonTextReader(new StringReader(StrictUtf8.GetString(payload))) { DateParseHandling = DateParseHandling.None };
        var token = JToken.ReadFrom(reader);
        reader.Read(); // throws on trailing text
        return token;
    }

    public static byte[] Serialize(object frame) => Utf8.GetBytes(JsonConvert.SerializeObject(frame));

    public static byte[] Result(long id, JToken result) =>
        Serialize(new Response { Id = id, Result = result });

    public static byte[] Fault(long? id, int code, string message) =>
        Serialize(new Response { Id = id, Error = new RpcError { Code = code, Message = message } });

    public static byte[] CatalogueError(long id, Error error) =>
        Serialize(new Response { Id = id, Error = new RpcError { Code = CatalogueFault, Message = error.Message, Data = error } });

    public static byte[] Notification(string method, JToken? p) =>
        Serialize(new Notification { Method = method, Params = p });

    public static Error MakeError(string code, string message, JToken? details = null) =>
        new Error { Code = code, Message = message, Retryable = ErrorCodes.DefaultRetryable(code), Details = details };

    public static Error FromException(IpcException e) => MakeError(e.Code, e.Message, e.Details);

    public static Error Cancelled() => MakeError(ErrorCodes.EXEC_CANCELLED, "The job was cancelled.");

    /// <summary>The integer id of a request-like object, or null when absent or not a 64-bit integer.</summary>
    public static long? IdOf(JToken frame) =>
        frame is JObject o && o["id"] is JValue v && v.Type == JTokenType.Integer && v.Value is long l ? l : (long?)null;

    /// <summary>Major version of "major.minor", or -1 when the text is not a version.</summary>
    public static int MajorOf(string version)
    {
        var dot = version.IndexOf('.');
        var head = dot < 0 ? version : version.Substring(0, dot);
        return int.TryParse(head, out var major) && major >= 0 ? major : -1;
    }
}

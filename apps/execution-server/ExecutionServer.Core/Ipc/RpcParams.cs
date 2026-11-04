using System;
using System.Linq;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ipc;

/// <summary>Reads and checks request params (spec 8.7). Pure: replies are the session's business.</summary>
internal static class RpcParams
{
    /// <summary>
    /// Reads params as <typeparamref name="T"/>. False if they are missing but required, not an object,
    /// or do not convert; the conversion error text is dropped because it can echo input.
    /// </summary>
    public static bool TryRead<T>(JToken? p, bool required, out T? result)
        where T : class, new()
    {
        result = null;
        try
        {
            if (p == null || p.Type == JTokenType.Null)
            {
                if (!required)
                {
                    result = new T();
                    return true;
                }
            }
            else if (p is JObject)
            {
                result = p.ToObject<T>(RpcFrames.Serializer);
                if (result != null)
                {
                    return true;
                }
            }
        }
        catch (Exception ex) when (ex is JsonException || ex is FormatException || ex is InvalidCastException || ex is ArgumentException || ex is OverflowException)
        {
            // Falls through to false.
        }

        return false;
    }

    /// <summary>Checks what a generated type cannot: minItems 1 and no null list items.</summary>
    public static bool HasValidShape(OpsApplyParams p) =>
        p.Groups.Count > 0
        && p.Groups.All(g => g != null && g.Operations.Count > 0 && g.Operations.All(o => o != null));
}

using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ledger;

/// <summary>
/// Completed operation IDs, results and documents in completion order (spec 8.7). Thread-safe; outlives
/// pipe sessions so a reconnecting core can ask for it. Documents compare ignoring case (Windows paths).
/// </summary>
public sealed class OperationLedger
{
    private sealed class Entry
    {
        public Entry(string document, string id, JToken? result)
        {
            Document = document;
            Id = id;
            Result = result;
        }

        public string Document { get; }

        public string Id { get; }

        public JToken? Result { get; }
    }

    private readonly object _gate = new object();
    private readonly List<Entry> _entries = new List<Entry>();
    private readonly Dictionary<string, Entry> _byId = new Dictionary<string, Entry>(StringComparer.Ordinal);

    /// <summary>True if the operation completed; <paramref name="result"/> is a copy of its original result.</summary>
    public bool TryGet(string operationId, out JToken? result)
    {
        lock (_gate)
        {
            if (_byId.TryGetValue(operationId, out var entry))
            {
                result = entry.Result?.DeepClone();
                return true;
            }
        }

        result = null;
        return false;
    }

    /// <summary>Records a completed operation. Recording an ID twice is a caller bug and throws.</summary>
    public void Record(string document, string operationId, JToken? result)
    {
        var entry = new Entry(document, operationId, result?.DeepClone());
        lock (_gate)
        {
            if (_byId.ContainsKey(operationId))
            {
                throw new InvalidOperationException("operation " + operationId + " is already recorded");
            }

            _byId.Add(operationId, entry);
            _entries.Add(entry);
        }
    }

    public IReadOnlyList<string> CompletedIds()
    {
        lock (_gate)
        {
            return _entries.Select(e => e.Id).ToList();
        }
    }

    /// <summary>Forgets a document's entries; called when the add-in sees the document destroyed.</summary>
    public void ForgetDocument(string document)
    {
        lock (_gate)
        {
            foreach (var entry in _entries.Where(e => string.Equals(e.Document, document, StringComparison.OrdinalIgnoreCase)).ToList())
            {
                _entries.Remove(entry);
                _byId.Remove(entry.Id);
            }
        }
    }
}

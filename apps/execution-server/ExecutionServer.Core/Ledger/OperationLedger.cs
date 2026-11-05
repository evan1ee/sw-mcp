using System;
using System.Collections.Generic;
using System.Linq;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ownership;
using Newtonsoft.Json.Linq;

namespace ExecutionServer.Core.Ledger;

/// <summary>
/// Completed operation IDs, results and documents in completion order (spec 8.7; closes K17). Thread-safe; outlives
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
            IsSuccess = true;
        }

        public Entry(string document, string id, string code, string effect, JToken? originalError)
        {
            Document = document;
            Id = id;
            Code = code;
            Effect = effect;
            OriginalError = originalError;
            IsSuccess = false;
        }

        public string Document { get; }
        public string Id { get; }
        public bool IsSuccess { get; }
        public JToken? Result { get; }
        public string? Code { get; }
        public string? Effect { get; }
        public JToken? OriginalError { get; }
    }

    private readonly object _gate = new object();
    private readonly List<Entry> _entries = new List<Entry>();
    private readonly Dictionary<string, Entry> _byId = new Dictionary<string, Entry>(StringComparer.Ordinal);

    /// <summary>True if the operation completed successfully; <paramref name="result"/> is a copy of its original result.</summary>
    public bool TryGet(string operationId, out JToken? result)
    {
        lock (_gate)
        {
            if (_byId.TryGetValue(operationId, out var entry) && entry.IsSuccess)
            {
                result = entry.Result?.DeepClone();
                return true;
            }
        }

        result = null;
        return false;
    }

    /// <summary>True if the operation completed with failure; <paramref name="originalError"/> is a copy of its original error.</summary>
    public bool TryGetFailure(string operationId, out JToken? originalError)
    {
        lock (_gate)
        {
            if (_byId.TryGetValue(operationId, out var entry) && !entry.IsSuccess)
            {
                originalError = entry.OriginalError?.DeepClone();
                return true;
            }
        }

        originalError = null;
        return false;
    }

    /// <summary>Records a completed successful operation. Recording an ID twice is a caller bug and throws.</summary>
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

    /// <summary>Records a failed operation whose effect was applied or unknown (spec 8.7, closes K17).</summary>
    public void RecordFailure(string document, string operationId, string code, string effect, JToken? originalError = null)
    {
        var entry = new Entry(document, operationId, code, effect, originalError?.DeepClone());
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
            return _entries.Where(e => e.IsSuccess).Select(e => e.Id).ToList();
        }
    }

    public IReadOnlyList<FailedOperation> FailedOperations()
    {
        lock (_gate)
        {
            return _entries
                .Where(e => !e.IsSuccess)
                .Select(e => new FailedOperation
                {
                    OperationId = e.Id,
                    Code = e.Code ?? string.Empty,
                    Effect = e.Effect ?? string.Empty,
                })
                .ToList();
        }
    }

    /// <summary>Forgets a document's entries; called when the add-in sees the document destroyed.</summary>
    public void ForgetDocument(string document)
    {
        var normalized = DocumentOwnershipTable.NormalizePath(document);
        lock (_gate)
        {
            foreach (var entry in _entries.Where(e =>
                string.Equals(e.Document, document, StringComparison.OrdinalIgnoreCase) ||
                string.Equals(DocumentOwnershipTable.NormalizePath(e.Document), normalized, StringComparison.OrdinalIgnoreCase)).ToList())
            {
                _entries.Remove(entry);
                _byId.Remove(entry.Id);
            }
        }
    }
}

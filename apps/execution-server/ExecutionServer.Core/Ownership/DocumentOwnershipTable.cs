using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using ExecutionServer.Core.Ipc.Generated;

namespace ExecutionServer.Core.Ownership;

public sealed class OwnershipDecision
{
    public bool Allowed { get; }
    public string? ErrorCode { get; }
    public string? Reason { get; }

    public bool IsAllowed => Allowed;

    private OwnershipDecision(bool allowed, string? errorCode, string? reason)
    {
        Allowed = allowed;
        ErrorCode = errorCode;
        Reason = reason;
    }

    public static OwnershipDecision Allow() => new OwnershipDecision(true, null, null);

    public static OwnershipDecision Refuse(string errorCode, string reason) =>
        new OwnershipDecision(false, errorCode, reason);
}

/// <summary>
/// Enforces document ownership and custody rules (ADR-022, ADR-046, spec 8.3).
/// Keyed by normalized path and job ID. Thread-safe, CAD-free.
/// </summary>
public sealed class DocumentOwnershipTable
{
    private sealed class OwnershipEntry
    {
        public OwnershipEntry(string normalizedPath, string jobId, bool owned, string instanceId, string? previousActive)
        {
            NormalizedPath = normalizedPath;
            JobId = jobId;
            Owned = owned;
            InstanceId = instanceId;
            PreviousActive = previousActive;
        }

        public string NormalizedPath { get; }
        public string JobId { get; }
        public bool Owned { get; }
        public string InstanceId { get; }
        public string? PreviousActive { get; }
    }

    private readonly Func<string, bool>? _isDocumentOpen;
    private readonly object _gate = new object();
    private readonly List<OwnershipEntry> _entries = new List<OwnershipEntry>();

    public event Action<string>? DocumentRecorded;

    public DocumentOwnershipTable(Func<string, bool>? isDocumentOpen = null)
    {
        _isDocumentOpen = isDocumentOpen;
    }

    private OwnershipEntry? GetEntry(string normalizedPath, string? jobId)
    {
        var entry = _entries.FirstOrDefault(e =>
            string.Equals(e.NormalizedPath, normalizedPath, StringComparison.OrdinalIgnoreCase) &&
            (jobId == null || string.Equals(e.JobId, jobId, StringComparison.Ordinal)));

        if (entry != null && _isDocumentOpen != null && !_isDocumentOpen(entry.NormalizedPath))
        {
            _entries.RemoveAll(e => string.Equals(e.NormalizedPath, entry.NormalizedPath, StringComparison.OrdinalIgnoreCase));
            return null;
        }

        return entry;
    }

    public bool IsTracked(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) return false;
        var normalized = NormalizePath(path);
        lock (_gate)
        {
            return GetEntry(normalized, null) != null;
        }
    }

    public bool HasEntry(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) return false;
        var normalized = NormalizePath(path);
        lock (_gate)
        {
            return _entries.Any(e => string.Equals(e.NormalizedPath, normalized, StringComparison.OrdinalIgnoreCase));
        }
    }

    public string? GetInstanceId(string path, string? jobId = null)
    {
        if (string.IsNullOrWhiteSpace(path)) return null;
        var normalized = NormalizePath(path);
        lock (_gate)
        {
            var entry = GetEntry(normalized, jobId);
            return entry?.InstanceId;
        }
    }

    public void Record(string path, string jobId, bool owned, string instanceId, string? previousActive)
    {
        if (string.IsNullOrWhiteSpace(path)) throw new ArgumentException("Path required", nameof(path));
        if (string.IsNullOrWhiteSpace(jobId)) throw new ArgumentException("JobId required", nameof(jobId));

        var normalized = NormalizePath(path);
        var entry = new OwnershipEntry(normalized, jobId, owned, instanceId, previousActive);

        lock (_gate)
        {
            // Replace existing entry for (normalized, jobId) if present
            _entries.RemoveAll(e =>
                string.Equals(e.NormalizedPath, normalized, StringComparison.OrdinalIgnoreCase) &&
                string.Equals(e.JobId, jobId, StringComparison.Ordinal));
            _entries.Add(entry);
        }

        DocumentRecorded?.Invoke(normalized);
    }

    public OwnershipDecision CheckSave(string path, string? targetPath, string? jobId)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return OwnershipDecision.Refuse(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, "Document path required.");
        }

        var normalizedPath = NormalizePath(path);
        if (IsPart(normalizedPath))
        {
            if (string.IsNullOrEmpty(jobId))
            {
                return OwnershipDecision.Refuse(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, "No job ID provided for part save.");
            }

            OwnershipEntry? entry;
            lock (_gate)
            {
                entry = GetEntry(normalizedPath, jobId);
            }

            if (entry == null || !entry.Owned)
            {
                return OwnershipDecision.Refuse(
                    ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED,
                    $"Job '{jobId}' does not own part '{path}'.");
            }

            if (!string.IsNullOrEmpty(targetPath))
            {
                var normalizedTarget = NormalizePath(targetPath);
                if (!string.Equals(normalizedPath, normalizedTarget, StringComparison.OrdinalIgnoreCase))
                {
                    return OwnershipDecision.Refuse(
                        ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED,
                        $"Cannot save owned part '{path}' to different target path '{targetPath}'.");
                }
            }

            return OwnershipDecision.Allow();
        }

        // For drawings (.SLDDRW or no extension / title): allowed (frozen flow)
        return OwnershipDecision.Allow();
    }

    public OwnershipDecision CheckClose(string path, string? jobId)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return OwnershipDecision.Refuse(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, "Document path required.");
        }

        var normalizedPath = NormalizePath(path);
        if (IsPart(normalizedPath))
        {
            if (string.IsNullOrEmpty(jobId))
            {
                return OwnershipDecision.Refuse(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, "No job ID provided for part close.");
            }

            OwnershipEntry? entry;
            lock (_gate)
            {
                entry = GetEntry(normalizedPath, jobId);
            }

            if (entry == null || !entry.Owned)
            {
                return OwnershipDecision.Refuse(
                    ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED,
                    $"Job '{jobId}' does not own part '{path}'.");
            }

            return OwnershipDecision.Allow();
        }

        // For drawings: unlisted drawing allowed; borrowed drawing of this job refused
        if (!string.IsNullOrEmpty(jobId))
        {
            OwnershipEntry? entry;
            lock (_gate)
            {
                entry = GetEntry(normalizedPath, jobId);
            }

            if (entry != null && !entry.Owned)
            {
                return OwnershipDecision.Refuse(
                    ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED,
                    $"Job '{jobId}' cannot close borrowed drawing '{path}'.");
            }
        }

        return OwnershipDecision.Allow();
    }

    public string? PreviousActive(string path, string jobId)
    {
        if (string.IsNullOrWhiteSpace(path) || string.IsNullOrWhiteSpace(jobId))
        {
            return null;
        }

        var normalizedPath = NormalizePath(path);
        lock (_gate)
        {
            var entry = GetEntry(normalizedPath, jobId);
            return entry != null && entry.Owned ? entry.PreviousActive : null;
        }
    }

    public void Forget(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) return;
        var normalized = NormalizePath(path);

        lock (_gate)
        {
            _entries.RemoveAll(e => string.Equals(e.NormalizedPath, normalized, StringComparison.OrdinalIgnoreCase));
        }
    }

    public static bool IsPart(string path)
    {
        var ext = Path.GetExtension(path);
        return string.Equals(ext, ".sldprt", StringComparison.OrdinalIgnoreCase);
    }

    public static string NormalizePath(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) return string.Empty;

        var trimmed = path!.Trim();
        try
        {
            if (Path.IsPathRooted(trimmed))
            {
                return Path.GetFullPath(trimmed).TrimEnd('\\', '/');
            }
        }
        catch
        {
            // Fallback for paths with chars invalid in Path.GetFullPath
        }

        return trimmed.Replace('/', '\\').TrimEnd('\\');
    }
}

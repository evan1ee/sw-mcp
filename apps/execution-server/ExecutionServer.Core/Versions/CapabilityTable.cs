using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;

namespace ExecutionServer.Core.Versions;

public enum VersionSupport
{
    Supported,
    NewerServicePack,
    Unsupported
}

/// <summary>
/// Central capability table mapping running SOLIDWORKS versions to support status
/// and named capabilities (ADR-045, ADR-062, spec 8.8.10, 8.9.7). Pure and CAD-free.
/// </summary>
public sealed class CapabilityTable
{
    private const int SupportedMajor = 33; // SOLIDWORKS 2025
    private static readonly int[] PinnedServicePack = { 0, 0 }; // SP0.0

    private static readonly string[] BaseCapabilities2025 =
    {
        "drawing.snapshot",
        "ops.apply",
        "part.measure",
        "op:feature.create:extrude",
        "op:feature.create:cut_extrude",
        "op:sketch.create:line",
        "op:sketch.create:circle",
        "op:sketch.create:arc",
        "op:sketch.create:relations"
    };

    private readonly HashSet<string> _names;

    private CapabilityTable(VersionSupport support, IEnumerable<string> capabilities)
    {
        Support = support;
        _names = new HashSet<string>(capabilities, StringComparer.Ordinal);
        Names = new ReadOnlyCollection<string>(_names.ToList());
    }

    public VersionSupport Support { get; }

    public IReadOnlyCollection<string> Names { get; }

    public bool Has(string capability)
    {
        if (capability == null) return false;
        return _names.Contains(capability);
    }

    public static CapabilityTable For(SolidWorksVersion running)
    {
        if (running == null)
        {
            throw new ArgumentNullException(nameof(running));
        }

        if (running.Major < SupportedMajor || running.Major > SupportedMajor)
        {
            return new CapabilityTable(VersionSupport.Unsupported, Array.Empty<string>());
        }

        // Major == 33 (SOLIDWORKS 2025)
        // Compare service pack against pinned SP0.0
        var isNewerSp = false;
        var segments = running.ServicePackSegments;
        for (int i = 0; i < segments.Count; i++)
        {
            var pinned = i < PinnedServicePack.Length ? PinnedServicePack[i] : 0;
            if (segments[i] > pinned)
            {
                isNewerSp = true;
                break;
            }
            if (segments[i] < pinned)
            {
                break;
            }
        }

        var support = isNewerSp ? VersionSupport.NewerServicePack : VersionSupport.Supported;
        return new CapabilityTable(support, BaseCapabilities2025);
    }
}

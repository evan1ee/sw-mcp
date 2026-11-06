using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace ExecutionServer.Core.Versions;

/// <summary>
/// Parsed SOLIDWORKS version and service pack (ADR-045, ADR-062). Pure and CAD-free.
/// </summary>
public sealed class SolidWorksVersion
{
    public int Major { get; }
    public string Version { get; }
    public string ServicePack { get; }
    public IReadOnlyList<int> ServicePackSegments { get; }
    public string Revision { get; }

    public SolidWorksVersion(int major, IReadOnlyList<int> spSegments, string revision)
    {
        Major = major;
        Version = (1992 + major).ToString();
        ServicePackSegments = spSegments ?? throw new ArgumentNullException(nameof(spSegments));
        ServicePack = "SP" + string.Join(".", spSegments);
        Revision = revision ?? throw new ArgumentNullException(nameof(revision));
    }

    public static SolidWorksVersion Parse(string revision)
    {
        if (revision == null)
        {
            throw new ArgumentNullException(nameof(revision), "Revision cannot be null.");
        }
        if (string.IsNullOrWhiteSpace(revision))
        {
            throw new ArgumentException("Revision cannot be empty.", nameof(revision));
        }

        revision = revision.Trim();
        var parts = revision.Split('.');
        if (parts.Length < 2)
        {
            throw new FormatException($"Revision must contain at least major and service pack: '{revision}'");
        }

        if (!int.TryParse(parts[0], out var major) || major <= 0)
        {
            throw new FormatException($"Invalid major revision in '{revision}'");
        }

        var spList = new List<int>();
        for (int i = 1; i < parts.Length; i++)
        {
            if (!int.TryParse(parts[i], out var spPart) || spPart < 0)
            {
                throw new FormatException($"Invalid service pack segment '{parts[i]}' in '{revision}'");
            }
            spList.Add(spPart);
        }

        return new SolidWorksVersion(major, new ReadOnlyCollection<int>(spList), revision);
    }

    public override string ToString() => $"{Version} {ServicePack} ({Revision})";
}

using System;
using System.Collections.Generic;
using ExecutionServer.Core.Dispatch;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Versions;
using Xunit;

namespace ExecutionServer.Tests.Versions;

public sealed class CapabilityTableTests
{
    [Fact]
    public void Parse_RealRevisions()
    {
        // 33.0.0 keeps every segment
        var v1 = SolidWorksVersion.Parse("33.0.0");
        Assert.Equal(33, v1.Major);
        Assert.Equal("2025", v1.Version);
        Assert.Equal("SP0.0", v1.ServicePack);
        Assert.Equal(new[] { 0, 0 }, v1.ServicePackSegments);
        Assert.Equal("33.0.0", v1.Revision);

        // Three-part service pack keeps every segment
        var v2 = SolidWorksVersion.Parse("33.1.2.3");
        Assert.Equal(33, v2.Major);
        Assert.Equal("2025", v2.Version);
        Assert.Equal("SP1.2.3", v2.ServicePack);
        Assert.Equal(new[] { 1, 2, 3 }, v2.ServicePackSegments);
        Assert.Equal("33.1.2.3", v2.Revision);

        // Two-part service pack
        var v3 = SolidWorksVersion.Parse("33.2.1");
        Assert.Equal(33, v3.Major);
        Assert.Equal("2025", v3.Version);
        Assert.Equal("SP2.1", v3.ServicePack);
        Assert.Equal(new[] { 2, 1 }, v3.ServicePackSegments);

        // Null, empty and malformed values fail
        Assert.Throws<ArgumentNullException>(() => SolidWorksVersion.Parse(null!));
        Assert.Throws<ArgumentException>(() => SolidWorksVersion.Parse(""));
        Assert.Throws<ArgumentException>(() => SolidWorksVersion.Parse("   "));
        Assert.Throws<FormatException>(() => SolidWorksVersion.Parse("33"));
        Assert.Throws<FormatException>(() => SolidWorksVersion.Parse("malformed"));
        Assert.Throws<FormatException>(() => SolidWorksVersion.Parse("33.a.0"));
        Assert.Throws<FormatException>(() => SolidWorksVersion.Parse("33.-1.0"));
        Assert.Throws<FormatException>(() => SolidWorksVersion.Parse("-33.0.0"));
    }

    [Fact]
    public void Support_FollowsAdr045()
    {
        // Supported: 2025 SP0.0
        var vSupported = SolidWorksVersion.Parse("33.0.0");
        var tableSupported = CapabilityTable.For(vSupported);
        Assert.Equal(VersionSupport.Supported, tableSupported.Support);
        Assert.True(tableSupported.Has("drawing.snapshot"));
        Assert.True(tableSupported.Has("ops.apply"));

        // Newer service pack with a warning: 2025 SP5.0 or SP0.1
        var vNewerSp = SolidWorksVersion.Parse("33.5.0");
        var tableNewerSp = CapabilityTable.For(vNewerSp);
        Assert.Equal(VersionSupport.NewerServicePack, tableNewerSp.Support);
        Assert.True(tableNewerSp.Has("drawing.snapshot"));
        Assert.True(tableNewerSp.Has("ops.apply"));

        var vNewerMinorSp = SolidWorksVersion.Parse("33.0.1");
        var tableNewerMinorSp = CapabilityTable.For(vNewerMinorSp);
        Assert.Equal(VersionSupport.NewerServicePack, tableNewerMinorSp.Support);

        // Older major refused: 2024 (major 32)
        var vOlder = SolidWorksVersion.Parse("32.0.0");
        var tableOlder = CapabilityTable.For(vOlder);
        Assert.Equal(VersionSupport.Unsupported, tableOlder.Support);

        // Newer major refused: 2026 (major 34)
        var vNewer = SolidWorksVersion.Parse("34.0.0");
        var tableNewer = CapabilityTable.For(vNewer);
        Assert.Equal(VersionSupport.Unsupported, tableNewer.Support);
    }

    [Fact]
    public void HelloLists_OnlyRegisteredOperations()
    {
        var router = new OperationRouter();
        router.Register("document.open", (doc, op, ct) => null!);
        router.Register("document.close", (doc, op, ct) => null!);

        var version = SolidWorksVersion.Parse("33.0.0");
        var table = CapabilityTable.For(version);

        var helloResult = new HelloResult
        {
            Protocol = "0.1",
            AddinVersion = "0.1.0",
            Solidworks = new SolidWorksInfo
            {
                Version = version.Version,
                ServicePack = version.ServicePack,
                UiLanguage = "en-US"
            },
            Capabilities = new List<string>(table.Names),
            Operations = new List<OperationInfo>(router.Operations),
            LicensedModules = new List<string>(),
            Warnings = new List<string>()
        };

        Assert.Equal(2, helloResult.Operations.Count);
        Assert.Contains(helloResult.Operations, o => o.Op == "document.open");
        Assert.Contains(helloResult.Operations, o => o.Op == "document.close");
        Assert.DoesNotContain(helloResult.Operations, o => o.Op == "drawing.create");
        Assert.DoesNotContain(helloResult.Operations, o => o.Op == "document.save");
    }
}

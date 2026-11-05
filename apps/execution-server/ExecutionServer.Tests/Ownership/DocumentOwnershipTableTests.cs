using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ownership;
using Xunit;

namespace ExecutionServer.Tests.Ownership;

public sealed class DocumentOwnershipTableTests
{
    [Fact]
    public void SaveOwnedPart_Allowed()
    {
        var table = new DocumentOwnershipTable();
        table.Record(@"C:\models\part1.SLDPRT", "job-1", owned: true, instanceId: "inst-1", previousActive: null);

        var decision = table.CheckSave(@"C:\models\part1.SLDPRT", targetPath: null, jobId: "job-1");
        Assert.True(decision.Allowed);

        // Also allowed when targetPath == path
        var decisionWithSameTarget = table.CheckSave(@"C:\models\part1.SLDPRT", targetPath: @"C:\models\part1.SLDPRT", jobId: "job-1");
        Assert.True(decisionWithSameTarget.Allowed);
    }

    [Fact]
    public void SavePartOfOtherJob_Refused()
    {
        var table = new DocumentOwnershipTable();
        table.Record(@"C:\models\part1.SLDPRT", "job-1", owned: true, instanceId: "inst-1", previousActive: null);

        var decision = table.CheckSave(@"C:\models\part1.SLDPRT", targetPath: null, jobId: "job-2");
        Assert.False(decision.Allowed);
        Assert.Equal(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, decision.ErrorCode);
    }

    [Fact]
    public void SaveUnknownPart_Refused()
    {
        var table = new DocumentOwnershipTable();
        var decision = table.CheckSave(@"C:\models\unknown.SLDPRT", targetPath: null, jobId: "job-1");
        Assert.False(decision.Allowed);
        Assert.Equal(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, decision.ErrorCode);
    }

    [Fact]
    public void SaveOwnedPartToOtherPath_Refused()
    {
        var table = new DocumentOwnershipTable();
        table.Record(@"C:\models\part1.SLDPRT", "job-1", owned: true, instanceId: "inst-1", previousActive: null);

        var decision = table.CheckSave(@"C:\models\part1.SLDPRT", targetPath: @"C:\models\other.SLDPRT", jobId: "job-1");
        Assert.False(decision.Allowed);
        Assert.Equal(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, decision.ErrorCode);
    }

    [Fact]
    public void SaveUnknownDrawing_Allowed()
    {
        var table = new DocumentOwnershipTable();
        // Title or drawing path with target_path, frozen flow
        var decisionTitle = table.CheckSave("Drawing1", targetPath: @"C:\drawings\saved.SLDDRW", jobId: "job-1");
        Assert.True(decisionTitle.Allowed);

        var decisionDwg = table.CheckSave(@"C:\drawings\test.SLDDRW", targetPath: @"C:\drawings\target.SLDDRW", jobId: "job-1");
        Assert.True(decisionDwg.Allowed);
    }

    [Fact]
    public void CloseUnownedPart_Refused()
    {
        var table = new DocumentOwnershipTable();
        table.Record(@"C:\models\part1.SLDPRT", "job-1", owned: false, instanceId: "inst-1", previousActive: null);

        var decision = table.CheckClose(@"C:\models\part1.SLDPRT", jobId: "job-1");
        Assert.False(decision.Allowed);
        Assert.Equal(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, decision.ErrorCode);

        // Also unlisted part is refused
        var decisionUnlisted = table.CheckClose(@"C:\models\unlisted.SLDPRT", jobId: "job-1");
        Assert.False(decisionUnlisted.Allowed);
        Assert.Equal(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, decisionUnlisted.ErrorCode);
    }

    [Fact]
    public void CloseOwnedPart_ReturnsPreviousActive()
    {
        var table = new DocumentOwnershipTable();
        table.Record(@"C:\models\part1.SLDPRT", "job-1", owned: true, instanceId: "inst-1", previousActive: @"C:\models\prev.SLDPRT");

        var decision = table.CheckClose(@"C:\models\part1.SLDPRT", jobId: "job-1");
        Assert.True(decision.Allowed);

        var prev = table.PreviousActive(@"C:\models\part1.SLDPRT", "job-1");
        Assert.Equal(@"C:\models\prev.SLDPRT", prev);
    }

    [Fact]
    public void CloseBorrowedDrawingOfThisJob_Refused()
    {
        var table = new DocumentOwnershipTable();
        table.Record(@"C:\drawings\borrowed.SLDDRW", "job-1", owned: false, instanceId: "inst-1", previousActive: null);

        var decision = table.CheckClose(@"C:\drawings\borrowed.SLDDRW", jobId: "job-1");
        Assert.False(decision.Allowed);
        Assert.Equal(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, decision.ErrorCode);
    }

    [Fact]
    public void CloseUnlistedDrawing_Allowed()
    {
        var table = new DocumentOwnershipTable();
        var decision = table.CheckClose(@"C:\drawings\unlisted.SLDDRW", jobId: "job-1");
        Assert.True(decision.Allowed);

        var decisionTitle = table.CheckClose("Drawing1", jobId: "job-1");
        Assert.True(decisionTitle.Allowed);
    }

    [Fact]
    public void DeadJobEntry_GrantsNothing()
    {
        var table = new DocumentOwnershipTable();
        table.Record(@"C:\models\part1.SLDPRT", "job-A", owned: true, instanceId: "inst-1", previousActive: @"C:\models\prev.SLDPRT");

        // Job B gets nothing
        var saveDecision = table.CheckSave(@"C:\models\part1.SLDPRT", targetPath: null, jobId: "job-B");
        Assert.False(saveDecision.Allowed);
        Assert.Equal(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, saveDecision.ErrorCode);

        var closeDecision = table.CheckClose(@"C:\models\part1.SLDPRT", jobId: "job-B");
        Assert.False(closeDecision.Allowed);
        Assert.Equal(ErrorCodes.AUTH_SOURCE_WRITE_NOT_ALLOWED, closeDecision.ErrorCode);

        var prev = table.PreviousActive(@"C:\models\part1.SLDPRT", "job-B");
        Assert.Null(prev);
    }

    [Fact]
    public void NonAsciiPath_Matches()
    {
        var table = new DocumentOwnershipTable();
        var nonAsciiPath = @"D:\零件\板.SLDPRT";
        table.Record(nonAsciiPath, "job-1", owned: true, instanceId: "inst-1", previousActive: null);

        var decision = table.CheckSave(@"d:\零件\板.sldprt", targetPath: null, jobId: "job-1");
        Assert.True(decision.Allowed);

        var closeDecision = table.CheckClose(@"D:\零件\板.SLDPRT", jobId: "job-1");
        Assert.True(closeDecision.Allowed);
    }
}

using System.Collections.Generic;
using ExecutionServer.Core.Events;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ledger;
using ExecutionServer.Core.Ownership;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests.Events;

public sealed class DocumentEventMonitorTests
{
    [Fact]
    public void UntaggedSaveOnOwnedPart_RaisesEvent()
    {
        var notifications = new List<(string Method, JToken Payload)>();
        var table = new DocumentOwnershipTable();
        var ledger = new OperationLedger();
        var monitor = new DocumentEventMonitor((method, payload) => notifications.Add((method, payload)), table, ledger);

        var partPath = @"C:\models\bracket.SLDPRT";
        table.Record(partPath, "job-1", owned: true, instanceId: "inst-1", previousActive: null);

        // Untagged save (outside active command scope / no CurrentJobId)
        monitor.OnDocumentEvent(partPath, DocumentEventParamsEvent.Save);

        Assert.Single(notifications);
        var (method, payload) = notifications[0];
        Assert.Equal("document.event", method);
        var docParam = payload["document"]?.Value<string>();
        var eventParam = payload["event"]?.Value<string>();
        Assert.Equal(DocumentOwnershipTable.NormalizePath(partPath), DocumentOwnershipTable.NormalizePath(docParam));
        Assert.Equal("save", eventParam);
        Assert.Null(payload["_meta"]);

        // If an unowned/untracked part raises an event, it should NOT raise
        notifications.Clear();
        monitor.OnDocumentEvent(@"C:\models\untracked.SLDPRT", DocumentEventParamsEvent.Save);
        Assert.Empty(notifications);
    }

    [Fact]
    public void EventDuringCommand_IsTagged()
    {
        var notifications = new List<(string Method, JToken Payload)>();
        var table = new DocumentOwnershipTable();
        var ledger = new OperationLedger();
        var monitor = new DocumentEventMonitor((method, payload) => notifications.Add((method, payload)), table, ledger);

        var partPath = @"C:\models\bracket.SLDPRT";
        table.Record(partPath, "job-1", owned: true, instanceId: "inst-1", previousActive: null);

        // Simulate an active command/job
        monitor.CurrentJobId = "job-1";

        monitor.OnDocumentEvent(partPath, DocumentEventParamsEvent.Regen);

        Assert.Single(notifications);
        var (method, payload) = notifications[0];
        Assert.Equal("document.event", method);
        Assert.Equal("regen", payload["event"]?.Value<string>());
        Assert.NotNull(payload["_meta"]);
        Assert.Equal("job-1", payload["_meta"]?["job_id"]?.Value<string>());

        // Command finishes
        monitor.CurrentJobId = null;

        notifications.Clear();
        monitor.OnDocumentEvent(partPath, DocumentEventParamsEvent.Regen);
        Assert.Single(notifications);
        Assert.Null(notifications[0].Payload["_meta"]);
    }

    [Fact]
    public void Close_ForgetsTableAndLedger()
    {
        var notifications = new List<(string Method, JToken Payload)>();
        bool isOpen = true;
        var table = new DocumentOwnershipTable(path => isOpen);
        var ledger = new OperationLedger();
        var monitor = new DocumentEventMonitor((method, payload) => notifications.Add((method, payload)), table, ledger);

        var partPath = @"C:\models\bracket.SLDPRT";
        table.Record(partPath, "job-1", owned: true, instanceId: "inst-1", previousActive: null);
        ledger.Record(partPath, "job-1:op-1", new JObject { ["status"] = "success" });

        Assert.True(table.IsTracked(partPath));
        Assert.True(ledger.TryGet("job-1:op-1", out _));

        // Document is closed in CAD when DestroyNotify2 fires
        isOpen = false;

        // Close event occurs (fired by DestroyNotify2)
        monitor.OnDocumentEvent(partPath, DocumentEventParamsEvent.Close);

        // Emits document.event with close
        Assert.Single(notifications);
        Assert.Equal("document.event", notifications[0].Method);
        Assert.Equal("close", notifications[0].Payload["event"]?.Value<string>());

        // Ownership table and ledger have forgotten the document
        Assert.False(table.HasEntry(partPath));
        Assert.False(ledger.TryGet("job-1:op-1", out _));
    }

    [Fact]
    public void StaleEntry_DroppedWhenDocumentGone()
    {
        bool isDocOpen = true;
        var table = new DocumentOwnershipTable(path => isDocOpen);
        var ledger = new OperationLedger();
        var monitor = new DocumentEventMonitor((method, payload) => { }, table, ledger);

        var partPath = @"C:\models\bracket.SLDPRT";
        table.Record(partPath, "job-1", owned: true, instanceId: "inst-1", previousActive: null);

        Assert.True(table.IsTracked(partPath));

        // Engineer closes the document in the UI without add-in seeing it
        isDocOpen = false;

        // Next time table entry is accessed/checked (lazy check), it should drop the entry
        Assert.False(table.IsTracked(partPath));

        // Confirm the entry was removed from the table entirely
        isDocOpen = true;
        Assert.False(table.IsTracked(partPath));
    }

    [Fact]
    public void PathNormalizes_ForTableLookup()
    {
        var table = new DocumentOwnershipTable();
        var ledger = new OperationLedger();
        var monitor = new DocumentEventMonitor((method, payload) => { }, table, ledger);

        var canonicalPath = @"C:\Models\SubDir\Plate.SLDPRT";
        table.Record(canonicalPath, "job-1", owned: true, instanceId: "inst-1", previousActive: @"C:\Models\Previous.SLDPRT");
        ledger.Record(canonicalPath, "job-1:op-1", null);

        // Lookups with forward slashes and different casing
        var altPath = "c:/models/subdir/plate.sldprt";
        Assert.True(table.IsTracked(altPath));

        var saveDecision = table.CheckSave(altPath, targetPath: null, jobId: "job-1");
        Assert.True(saveDecision.Allowed);

        var closeDecision = table.CheckClose(altPath, jobId: "job-1");
        Assert.True(closeDecision.Allowed);

        var prevActive = table.PreviousActive(altPath, "job-1");
        Assert.Equal(@"C:\Models\Previous.SLDPRT", prevActive);

        // Close via altPath forgets the canonicalPath entry in both table and ledger
        monitor.OnDocumentEvent(altPath, DocumentEventParamsEvent.Close);
        Assert.False(table.IsTracked(canonicalPath));
        Assert.False(ledger.TryGet("job-1:op-1", out _));
    }
}

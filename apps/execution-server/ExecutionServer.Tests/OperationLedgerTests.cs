using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using ExecutionServer.Core.Ledger;
using ExecutionServer.Tests.Support;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests;

public sealed class OperationLedgerTests
{
    [Fact]
    public void Records_in_completion_order()
    {
        var ledger = new OperationLedger();
        ledger.Record("C:/a", "j:2", null);
        ledger.Record("C:/b", "j:1", null);
        ledger.Record("C:/a", "j:3", null);

        Assert.Equal(new[] { "j:2", "j:1", "j:3" }, ledger.CompletedIds());
    }

    [Fact]
    public void TryGet_returns_original_result()
    {
        var ledger = new OperationLedger();
        var original = new JObject { ["owned"] = true };
        ledger.Record("C:/a", "j:1", original);
        original["owned"] = false; // the ledger keeps its own copy

        Assert.True(ledger.TryGet("j:1", out var result));
        Assert.True(JToken.DeepEquals(new JObject { ["owned"] = true }, result));
        Assert.False(ledger.TryGet("j:9", out var missing));
        Assert.Null(missing);
    }

    [Fact]
    public void Record_with_null_result_is_found()
    {
        var ledger = new OperationLedger();
        ledger.Record("C:/a", "j:1", null);

        Assert.True(ledger.TryGet("j:1", out var result));
        Assert.Null(result);
    }

    [Fact]
    public void Recording_an_id_twice_throws()
    {
        var ledger = new OperationLedger();
        ledger.Record("C:/a", "j:1", null);

        Assert.Throws<InvalidOperationException>(() => ledger.Record("C:/a", "j:1", null));
    }

    [Fact]
    public void ForgetDocument_removes_only_its_entries()
    {
        var ledger = new OperationLedger();
        ledger.Record("C:/A.sldprt", "a:1", null);
        ledger.Record("C:/b.sldprt", "b:1", null);
        ledger.Record("C:/a.sldprt", "a:2", null); // same document, other case

        ledger.ForgetDocument("C:/a.sldprt");

        Assert.Equal(new[] { "b:1" }, ledger.CompletedIds());
        Assert.False(ledger.TryGet("a:1", out _));
        Assert.True(ledger.TryGet("b:1", out _));
    }

    [Fact]
    public void Thread_safe_under_parallel_record()
    {
        var ledger = new OperationLedger();
        const int Threads = 8;
        const int PerThread = 500;

        Parallel.For(0, Threads, new ParallelOptions { MaxDegreeOfParallelism = Threads }, t =>
        {
            for (var i = 0; i < PerThread; i++)
            {
                ledger.Record("C:/doc" + t, "t" + t + ":" + i, new JValue(i));
                ledger.CompletedIds();
                ledger.TryGet("t" + t + ":" + i, out _);
            }
        });

        var ids = ledger.CompletedIds();
        Assert.Equal(Threads * PerThread, ids.Count);
        Assert.Equal(ids.Count, ids.Distinct().Count());
        for (var t = 0; t < Threads; t++)
        {
            var mine = ids.Where(id => id.StartsWith("t" + t + ":", StringComparison.Ordinal))
                .Select(id => int.Parse(id.Substring(id.IndexOf(':') + 1))).ToList();
            Assert.Equal(mine.OrderBy(x => x).ToList(), mine);
        }
    }

    [Fact]
    public void FailureWithEffectApplied_IsRecorded()
    {
        var ledger = new OperationLedger();
        var handler = new ScriptedHandler();
        handler.OnExecute = (doc, op, ct) =>
            throw new IpcException(ErrorCodes.BACKEND_REBUILD_ERROR, "rebuild failed", new JObject { ["effect"] = "applied" });

        var applyParams = Rpc.OpsParams("doc.sldprt", "j1:1").ToObject<OpsApplyParams>()!;
        var result = OpsBatchRunner.Run(applyParams, ledger, handler, CancellationToken.None);

        Assert.Equal(ErrorCodes.BACKEND_REBUILD_ERROR, result.Outcomes[0].Error?.Code);
        Assert.Empty(ledger.CompletedIds());
        var failed = ledger.FailedOperations();
        Assert.Single(failed);
        Assert.Equal("j1:1", failed[0].OperationId);
        Assert.Equal(ErrorCodes.BACKEND_REBUILD_ERROR, failed[0].Code);
        Assert.Equal("applied", failed[0].Effect);
    }

    [Fact]
    public void FailureWithEffectUnknown_IsRecorded()
    {
        var ledger = new OperationLedger();
        var handler = new ScriptedHandler();
        handler.OnExecute = (doc, op, ct) =>
            throw new IpcException(ErrorCodes.BACKEND_REBUILD_ERROR, "rebuild failed", new JObject { ["effect"] = "unknown" });

        var applyParams = Rpc.OpsParams("doc.sldprt", "j1:1").ToObject<OpsApplyParams>()!;
        var result = OpsBatchRunner.Run(applyParams, ledger, handler, CancellationToken.None);

        Assert.Empty(ledger.CompletedIds());
        var failed = ledger.FailedOperations();
        Assert.Single(failed);
        Assert.Equal("j1:1", failed[0].OperationId);
        Assert.Equal("unknown", failed[0].Effect);
    }

    [Fact]
    public void FailureWithEffectNone_IsNotRecorded()
    {
        var ledger = new OperationLedger();
        var handler = new ScriptedHandler();
        handler.OnExecute = (doc, op, ct) =>
            throw new IpcException(ErrorCodes.AUTH_PATH_DENIED, "denied", new JObject { ["effect"] = "none" });

        var applyParams = Rpc.OpsParams("doc.sldprt", "j1:1").ToObject<OpsApplyParams>()!;
        OpsBatchRunner.Run(applyParams, ledger, handler, CancellationToken.None);

        Assert.Empty(ledger.CompletedIds());
        Assert.Empty(ledger.FailedOperations());
    }

    [Fact]
    public void FailureWithoutEffect_IsNotRecorded()
    {
        var ledger = new OperationLedger();
        var handler = new ScriptedHandler();
        // Frozen drawing flow: no details / no effect
        handler.OnExecute = (doc, op, ct) =>
            throw new IpcException(ErrorCodes.AUTH_PATH_DENIED, "denied");

        var applyParams = Rpc.OpsParams("doc.sldprt", "j1:1").ToObject<OpsApplyParams>()!;
        OpsBatchRunner.Run(applyParams, ledger, handler, CancellationToken.None);

        Assert.Empty(ledger.CompletedIds());
        Assert.Empty(ledger.FailedOperations());
    }

    [Fact]
    public void UnexpectedException_IsRecordedAsUnknown()
    {
        var ledger = new OperationLedger();
        var handler = new ScriptedHandler();
        handler.OnExecute = (doc, op, ct) =>
            throw new InvalidOperationException("unexpected crash");

        var applyParams = Rpc.OpsParams("doc.sldprt", "j1:1").ToObject<OpsApplyParams>()!;
        Assert.Throws<InvalidOperationException>(() =>
            OpsBatchRunner.Run(applyParams, ledger, handler, CancellationToken.None));

        Assert.Empty(ledger.CompletedIds());
        var failed = ledger.FailedOperations();
        Assert.Single(failed);
        Assert.Equal("j1:1", failed[0].OperationId);
        Assert.Equal("-32603", failed[0].Code);
        Assert.Equal("unknown", failed[0].Effect);
    }

    [Fact]
    public void RepeatOfRecordedFailure_ReturnsDuplicateWithOriginalError_AndDoesNotRun()
    {
        var ledger = new OperationLedger();
        var calls = 0;
        var handler = new ScriptedHandler();
        handler.OnExecute = (doc, op, ct) =>
        {
            calls++;
            throw new IpcException(ErrorCodes.BACKEND_REBUILD_ERROR, "rebuild failed", new JObject { ["effect"] = "applied" });
        };

        var applyParams = Rpc.OpsParams("doc.sldprt", "j1:1").ToObject<OpsApplyParams>()!;
        OpsBatchRunner.Run(applyParams, ledger, handler, CancellationToken.None);
        Assert.Equal(1, calls);

        // Run again with the same operation ID
        var repeatResult = OpsBatchRunner.Run(applyParams, ledger, handler, CancellationToken.None);
        Assert.Equal(1, calls); // Did not run!
        Assert.Single(repeatResult.Outcomes);
        var outcome = repeatResult.Outcomes[0];
        Assert.Null(outcome.Result);
        Assert.NotNull(outcome.Error);
        Assert.Equal(ErrorCodes.DUPLICATE_OPERATION, outcome.Error.Code);
        Assert.NotNull(outcome.Error.Details);
        var originalErr = outcome.Error.Details["original_error"];
        Assert.NotNull(originalErr);
        Assert.Equal(ErrorCodes.BACKEND_REBUILD_ERROR, originalErr["code"]?.ToString());
    }

    [Fact]
    public void RecordedFailure_NotInOperationIds_ListedInFailedOperations()
    {
        var ledger = new OperationLedger();
        ledger.Record("doc.sldprt", "j1:1", new JObject { ["ok"] = true });
        ledger.RecordFailure("doc.sldprt", "j1:2", ErrorCodes.BACKEND_REBUILD_ERROR, "applied", null);

        Assert.Equal(new[] { "j1:1" }, ledger.CompletedIds());
        var failed = ledger.FailedOperations();
        Assert.Single(failed);
        Assert.Equal("j1:2", failed[0].OperationId);
        Assert.Equal(ErrorCodes.BACKEND_REBUILD_ERROR, failed[0].Code);
        Assert.Equal("applied", failed[0].Effect);
    }
}

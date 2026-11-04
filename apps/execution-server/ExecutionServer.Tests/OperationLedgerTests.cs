using System;
using System.Linq;
using System.Threading.Tasks;
using ExecutionServer.Core.Ledger;
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
}

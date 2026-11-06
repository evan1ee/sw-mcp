using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Threading;
using ExecutionServer.Core.Dispatch;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ledger;
using ExecutionServer.Tests.Support;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests.Dispatch;

public sealed class UIThreadDispatcherTests
{
    private sealed class TrackingSyncContext : SynchronizationContext
    {
        public ConcurrentQueue<Action> PostedActions { get; } = new ConcurrentQueue<Action>();
        public int PostCount => PostedActions.Count;
        public bool AutoExecute { get; set; }

        public override void Post(SendOrPostCallback d, object? state)
        {
            Action action = () => d(state);
            PostedActions.Enqueue(action);
            if (AutoExecute)
            {
                action();
            }
        }
    }

    [Fact]
    public void DrainOnWrongThread_RunsNothingAndReports()
    {
        var syncContext = new TrackingSyncContext { AutoExecute = false };
        var reported = new List<Exception>();
        // Captured target thread is 999999, but current thread is not
        var dispatcher = new UIThreadDispatcher(
            syncContext,
            targetThreadId: 999999,
            onUnexpected: reported.Add);

        var config = Rpc.Config();
        var ledger = new OperationLedger();
        var handler = new ScriptedHandler();
        var sink = new RecordingSink();
        var session = new IpcSession(config, ledger, handler, sink);

        // Authenticate and enqueue a command
        session.Receive(Rpc.Hello(1, config.Token));
        session.Receive(Rpc.Request(2, "drawing.snapshot", Rpc.SnapshotParams()));
        Assert.True(session.HasQueuedCommands);

        dispatcher.Drain(session);

        // Command was NOT run
        Assert.True(session.HasQueuedCommands);
        // Defect was reported
        Assert.Single(reported);
        Assert.IsType<InvalidOperationException>(reported[0]);
        Assert.Contains("wrong thread", reported[0].Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void ReentrantDrain_IsRefusedAndNothingIsLost()
    {
        var syncContext = new TrackingSyncContext { AutoExecute = false };
        var reported = new List<Exception>();
        var currentThreadId = Thread.CurrentThread.ManagedThreadId;
        UIThreadDispatcher? dispatcher = null;
        dispatcher = new UIThreadDispatcher(
            syncContext,
            targetThreadId: currentThreadId,
            onUnexpected: reported.Add);

        var config = Rpc.Config();
        var ledger = new OperationLedger();
        var handler = new ScriptedHandler();
        var sink = new RecordingSink();
        var session = new IpcSession(config, ledger, handler, sink);

        int cmd1Ran = 0;
        int cmd2Ran = 0;
        int reentrantDrainCalls = 0;

        handler.OnSnapshot = (p, ct) =>
        {
            if (cmd1Ran == 0)
            {
                cmd1Ran++;
                reentrantDrainCalls++;
                // Attempt re-entrant drain while command 1 is still running
                dispatcher!.Drain(session);
                return new JObject { ["schema_version"] = "0.1", ["cmd"] = 1 };
            }
            cmd2Ran++;
            return new JObject { ["schema_version"] = "0.1", ["cmd"] = 2 };
        };

        // Authenticate and enqueue 2 commands
        session.Receive(Rpc.Hello(1, config.Token));
        session.Receive(Rpc.Request(2, "drawing.snapshot", Rpc.SnapshotParams()));
        session.Receive(Rpc.Request(3, "drawing.snapshot", Rpc.SnapshotParams()));

        Assert.Equal(2, session.QueuedCount);

        // Drain first command
        dispatcher.Drain(session);

        Assert.Equal(1, cmd1Ran);
        Assert.Equal(1, reentrantDrainCalls);

        // When command 1 ended, it re-posted for remaining queued command
        // Execute the re-posted drain from syncContext
        while (syncContext.PostedActions.TryDequeue(out var action))
        {
            action();
        }

        Assert.Equal(1, cmd2Ran);
        Assert.False(session.HasQueuedCommands);
        Assert.Empty(reported);
    }

    [Fact]
    public void CommandPostedWhileOneRuns_RunsAfterwards()
    {
        var syncContext = new TrackingSyncContext { AutoExecute = false };
        var reported = new List<Exception>();
        var currentThreadId = Thread.CurrentThread.ManagedThreadId;
        UIThreadDispatcher? dispatcher = null;
        dispatcher = new UIThreadDispatcher(
            syncContext,
            targetThreadId: currentThreadId,
            onUnexpected: reported.Add);

        var config = Rpc.Config();
        var ledger = new OperationLedger();
        var handler = new ScriptedHandler();
        var sink = new RecordingSink();
        var session = new IpcSession(
            config,
            ledger,
            handler,
            sink,
            onCommandEnqueued: s => dispatcher!.Dispatch(s));

        var executedCommands = new List<long>();

        handler.OnSnapshot = (p, ct) =>
        {
            var id = executedCommands.Count + 1;
            executedCommands.Add(id);
            if (id == 1)
            {
                // Enqueue command 2 while command 1 is currently running
                session.Receive(Rpc.Request(3, "drawing.snapshot", Rpc.SnapshotParams()));
            }
            return new JObject { ["schema_version"] = "0.1" };
        };

        session.Receive(Rpc.Hello(1, config.Token));
        // Enqueue command 1
        session.Receive(Rpc.Request(2, "drawing.snapshot", Rpc.SnapshotParams()));

        // Run the posted action for command 1
        Assert.True(syncContext.PostedActions.TryDequeue(out var action1));
        action1();

        Assert.Single(executedCommands);

        // Command 2 was posted while Command 1 was running.
        // It must run afterwards and not be stranded!
        while (syncContext.PostedActions.TryDequeue(out var actionRemaining))
        {
            actionRemaining();
        }

        Assert.Equal(2, executedCommands.Count);
        Assert.False(session.HasQueuedCommands);
    }
}

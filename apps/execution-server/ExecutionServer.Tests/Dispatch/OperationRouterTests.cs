using System.Linq;
using System.Threading;
using ExecutionServer.Core.Dispatch;
using ExecutionServer.Core.Ipc;
using ExecutionServer.Core.Ipc.Generated;
using Newtonsoft.Json.Linq;
using Xunit;

namespace ExecutionServer.Tests.Dispatch;

public sealed class OperationRouterTests
{
    [Fact]
    public void UnknownOperation_IsError()
    {
        var router = new OperationRouter();
        var op = new Operation { Op = "unknown.operation", OperationId = "j1:1" };

        var ex = Assert.Throws<IpcException>(() => router.Route("doc", op, CancellationToken.None));
        Assert.Equal(ErrorCodes.BACKEND_CAPABILITY_MISSING, ex.Code);
    }

    [Fact]
    public void RouterOperations_MatchHello()
    {
        var router = new OperationRouter();
        var expected = new[]
        {
            "document.open",
            "document.close",
            "sheet_format.generate",
            "drawing.create",
            "view.create",
            "view.update",
            "model_items.insert",
            "dimensions.auto_arrange",
            "center_mark.add",
            "dimension.hide",
            "dimension.show",
            "dimension.move",
            "document.save"
        };

        foreach (var op in expected)
        {
            router.Register(op, (doc, o, ct) => new JObject());
        }

        Assert.Equal(13, router.Operations.Count);
        Assert.Equal(expected.OrderBy(x => x), router.Operations.Select(o => o.Op).OrderBy(x => x));
    }
}

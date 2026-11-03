# execution-server

C# SOLIDWORKS add-in (.NET Framework 4.8, x64) that runs in process and talks to the core service over a named pipe. See ADR-028, ADR-036 and ADR-038.

| Project | Contents |
| --- | --- |
| `ExecutionServer.AddIn` | `ISwAddin`, pipe host, dispatcher, events, diagnostics |
| `ExecutionServer.Core` | IPC protocol, operation-ID ledger, units. No SOLIDWORKS references |
| `ExecutionServer.Adapters` | Per-domain SOLIDWORKS adapters |
| `ExecutionServer.Tests` | xUnit tests for Core |

Without SOLIDWORKS, build only Core and its tests:

```bash
dotnet test ExecutionServer.Tests/ExecutionServer.Tests.csproj
```

On the SOLIDWORKS machine, build everything. Set `SolidWorksInstallDir` if SOLIDWORKS is not in the default folder:

```bash
dotnet build ExecutionServer.sln -p:SolidWorksInstallDir="D:\SOLIDWORKS\\"
```

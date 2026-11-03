# sw-mcp

An MCP server and SOLIDWORKS execution engine that lets AI agents build parametric models and production drawings through a deterministic, verified pipeline.

The specification is in [docs/](docs/README.md). Start with the [product specification](docs/specifications/product-spec.md) and the [roadmap](docs/specifications/roadmap.md).

## Layout

| Path | Contents |
| --- | --- |
| `apps/mcp-server/` | Python: thin stdio MCP front-end (ADR-041) |
| `apps/core-service/` | Python: long-lived per-user core service (ADR-041) |
| `apps/execution-server/` | C#: SOLIDWORKS add-in (ADR-028, ADR-038) |
| `packages/` | Python libraries: IR, compiler, drawing pipeline, references, verification, protocol, application |
| `schemas/` | JSON Schema 2020-12 contracts; Python and C# types are generated from them (ADR-035) |
| `standards/iso/` | Drafting standard, templates, sheet formats, hole-callout file |
| `tests/` | Integration, end-to-end, benchmark and regression suites |

Full layout: [section 17](docs/development/repository-structure.md).

## Setup

Requirements: Windows x64, [uv](https://docs.astral.sh/uv/), .NET SDK 9 or newer. SOLIDWORKS 2025 or newer only for the add-in and live tests.

```bash
uv sync
uv run pytest
```

```bash
dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj
```

Building the full add-in needs SOLIDWORKS installed. If it is not in the default folder, pass `-p:SolidWorksInstallDir=<folder>\`.

```bash
dotnet build apps/execution-server/ExecutionServer.sln
```

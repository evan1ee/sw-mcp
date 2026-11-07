# 17. Repository Architecture

> Specification v1.44, section 17. Index and section map: [specifications/README.md](../specifications/README.md).

Target structure for the new implementation (ADR-039). Python lives in `apps/mcp-server/`, `apps/core-service/` and `packages/` (ADR-034, ADR-041); C# lives only in `apps/execution-server/` (ADR-038); `schemas/` is the contract both sides are generated from (ADR-035).

```
sw-mcp/
├── apps/
│   ├── mcp-server/                    Python: thin stdio MCP front-end, no state (ADR-041)
│   ├── core-service/                  Python: long-lived per-user service; hosts tools, jobs, store, add-in connections (ADR-041)
│   └── execution-server/              C#: ExecutionServer.sln (ADR-028, ADR-038)
│       ├── ExecutionServer.AddIn/     ISwAddin, pipe host, dispatcher, events, diagnostics
│       ├── ExecutionServer.Core/      IPC protocol (ADR-036), operation-ID ledger, units; no SOLIDWORKS refs
│       ├── ExecutionServer.Adapters/  handlers and observers: documents, parts, assemblies, drawings, native helpers. Never judges (ADR-063)
│       ├── ExecutionServer.Tests/
│       └── launcher/
├── packages/                          Python, one uv workspace member each
│   ├── cad-ir/                        core, bundle, part-feature-graph, assembly-graph, design-intent, drawing-intent, drawing-layout, drawing-template
│   ├── cad-compiler/                  parser, validator, graph, lowering, planner
│   ├── cad-drawing/                   view-planning, cleanup, placement, checks, profiles, solidworks (1.3)
│   ├── cad-geometry/                  signatures, topology, measurements
│   ├── cad-references/                semantic, persistent, resolver
│   ├── cad-verification/              api, geometry, design-intent
│   ├── cad-protocol/                  IPC client and ReplayBackend (ADR-036); message types are generated into cad-ir (G2, ADR-051)
│   └── cad-application/               tool handlers, design, graph, compilation, execution, jobs, synchronization, recovery, store (13.1)
├── schemas/                           JSON Schema 2020-12 (ADR-035)
│   ├── common/                        shared-core types, geometry-reference, errors (ADR-037)
│   ├── part-feature-graph/ assembly-graph/ design-intent/ drawing-intent/ drawing-layout/ drawing-template/ bundle/
│   ├── resolved-scheme/ drawing-geometry-snapshot/ execution-plan/ execution-evidence/ drawing-report/
│   ├── ipc/                           add-in and core-service messages (ADR-036, ADR-041)
│   ├── mcp/                           one contract file per MCP tool (12.4.1)
│   └── config/                        configuration schema (13.3.2)
├── standards/iso/                     drafting standard file, templates, sheet formats, hole-callout file
├── tests/                             integration, e2e, cad-benchmark, drawing-benchmark, regression (unit tests live in each package)
├── examples/  scripts/  docs/
├── .github/workflows/                 hosted and self-hosted CI (ADR-039)
├── pyproject.toml  uv.lock  .python-version
├── AGENTS.md
└── README.md
```

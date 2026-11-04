# Documentation

Documentation for the AI-native Parametric CAD System: an MCP server and SOLIDWORKS execution engine that lets AI agents build parametric models and production drawings through a deterministic, verified pipeline.

The [specification](specifications/README.md) (v1.20) is split across these folders by topic. Section numbers are kept, so a reference such as "see 11.5" resolves through the [section map](specifications/README.md#how-this-specification-is-organized).

```
docs/
├── specifications/   what the product is and when it ships
├── architecture/     how the system works, one file per component or IR module
├── api/              the MCP tool surface agents call
├── adr/              architecture decision records, ADR-001 … ADR-049
└── development/      repository layout and testing
```

## Reading order

1. [Product specification](specifications/product-spec.md) — vision, scope, targets, definition of done
2. [Architecture overview](architecture/overview.md) — layers, components, task-driven IR composition
3. [Production drawings](architecture/production-drawings.md) — the P0 capability
4. [Roadmap](specifications/roadmap.md) — phases and the Phase 0 assumption register
5. [Decisions](adr/README.md) — why things are the way they are

## Specifications

| File | Contents |
| --- | --- |
| [README.md](specifications/README.md) | Version, status, conventions, section map |
| [product-spec.md](specifications/product-spec.md) | §1 Executive summary, §2 Scope, §16 Targets, §20 Definition of done, §21 Product definition |
| [roadmap.md](specifications/roadmap.md) | §18 Phases 0–5 |
| [CHANGELOG.md](specifications/CHANGELOG.md) | What changed in each specification version |
| [open-decisions.md](specifications/open-decisions.md) | Register of decisions found missing before implementation, where each is now recorded, and the place to log new gaps |

## Architecture

| File | Contents |
| --- | --- |
| [overview.md](architecture/overview.md) | §3 Layers, components, IR modules and composition |
| **IR modules** | |
| [shared-ir-core.md](architecture/shared-ir-core.md) | §3.4 Identifiers, keyed collections, reference grammar, units, canonical hashing, revisions, bundles, validation errors |
| [part-feature-graph-ir.md](architecture/part-feature-graph-ir.md) | §5.1–5.5 Part Feature Graph IR, feature tiers |
| [assembly-graph-ir.md](architecture/assembly-graph-ir.md) | §5.6 Assembly Graph IR (optional) |
| [feature-schema-guide.md](architecture/feature-schema-guide.md) | §5.7 Feature node conventions, shared objects, sketches, roles, defaults |
| [read-path.md](architecture/read-path.md) | §5.8 Reading hand-modelled parts into read-only graphs |
| [design-intent-ir.md](architecture/design-intent-ir.md) | §4 Design Intent IR (optional) |
| [drawing-intent-ir.md](architecture/drawing-intent-ir.md) | §11.10 Drawing Intent IR, dimension scheme |
| [drawing-layout-ir.md](architecture/drawing-layout-ir.md) | §11.11 Drawing Layout IR, pins |
| **Pipeline** | |
| [cad-compiler.md](architecture/cad-compiler.md) | §6 Compiler pipeline and determinism; §6.7 stage contract |
| [backend-operations.md](architecture/backend-operations.md) | §6.5 Backend operation vocabulary and Execution Plan; §6.6 capability profile |
| [geometry-references.md](architecture/geometry-references.md) | §7 Semantic geometry references |
| [execution-engine.md](architecture/execution-engine.md) | §8 SOLIDWORKS add-in, COM rules, job lifecycle |
| [addin-runtime.md](architecture/addin-runtime.md) | §8.6 Add-in loading, session discovery, threading, time limits, settings guard |
| [incremental-sync.md](architecture/incremental-sync.md) | §9 Graph diff and state synchronization |
| [verification-engine.md](architecture/verification-engine.md) | §10 Verification layers |
| [production-drawings.md](architecture/production-drawings.md) | §11.1–11.9 Drawing pipeline, checks D1–D10, benchmark |
| **Cross-cutting** | |
| [data-management.md](architecture/data-management.md) | §13 Storage and document identity |
| [project-store.md](architecture/project-store.md) | §13.2 Store layout, atomic writes, job journal, retention |
| [configuration.md](architecture/configuration.md) | §13.3 Configuration sources, keys, title-block mapping |
| [security-reliability.md](architecture/security-reliability.md) | §14 Security and reliability |

## API

| File | Contents |
| --- | --- |
| [mcp-interface.md](api/mcp-interface.md) | §12 Tool naming, categories, toolsets and token budget |
| [tool-contracts.md](api/tool-contracts.md) | §12.4 Contract files, conventions, tool kinds and the table of all tools; §12.5 file access |

## Development

| File | Contents |
| --- | --- |
| [repository-structure.md](development/repository-structure.md) | §17 Target repository layout |
| [testing-strategy.md](development/testing-strategy.md) | §15 Unit, integration, end-to-end, benchmarks, contract tests, test policy |
| [implementation-guidelines.md](development/implementation-guidelines.md) | G1 COM objects, G2 Python layering, G3 logging |

## Conventions

- **The spec is the source of truth.** Change the topic file, bump the version in [specifications/README.md](specifications/README.md), and add an entry to [CHANGELOG.md](specifications/CHANGELOG.md).
- **Keep section numbers stable.** Other files and the changelog refer to sections by number.
- **New decisions get an ADR.** Use [adr/template.md](adr/template.md) and the next free number; never reuse an ID.
- **[Builder's call]** marks a decision made while writing, not by the owner; it may be revisited.

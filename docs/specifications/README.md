# AI-native Parametric CAD System

## Product & Technical Specification

**Document Version:** 1.29
**Date:** November 5, 2026
**Status:** Proposed Architecture (refined after owner interview, two SOLIDWORKS reviews, an architecture review and a development-readiness review)
**Reference Implementation:** SolidPilot — a behavioral reference only. This system is implemented independently: no SolidPilot code is copied into it. The reference may be studied for behavior, tool contracts and lessons learned, and its observable behavior may be matched. Everywhere else, this document calls it "the reference implementation".
**Primary CAD Backend:** SOLIDWORKS 2025 and newer
**Primary Integration Protocol:** Model Context Protocol (MCP)

Change history: [CHANGELOG.md](CHANGELOG.md).

Decisions marked **[Builder's call]** were made while writing this document, not by the owner; they may be revisited during planning.

## How this specification is organized

The specification is split across `docs/` by topic. Section numbers are unchanged, so references such as "see 11.5" or "(8.3 rule 13)" resolve through the map below.

| § | Section | File |
| --- | --- | --- |
| 1 | Executive Summary | [specifications/product-spec.md](../specifications/product-spec.md) |
| 2 | System Scope | [specifications/product-spec.md](../specifications/product-spec.md) |
| 3 | High-Level Architecture | [architecture/overview.md](../architecture/overview.md) |
| 4 | Design Intent IR | [architecture/design-intent-ir.md](../architecture/design-intent-ir.md) |
| 5 | Part Feature Graph IR and Assembly Graph IR | [architecture/part-feature-graph-ir.md](../architecture/part-feature-graph-ir.md) |
| 6 | CAD Compiler | [architecture/cad-compiler.md](../architecture/cad-compiler.md) |
| 7 | Semantic Geometry Reference System (P1) | [architecture/geometry-references.md](../architecture/geometry-references.md) |
| 8 | Execution Engine | [architecture/execution-engine.md](../architecture/execution-engine.md) |
| 9 | Incremental Compilation and Synchronization (P2) | [architecture/incremental-sync.md](../architecture/incremental-sync.md) |
| 10 | Verification Engine | [architecture/verification-engine.md](../architecture/verification-engine.md) |
| 11 | Production Drawings (P0) | [architecture/production-drawings.md](../architecture/production-drawings.md) |
| 12 | MCP Interface | [api/mcp-interface.md](../api/mcp-interface.md) |
| 13 | Data Management and Persistence | [architecture/data-management.md](../architecture/data-management.md) |
| 14 | Security and Reliability | [architecture/security-reliability.md](../architecture/security-reliability.md) |
| 15 | Testing Strategy | [development/testing-strategy.md](../development/testing-strategy.md) |
| 16 | Performance and Quality Targets | [specifications/product-spec.md](../specifications/product-spec.md) |
| 17 | Repository Architecture | [development/repository-structure.md](../development/repository-structure.md) |
| 18 | Roadmap | [specifications/roadmap.md](../specifications/roadmap.md) |
| 19 | Key Architectural Decisions | [adr/README.md](../adr/README.md) |
| 20 | Definition of Done (production-ready release) | [specifications/product-spec.md](../specifications/product-spec.md) |
| 21 | Final Product Definition | [specifications/product-spec.md](../specifications/product-spec.md) |

Subsections that live in their own file:

| § | Section | File |
| --- | --- | --- |
| 3.4 | Shared IR Core | [architecture/shared-ir-core.md](../architecture/shared-ir-core.md) |
| 5.6 | Assembly Graph IR | [architecture/assembly-graph-ir.md](../architecture/assembly-graph-ir.md) |
| 5.7 | Part Feature Graph Schema Guide | [architecture/feature-schema-guide.md](../architecture/feature-schema-guide.md) |
| 5.8 | Read Path | [architecture/read-path.md](../architecture/read-path.md) |
| 6.5–6.6 | Backend Operations and Execution Plans; Capability Profile | [architecture/backend-operations.md](../architecture/backend-operations.md) |
| 6.7 | Compiler Stage Contract | [architecture/cad-compiler.md](../architecture/cad-compiler.md#67-stage-contract) |
| 8.6 | Add-in Runtime | [architecture/addin-runtime.md](../architecture/addin-runtime.md) |
| 11.10 | Drawing Intent IR | [architecture/drawing-intent-ir.md](../architecture/drawing-intent-ir.md) |
| 11.11 | Drawing Layout IR | [architecture/drawing-layout-ir.md](../architecture/drawing-layout-ir.md) |
| 11.12 | Drawing Template IR | [architecture/drawing-template-ir.md](../architecture/drawing-template-ir.md) |
| 12.4–12.5 | Tool Contracts; Projects and File Access | [api/tool-contracts.md](../api/tool-contracts.md) |
| 13.2 | Project Store and Job Journal | [architecture/project-store.md](../architecture/project-store.md) |
| 13.3 | Configuration | [architecture/configuration.md](../architecture/configuration.md) |
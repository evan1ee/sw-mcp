# Agent Instructions

Instructions and development workflow for AI coding agents working in the `sw-mcp` codebase.

---

## 1. Source of Truth & Governance

1. **The specification in `docs/` decides what to build.** Always read [`docs/README.md`](docs/README.md) first, then the specific section for your task. Sections are referenced by number (e.g., "11.5.2"), resolved through the [section map](docs/specifications/README.md).
2. **Decisions live in `docs/adr/`.** Do not contradict an ADR in code. If code requires a different decision, change the spec and propose/update an ADR first. See [`docs/adr/README.md`](docs/adr/README.md).
3. **Changing the specification:**
   - Edit the topic file in `docs/architecture/`, `docs/specifications/`, or `docs/api/`.
   - Bump the specification version in `docs/specifications/README.md` and in every topic file's header line.
   - Add an entry to `docs/specifications/CHANGELOG.md`.
   - Keep section numbers stable.
4. **Log gaps before working around them:** Any gap or ambiguity found during implementation must be recorded in [`docs/specifications/open-decisions.md`](docs/specifications/open-decisions.md) before implementing a workaround.

---

## 2. Hard Rules

- **Clean-room implementation (ADR-010):** Never copy code from the reference implementation (SolidPilot). Study its observable behavior, tool contracts, and failure modes only.
- **Custody of source files (ADR-022):** Never write to source parts, assemblies, or PDM-vaulted files without explicit permission. Never run SOLIDWORKS macros (section 14).
- **Schema-first contracts (ADR-035):** `schemas/` is the single source of truth for contracts. Generated Python and C# types are build outputs; never edit generated files by hand.
- **Python layering & purity (Guideline G2):** Strictly enforce dependency direction. Pure core packages (`cad-ir`, `cad-compiler`, `cad-drawing`, `cad-geometry`, `cad-references`, `cad-verification`) must perform **zero I/O**, have no network/clock dependencies, and contain no CAD vendor imports. Enforced by `lint-imports`.
- **C# COM object safety (Guideline G1):** The add-in runs in-process inside SOLIDWORKS (`ISwAddin`). Release COM objects explicitly with `Marshal.ReleaseComObject` in `finally` blocks. Never call `Marshal.FinalReleaseComObject`. Never cache COM proxies across commands. No COM objects leave the STA UI thread.
- **ExecutionServer.Core CAD-free (ADR-038):** `ExecutionServer.Core` must have no SOLIDWORKS references and remain cross-platform testable. Banned SOLIDWORKS APIs are enforced by analyzer rules in `apps/execution-server/BannedSymbols.txt`.
- **Logging & correlation (Guideline G3):** JSON Lines format with `request_id`, `job_id`, and `operation_id` propagated across all processes (front-end -> core -> add-in). Never log geometry or file contents.

---

## 3. Implementation Workflow: Spec (if needed) → Plan → Implement → Verify

Every task must follow this four-phase engineering discipline:

```
┌───────────────────────┐
│  1. Spec (if needed)  │  Align or update docs/ & schemas/ when contracts change
└──────────┬────────────┘
           │
┌──────────▼────────────┐
│       2. Plan         │  Deconstruct into testable units, verify boundaries & rules
└──────────┬────────────┘
           │
┌──────────▼────────────┐
│     3. Implement      │  TDD (test-first), preserve purity, enforce COM rules
└──────────┬────────────┘
           │
┌──────────▼────────────┐
│      4. Verify        │  Run full verification suite; evidence before completion claims
└───────────────────────┘
```

### Phase 1: Spec (If Needed)
*Determine whether the task requires changing or clarifying the contract.*
- **Skip this phase** if the work is an internal bugfix, refactoring, test addition, or routine implementation cleanly within existing specifications.
- **Execute this phase** if the task introduces a new feature, changes tool interfaces, modifies IR schemas, adds backend operations, or resolves an unhandled edge case:
  1. Consult [`docs/specifications/open-decisions.md`](docs/specifications/open-decisions.md). If resolving an open item, note its resolution. If encountering a new gap, log it before proceeding.
  2. If making an architectural choice between real alternatives, draft an ADR in `docs/adr/` using `template.md`.
  3. Update the normative topic spec in `docs/specifications/`, `docs/architecture/`, or `docs/api/`.
  4. If schemas are impacted, update or author the JSON Schema (2020-12) under `schemas/`.
  5. Bump the spec version in `docs/specifications/README.md` and headers, and document changes in `docs/specifications/CHANGELOG.md`.

### Phase 2: Plan
*Deconstruct the work before modifying code.*
- Map the change across layers:
  - Schemas: `schemas/`
  - Pure Python libraries: `packages/cad-ir/`, `packages/cad-compiler/`, `packages/cad-drawing/`, etc.
  - Python application/services: `packages/cad-application/`, `apps/core-service/`, `apps/mcp-server/`
  - C# execution engine: `apps/execution-server/ExecutionServer.Core/`, `ExecutionServer.AddIn/`, `ExecutionServer.Adapters/`
  - Tests: unit test fixtures, contract tests, integration suites.
- Verify that planned dependencies respect G2 (`apps/mcp-server` → `apps/core-service` → `cad-application` → pure packages / ports).
- Formulate a clear, step-by-step checklist or task artifact before writing code.

### Phase 3: Implement
*Build with engineering rigor.*
- **Test-Driven Development (TDD):** Write failing unit or contract tests first. Confirm the test fails for the expected reason, then write the minimal implementation to pass.
- **Pure Core Isolation:** Keep core packages purely functional. Inject side effects (file system, CAD backend, clocks, ULID generation) through ports (`Backend`, `Store`, `Clock`, `IdSource`).
- **COM Lifecycle:** In C# add-in code, adhere strictly to Guideline G1. Wrap enumerators, entity selections, and temporary geometry in `try/finally` blocks with `Marshal.ReleaseComObject`.
- **Contracts & Code Generation:** Edit schemas in `schemas/`. When schemas change, regenerate Python models and C# types via build scripts; never hand-edit generated files.
- **Determinism:** Preserve canonical serialization (RFC 8785) and use quantized units (3.4.3) for numerical equality.

### Phase 4: Verify
*Evidence before claims, always.*
- **No completion claims without fresh verification output:** Never claim code is working, passing, or complete without running the verification commands and confirming zero errors.
- **Execute standard verification suite:** Run linters, type checks, import linter, and unit tests locally.
- **Contract & Fixture Testing:** Verify changes against schema fixtures in `tests/fixtures/schemas/` and recorded IPC/MCP transcripts.
- **No Automatic Retries:** Do not mask nondeterminism. If a test flakes, isolate and quarantine it per section 15.6.

---

## 4. Commands & Verification Suite

### Python Verification
```bash
uv sync
uv run python scripts/generate_contracts.py --check
uv run ruff check
uv run ruff format --check
uv run pyright
uv run lint-imports
uv run pytest
```

### C# Verification
```bash
# Run unit & contract tests (CAD-free)
dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj

# Build full solution (requires SOLIDWORKS installed or SolidWorksInstallDir passed)
dotnet build apps/execution-server/ExecutionServer.sln
```

### Live SOLIDWORKS Tests
- Live suites require a dedicated Windows x64 environment with a licensed SOLIDWORKS 2025+ install, an active interactive user desktop session, and a visible SOLIDWORKS window (Section 15.2, ADR-039).
- Live tests do not run in headless CI environments.

---

## 5. Session Handoff

[`HANDOFF.md`](HANDOFF.md) carries project state between sessions and agents.

- **At the start of a session:** read it after this file, and check anything you rely on against the repository.
- **At the end of each session:** update it under these headings:
  - **Current State:** what is complete and the project's current status.
  - **Changes Made:** key implementations, decisions and files modified.
  - **Next Steps:** prioritized tasks and recommended actions.
  - **Known Issues:** outstanding bugs, blockers and unresolved decisions.
- **Keep it accurate:** rewrite existing content instead of appending, remove what is outdated, and report only state you verified, including what is unverified.
- **Keep it concise:** link to the spec, ADRs and plans instead of repeating them. `HANDOFF.md` never overrides `docs/`; decisions still go in the spec or an ADR.

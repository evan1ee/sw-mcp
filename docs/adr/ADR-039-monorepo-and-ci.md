# ADR-039: Monorepo layout and CI

- **Status:** Proposed
- **Source:** specification v1.10, readiness review (2026-11-03)

## Context

Section 17 named the root `ai-native-cad/` (this repository is `sw-mcp`), listed `adapters/solidworks/` separately from the C# add-in that contains those adapters, and did not say which language `application/` is written in. Section 15.2 needs live suites on a dedicated machine, but nothing said what runs elsewhere.

## Decision

- **One repository**, `sw-mcp`, holding Python, C#, schemas, standards files and docs, so a contract change and both sides of it land in one commit.
- **Languages by folder.** Python lives in `apps/mcp-server/` and `packages/`. C# lives only in `apps/execution-server/`. The old `application/` folder becomes the Python package `packages/cad-application/`; the old `adapters/solidworks/` becomes `ExecutionServer.Adapters` inside the C# solution (ADR-038). Section 17 shows the result.
- **Hosted CI** (GitHub Actions, `windows-latest`) on every push and pull request:
  - `uv sync`, `ruff`, `pyright`, `pytest` with coverage on `packages/` (including snapshot-replay drawing checks, 11.5.1);
  - schema validation of every example and fixture, and the generated-code drift check (ADR-035);
  - C# `Core` build and tests (ADR-038);
  - token budgets (12.3) and the reference tool-name clash check (12.1).
- **Self-hosted CI** on the SOLIDWORKS machine (15.2), running as the logged-in user: live integration suites and the drawing benchmark, on a nightly schedule and on demand for pull requests labelled `live`. The holdout set (11.8) runs only on manual dispatch at increment acceptance.
- `main` is protected: hosted CI must pass; live CI must pass before an increment is accepted.

## Rationale

A monorepo keeps contracts, both implementations and the spec in step. Placing each language in its own folders removes the §17 ambiguity. Running everything that does not need SOLIDWORKS on hosted runners keeps the scarce licensed machine for what only it can do.

## Consequences

- The repository needs `git init` and a remote before Phase 0 work is committed.
- The SOLIDWORKS machine needs a self-hosted runner installed under the interactive user account.

## Where it applies

- [development/repository-structure.md](../development/repository-structure.md) — section 17
- [development/testing-strategy.md](../development/testing-strategy.md) — section 15.2
- [api/mcp-interface.md](../api/mcp-interface.md) — section 12.1, 12.3

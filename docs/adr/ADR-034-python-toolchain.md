# ADR-034: Python toolchain

- **Status:** Proposed
- **Source:** specification v1.10, readiness review (2026-11-03)

## Context

ADR-001 puts the MCP server, compiler, drawing pipeline and job state in Python, but no version, package manager, MCP library or quality tooling was chosen. Section 17 splits the Python side into several packages that must be versioned and tested together.

## Decision

- **CPython 3.13**, pinned in `.python-version`. Windows x64 only, matching SOLIDWORKS.
- **uv workspace** at the repository root: one `pyproject.toml` per package under `packages/`, `apps/mcp-server/` and `apps/core-service/`, one shared `uv.lock`.
- **Official MCP Python SDK** (`mcp`), stdio transport by default, used only by the thin MCP front-end; the tools run in the core service (ADR-041). The exact version is pinned in `uv.lock`; upgrades go through the token-budget and tool-name CI checks (12.1, 12.3).
- **Pydantic v2** for typed IR access, generated from the JSON Schemas (ADR-035), never hand-edited.
- **Quality:** `ruff` (lint and format), `pyright` in strict mode, `pytest` with `pytest-cov`. Coverage target 80% on `packages/` (15.1).

## Rationale

uv gives one lockfile and fast, reproducible installs across a multi-package repository. 3.13 is mature and has wheels for every dependency listed here. The official SDK tracks the MCP specification; wrapping it keeps tool contracts in this system's own code. Strict typing catches IR misuse before a live SOLIDWORKS run, which is the expensive place to find it.

## Consequences

- Contributors install uv; `uv sync` sets up everything.
- A Python minor-version upgrade is a deliberate change with its own CI run, not drift.
- Generated Pydantic models are build outputs; the schema files are what reviewers read.

## Where it applies

- [architecture/execution-engine.md](../architecture/execution-engine.md) — section 8.2
- [development/repository-structure.md](../development/repository-structure.md) — section 17
- [development/testing-strategy.md](../development/testing-strategy.md) — section 15.1

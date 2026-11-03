# Agent instructions

## Source of truth

- The specification in `docs/` decides what to build. Read [docs/README.md](docs/README.md) first, then the section you are working on. Sections are referenced by number ("11.5.2"), resolved through the [section map](docs/specifications/README.md).
- Decisions live in [docs/adr/](docs/adr/README.md). Do not contradict an ADR in code. If code needs a different decision, change the spec first.
- Changing the spec: edit the topic file, bump the version in `docs/specifications/README.md` and in every file's header line, and add an entry to `docs/specifications/CHANGELOG.md`. Keep section numbers stable.
- A gap found while implementing goes into `docs/specifications/open-decisions.md` before it is worked around.

## Hard rules

- **No code from the reference implementation (SolidPilot).** Study its behavior only (ADR-010).
- Never write to source parts, assemblies or PDM-vaulted files (ADR-022). Never run SOLIDWORKS macros (section 14).
- `schemas/` is the contract. Generated Python and C# types are build outputs; never edit them by hand (ADR-035).
- Python layering follows guideline G2 and is enforced by `lint-imports`. Pure packages (`cad-ir`, `cad-compiler`, `cad-drawing`, `cad-geometry`, `cad-references`, `cad-verification`) do no I/O.
- C#: `ExecutionServer.Core` has no SOLIDWORKS references. Banned SOLIDWORKS APIs are listed in `apps/execution-server/BannedSymbols.txt`.

## Commands

```bash
uv sync
uv run ruff check
uv run ruff format --check
uv run pyright
uv run lint-imports
uv run pytest
dotnet test apps/execution-server/ExecutionServer.Tests/ExecutionServer.Tests.csproj
```

Live SOLIDWORKS tests run only on the SOLIDWORKS machine (section 15.2, ADR-039).

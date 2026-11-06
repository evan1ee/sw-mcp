# ADR-051: One generator for Python and C# contract types

- **Status:** Proposed — Builder's call
- **Source:** specification v1.21, register K5

## Context

ADR-035 named `datamodel-code-generator` for Python models and said C# types would be generated "the same way", without naming a C# tool. Trying it on the repository's schemas (version 0.30.1):

- It parses schemas with a YAML loader, which fails on `schemas/common/v0.json`: the `SolidWorksDimRef` pattern holds U+007F, which YAML does not allow.
- It would add Pydantic as a runtime dependency to re-check documents that `validate_against_schema` already validates, against the schema itself.
- It does nothing for C#. C# tools (NJsonSchema, quicktype) would add a .NET or Node toolchain to the Python-side generation step, and their 2020-12 support would still need proving.

## Decision

- `scripts/generate_contracts.py` generates the types, from one reading of the schema, for both languages: frozen dataclasses in `cad_ir/generated/ipc.py` and Newtonsoft-attributed classes in `ExecutionServer.Core/Ipc/Generated/`. It also generates the C# error catalogue from `errors.json`.
- It covers `schemas/ipc/` only, so far. Other contracts are added when code needs them.
- It supports a closed set of shapes: objects with `properties` and `required`, arrays, `string`, `integer`, `number`, `boolean`, `const`, string `enum`, `$ref` to its own `$defs` or to `common/v0.json`, and `anyOf` of one type with `null`. The error-code `$ref` to `errors.json` becomes a string (ADR-042). A `$ref` to another contract, and an object with no `properties`, become opaque JSON. **Any other shape stops the generator with an error naming the schema path**, so a type can never silently disagree with its schema.
- Validation stays with the schema. In Python, the generated types only carry data, after `validate_against_schema` or for trusted output. In C#, deserialization rejects a missing required field, a wrong JSON type and an unknown value of an input enum. Patterns and ranges are not enforced in C#: the add-in's input comes from the core, which validated it (15.5).

## Rationale

The types needed are simple, and the generator already exists and already has a `--check` mode that CI runs. A small emitter with a closed shape set is cheaper to own than two third-party tools, adds no dependency and keeps the frozen-dataclass style of the rest of the code.

## Consequences

- The project owns about 300 lines of generator, tested by the same contract tests as the types.
- A schema using a new shape must extend the generator first. That is deliberate friction.
- Should Pydantic-level validation ever be wanted in Python, this decision can be replaced without changing the schemas.

## Where it applies

- [ADR-035](ADR-035-json-schema-contracts.md), [ADR-036](ADR-036-ipc-protocol.md)
- [development/testing-strategy.md](../development/testing-strategy.md) — section 15.5
- [development/repository-structure.md](../development/repository-structure.md) — section 17

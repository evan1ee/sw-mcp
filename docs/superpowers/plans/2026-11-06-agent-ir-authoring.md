# Plan: the agent turns user input into valid IR

Status: approved by the owner on 2026-11-06. Follows [the part chain MVP plan](2026-11-05-part-chain-mvp.md).

## Goal

The MCP client LLM reads a natural-language request, follows the IR rules, writes a Part Feature Graph that matches it, validates it, and applies it. `sw-mcp` has no language-understanding component (ADR-019: features are IR data, not tools). It gives the agent what it needs to write correct IR and to say no when it cannot.

## Decisions (owner, 2026-11-06)

1. **Unsupported requests are refused.** The agent replies that it cannot fulfil the request and says what the MVP cannot do. It never approximates (for example, a through-hole for a hole in a face).
2. **About 10 evaluation prompts are enough.**
3. **The guide ships as a read-only tool, `get_authoring_guide`, not as an MCP resource.** The MCP front-end may import none of the `cad_*` packages (import-linter contract "MCP front-end holds no state and calls only the core service") and speaks to the core only through tools. A resource would need a new core protocol path. ADR-044's "no prompts" is respected.

## What exists

`list_feature_types`, `get_feature_schema`, `validate_part_graph` (issues, build order, expected geometry), `apply_part_graph`, `get_execution_status`.

## What is missing

- One document of the authoring rules: coordinate frame, extrude direction, planes, end conditions, limits.
- Server instructions that tell the agent the workflow.
- A measure of whether prompts turn into correct IR.

## Phases

1. **Spec.** Document the IR authoring contract and the new tool in `docs/api/`, bump the spec version, add a changelog entry.
2. **Guide generator** (`cad_application`, pure function). Built from the real planes, schemas and feature registry so it cannot drift. Sections: units and planes, node types and end conditions, validator rules, limits and the refusal rule, worked examples. Tests first: every supported type and plane appears; every embedded example parses and validates.
3. **Tool and instructions.** `schemas/mcp/get_authoring_guide.json`, handler, registry entry, regenerate contracts. Static server `instructions` in `mcp_server` that state the workflow and name the guide tool.
4. **Validation feedback.** Each rule's message says what to change; tests per rule.
5. **Evaluation set.** About 10 prompts with expected facts (box, volume, hole count and diameter), including unsupported ones whose correct answer is a refusal. A checker scores an IR against the facts using `validate_part_graph` logic and `expected_geometry`. No LLM calls in the pytest run.
6. **Verify.** Full Python verification suite, C# tests. No live run unless the owner asks.

## Not in this plan

Face references, blind holes from a face, arcs and patterns. They change what the IR can say and need their own spec and ADR.

## Risks

- A guide that drifts from the schemas: generated from them and tested.
- Different LLMs read the same rules differently: the evaluation set samples this; a pass rate is reported, not reliability.

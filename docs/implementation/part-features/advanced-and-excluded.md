# Advanced and Excluded

Weldments, excluded features and undecided specialist features.

> Conventions (status, scope, priority, layers, evidence legend) are defined once in the [master index](../README.md#conventions). This file owns only the rows below.

## ADV-WLD — Weldments

Weldment features. Out of scope per 5.3.5.

### Weldment

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ADV-WLD-001` | Structural member | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |
| `ADV-WLD-002` | End cap | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |
| `ADV-WLD-003` | Gusset (weldment) | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |
| `ADV-WLD-004` | Trim / extend | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |
| `ADV-WLD-005` | Weld bead | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |
| `ADV-WLD-006` | Cut list | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.5 |
| SOLIDWORKS API | — |
| Tests | — |
| Depends on | — |

## ADV-EXC — Other Excluded Features

Features 5.3.5 excludes.

### Excluded

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ADV-EXC-001` | Mold tooling: core / cavity, tooling split | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |
| `ADV-EXC-002` | Direct edit: move face | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |
| `ADV-EXC-003` | Direct edit: delete face | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |
| `ADV-EXC-004` | Routing | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |
| `ADV-EXC-005` | FeatureWorks recognition | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |
| `ADV-EXC-006` | Toolbox and library features (Create) | Out of Scope | P3 | Not Applicable | N/A | N/A | N/A | N/A | N/A | N/A | 5.3.5 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.5 |
| SOLIDWORKS API | — |
| Tests | — |
| Depends on | — |

## ADV-OTH — Molded Support and Fastening

Read-only in Tier 1 or Tier 3.

### Molded support (Create undecided)

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ADV-OTH-001` | Mounting boss | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `ADV-OTH-002` | Snap hook | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `ADV-OTH-003` | Lip / groove | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |
| `ADV-OTH-004` | Vent | Under Evaluation | P3 | Under Evaluation | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Read-only in Tier 1 (5.3.2); Create undecided |

### Fastening

| ID | Item | Scope | Pri | Status | IR | Compiler | Adapter | Execution | Validation | Integration Test | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ADV-OTH-005` | Fastening features (Create) | In Scope | P3 | Deferred | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | Tier 3 |

**Metadata**

| Item | Value |
|---|---|
| Spec | [5.3](../../../docs/architecture/part-feature-graph-ir.md#53-feature-taxonomy-and-coverage) §5.3.2, §5.3.4 |
| SOLIDWORKS API | No member found by name search |
| Tests | — |
| Depends on | — |

# ADR-003: Five domain IR modules on a shared core

- **Status:** Accepted
- **Source:** specification v1.9, section 19

## Decision

Five domain IR modules on a shared core: Part Feature Graph, Assembly Graph, Design Intent, Drawing Intent, Drawing Layout; dependencies declared, references point only to depended-on modules

## Rationale

Separate geometry, structure, requirements, specification and arrangement so each changes without breaking the others

## Where it applies

- Section 19 only.

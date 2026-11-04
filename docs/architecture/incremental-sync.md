# 9. Incremental Compilation and Synchronization (P2)

> Specification v1.27, section 9. Index and section map: [specifications/README.md](../specifications/README.md).

## 9.1 Purpose

Edit existing models without rebuilding them. Example: base diameter 20 → 25 mm. The compiler identifies the changed parameter, finds affected and dependent nodes, re-resolves affected references, emits an incremental plan, executes it, rebuilds and verifies.

The compiler limits what it *submits*; SOLIDWORKS may still rebuild the downstream chain. The system distinguishes parameter updates, feature parameter updates, insertion/deletion, dependency changes and topology-changing edits.

## 9.2 Graph Diff

Detects added and removed features, modified parameters, changed dependencies and references, suppression changes, and affected downstream features.

## 9.3 State Synchronization

Distinguishes intended IR state, last compiled state, last executed state and actual CAD document state. Detects external edits made in SOLIDWORKS through the add-in's document events (8.2) and, for edits made while the add-in was not running, by comparing the feature tree and rebuild state with the last executed state. On divergence, it reports it and requires synchronization before unsafe updates.

When a model changes, its drawings are re-checked (section 11.7).

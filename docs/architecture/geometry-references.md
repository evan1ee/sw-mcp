# 7. Semantic Geometry Reference System (P1)

> Specification v1.35, section 7. Index and section map: [specifications/README.md](../specifications/README.md).

## 7.1 Purpose

Topology changes when upstream features change, so an index-based face or edge reference cannot be trusted after rebuild. Drawings depend on this too: datums, GD&T targets and critical dimensions reference geometry. This is why references come immediately after drawings in the roadmap.

## 7.2 Reference Model

| Field | Description |
| --- | --- |
| reference_id | Unique identifier |
| owner_feature_id | Feature that produced the geometry |
| entity_type | Face, Edge, Vertex, Body |
| semantic_role | Top face, cylindrical wall, outer edge, … |
| geometric_signature | Geometric properties (7.3) |
| spatial_context | Position and orientation |
| adjacency | Connected entities |
| persistent_reference | Native CAD persistent reference |
| resolution_policy | Resolution rules, incl. ambiguity behavior |
| confidence | Resolution confidence |
| revision | Reference revision |

## 7.3 Geometric Signature

- **Face:** surface type, area, normal, centroid, bounding box, curvature, adjacent edges/faces.
- **Edge:** curve type, length, endpoints, tangent, adjacent faces, curvature.
- **Vertex:** position, connected edges, local context.

## 7.4 Resolution Strategy

Signals, in order: native persistent reference, feature provenance, semantic role, geometric signature, topological adjacency, spatial context. The resolver computes a confidence score.

| Confidence | Action |
| --- | --- |
| High | Resolve automatically |
| Medium | Resolve only if an independent check confirms it: the resolved entity's geometric signature (7.3) matches within tolerance, and no other candidate scores within a set margin. Otherwise treat as Low |
| Low | Ask the agent or user |
| Ambiguous | Fail safely |

Thresholds are configurable and calibrated on the CAD benchmark. **The system never silently picks an arbitrary entity when several are plausible.** The goal is not that references never break; it is that broken references are detected and never silently resolved to the wrong geometry.

## 7.5 SOLIDWORKS

Gathering candidates happens in the add-in and every decision in Python (ADR-049). Use `IModelDocExtension::GetPersistReference3`, `GetObjectByPersistReference3`, `IEntity`, `IFace2`, `IEdge`, `IVertex`. Persistent references are validated after topology changes; they are not a guarantee of semantic identity. Which other native identifiers are unsuitable, and why, is [8.9.12](../specifications/solidworks-adapter.md#8912-reference-resolution-in-the-adapter). The authored forms are [22.6](../specifications/ir-specification.md#226-reference-model).

**Model geometry vs drawing-view geometry.** A drawing dimension or annotation attaches to the entity as it appears in a particular view, not to the model entity. Drawing references therefore resolve in two steps: the reference resolves to a model entity, then the adapter maps it to the corresponding entity in the target view (through `IView` entity mapping) and checks that it is visible there. An entity that is not visible in the view, or that maps to more than one view entity, is reported. It is never attached to a guessed edge.

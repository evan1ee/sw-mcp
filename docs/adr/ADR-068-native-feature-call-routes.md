# ADR-068: Feature-data calls where positional calls are obsolete

- **Status:** Proposed
- **Source:** specification v1.35, section 8.9.11; extends ADR-058 and ADR-062. API facts from the installed 2025 help, not measured

## Context

SOLIDWORKS has two routes to create a feature: long positional methods on `IFeatureManager`, and `CreateDefinition`, a typed feature data object, then `CreateFeature`. The 2025 help marks several positional calls obsolete: `InsertProtrusionSwept4` and `InsertCutSwept5` (2018 sweep architecture), `FeatureFillet3` for constant radius (2020), `FeatureLinearPattern5` and `FeatureCircularPattern5`. `FeatureExtrusion3`, `FeatureCut4`, `FeatureRevolve2`, `InsertProtrusionBlend2`, `InsertFeatureChamfer` and `InsertMirrorFeature2` are not so marked, and the first two are proven by the spike. `AGENTS.md` and 8.3 ban `SelectByID2`, which most help pages use for pre-selection.

## Decision

- **Use the feature-data route wherever the help marks the positional call obsolete,** and the positional call otherwise. Keep the proven `FeatureExtrusion3` and `FeatureCut4`.
- **With a feature-data route, set every property the IR relies on explicitly, and read it back.** Do not rely on the defaults `CreateDefinition` fills.
- **Selection stays by entity** (`IFeature.Select2`, `IEntity.Select4`) with the marks the help gives. Each route passes a spike before its phase (K26).
- Each native route remains one method behind a translator record (8.8.6, 8.8.10).

## Rationale

Obsolete members risk removal, and ADR-062 assumes signature changes stay rare and local. Feature data objects have named properties, so they are easier to read and check than 20 or more positional arguments. Replacing proven calls now would gain nothing.

## Consequences

- Defaults inside `CreateDefinition` can change between versions, so explicit setting and read-back are required, and each version admission re-checks them (ADR-045).
- `ISimpleFilletFeatureData2` needs `Initialize` first, so handlers differ by type.
- If a route fails its spike, its phase records the fallback here rather than silently using an obsolete call.

## Where it applies

- [specifications/solidworks-adapter.md](../specifications/solidworks-adapter.md) — section 8.9.11
- [architecture/solidworks-adapter.md](../architecture/solidworks-adapter.md) — sections 8.8.6, 8.8.10

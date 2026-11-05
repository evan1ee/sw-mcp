# 8.9 SOLIDWORKS Adapter Interface Specification

> Specification v1.33, section 8.9. Index and section map: [README.md](README.md).

**Status: Accepted by the owner, 2026-11-05. Not built yet.** Architecture: [8.8](../architecture/solidworks-adapter.md). This section extends 6.5, 6.6 and 8.7 and repeats none of their rules. Until the roadmap delivers each part, the schemas and code stay as they are, and the [ADRs](../adr/README.md) say where they must change. JSON here is illustrative. **`schemas/` is the normative form once written (ADR-035).**

**How API facts are marked.** ✔ means measured in the [2026-11-05 spike](../superpowers/review/2026-11-05-part-chain-spike.md). ? means from general API knowledge and unverified, and it must pass a spike before use.

## 8.9.1 Contract map

| Contract | Owner | Consumers | Location | Status |
| --- | --- | --- | --- | --- |
| Operations and read commands | Schemas | Compiler output, job, add-in | `schemas/ipc/` | Exists; extended below |
| `Backend` port | Python application layer | Job layer; `cad-protocol` implements it | `cad_application/ports.py` | Exists |
| Capability profile | Add-in reports it; compiler consumes it | Lowering, job | 6.6, `cad_compiler/profile.py` | Exists; extended in 8.9.7 |
| Error catalogue | Schemas | Everyone | `schemas/common/errors.json` | Exists; one addition |
| Execution evidence | Python verification | Job, MCP, humans | `schemas/execution-evidence/v0.json`, written in roadmap A0 | New |
| `IOperationHandler`, read handlers | C# Core | Router; Adapters implement | `ExecutionServer.Core/Dispatch` | New, add-in internal |
| Translators and call records | C# Core | Adapters | `ExecutionServer.Core/Parts` | New, add-in internal |
| `ComScope`, `DocumentLocator`, scopes | C# Adapters | Handlers, observers | `ExecutionServer.Adapters/Native` | New, implementation-specific |

The compiler depends only on the first three rows. C# types are never part of the compiler's contract ([ADR-061](../adr/ADR-061-contract-ownership.md)).

## 8.9.2 Backend port

Stays small. No per-feature method is added, since features are data in `ops.apply`.

```python
class Backend(Protocol):
    @property
    def session(self) -> HelloResult: ...
    def apply_ops(
        self, groups: Sequence[OperationGroup], *, meta: Meta | None = None
    ) -> OpsApplyResult: ...
    def measure_part(self, document: str, *, meta: Meta | None = None) -> JsonValue: ...
    def snapshot_drawing(
        self, document: str, sheets: Sequence[str] | None = None, *, meta: Meta | None = None
    ) -> JsonValue: ...
    def completed_operations(self) -> tuple[str, ...]: ...
    def cancel(self, *, meta: Meta | None = None) -> bool: ...
    def close(self) -> None: ...

    # Added in the phase that needs each (both are already named by G2):
    def read_features(
        self, document: str, *, page: str | None = None, meta: Meta | None = None
    ) -> JsonValue: ...  # A3
    def geometry_candidates(
        self, document: str, requests: JsonValue, *, meta: Meta | None = None
    ) -> JsonValue: ...  # A6
```

## 8.9.3 Operations

General rules are 6.5.1. This section adds:

1. **Five stages.** A handler admits, translates, invokes, reads back and reports (8.8.6).
2. **Results are observed.** Every value in `result` comes from SOLIDWORKS after the call, never from the request.
3. **`source` stays in the plan.** The wire carries `node_id` where a native object is created, which is enough to join to the plan's `source`.
4. **No positional or vendor terms in params.** No `T1`, `Sd`, `swEndCondThroughAll` or selection marks.
5. **Lengths in the document's IR unit** in params (mm in the MVP, 6.5.2). The translator converts them once. Read commands return raw SI (8.7).
6. **Standard result fields** for an operation creating a native feature: `native_id`, `feature_id`, `status`, and `node_id` echoed only as the join key. `status` values: `ok`, `warning`, `error`, `suppressed`.
7. **Observation in the result (ADR-064).** An operation that creates a native object also returns `observation`: `native_type`, neutral `type`, `error_code`, `is_warning`, `suppressed`, `parents`, `parameters`, `solid_body_count`, `needs_rebuild`, `update_stamp` and `completeness`, as far as its tier reads them (10.2.2). Reading them must not change the document. These are additive to the schemas in roadmap A0.

**Vocabulary by phase.** Names and parameters beyond the MVP are proposals, written to schemas before their phase. Feature names follow 5.3.2 and 5.7.

| Phase | Operation | Key params | Observed result | Native route |
| --- | --- | --- | --- | --- |
| A1 | `document.open` | `read_only` | `owned`, `instance_id`, `read_only`, `was_open` | `OpenDoc6` ✔, `GetOpenDocumentByName` ✔ |
| A1 | `document.close` | | `closed`, confirmed by lookup | `CloseDoc` ✔ then `GetOpenDocumentByName` ✔ |
| A1 | `document.save` | `target_path` | `path`, `size_bytes`, `dirty` | `SaveAs4` ✔, with its error outputs |
| A2 | `part.create` | `template`, working path | `native_id`, `path`, `instance_id`, `previous_active`, `template` | `NewDocument` ✔, `SaveAs4` ✔ |
| A2 | `sketch.create` | `node_id`, `plane`, `entities` | `native_id`, `feature_id`, `entity_count` | `Select2`, `InsertSketch`, `CreateLine`, `CreateCircleByRadius` ✔ |
| A2 | `feature.create` `extrude`, `cut_extrude` | `node_id`, `type`, `profile`, `end_condition` | `native_id`, `feature_id`, `status` | `FeatureExtrusion3`, `FeatureCut4` ✔ |
| A2 | `document.rebuild` | `force` | `ok`, `errors` | `ForceRebuild3` ✔ |
| A4 | `sketch.create` adds `arc` | `center`, `start`, `end` | Same, plus `solved` | ? |
| A4 | `sketch.create` adds `relations`, `dimensions` (5.7.4) | Keyed by ID | `fully_defined`, per-relation result, `dimension_values` | ? |
| A5 | `feature.create` `revolve`, `cut_revolve` | `profile`, `axis`, `angle` | As above | ? |
| A6 | `feature.create` `fillet`, `chamfer` | Pinned `edges`, `radius` or `distance`, `angle` | As above, plus `edge_count` | ? |
| A6 | `sketch.create` on a pinned face | `plane` as a pinned reference | As above | ? |
| A7 | `reference_plane.create` | Offset or angle definition | `native_id`, `feature_id`, `status` | ? |
| A7 | `feature.create` `linear_pattern`, `circular_pattern`, `mirror` | Seed features, direction, count, spacing | Plus `instance_count` | ? |
| A8 | Assembly and drawing groups | 6.5.2, 5.6 | Reviewed when the freeze lifts | Existing, frozen |

**Postconditions** are evaluated by the core from these results (8.8.6), against a contract derived from the IR (10.2.2). The existing names in 6.5.3 are enough to start: `feature_exists`, `feature_status_ok`, `rebuild_ok`, `entity_count`, `parameter_equals`.

## 8.9.4 Read commands

Reads are commands, not operations (6.5.2). They mutate nothing, take no operation ID, and do not touch the ledger.

**`part.measure`** is as specified in 8.7. Addition, roadmap A2: `completeness`, one state per collection (8.9.6).

**`features.read`** implements 5.8, paged. Intended shape, fixed when its schema is written in roadmap A3:

```json
{
  "path": "D:/parts/plate.SLDPRT",
  "instance_id": "i_01J...",
  "configuration": "Default",
  "dirty": false,
  "completeness": { "features": "present", "dimensions": "present", "sketch_geometry": "unsupported" },
  "features": [
    { "feature_id": "f79", "native_type": "Extrusion", "type": "extrude", "tree_order": 21,
      "display_name": "Boss-Extrude1", "status": "ok", "suppressed": false,
      "parents": ["f73"], "dimensions": { "d1": { "value_si": 0.01, "kind": "linear", "full_name": "D1@Boss-Extrude1" } } }
  ],
  "next_page": null
}
```

✔ `GetID`, `GetTypeName2`, and the `RefPlane` order. ? `parents` through `IFeature.GetParents`, the dimension enumeration, suppression state, per-configuration read. Those need a spike (K15) that also proves the document's dirty flag and selection do not change.

**`geometry.candidates`** is as in ADR-049. It is out of this design's scope apart from its phase.

## 8.9.5 Error contract

Errors use the ADR-037 catalogue. A handler either returns a result or throws one catalogued error. A silent catch is a defect.

```json
{ "code": "PROPOSED_OPERATION_FAILED",
  "message": "Extrude created no feature",
  "details": {
    "effect": "none",
    "stage": "invoke",
    "native": { "call": "FeatureExtrusion3", "returned": "null", "hresult": null, "error_code": null }
  } }
```

| `details` field | Values | Purpose |
| --- | --- | --- |
| `effect` | `none`, `applied`, `unknown` | Whether the document may have changed. **Required on every operation failure from stage 3 on** |
| `stage` | `admit`, `translate`, `invoke`, `read_back`, `report` | Where it failed |
| `native` | `call`, `returned`, `hresult`, `error_code` | Diagnostics only. **Agents never branch on it** (ADR-037) |

**Normalization.**

| Native signal | Code | `effect` |
| --- | --- | --- |
| Operation not in the router | `BACKEND_CAPABILITY_MISSING` | `none` |
| Capability absent for this variant | `BACKEND_CAPABILITY_MISSING` | `none` |
| Params fail shape or range checks | `IR_SCHEMA_INVALID` | `none` |
| Part not owned, or path already exists | `AUTH_SOURCE_WRITE_NOT_ALLOWED` | `none` |
| Document not open at that path, or template missing | `FILE_NOT_FOUND` | `none` |
| Document instance is not the one recorded | `EXEC_INTERRUPTED_BY_USER` | `none` |
| Writing to a read-only document | `BACKEND_READ_ONLY` | `none` |
| Feature call returned null ✔ | `BACKEND_REBUILD_ERROR` (6.5.2) | `none`, after confirming the feature count did not change, otherwise `unknown` |
| Feature created with an error status | `BACKEND_REBUILD_ERROR` | `applied` |
| Rebuild reports errors | `BACKEND_REBUILD_ERROR` | `applied` |
| Native call returned false, or its error output is non-zero | `PROPOSED_OPERATION_FAILED` | `unknown`, unless proven |
| `COMException` from a native call | `PROPOSED_OPERATION_FAILED`, with `hresult` | `unknown` |
| Read-back disagrees with the call's claim | `PROPOSED_OPERATION_FAILED` | `applied` or `unknown` |
| Cancellation between steps | `EXEC_CANCELLED` | `none` |
| Any other exception (a bug) | JSON-RPC `-32603`, logged with a stack (8.7) | `unknown` |

**New catalogue entry** (added in roadmap A0). `PROPOSED_OPERATION_FAILED` is a placeholder until then, because the docs may name only catalogued codes (`tests/contract/test_error_catalogue.py`). Its intended name is `OPERATION_FAILED` under the `BACKEND_` prefix:

```json
{ "const": "PROPOSED_OPERATION_FAILED",
  "description": "A native call failed or its read-back disagreed; details.effect says whether the document may have changed.",
  "x-retryable": "after_fix" }
```

It stops codes such as `BACKEND_LOST` being misused for an ordinary failure (`ViewCreationAdapter.cs:124`, F13), which clients read as a dead session.

**Failed contract (ADR-064).** The add-in does not know contracts, so this is not an operation error and has no `effect` of its own. The core ends the job with `PROPOSED_FEATURE_VERIFICATION_FAILED`, a placeholder until roadmap A0, with `details.node` and `details.checks`.

**Ledger (owner decision, 2026-11-05; rule in 8.7).** Any operation whose `effect` is `applied` or `unknown` is recorded with its error, so a repeat answers `DUPLICATE_OPERATION` with the original error and never runs again. `session.completed_operations` keeps failures out of `operation_ids` and lists them in `failed_operations`, so crash recovery cannot read one as a success. Jobs already never resend, so this closes a gap in the protective layer and changes no job's normal path.

## 8.9.6 Execution evidence

One file per `plan` job, `jobs/<job_id>/evidence.json`, written once before the final state is reported, and retained with the job (13.2.4). It is built by a pure function:

```python
def build_evidence(
    plan, journal, results, observations, checks, environment
) -> ExecutionEvidence: ...
```

The `parts/` record gains `feature_ids` (already in `part_result`) and `measured`, so reconciliation outlives job retention. `part_result` stays as the summary `get_execution_status` returns. A new optional `evidence_ref` links to the full record.

**Illustrative record: the plate, with the middle shortened.**

```json
{
  "evidence_schema_version": "0.1",
  "job_id": "job_01J...",
  "graph": "part:plate_4h@1",
  "plan_hash": "sha256:3f...",
  "recovered": false,
  "environment": {
    "solidworks": { "version": "2025", "service_pack": "SP0.0", "ui_language": "zh-CN" },
    "addin_version": "0.1.0",
    "protocol": "0.1",
    "profile_hash": "sha256:a1...",
    "template": { "path": "D:/templates/ISO-mm.prtdot", "sha256": "9c..." }
  },
  "outcome": {
    "job_state": "COMMITTED",
    "execution_status": "succeeded",
    "rebuild_status": "ok",
    "verification_status": "passed"
  },
  "operations": [
    {
      "plan_op": "op_extrude_base",
      "operation_id": "job_01J...:3",
      "op": "feature.create",
      "source": "extrude_base",
      "execution_status": "succeeded",
      "effect": "applied",
      "native": { "feature_id": "f79", "native_id": "79", "native_type": "Extrusion", "status": "ok" },
      "postconditions": [
        { "name": "feature_exists", "status": "passed" },
        { "name": "feature_status_ok", "status": "passed" }
      ],
      "error": null
    }
  ],
  "observations": [
    {
      "stage": "in_session",
      "instance_id": "i_01J...",
      "read_only": false,
      "dirty": false,
      "completeness": { "bodies": "present", "cylinders": "present", "features": "present", "mass": "present" },
      "measured": { "solid_body_count": 1, "volume_m3": 5.798938e-05, "bbox_m": { "min": [-0.05, -0.03, 0], "max": [0.05, 0.03, 0.01] } }
    },
    { "stage": "reopened", "instance_id": "i_01K...", "read_only": true, "dirty": false, "completeness": {}, "measured": {} }
  ],
  "checks": [
    {
      "check": "volume",
      "stage": "reopened",
      "requirement": "Part volume equals the IR's",
      "source": ["extrude_base", "cut_holes"],
      "expected": 57989.38,
      "measured": 57989.38,
      "unit": "mm3",
      "tolerance": { "kind": "relative", "value": 0.0001 },
      "method": "IMassProperty, system units",
      "status": "passed"
    }
  ],
  "warnings": [],
  "artifact": { "path": "D:/parts/plate.SLDPRT", "fingerprint": "sha256:77...", "published": true },
  "failed_artifact": null
}
```

**Status values and rules.**

| Field | Values | Rule |
| --- | --- | --- |
| Operation `execution_status` | `not_attempted`, `succeeded`, `failed`, `cancelled`, `unknown` | `unknown` when sent without an answer (13.2.3) |
| Outcome `execution_status` | Same values | `succeeded` only if every planned operation succeeded |
| `rebuild_status` | `ok`, `errors`, `not_evaluated` | From the last `part.measure` of the stage that counted |
| Check and postcondition `status` | `passed`, `failed`, `warning`, `not_applicable`, `not_evaluated` | `not_evaluated` and `not_applicable` need a `reason`. `not_evaluated` reasons: `not_executed`, `unsupported`, `missing_data`, `malformed_data`. Only the IR can make a check `not_applicable`, never the backend (ADR-064) |
| Outcome `failure_class` | `compilation`, `execution`, `feature_verification`, `final_verification`, or absent on success | The stage that ended the job (ADR-064) |
| Operation `blocked_by` | Plan-local ID | On a `not_attempted` operation, the failed operation it depends on, from `depends_on` |
| Outcome `verification_status` | `passed`, `failed`, `not_evaluated` | `failed` if any failed or, in the MVP, is a `warning` (ADR-064, K22), else `not_evaluated` if any required check is, else `passed`. `not_applicable` is ignored. **`passed` requires at least one check for each 10.2.1 row and both observation stages** |
| `completeness` value | `present`, `empty`, `unavailable`, `unsupported` | Missing means `unavailable`. `empty` is never evidence of success by itself (F2) |

A job reaches COMMITTED only when `execution_status` is `succeeded`, `rebuild_status` is `ok` and `verification_status` is `passed`. A required check that is `not_evaluated` ends the job FAILED.

**After a crash,** recovery writes the record from the journal alone, with `recovered: true`. Operations with no result are `unknown`, and verification is `not_evaluated`. It never invents a result.

**Privacy.** The record holds measurements, IDs and paths, but no sketch or face geometry dump. The `measured` values are the same quantities `part_result` already stores. Nothing here goes to logs (G3).

**Tolerances** are those of 10.2.1, recorded per check. Floats are never compared for exact equality, apart from counts.

## 8.9.7 Capabilities

`HelloResult` keeps its shape. Only the contents of `capabilities`, already an array of strings, gain structure, so no schema change is needed. Names are matched as exact strings:

| Pattern | Meaning | Example |
| --- | --- | --- |
| `<command>` | A read or batch command | `ops.apply`, `part.measure`, `features.read` |
| `op:<op>:<variant>` | One variant of an operation | `op:feature.create:extrude`, `op:sketch.create:arc`, `op:sketch.create:relations` |
| `api.<name>` | An API member newer than the oldest supported version (ADR-045) | `api.annotation_display_data_v2` |

- **Lowering checks the variant** as well as the operation, so a missing feature fails at compile time with `BACKEND_CAPABILITY_MISSING`, as 6.6 requires.
- **`operations`** remains the list of `{op, schema_version}`.
- **`solidworks`** is read, never defaulted. A value that cannot be read fails `ConnectToSW`'s version check, and is never replaced by a guess (F3). ? `ISldWorks.GetBuildNumbers2` may give a more precise service pack than `RevisionNumber`, and resolves the SP0.0 versus SP0.1 disagreement in the records.
- **Router and table.** `session.hello` is built from the registered handlers and `CapabilityTable`, so an operation cannot be listed without a handler, or the reverse (F24).

```csharp
public sealed class CapabilityTable
{
    // Pure and CAD-free: unit-tested with any version.
    public static CapabilityTable For(SolidWorksVersion running);
    public VersionSupport Support { get; }          // Supported, NewerServicePack, Unsupported (ADR-045)
    public IReadOnlyCollection<string> Names { get; }
    public bool Has(string capability);
}
```

## 8.9.8 Add-in interfaces

These are add-in internals, shown as the representative shape. They may change without touching the compiler.

**In `ExecutionServer.Core/Dispatch` (CAD-free).**

```csharp
/// <summary>One operation. Runs on the UI thread; returns plain data; never retains COM objects.</summary>
public interface IOperationHandler
{
    string Op { get; }
    string SchemaVersion { get; }
    IReadOnlyList<string> Variants { get; }

    /// <summary>Throws IpcException with a catalogued code and details.effect on failure.</summary>
    JToken Execute(OperationRequest request);
}

/// <summary>A read-back command, such as part.measure or features.read. Must not change the document.</summary>
public interface IReadCommandHandler
{
    string Method { get; }
    string RequiredCapability { get; }
    JToken Read(JObject parameters, CommandContext context);
}

public sealed class CommandContext
{
    public string? JobId { get; }
    public string? RequestId { get; }
    public CancellationToken Cancellation { get; }
}

public sealed class OperationRequest
{
    public string Document { get; }       // Full path. Bound by the job, never a symbol
    public string OperationId { get; }
    public string Op { get; }
    public JObject Parameters { get; }
    public CommandContext Context { get; }
}

public sealed class OperationRouter : ICommandHandler
{
    public void Register(IOperationHandler handler);
    public void Register(IReadCommandHandler handler);
    public IReadOnlyList<OperationInfo> Operations { get; }   // Feeds session.hello
    // Unknown op: BACKEND_CAPABILITY_MISSING, never recorded in the ledger.
}
```

`ICommandHandler` today has `Snapshot` and `Execute`. It gains `JToken Read(string method, JObject parameters, CommandContext context)`, routed the same way, and `Snapshot` is kept until the freeze lifts. This is compatible with MVP Task 7a's `OperationRouter`.

**Translators, in `ExecutionServer.Core/Parts` (CAD-free).**

```csharp
public sealed class ExtrudeCall
{
    public bool IsCut { get; }
    public EndConditionKind EndCondition { get; }  // This project's enum, not swEndConditions_e
    public double DepthM { get; }
    public bool ReverseDirection { get; }          // Blind cut: true (spike answer 4)
}

public static class FeatureTranslator
{
    /// <summary>Pure. Converts units and applies direction and default rules.</summary>
    public static ExtrudeCall Translate(FeatureCreateParams p);
}
```

Records may replace these classes once an `IsExternalInit` polyfill exists on net48. That is a code style choice, not a contract.

**Native helpers, in `ExecutionServer.Adapters/Native` (implementation-specific, no interface).**

```csharp
/// <summary>Owns temporary COM objects for one scope (G1, ADR-059).</summary>
public sealed class ComScope : IDisposable
{
    public T Own<T>(T comObject) where T : class;  // Enumerators, faces, edges, surfaces, selection data
    public void Dispose();                         // Marshal.ReleaseComObject in reverse order; never FinalRelease
}

public sealed class DocumentLocator
{
    /// <summary>GetOpenDocumentByName by full path ✔. Never ActiveDoc. Throws FILE_NOT_FOUND. Not retained.</summary>
    public IModelDoc2 Require(string fullPath);
}

public sealed class SketchEditScope : IDisposable { /* AddToDB, inference; always leaves sketch mode */ }
public sealed class SelectionScope : IDisposable { /* Clears on entry and exit, owned documents only */ }
```

`IModelDoc2`, `ISldWorks` and manager objects are not put in `ComScope` (ADR-059).

**A handler, in `ExecutionServer.Adapters/Parts`.**

```csharp
public sealed class FeatureCreateHandler : IOperationHandler
{
    public string Op => "feature.create";
    public string SchemaVersion => "0.1";
    public IReadOnlyList<string> Variants { get; } = new[] { "extrude", "cut_extrude" };

    public JToken Execute(OperationRequest request)
    {
        var parameters = request.Parameters.ToObject<FeatureCreateParams>()
            ?? throw new IpcException(ErrorCodes.IR_SCHEMA_INVALID, "Invalid params for feature.create");
        var call = FeatureTranslator.Translate(parameters);          // Stage 2: pure

        var document = _documents.Require(request.Document);
        using var com = new ComScope();
        using var selection = new SelectionScope(document);

        var profile = _features.RequireSketch(document, parameters.Profile);
        var feature = com.Own(_native.Extrude(document, profile, call));  // Stage 3: the one positional call

        if (feature is null)
        {
            throw BackendErrors.FeatureNotCreated(document, parameters.NodeId);
        }

        return FeatureResult.ReadFrom(feature);                      // Stage 4: observed
    }
}
```

**Read command in Python's terms.** The core converts SI at the boundary (8.7), so C# observers perform no unit conversion.

## 8.9.9 Reconciliation contract

```python
class DriftKind(StrEnum):
    MISSING_FEATURE = "missing_feature"
    UNEXPECTED_FEATURE = "unexpected_feature"
    STATUS_CHANGED = "status_changed"  # Suppressed, failed, rolled back
    TYPE_CHANGED = "type_changed"
    PARAMETER_CHANGED = "parameter_changed"
    ORDER_CHANGED = "order_changed"
    GEOMETRY_CHANGED = "geometry_changed"
    FINGERPRINT_CHANGED = "fingerprint_changed"  # File differs; contents not yet read
    NOT_COMPARABLE = "not_comparable"  # Unrecognized type or unavailable data


@dataclass(frozen=True, slots=True)
class Drift:
    kind: DriftKind
    node: str | None  # IR node, when bound
    feature_id: str | None  # Native, when present
    expected: JsonValue
    actual: JsonValue
    method: str


def reconcile(graph, bindings, read_graph, measured, expected, tolerances) -> DriftReport: ...
```

Pure, in `cad-verification`. `DriftReport.state` is one of `in_sync`, `diverged`, `not_comparable`. `in_sync` requires every comparison to have run, so `NOT_COMPARABLE` prevents it. Limits are 8.8.9.

## 8.9.10 Test contract

| Level | Runs where | Covers | Must show |
| --- | --- | --- | --- |
| **Unit** | Hosted CI, no SOLIDWORKS | Translators, router, ownership, capability table, version parsing, error rules, `build_evidence`, `reconcile`, `expected_geometry`, `compare` | Blind cut direction per plane; `ParseRevision` for real revision strings; an unknown operation is an error; `not_evaluated` never becomes `passed`; drift kinds from fixtures |
| **Contract** | Hosted CI | Schema fixtures, transcripts (15.5), a fake `IOperationHandler` through `IpcSession` | Both languages agree; `details.effect` present; R1 by masked transcript comparison |
| **Integration** | Live: a throwaway SOLIDWORKS instance, never the owner's working session | Document lifecycle, each handler, read-back, events, settings restore, COM leak test, error mapping with real failures | Each row of 8.9.3 and 8.9.5 is exercised, and the suite reports which ones ran (15.6) |
| **Verification** | Live | Real models measured against IR values | See below |

**Verification cases.** Each feature ships with these, and each has a seeded defect, so the checks are proven to fail. A verification test with no seeded failure proves nothing.

| Check | Tolerance | Seeded defect |
| --- | --- | --- |
| Feature exists and type matches, by `feature_id` | Exact | Extra sketch or feature; missing cut |
| Extrude depth | Through bbox ±0.01 mm, and volume | Plan depth 9 mm, graph 10 mm |
| Solid body count | Exact | Cut that splits the body |
| Bounding box | ±0.01 mm per axis | Moved profile |
| Volume, surface area | ±0.01% | Missing hole |
| Center of mass | ±0.01 mm per axis | Asymmetric hole |
| Cylinders | Axis position and radius ±0.01 mm; direction parallel | Moved holes with the same volume and box |
| Rebuild | No errors | Feature forced into an error state, if a repeatable way exists |
| Failed or suppressed features | None unexpected | Suppressed feature |
| Save and reopen | All the above on a new `instance_id`, `dirty` false | File replaced while closed (spike answer 12) |

Each check in a per-operation contract (10.2.2) also has a seeded failure, offline, against a recorded observation. Tolerances come from 10.2.1. Curved bodies need K12 before any curved feature ships. Parts whose expected values cannot be computed exactly need K16.

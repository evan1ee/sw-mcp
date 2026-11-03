# Shared IR Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the shared IR core (§3.4) and the error catalogue (ADR-037) as JSON Schemas plus pure Python in `cad-ir`, so every later module schema and validator builds on one tested base.

**Architecture:** Contracts live in `schemas/common/` and `schemas/bundle/` (ADR-035, §3.4.8). `cad_ir.core` holds pure functions: identifier checks, typed reference parsers, quantization, canonical JSON and hashes, derived IDs, validation issues and schema validation. A generator script embeds the schemas and the error codes into `cad_ir/generated/` so the pure package needs no file I/O. `cad_ir.bundle` validates the bundle manifest.

**Tech Stack:** Python 3.13, uv workspace, `jsonschema` (Draft 2020-12), `rfc8785` (RFC 8785 serialization; new dependency, justified below), pytest, pyright strict, ruff, import-linter.

**Spec:** `docs/architecture/shared-ir-core.md` (§3.4.1–3.4.8), `docs/adr/ADR-035`, `ADR-037`, `ADR-042`, `docs/development/testing-strategy.md` §15.5, guideline G2.

## Global Constraints

- `cad-ir` is pure: no file I/O, no clock, no globals that change, no network, no CAD imports; it imports nothing else of ours (G2, enforced by `lint-imports`).
- Never hand-edit anything under a `generated/` directory or `uv.lock` (a hook blocks it). Add dependencies with `uv add --package cad-ir <name>`.
- Python 3.13, pyright **strict** with 0 errors, ruff check + ruff format clean, line length 100.
- Data types are immutable: `@dataclass(frozen=True, slots=True)`, tuples not lists in fields; functions return new values and never mutate inputs.
- Regexes: match with `re.fullmatch` (never `re.match` + `$`, which lets a trailing `\n` through). Schema patterns are the same text wrapped in `^…$` (§3.4.8).
- Unit tests live in `packages/cad-ir/tests/`; schema contract tests in `tests/contract/`; fixtures in `tests/fixtures/schemas/<name>/`.
- `rfc8785` (Trail of Bits, pure Python, Apache-2.0): RFC 8785 number formatting (ECMAScript shortest round-trip, exponent rules) is easy to get subtly wrong. A tested library is safer than a hand-rolled serializer. No other new dependencies. `jsonschema` is added explicitly to `cad-ir` (it is already in the lock through `mcp`).
- Every task ends with the full suite green: `uv run ruff check && uv run ruff format --check && uv run pyright && uv run lint-imports && uv run pytest`.

## Review Focus

1. **Non-finite and disguised numbers.** `json.loads` accepts `NaN`/`Infinity`, and Python's `True` is an `int`. Both must be rejected with a pointer (§3.4.3). Tests: Task 2 `test_require_finite_rejects`, Task 6 `test_validate_rejects_nan_with_pointer`.
2. **Near-miss reference strings.** Inputs such as `part:x@0`, `part:x@01`, `part:x@`, `bore_1\n`, ` part:x` and `PART:x` must be rejected, never normalized. Test: Task 1 `test_parse_document_ref_rejects`.
3. **Display names used as IDs.** `前视基准面`, `Boss-Extrude1` and other non-ASCII or display names are not item IDs (§3.4.1). Text in NFD form must normalize to NFC before it is compared or hashed. Tests: Task 1 `test_item_id_rejects_display_names`, Task 2 `test_normalize_text_nfc`.
4. **JSON Pointer escaping.** Keys containing `/` or `~` must yield RFC 6901 pointers (`~1`, `~0`). Test: Task 6 `test_json_pointer_escapes`.
5. **Half-quantum and negative-zero values.** Quantization must be deterministic: half-even on the decimal repr, and `-0.0` comes out as `0.0`. Test: Task 2 `test_quantize_half_even_and_negative_zero`.

---

### Task 1: Identifiers and typed references

**Files:**
- Create: `packages/cad-ir/src/cad_ir/core/ids.py`, `packages/cad-ir/src/cad_ir/core/refs.py`
- Test: `packages/cad-ir/tests/test_ids.py`, `packages/cad-ir/tests/test_refs.py`

**Interfaces:**
- Produces (`ids.py`):
  - `type ModuleKey = Literal["part", "assembly", "design_intent", "drawing_intent", "drawing_layout"]`
  - `MODULE_KEYS: tuple[ModuleKey, ...]`, in that order
  - Pattern strings, without anchors:
    - `DOCUMENT_ID_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"`
    - `ITEM_ID_PATTERN = r"[a-z][a-z0-9_]{0,63}"`
    - `DATUM_LABEL_PATTERN = r"[A-HJ-NPR-Z]{1,2}"`
    - `REVISION_PATTERN = r"[1-9][0-9]*"`
  - `is_module_key(s: str) -> TypeGuard[ModuleKey]`, `is_document_id(s: str) -> bool`, `is_item_id(s: str) -> bool`, `is_datum_label(s: str) -> bool`
- Produces (`refs.py`), all frozen dataclasses whose `__str__` gives back the exact input form:
  - `DocumentRef(module: ModuleKey, document_id: str, revision: int | None = None)`
  - `ItemRef(document: DocumentRef, item_id: str)`
  - `LocalRef(item_id: str)`
  - `IntentItemRef(kind: Literal["scheme", "critical", "gdt", "datum", "finish"], id: str)`. The id is a datum label when the kind is `datum`, otherwise an item ID.
  - `ParamRef(feature_id: str, parameter: str)` and `FeatureRoleRef(feature_id: str, role: str)`. Both parts follow the item-ID grammar.
  - `StoredGeometryRef(reference_id: str)` for `geo:<item-id grammar>`
  - `StandardGeometryRef(name: Literal["plane:front", "plane:top", "plane:right", "origin"])`
  - `DatumGeometryRef(label: str)` for `datum:<label>`
  - `type GeometryRef = FeatureRoleRef | StoredGeometryRef | StandardGeometryRef | DatumGeometryRef`
  - `SolidWorksDimRef(full_name: str)`: `swdim:` followed by a non-empty name with no control characters
  - `class ReferenceSyntaxError(ValueError)` with attributes `ref: str` and `expected: str`, where `expected` is the form from the §3.4.2 table, for example `"<module>:<document_id>[@<revision>]"`
  - One parser per type, each raising `ReferenceSyntaxError`: `parse_document_ref`, `parse_item_ref`, `parse_local_ref`, `parse_intent_item_ref`, `parse_param_ref`, `parse_geometry_ref`, `parse_solidworks_dim_ref` (each `(s: str) -> <Type>`)

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.parametrize("s", ["bore_1", "a", "a" * 64])
def test_item_id_accepts(s):
    assert is_item_id(s)


@pytest.mark.parametrize(
    "s", ["Bore_1", "1bore", "a" * 65, "bore-1", "bore_1\n", "", "前视基准面", "Boss-Extrude1"]
)
def test_item_id_rejects_display_names(s):
    assert not is_item_id(s)


@pytest.mark.parametrize("s", ["A", "AB", "Z"])  # accepted datum labels
@pytest.mark.parametrize("s", ["I", "O", "Q", "AI", "a", "ABC", ""])  # rejected (separate test)
# document ID: "BRK-001-DI", "x", "a.b_c-d" ok; "-x", ".x", "a"*129, "a b" rejected

def test_parse_document_ref_roundtrip():
    r = parse_document_ref("part:bracket@4")
    assert r == DocumentRef("part", "bracket", 4) and str(r) == "part:bracket@4"
    assert parse_document_ref("drawing_intent:BRK-001-DI").revision is None


@pytest.mark.parametrize(
    "s",
    [
        "part:x@0",
        "part:x@01",
        "part:x@",
        "part:x@-1",
        " part:x",
        "PART:x",
        "foo:x",
        "part:",
        "part:x/bore_1",
        "part:x\n",
    ],
)
def test_parse_document_ref_rejects(s):
    with pytest.raises(ReferenceSyntaxError) as e:
        parse_document_ref(s)
    assert e.value.ref == s and e.value.expected


def test_parse_item_ref():
    assert parse_item_ref("design_intent:BRK-001-DES@2/r1") == ItemRef(
        DocumentRef("design_intent", "BRK-001-DES", 2), "r1"
    )


def test_parse_intent_item_ref():
    assert parse_intent_item_ref("datum:A") == IntentItemRef("datum", "A")
    assert (
        parse_intent_item_ref("scheme:ds_bore_1_diameter_b41219").id == "ds_bore_1_diameter_b41219"
    )
    # rejected: "datum:I", "datum:a", "scheme:A", "tolerance:x"


def test_parse_geometry_ref_variants():
    assert parse_geometry_ref("bore_1.cylindrical_face") == FeatureRoleRef(
        "bore_1", "cylindrical_face"
    )
    assert parse_geometry_ref("geo:g7f3a21c0") == StoredGeometryRef("g7f3a21c0")
    assert parse_geometry_ref("plane:right") == StandardGeometryRef("plane:right")
    assert parse_geometry_ref("origin") == StandardGeometryRef("origin")
    assert parse_geometry_ref("datum:A") == DatumGeometryRef("A")
    # rejected: "plane:left", "bore_1", "bore_1.a.b", "part:x"


def test_parsers_reject_other_kinds():  # the field type decides (§3.4.2)
    for parse, s in [
        (parse_param_ref, "part:x"),
        (parse_local_ref, "bore_1.diameter"),
        (parse_document_ref, "part:x/r1"),
        (parse_solidworks_dim_ref, "swdim:"),
    ]:
        with pytest.raises(ReferenceSyntaxError):
            parse(s)


# every parsed value: str(parse_x(s)) == s  (parametrized round-trip over all valid examples above)
```

- [ ] **Step 2: Run** `uv run pytest packages/cad-ir/tests/test_ids.py packages/cad-ir/tests/test_refs.py -q`. Expected: FAIL (import error).
- [ ] **Step 3: Implement** `ids.py` and `refs.py`. Build each parser's compiled regex from the `ids.py` pattern constants and use `fullmatch`. Use one private helper that raises `ReferenceSyntaxError(ref, expected)`.
- [ ] **Step 4: Run** the same command. Expected: PASS. Then run the full suite from the Global Constraints.

### Task 2: Numbers, quanta and text

**Files:**
- Create: `packages/cad-ir/src/cad_ir/core/numbers.py`, `packages/cad-ir/src/cad_ir/core/text.py`
- Test: `packages/cad-ir/tests/test_numbers.py`, `packages/cad-ir/tests/test_text.py`

**Interfaces:**
- Produces:
  - `type QuantityKind = Literal["length", "angle", "ratio", "count"]` and `type LengthUnit = Literal["mm", "in"]`
  - `quantum(kind: QuantityKind, units: LengthUnit = "mm") -> Decimal`. The values are length `1e-6` (mm) or `1e-7` (in), angle `1e-6`, ratio `1e-9`. `count` raises `ValueError`.
  - `require_finite(value: object) -> int | float`. Raises `ValueError` for `bool`, `str`, `NaN`, `±inf` and non-numbers.
  - `quantize(value: int | float, kind: QuantityKind, units: LengthUnit = "mm") -> int | float`. For `count`, the value must be an `int` and is returned unchanged. Otherwise the result is a `float`, computed as `float(Decimal(repr(float(value))).quantize(quantum, ROUND_HALF_EVEN))`, with `-0.0` mapped to `0.0`.
  - `values_equal(a: int | float, b: int | float, kind: QuantityKind, units: LengthUnit = "mm") -> bool`. Uses `abs(Decimal(repr(a)) - Decimal(repr(b))) <= quantum`; `count` compares exactly.
  - `normalize_text(s: str) -> str`, which applies Unicode NFC.

- [ ] **Step 1: Write failing tests**

```python
def test_quantize_removes_float_noise():
    assert quantize(0.1 + 0.2, "length") == 0.3


def test_quantize_half_even_and_negative_zero():
    assert quantize(1.0000005, "length") == 1.0 and quantize(1.0000015, "length") == 1.000002
    r = quantize(-0.0000001, "length")
    assert r == 0.0 and math.copysign(1, r) == 1


def test_quantize_inch_and_ratio():
    assert (
        quantize(1.00000004, "length", "in") == 1.0
        and quantize(0.1234567891, "ratio") == 0.123456789
    )


def test_values_equal_quanta():
    assert values_equal(10.0, 10.000001, "length") and not values_equal(10.0, 10.0000011, "length")
    assert values_equal(1.0, 1.0000001, "length", "in") and not values_equal(
        1.0, 1.0000002, "length", "in"
    )
    assert values_equal(90.0, 90.000001, "angle") and not values_equal(3, 4, "count")


@pytest.mark.parametrize("v", [math.nan, math.inf, -math.inf, True, "1.0", None])
def test_require_finite_rejects(v):
    with pytest.raises(ValueError):
        require_finite(v)


def test_count_must_be_int():
    with pytest.raises(ValueError):
        quantize(2.5, "count")


def test_normalize_text_nfc():
    assert normalize_text("é") == "é"
```

- [ ] **Step 2: Run** `uv run pytest packages/cad-ir/tests/test_numbers.py packages/cad-ir/tests/test_text.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** as specified above.
- [ ] **Step 4: Run** the same command. Expected: PASS. Then run the full suite.

### Task 3: Canonical form, content hash and derived IDs

**Files:**
- Create: `packages/cad-ir/src/cad_ir/core/json_types.py`, `pointer.py`, `canonical.py`, `derived_ids.py` (all in `packages/cad-ir/src/cad_ir/core/`)
- Modify: `packages/cad-ir/pyproject.toml`, through `uv add --package cad-ir rfc8785 jsonschema`
- Test: `packages/cad-ir/tests/test_pointer.py`, `test_canonical.py`, `test_derived_ids.py`

**Interfaces:**
- Consumes: `quantize`, `QuantityKind` and `LengthUnit` (Task 2)
- Produces:
  - `type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]` (in `json_types.py`)
  - `json_pointer(*tokens: str | int) -> str`. Implements RFC 6901: `~` becomes `~0` and `/` becomes `~1`; no tokens gives `""`.
  - `class CanonicalizationError(ValueError)`
  - `canonical_bytes(value: JsonValue) -> bytes`. Uses `rfc8785.dumps` and wraps its errors in `CanonicalizationError`; non-finite floats are rejected.
  - `content_hash(value: JsonValue) -> str`. Returns `"sha256:" + sha256(canonical_bytes(value)).hexdigest()`.
  - `canonicalize(value: JsonValue, *, quantity_at: Callable[[str], tuple[QuantityKind, LengthUnit] | None] = lambda _: None, unordered_at: Callable[[str], bool] = lambda _: False) -> JsonValue`
    - Returns a new value and never mutates the input.
    - Each callback receives the JSON Pointer of the node.
    - Quantizes numbers where `quantity_at` returns a kind.
    - Sorts an array by the `canonical_bytes` of its (already canonicalized) elements where `unordered_at` is true.
    - `bool` is never treated as a number.
    - The schema-driven callbacks come in a later milestone. This task only provides the walk.
  - `scheme_entry_id(kind: str, covers: Sequence[str], measures: Mapping[str, JsonValue] | None, source: str, *, taken: Mapping[str, str] | None = None) -> str` (§3.4.4 Derived IDs). The steps:
    1. Hash input: `{"kind", "covers": sorted(covers), "source"}`, plus `"measures"` only when it is not `None`.
    2. Slug: `sorted(covers)[0]` if `covers` is non-empty, else `measures["to"]`. Every character outside `[a-z0-9_]` becomes `_`, then cut to 40 characters.
    3. Without a slug, raise `ValueError`.
    4. `taken` maps existing ID → its content hash. If `ds_<slug>_<hash6>` is taken by a different hash, try 8, then 12 hex characters, then raise `ValueError`.

- [ ] **Step 1: Write failing tests**

```python
def test_json_pointer_escapes(): assert json_pointer("nodes", "a/b", "m~n", 0) == "/nodes/a~1b/m~0n/0"; assert json_pointer() == ""
def test_canonical_bytes_rfc8785():
    assert canonical_bytes({"b": 1, "a": [1.0, "x"]}) == b'{"a":[1,"x"],"b":1}'
    assert canonical_bytes([1e21, 1e-7, -0.0]) == b"[1e+21,1e-7,0]"
def test_canonical_bytes_rejects_nan():
    with pytest.raises(CanonicalizationError): canonical_bytes({"x": math.nan})
def test_content_hash(): assert content_hash({}) == "sha256:" + hashlib.sha256(b"{}").hexdigest()
def test_canonicalize_quantizes_and_sorts_without_mutation():
    doc = {"covers": ["b", "a"], "x": 0.1000004, "seq": [2, 1], "flag": True}
    out = canonicalize(doc, quantity_at=lambda p: ("length", "mm") if p == "/x" else None,
                       unordered_at=lambda p: p == "/covers")
    assert out == {"covers": ["a", "b"], "x": 0.1, "seq": [2, 1], "flag": True}
    assert doc["covers"] == ["b", "a"]
def test_scheme_entry_id_shape_and_order_independence():
    a = scheme_entry_id("diameter", ["bore_1.diameter"], None, "model")
    assert re.fullmatch(r"ds_bore_1_diameter_[0-9a-f]{6}", a)
    assert scheme_entry_id("x", ["b.c", "a.b"], None, "s") == scheme_entry_id("x", ["a.b", "b.c"], None, "s")
def test_scheme_entry_id_uses_measures_to_and_cuts_slug():
    i = scheme_entry_id("distance", [], {"to": "Plane.Right" * 10}, "model")
    assert re.fullmatch(r"ds_[a-z0-9_]{40}_[0-9a-f]{6}", i)
def test_scheme_entry_id_grows_on_collision():
    first = scheme_entry_id("d", ["a.b"], None, "s")
    grown = scheme_entry_id("d", ["a.b"], None, "s", taken={first: "sha256:other"})
    assert re.fullmatch(r"ds_a_b_[0-9a-f]{8}", grown) and grown.startswith(first)
    assert scheme_entry_id("d", ["a.b"], None, "s", taken={first: <its own hash>}) == first  # same entry: no growth
def test_scheme_entry_id_needs_slug():
    with pytest.raises(ValueError): scheme_entry_id("d", [], None, "s")
```

- [ ] **Step 2: Run** `uv run pytest packages/cad-ir/tests/test_pointer.py packages/cad-ir/tests/test_canonical.py packages/cad-ir/tests/test_derived_ids.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** For the `<its own hash>` test, compute the hash with a small private helper the test may import (`_entry_hash`). `rfc8785` may not ship type stubs; if pyright strict complains, add a minimal typed wrapper in `canonical.py`. Do not loosen the pyright config.
- [ ] **Step 4: Run** the same command. Expected: PASS. Then run the full suite.

### Task 4: Common and bundle schemas, error catalogue, fixture harness

**Files:**
- Create: `schemas/common/v0.json`, `schemas/common/errors.json`, `schemas/bundle/v1.json` (delete the `.gitkeep` in each directory you fill)
- Create: `tests/fixtures/schemas/common/valid/<Def>.json`, `tests/fixtures/schemas/common/invalid/<Def>.json`, `tests/fixtures/schemas/bundle/valid/*.json`, `tests/fixtures/schemas/bundle/invalid/*.json`
- Create: `tests/contract/__init__.py` (empty, only if pytest needs it), `tests/contract/test_schema_fixtures.py`, `tests/contract/test_error_catalogue.py`

**Interfaces:**
- Consumes: the pattern constants from `ids.py` (Task 1)
- Produces:
  - `$id` values `https://sw-mcp.invalid/schemas/common/v0.json`, `…/common/errors.json` and `…/bundle/v1.json`, all with `"$schema": "https://json-schema.org/draft/2020-12/schema"` (§3.4.8)
  - `common/v0.json` `$defs`:
    - Identifiers: `ModuleKey` (enum), `DocumentId`, `ItemId`, `DatumLabel`, `Revision` (integer ≥ 1), `Units` (enum `mm`/`in`), `SchemaVersion` (`^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`), `ContentHash` (`^sha256:[0-9a-f]{64}$`)
    - References: `DocumentRef`, `ItemRef`, `LocalRef`, `IntentItemRef`, `ParamRef`, `GeometryRef` (an `anyOf` of the four forms), `SolidWorksDimRef`. Patterns are built from the `ids.py` constants.
    - Numbers: `Length`, `Angle`, `Ratio` (`"type": "number"`) and `Count` (`"type": "integer", "minimum": 0`), each with `x-quantity`
    - `DocumentHeader`: properties `module`, `id`, `schema_version`, `units`, `revision`, `origin` (enum `built`/`read`); required `module` and `schema_version`. It is not closed, because modules extend it with `allOf`/`$ref` and close themselves with `unevaluatedProperties: false`.
    - `ValidationIssue` (§3.4.7): required `code`, `pointer`, `message`; optional `severity` (enum `error`/`warning`), `expected` (array of strings), `ref`, `patch_op` (integer ≥ 0); `additionalProperties: false`
    - `Error` (ADR-037): required `code`, `message`, `retryable` (enum `never`/`after_fix`/`safe`); optional `details` (object); `additionalProperties: false`
    - `Envelope`: required `ok` (boolean), `data`, `error` (`Error` or null), `ids` (object with required `request_id` and optional `execution_id`, `report_id`)
    - `code` in `ValidationIssue` and `Error` is `$ref: "errors.json"`
  - `errors.json`: `"type": "string"` and a `oneOf` with one branch per code: `{"const", "description", "x-retryable"}`. The codes are exactly the 38 in ADR-037, in table order. `DUPLICATE_OPERATION` is kept as written: codes are never renamed.

    Default `x-retryable` values:

    | Value | Codes |
    | --- | --- |
    | `safe` | `BACKEND_BUSY`, `BACKEND_UI_BLOCKED`, `BACKEND_LOST`, `STORE_LOCKED`, `EXEC_TIMEOUT`, `EXEC_INTERRUPTED` |
    | `never` | every `AUTH_*` code, every code ending in `_UNSUPPORTED`, `COMPILE_UNSUPPORTED_FEATURE`, `BACKEND_CAPABILITY_MISSING`, `BACKEND_READ_ONLY`, `EXEC_NOT_FOUND`, `EXEC_CANCELLED`, `EXEC_INTERRUPTED_BY_USER`, `DUPLICATE_OPERATION`, `STORE_CORRUPT`, `DRAWING_UNSUPPORTED_PART` |
    | `after_fix` | everything else |
  - `bundle/v1.json`: closed object. `bundle_schema_version` matches `^1\.(0|[1-9][0-9]*)$`. `modules` is an array of `../common/v0.json#/$defs/DocumentRef` with `minItems: 1`, `uniqueItems: true` and `x-unordered: true`.
  - Fixture format: `tests/fixtures/schemas/common/{valid,invalid}/<DefName>.json` is a JSON array of instances checked against `common/v0.json#/$defs/<DefName>`. `bundle/{valid,invalid}/<case>.json` is one document per file.

- [ ] **Step 1: Write the harness test first.** `tests/contract/test_schema_fixtures.py` loads every file under `schemas/` into a `referencing.Registry` keyed by `$id`. It parametrizes over each fixture and asserts that `Draft202012Validator` (with `format_checker`) accepts every valid instance and rejects every invalid one. Add `test_every_schema_is_valid_2020_12` (`Draft202012Validator.check_schema`) and `test_id_patterns_match_python`: each of `DocumentId`, `ItemId` and `DatumLabel` in `common/v0.json` must equal `"^" + <ids.py constant> + "$"`. Fixtures must include:
  - the bundle example from §3.4.5, which must be valid
  - in `invalid/`: `I`, `O` and `Q` as datum labels; `part:x@0`; `bore_1\n`; `前视基准面` as an `ItemId`; `NaN`-free numeric strings such as `"1.0"` as a `Length`; a bundle with an extra property, with empty `modules`, and with module `foo:x`
- [ ] **Step 2: Write** `tests/contract/test_error_catalogue.py`:
  - `test_catalogue_matches_adr_037`: the set of `const` values equals the 38 codes, with the list written out in the test.
  - `test_docs_mention_only_catalogued_codes`: scan `docs/**/*.md` with `\b(IR|REV|REF|COMPILE|EXEC|BACKEND|DRAWING|AUTH|STORE|CONFIG)_[A-Z0-9_]+\b|\bDUPLICATE_OPERATION\b` and assert the matches are a subset of the catalogue.
  - `test_every_code_has_retryable_and_description`.
- [ ] **Step 3: Run** `uv run pytest tests/contract -q`. Expected: FAIL (no schemas).
- [ ] **Step 4: Write** the three schema files and the fixtures.
- [ ] **Step 5: Run** `uv run pytest tests/contract -q`. Expected: PASS. Then run the full suite.

### Task 5: Contract generator and generated constants

**Files:**
- Create: `scripts/generate_contracts.py`, plus generated outputs (written only by the script) `packages/cad-ir/src/cad_ir/generated/__init__.py`, `schemas.py` and `error_codes.py`
- Modify: `.github/workflows/ci.yml` (add the step `uv run python scripts/generate_contracts.py --check` after `uv sync --locked`); `AGENTS.md` §4 Python Verification (add the same command)
- Test: `tests/contract/test_generated_contracts.py`

**Interfaces:**
- Consumes: the schema files (Task 4)
- Produces:
  - `cad_ir.generated.schemas.SCHEMAS: Mapping[str, JsonValue]`: every schema under `schemas/`, keyed by `$id`, as a Python literal (`pprint.pformat(..., sort_dicts=True, width=100)`), wrapped in `types.MappingProxyType`
  - `cad_ir.generated.error_codes`:
    - `class ErrorCode(StrEnum)`, with members named and valued by the code and in catalogue order
    - `type Retryable = Literal["never", "after_fix", "safe"]`
    - `DEFAULT_RETRYABLE: Mapping[ErrorCode, Retryable]`
  - `scripts/generate_contracts.py [--check]`:
    - writes the files with LF endings and a header line `# Generated by scripts/generate_contracts.py from schemas/. Do not edit.`
    - with `--check`, writes nothing, prints the stale paths and exits 1 if any output would differ
    - is deterministic: files are sorted and output does not depend on the OS

- [ ] **Step 1: Write failing tests**: `test_generated_up_to_date` (run the script with `--check` through `subprocess` and expect exit 0), `test_error_code_enum_matches_catalogue`, `test_schemas_keyed_by_id`.
- [ ] **Step 2: Run** `uv run pytest tests/contract/test_generated_contracts.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the script and run `uv run python scripts/generate_contracts.py`. Confirm that pyright and ruff already exclude `**/generated/**`. Export `ErrorCode` from `cad_ir.generated`.
- [ ] **Step 4: Run** the test, then `uv run python scripts/generate_contracts.py --check`. Expected: PASS, exit 0. Then run the full suite.

### Task 6: Validation issues and schema validation

**Files:**
- Create: `packages/cad-ir/src/cad_ir/core/issues.py`, `packages/cad-ir/src/cad_ir/core/schema_validation.py`
- Modify: `packages/cad-ir/src/cad_ir/core/__init__.py`, to re-export the public names of Tasks 1–3 and 6
- Test: `packages/cad-ir/tests/test_issues.py`, `packages/cad-ir/tests/test_schema_validation.py`

**Interfaces:**
- Consumes: `ErrorCode`, `SCHEMAS` (Task 5); `json_pointer`, `JsonValue` (Task 3)
- Produces:
  - `type Severity = Literal["error", "warning"]`
  - `ValidationIssue(code: ErrorCode, pointer: str, message: str, severity: Severity = "error", expected: tuple[str, ...] | None = None, ref: str | None = None, patch_op: int | None = None)`. Method `to_json() -> dict[str, JsonValue]` omits `None` fields and `severity == "error"`; its output must validate against `common/v0.json#/$defs/ValidationIssue`.
  - `MAX_REPORTED_ISSUES = 50`
  - `IssueReport(issues: tuple[ValidationIssue, ...], omitted: int)`, with property `has_errors: bool`
  - `build_report(issues: Iterable[ValidationIssue]) -> IssueReport`. Sorts by `(pointer, code, message)`, keeps the first 50 and sets `omitted` to the number of the rest.
  - `validate_against_schema(instance: JsonValue, schema_id: str) -> tuple[ValidationIssue, ...]`. The steps:
    1. Walk the instance for non-finite floats and report each as `IR_SCHEMA_INVALID` with its pointer and `expected=("finite number",)`.
    2. Run `Draft202012Validator` over the `SCHEMAS` registry and map each error to `IR_SCHEMA_INVALID` with `pointer = json_pointer(*error.absolute_path)` and a one-line message.
    3. Raise `KeyError` for an unknown `schema_id`.
    4. Return the issues in the order `build_report` uses.

- [ ] **Step 1: Write failing tests**
  - `test_build_report_orders_and_caps`: 60 issues in reverse order. The result holds the first 50 by pointer and `omitted == 10`.
  - `test_build_report_deterministic`: the same input gives an equal report.
  - `test_issue_to_json_matches_schema`: validate `to_json()` with `validate_against_schema` against the `ValidationIssue` def's `$id` + `#/$defs/ValidationIssue`.
  - `test_validate_rejects_nan_with_pointer`: `{"bundle_schema_version": "1.0", "modules": [math.nan]}` gives an issue at `/modules/0`.
  - `test_validate_bundle_example_ok`.
  - `test_validate_reports_all_errors`: a bundle with an extra key and a bad ref reports both, sorted.
- [ ] **Step 2: Run** `uv run pytest packages/cad-ir/tests/test_issues.py packages/cad-ir/tests/test_schema_validation.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Build the registry once at import as a module-level constant derived from `SCHEMAS`. That is allowed: it is immutable and does no I/O.
- [ ] **Step 4: Run** the same command. Expected: PASS. Then run the full suite.

### Task 7: Bundle manifest validation

**Files:**
- Create: `packages/cad-ir/src/cad_ir/bundle/manifest.py`; modify `packages/cad-ir/src/cad_ir/bundle/__init__.py`
- Test: `packages/cad-ir/tests/test_bundle_manifest.py`

**Interfaces:**
- Consumes: `validate_against_schema`, `ValidationIssue`, `build_report`, `IssueReport` (Task 6); `parse_document_ref`, `DocumentRef` (Task 1)
- Produces:
  - `BUNDLE_SCHEMA_ID = "https://sw-mcp.invalid/schemas/bundle/v1.json"`
  - `BundleManifest(bundle_schema_version: str, modules: tuple[DocumentRef, ...])`
  - `parse_bundle_manifest(doc: JsonValue) -> BundleManifest | IssueReport`. The steps:
    1. Run schema validation first; if it finds issues, return the report (§3.4.7 stages).
    2. Then apply the semantic rule from §3.4.5: at most one document per module key, except `part`. A second document for the same key is `IR_RULE_VIOLATED` at `/modules/<index of the later one>`, with `ref` set to that string.
    3. Return the manifest only when there are no errors.

    Resolving floating refs needs the store and is out of scope for this task.

- [ ] **Step 1: Write failing tests**
  - `test_spec_example_parses`: the §3.4.5 manifest gives 3 `DocumentRef`s and `revision == 4` for the part.
  - `test_two_drawing_intents_rejected`: `IR_RULE_VIOLATED` at `/modules/1`.
  - `test_multiple_parts_allowed`.
  - `test_schema_errors_stop_before_semantics`: a manifest with an extra key and a duplicate key reports only `IR_SCHEMA_INVALID`.
- [ ] **Step 2: Run** `uv run pytest packages/cad-ir/tests/test_bundle_manifest.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full suite, plus `uv run pytest --cov=packages/cad-ir/src --cov-report=term-missing -q`. Expected: all checks pass and `cad_ir` coverage is ≥ 80%.

## Out of scope (next milestones)

- Schema-driven `quantity_at` / `unordered_at`, which needs the first module schema.
- Pydantic model generation (`datamodel-code-generator`) for module schemas.
- C# type generation (ADR-035).
- IPC schemas (ADR-036).
- Store-backed resolution of floating references.

"""Shapes of a stored drawing report for ``get_drawing_report`` (spec 12.4.5, 12.3 rule 4).

A stored report is read defensively: any structural surprise raises ``CorruptReport``, which the
handler turns into ``STORE_CORRUPT``. Nothing here changes the stored report.
"""

from dataclasses import dataclass
from typing import Final, Literal

from cad_ir.core.json_types import JsonValue

from cad_application.store.codec import Obj
from cad_application.store.records import JobWarning

type Section = Literal["checks", "conflicts", "warnings", "soft_metrics"]

TOP_FAILURES: Final = 5
TOP_FAILURE_ITEMS: Final = 3
_CHECK_FIELDS: Final = ("status", "failure_count", "reasons")


class CorruptReport(Exception):  # noqa: N818 - names the stored report's state, not a failure
    """The stored report is not shaped like a drawing report (11.5.4)."""


@dataclass(frozen=True, slots=True)
class SummaryParts:
    """What the summary needs besides the report itself."""

    report_id: str
    execution_id: str
    path: str
    drawing_id: str
    snapshot_id: str
    job_warnings: tuple[JobWarning, ...]


def _obj(value: JsonValue | None) -> Obj:
    if not isinstance(value, dict):
        raise CorruptReport
    return value


def _list(value: JsonValue | None) -> list[JsonValue]:
    if not isinstance(value, list):
        raise CorruptReport
    return value


def _count(value: JsonValue | None) -> int:
    if type(value) is not int:
        raise CorruptReport
    return value


def _text(value: JsonValue | None) -> str:
    if not isinstance(value, str):
        raise CorruptReport
    return value


def verdict_of(report: JsonValue) -> str:
    return _text(_obj(report).get("verdict"))


def checks_of(report: JsonValue) -> Obj:
    """The report's ``checks``, each entry an object with a status."""
    checks = _obj(_obj(report).get("checks"))
    for entry in checks.values():
        _text(_obj(entry).get("status"))
    return checks


def _short_check(entry: JsonValue) -> JsonValue:
    obj = _obj(entry)
    _count(obj.get("failure_count"))
    _list(obj.get("reasons"))
    return {name: obj[name] for name in _CHECK_FIELDS}


def _top_failure(failure: JsonValue) -> JsonValue:
    obj = _obj(failure)
    ids: list[JsonValue] = [_text(_obj(i).get("id")) for i in _list(obj.get("items"))]
    sheet, code = obj.get("sheet"), obj.get("code")
    return {
        "check": _text(obj.get("check")),
        "sheet": None if sheet is None else _text(sheet),
        "code": None if code is None else _text(code),
        "items": ids[:TOP_FAILURE_ITEMS],
    }


def summary_data(report: JsonValue, parts: SummaryParts, *, full: bool) -> Obj:
    """``detail: "summary"`` (12.4.5); ``full`` adds the whole ``checks``, ``sheets`` and
    ``thresholds``."""
    body = _obj(report)
    checks = checks_of(report)
    failures = _list(body.get("failures"))
    job_warnings: list[JsonValue] = [w.to_json() for w in parts.job_warnings]
    data: Obj = {
        "report_id": parts.report_id,
        "execution_id": parts.execution_id,
        "drawing": {"path": parts.path, "drawing_id": parts.drawing_id},
        "verdict": verdict_of(report),
        "calibration": _obj(body.get("calibration")),
        "checks": checks if full else {n: _short_check(c) for n, c in checks.items()},
        "conflict_count": _count(body.get("conflict_count")),
        "top_failures": [_top_failure(f) for f in failures[:TOP_FAILURES]],
        "warning_count": len(_list(body.get("warnings"))),
        "job_warnings": job_warnings,
        "links": {
            "report": f"cad://reports/{parts.report_id}",
            "snapshot": f"cad://snapshots/{parts.snapshot_id}",
        },
    }
    if full:
        data["sheets"] = _obj(body.get("sheets"))
        data["thresholds"] = _obj(body.get("thresholds"))
    return data


def section_items(report: JsonValue, section: Section) -> Obj | list[JsonValue]:
    """The whole section: an object for ``checks`` and ``soft_metrics``, else a list."""
    body = _obj(report)
    if section == "checks":
        return checks_of(report)
    if section == "soft_metrics":
        return _obj(body.get("sheets"))
    return _list(body.get("failures" if section == "conflicts" else "warnings"))

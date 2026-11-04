"""The G3 log sink: JSON Lines, a daily file, an allow-list of fields."""

import json
from datetime import UTC, datetime
from pathlib import Path

from cad_application.testing.fake_clock import FakeClock
from core_service.jsonl_log import ALLOWED_FIELDS, JsonlEventLog


def _clock() -> FakeClock:
    return FakeClock(datetime(2026, 11, 4, 9, 0, 0, 123000, tzinfo=UTC))


def _lines(tmp_path: Path) -> list[dict[str, object]]:
    (file,) = tmp_path.glob("core-*.jsonl")
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()]


def test_sink_drops_unknown_fields(tmp_path: Path) -> None:
    log = JsonlEventLog(str(tmp_path), "core", _clock())
    log.emit(
        "job.finished",
        "info",
        job_id="job_1",
        state="COMMITTED",
        file_contents="SECRET-BODY",
        token="tok-abc",
        path_hint="C:\\x",
    )
    (line,) = _lines(tmp_path)
    assert set(line) <= ALLOWED_FIELDS
    assert line["job_id"] == "job_1"
    assert line["state"] == "COMMITTED"
    text = next(tmp_path.glob("core-*.jsonl")).read_text(encoding="utf-8")
    assert "SECRET-BODY" not in text
    assert "tok-abc" not in text


def test_sink_writes_one_json_object_per_line(tmp_path: Path) -> None:
    clock = _clock()
    log = JsonlEventLog(str(tmp_path), "core", clock)
    log.emit("a", "info", count=1)
    clock.advance(1)
    log.emit("b", "warning", reason="x")
    lines = _lines(tmp_path)
    assert [line["event"] for line in lines] == ["a", "b"]
    assert lines[0]["ts"] == "2026-11-04T09:00:00.123Z"
    assert lines[0]["level"] == "info"
    assert lines[0]["process"] == "core"
    assert isinstance(lines[0]["pid"], int)


def test_sink_names_file_by_day(tmp_path: Path) -> None:
    clock = _clock()
    log = JsonlEventLog(str(tmp_path), "core", clock)
    log.emit("a", "info")
    clock.advance(24 * 3600)
    log.emit("b", "info")
    assert sorted(p.name for p in tmp_path.glob("core-*.jsonl")) == [
        "core-2026-11-04.jsonl",
        "core-2026-11-05.jsonl",
    ]


def test_sink_filters_by_level(tmp_path: Path) -> None:
    log = JsonlEventLog(str(tmp_path), "core", _clock(), level="warning")
    log.emit("quiet", "info")
    log.emit("loud", "error")
    assert [line["event"] for line in _lines(tmp_path)] == ["loud"]


def test_sink_prunes_files_older_than_retention(tmp_path: Path) -> None:
    (tmp_path / "core-2026-10-01.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "core-2026-11-01.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("keep", encoding="utf-8")
    log = JsonlEventLog(str(tmp_path), "core", _clock(), retention_days=14)
    log.emit("a", "info")
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["core-2026-11-01.jsonl", "core-2026-11-04.jsonl", "other.txt"]


def test_sink_survives_odd_values_and_unwritable_folder(tmp_path: Path) -> None:
    log = JsonlEventLog(str(tmp_path), "core", _clock())
    log.emit("a", "info", document="C:\\Work\\ünï_图\ud800.slddrw")  # a lone surrogate
    (line,) = _lines(tmp_path)
    assert "图" in str(line["document"])
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the folder should be", encoding="utf-8")
    broken = JsonlEventLog(str(blocked), "core", _clock())
    broken.emit("a", "info")  # must not raise
    assert broken.failures == 1

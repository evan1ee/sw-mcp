"""The JSON Lines log sink (guideline G3): a daily file, an allow-list of fields.

``cad_application`` emits through the ``EventLog`` port and never formats lines. This sink drops
every field outside the allow-list, so a value passed by mistake (a token, file contents) cannot
reach the file. A failure to write is counted, never raised: logging must not stop a job.
"""

import json
import os
import re
import threading
from datetime import date, timedelta
from typing import Final

from cad_application.ports import Clock, LogValue

# The common fields of G3, then the allowed extras.
ALLOWED_FIELDS: Final = frozenset(
    {
        "ts",
        "level",
        "process",
        "pid",
        "event",
        "request_id",
        "job_id",
        "operation_id",
        "document",
        "duration_ms",
        "error_code",
        "state",
        "from",
        "to",
        "tool",
        "reason",
        "count",
        "store",
    }
)
_LEVELS: Final = {"debug": 10, "info": 20, "warning": 30, "error": 40}
_DEFAULT_LEVEL: Final = "info"


class JsonlEventLog:
    def __init__(
        self,
        directory: str,
        process: str,
        clock: Clock,
        *,
        level: str = _DEFAULT_LEVEL,
        retention_days: int = 14,
    ) -> None:
        self._dir = directory
        self._process = process
        self._clock = clock
        self._threshold = _LEVELS.get(level, _LEVELS[_DEFAULT_LEVEL])
        self._retention_days = retention_days
        self._pattern = re.compile(rf"^{re.escape(process)}-(\d{{4}}-\d{{2}}-\d{{2}})\.jsonl$")
        self._guard = threading.Lock()
        self._pruned_on: date | None = None
        self.failures = 0

    def emit(self, event: str, level: str, **fields: LogValue) -> None:
        if _LEVELS.get(level, _LEVELS[_DEFAULT_LEVEL]) < self._threshold:
            return
        now = self._clock.now()
        record: dict[str, LogValue] = {
            "ts": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
            "level": level,
            "process": self._process,
            "pid": os.getpid(),
            "event": event,
        }
        record.update({k: v for k, v in fields.items() if k in ALLOWED_FIELDS})
        line = json.dumps(record, ensure_ascii=False).encode("utf-8", "backslashreplace") + b"\n"
        with self._guard:
            try:
                self._write(now.date(), line)
            except OSError:
                self.failures += 1

    def _write(self, today: date, line: bytes) -> None:
        os.makedirs(self._dir, exist_ok=True)
        path = os.path.join(self._dir, f"{self._process}-{today.isoformat()}.jsonl")
        with open(path, "ab") as handle:
            handle.write(line)
            handle.flush()
        if self._pruned_on != today:
            self._pruned_on = today
            self._prune(today)

    def _prune(self, today: date) -> None:
        cutoff = today - timedelta(days=self._retention_days)
        for name in os.listdir(self._dir):
            found = self._pattern.match(name)
            if found is None:
                continue
            try:
                stamp = date.fromisoformat(found.group(1))
            except ValueError:
                continue
            if stamp < cutoff:
                os.remove(os.path.join(self._dir, name))

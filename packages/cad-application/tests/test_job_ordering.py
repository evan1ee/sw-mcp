"""Journal-before-state inside a whole job run (spec 13.2.2)."""

import json

from cad_application.testing.job_rig import make_rig
from cad_application.testing.memory_fs import MemoryFileSystem
from cad_ir.core.json_types import JsonValue

type Doc = dict[str, JsonValue]


class _OrderFs(MemoryFileSystem):
    """Notes every job.json write whose state the journal has not recorded yet."""

    def __init__(self) -> None:
        super().__init__()
        self.journalled: set[str] = set()
        self.violations: list[str] = []
        self.state_writes = 0

    def append_line(self, path: str, line: str) -> None:
        super().append_line(path, line)
        record = json.loads(line)
        if record.get("type") == "state":
            self.journalled.add(record["to"])

    def write_atomic(self, path: str, data: bytes) -> None:
        if path.lower().endswith("job.json"):
            state = json.loads(data)["state"]
            self.state_writes += 1
            if state not in self.journalled:
                self.violations.append(state)
        super().write_atomic(path, data)


def test_job_state_changes_are_journalled_before_job_json(good_snapshot: Doc) -> None:
    fs = _OrderFs()
    rig = make_rig(snapshot=good_snapshot, fs=fs)
    rig.submit()
    assert rig.engine.run_next()
    assert fs.state_writes > 0
    assert fs.violations == []

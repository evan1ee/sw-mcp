"""Fixtures: a factory for started services over a temporary folder, stopped after the test."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from cad_application.ports import BackendProvider, FileSystem
from core_service.testing import ServiceRig, replay_provider

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "ipc"

type RigFactory = Callable[..., ServiceRig]


@pytest.fixture
def start_rig(tmp_path: Path) -> Iterator[RigFactory]:
    """``start_rig(scenario)`` replays ``tests/fixtures/ipc/<scenario>.jsonl`` against a real
    file on disk; ``provider=`` and ``fs=`` replace the replay; ``base=`` starts another service
    on an existing folder (a restart)."""
    started: list[ServiceRig] = []

    def make(  # noqa: PLR0913 - one knob per thing a test varies
        scenario: str | None = None,
        *,
        provider: BackendProvider | None = None,
        fs: FileSystem | None = None,
        name: str = "a.slddrw",
        user_extra: str = "",
        prepare: bool = True,
    ) -> ServiceRig:
        project, drawing = ServiceRig.prepare(tmp_path, name, user_extra)
        if not prepare:
            drawing = str(project / name)
        chosen = provider
        if chosen is None:
            assert scenario is not None
            chosen = replay_provider(scenario, drawing, FIXTURES)
        rig = ServiceRig.start(tmp_path, chosen, project=project, drawing=drawing, fs=fs)
        started.append(rig)
        return rig

    yield make
    for rig in started:
        rig.stop()

"""Backend providers (guideline G2). Until the pipe transport exists (milestone 6) the one
provider replays a transcript, so the whole core runs without SOLIDWORKS."""

import threading
from collections.abc import Callable
from pathlib import Path

from cad_application.ports import Backend, BackendUnavailable
from cad_ir.core.json_types import JsonValue
from cad_protocol.errors import IpcError, IpcProtocolFault
from cad_protocol.replay import Transcript, load_transcript, replay_backend

from core_service.discovery import NamedPipeBackendProvider

type NotificationCallback = Callable[[str, JsonValue], None]

__all__ = ["NamedPipeBackendProvider", "NotificationCallback", "ReplayBackendProvider"]


class ReplayBackendProvider:
    """Every ``acquire`` starts the transcript again. A transcript that cannot be read, or whose
    handshake fails, is ``BackendUnavailable`` with the catalogue code of the failure."""

    def __init__(self, transcript: Transcript | None = None, *, path: str | None = None) -> None:
        if (transcript is None) == (path is None):
            raise ValueError("give a transcript or a path, not both and not neither")
        self._transcript = transcript
        self._path = path
        self._guard = threading.Lock()

    @classmethod
    def from_file(cls, path: str) -> "ReplayBackendProvider":
        """A provider that reads ``path`` when it is first needed."""
        return cls(path=path)

    def acquire(self, on_notification: NotificationCallback) -> Backend:
        transcript = self._load()
        try:
            return replay_backend(transcript, on_notification=on_notification)
        except IpcError as error:
            raise BackendUnavailable(error.code, error.message, error.details) from None
        except IpcProtocolFault:
            raise BackendUnavailable(
                "BACKEND_LOST", "The add-in sent a frame the core cannot use."
            ) from None

    def _load(self) -> Transcript:
        with self._guard:
            if self._transcript is not None:
                return self._transcript
            assert self._path is not None
            try:
                text = Path(self._path).read_text(encoding="utf-8")
                self._transcript = load_transcript(text)
            except (OSError, ValueError, KeyError):  # UnicodeDecodeError is a ValueError
                raise BackendUnavailable("BACKEND_LOST", "The transcript cannot be read.") from None
            return self._transcript

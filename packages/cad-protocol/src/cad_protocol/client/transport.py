"""The byte transport under the IPC client: one frame per ``send`` and ``receive``."""

from typing import Protocol


class TransportTimeout(Exception):  # noqa: N818 - name fixed by the plan
    """No frame arrived within the limit."""


class TransportClosed(Exception):  # noqa: N818 - name fixed by the plan
    """The other end closed the pipe."""


class Transport(Protocol):
    def send(self, payload: bytes) -> None: ...

    def receive(self, timeout_s: float) -> bytes: ...

    def close(self) -> None: ...

"""Transcript replay (spec 8.7, 15.5): a scripted add-in for the Python client, no pipe, no clock.

A transcript is a timeline. ``send`` must match the next ``core_to_addin`` entry (ignoring
``_meta``); ``receive`` returns the next ``addin_to_core`` entry, or raises ``TransportTimeout``
when its ``t_ms`` is later than the limit allows after the last frame sent.
"""

import json
from dataclasses import dataclass
from typing import Any, Final, cast

from cad_ir.core.json_types import JsonValue

from cad_protocol.backend import IpcBackend
from cad_protocol.client.ipc_client import IpcClient, NotificationHandler
from cad_protocol.client.transport import TransportClosed, TransportTimeout

TRANSCRIPT_VERSION: Final = "0.1"
CORE_TO_ADDIN: Final = "core_to_addin"
ADDIN_TO_CORE: Final = "addin_to_core"
_SOURCES: Final = ("synthetic", "recorded")
_SIDES: Final = ("python", "csharp")
_MS_PER_S: Final = 1000

type Frame = dict[str, Any]


class TranscriptMismatch(AssertionError):  # noqa: N818 - reads as a failed assertion in tests
    """The client did something the transcript does not say."""


@dataclass(frozen=True, slots=True)
class TranscriptHeader:
    transcript: str
    scenario: str
    source: str
    sides: tuple[str, ...]
    config: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Entry:
    direction: str
    t_ms: int
    frame: Frame | None  # None for a close entry

    @property
    def is_close(self) -> bool:
        return self.frame is None


@dataclass(frozen=True, slots=True)
class Transcript:
    header: TranscriptHeader
    entries: tuple[Entry, ...]


# --- loading ------------------------------------------------------------------------------


def _object(line: str, number: int) -> dict[str, Any]:
    try:
        value = json.loads(line)
    except ValueError:
        raise ValueError(f"line {number}: not valid JSON") from None
    if not isinstance(value, dict):
        raise ValueError(f"line {number}: expected a JSON object")
    return cast("dict[str, Any]", value)


def _header(line: str) -> TranscriptHeader:
    raw = _object(line, 1)
    sides = cast("list[Any]", raw["sides"]) if isinstance(raw.get("sides"), list) else []
    problems = {
        "transcript must be " + TRANSCRIPT_VERSION: raw.get("transcript") != TRANSCRIPT_VERSION,
        "header needs a scenario name": not isinstance(raw.get("scenario"), str),
        "header source must be synthetic or recorded": raw.get("source") not in _SOURCES,
        "header sides must list python and/or csharp": not sides
        or not all(side in _SIDES for side in sides),
        "header needs a config object": not isinstance(raw.get("config"), dict),
    }
    for message, failed in problems.items():
        if failed:
            raise ValueError(f"line 1: {message}")
    return TranscriptHeader(
        transcript=raw["transcript"],
        scenario=raw["scenario"],
        source=raw["source"],
        sides=tuple(raw["sides"]),
        config=raw["config"],
    )


def _entry(line: str, number: int, previous_t: int) -> Entry:
    raw = _object(line, number)
    t_ms = raw.get("t_ms")
    if isinstance(t_ms, bool) or not isinstance(t_ms, int) or t_ms < previous_t:
        raise ValueError(f"line {number}: t_ms must be an integer that does not go backwards")
    direction = raw.get("dir")
    if direction not in (CORE_TO_ADDIN, ADDIN_TO_CORE):
        raise ValueError(f"line {number}: dir must be {CORE_TO_ADDIN} or {ADDIN_TO_CORE}")
    if raw.get("close") is True and direction == ADDIN_TO_CORE and "frame" not in raw:
        return Entry(direction, t_ms, None)
    frame = raw.get("frame")
    if not isinstance(frame, dict):
        raise ValueError(f"line {number}: an entry needs a frame object, or close from the add-in")
    return Entry(direction, t_ms, cast("Frame", frame))


def load_transcript(text: str) -> Transcript:
    """Parse JSON Lines text; pure, so callers read the file themselves."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("transcript has no header line")
    entries: list[Entry] = []
    previous_t = 0
    for number, line in enumerate(lines[1:], start=2):
        entry = _entry(line, number, previous_t)
        previous_t = entry.t_ms
        entries.append(entry)
    return Transcript(_header(lines[0]), tuple(entries))


# --- comparison ---------------------------------------------------------------------------


def _masked(value: JsonValue) -> JsonValue:
    """The value without ``_meta`` (spec 8.7 masking)."""
    if isinstance(value, dict):
        return {k: _masked(v) for k, v in value.items() if k != "_meta"}
    if isinstance(value, list):
        return [_masked(v) for v in value]
    return value


def _shown(value: JsonValue) -> str:
    """The value as text for a failure message, with tokens hidden (G3)."""
    if isinstance(value, dict):
        hidden = {k: "***" if k == "token" else json.loads(_shown(v)) for k, v in value.items()}
        return json.dumps(hidden, ensure_ascii=False, sort_keys=True)
    if isinstance(value, list):
        return json.dumps([json.loads(_shown(v)) for v in value], ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False)


# --- the transport ------------------------------------------------------------------------


class ReplayTransport:
    """A ``Transport`` that plays a transcript."""

    def __init__(self, transcript: Transcript) -> None:
        self._entries = transcript.entries
        self._index = 0
        self._last_sent_ms = 0
        self._closed = False
        self._sent: list[Frame] = []

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def exhausted(self) -> bool:
        return self._index >= len(self._entries)

    @property
    def sent_frames(self) -> tuple[Frame, ...]:
        return tuple(self._sent)

    def send(self, payload: bytes) -> None:
        if self._closed:
            raise TransportClosed
        frame = cast("Frame", json.loads(payload))
        self._sent.append(frame)
        if self.exhausted:
            raise TranscriptMismatch(f"the transcript is over, but the client sent {_shown(frame)}")
        entry = self._entries[self._index]
        if entry.frame is None:
            self._index += 1
            self._closed = True
            raise TransportClosed
        if entry.direction != CORE_TO_ADDIN:
            raise TranscriptMismatch(
                f"the client sent {_shown(frame)} while the add-in's {_shown(entry.frame)} "
                "was still to come"
            )
        if _masked(frame) != _masked(entry.frame):
            raise TranscriptMismatch(
                f"sent {_shown(_masked(frame))}\nexpected {_shown(_masked(entry.frame))}"
            )
        self._index += 1
        self._last_sent_ms = entry.t_ms

    def receive(self, timeout_s: float) -> bytes:
        if self._closed:
            raise TransportClosed
        ahead = next(
            (
                i
                for i in range(self._index, len(self._entries))
                if self._entries[i].direction == ADDIN_TO_CORE
            ),
            None,
        )
        if ahead is None:
            raise TranscriptMismatch("the client waited for a frame the transcript does not have")
        entry = self._entries[ahead]
        if entry.t_ms - self._last_sent_ms > timeout_s * _MS_PER_S:
            raise TransportTimeout
        if ahead != self._index:
            expected = self._entries[self._index].frame
            raise TranscriptMismatch(f"the client should have sent {_shown(expected)} first")
        self._index += 1
        if entry.frame is None:
            self._closed = True
            raise TransportClosed
        return json.dumps(entry.frame, ensure_ascii=False).encode("utf-8")

    def close(self) -> None:
        self._closed = True


def replay_backend(
    transcript: Transcript, *, on_notification: NotificationHandler | None = None
) -> IpcBackend:
    """A backend over a transcript; the handshake is already done.

    ``on_notification`` receives each notification of the add-in, as ``IpcClient`` delivers it.
    """
    # A frozen clock: the transcript's t_ms is the only time, so real elapsed time never counts.
    client = IpcClient(
        ReplayTransport(transcript),
        token=transcript.header.config["token"],
        on_notification=on_notification,
        monotonic=lambda: 0.0,
    )
    return IpcBackend(client)

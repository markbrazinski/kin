"""Deterministic FakeWhisperModel for tests — duck-typed against faster-whisper.

Mirrors faster-whisper's WhisperModel surface enough for WhisperAdapter to
exercise: a sync transcribe(audio_path, **kw) returning (segments, info).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeSegment:
    text: str


@dataclass
class FakeInfo:
    language: str = "es"
    language_probability: float = 0.95
    duration: float = 5.0


class FakeWhisperModel:
    """Returns a configured set of segments + info on each transcribe() call.

    Captures the kwargs passed by the adapter (`language`, `task`,
    `beam_size`, etc.) so tests can assert routing behavior.
    """

    def __init__(
        self,
        segments: list[str] | None = None,
        info: FakeInfo | None = None,
    ) -> None:
        self._segment_texts: list[str] = segments if segments is not None else ["hola"]
        self._info: FakeInfo = info if info is not None else FakeInfo()
        self.call_count = 0
        self.last_kwargs: dict[str, Any] = {}
        self.last_audio_path: str | None = None

    def transcribe(
        self, audio_path: str, **kwargs: Any
    ) -> tuple[Iterator[FakeSegment], FakeInfo]:
        self.call_count += 1
        self.last_audio_path = audio_path
        self.last_kwargs = dict(kwargs)
        return iter([FakeSegment(text=t) for t in self._segment_texts]), self._info


@dataclass
class RaisingWhisperModel:
    """transcribe() raises a configured exception on every call."""

    error: Exception
    call_count: int = field(default=0, init=False)

    def transcribe(self, audio_path: str, **kwargs: Any) -> Any:
        self.call_count += 1
        raise self.error

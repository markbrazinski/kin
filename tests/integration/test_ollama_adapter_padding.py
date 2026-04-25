"""Padding-branch coverage for OllamaAdapter (Day 5 Session 1B).

Two tests against real ffmpeg (or its absence):

  - test_padding_unavailable_when_ffmpeg_missing — PATH cleared so
    ffmpeg cannot be exec'd; PaddingUnavailable raised before any
    inference call attempted.
  - test_padding_failed_on_invalid_audio — real ffmpeg exits non-zero
    on malformed bytes; PaddingFailed raised with returncode + stderr.

Both raise inside _preprocess(), well before _call_with_timeout(). No
FakeClock needed; no inference call ever issued.
"""

from pathlib import Path

import pytest

from integration.ollama_adapter import (
    OllamaAdapter,
    PaddingFailed,
    PaddingUnavailable,
)


class _NeverCalledClient:
    """Sentinel client. If chat() is invoked, the test failed earlier
    than expected — _preprocess should have raised before we got here.
    """

    def __init__(self) -> None:
        self.call_count = 0

    def chat(self, **_kwargs: object) -> None:
        self.call_count += 1
        raise AssertionError(
            "OllamaAdapter.transcribe reached chat() despite a padding failure; "
            "PaddingUnavailable / PaddingFailed should raise before inference."
        )


@pytest.mark.asyncio
async def test_padding_unavailable_when_ffmpeg_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PATH cleared → subprocess.run(['ffmpeg', ...]) raises FileNotFoundError
    → adapter maps to PaddingUnavailable, no inference attempted.
    """
    monkeypatch.setenv("PATH", "")

    audio = tmp_path / "input.wav"
    audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    client = _NeverCalledClient()
    adapter = OllamaAdapter(client=client)

    with pytest.raises(PaddingUnavailable, match=r"ffmpeg"):
        await adapter.transcribe(audio)

    assert client.call_count == 0


@pytest.mark.asyncio
async def test_padding_failed_on_invalid_audio(tmp_path: Path) -> None:
    """Real ffmpeg + bad input bytes → non-zero exit → PaddingFailed
    carrying ffmpeg's exit code in the message. No inference attempted.
    """
    audio = tmp_path / "bad.wav"
    audio.write_bytes(b"not a wav file")

    client = _NeverCalledClient()
    adapter = OllamaAdapter(client=client)

    with pytest.raises(PaddingFailed, match=r"exit="):
        await adapter.transcribe(audio)

    assert client.call_count == 0

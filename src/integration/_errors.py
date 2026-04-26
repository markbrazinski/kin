"""Shared adapter exception base classes — Whisper and Ollama both raise these."""

from __future__ import annotations


class AdapterError(Exception):
    """Base for all Integration-layer adapter failures."""


class InferenceTimeout(AdapterError):
    """Per-adapter timeout fired before the model returned.

    NOTE: this is a Core-time guarantee only. The worker thread wrapping
    the underlying sync call (ollama.chat / WhisperModel.transcribe)
    continues running to natural completion; results are discarded
    client-side. See scripts/gemma_hello.py finding 1 and
    PROJECT_PLAN §7 Locked.
    """


class InferenceFailed(AdapterError):
    """Inference call surfaced a non-timeout error and exhausted any retries.

    For OllamaAdapter this means both attempts at ollama.chat raised
    ollama.ResponseError or ollama.RequestError. For WhisperAdapter
    there is no retry; any non-timeout exception from
    WhisperModel.transcribe converts directly to this class.
    InferenceTimeout is a separate path and never converts to this.
    """

"""build_model(provider, size) -> a ChatModel. Imports happen inside, so tests never load torch."""

from __future__ import annotations

from mcpagent.llm.base import ChatModel, ChatResult, ToolCall

__all__ = ["ChatModel", "ChatResult", "ToolCall", "build_model"]


def build_model(provider: str, model: str | None = None) -> ChatModel:
    """provider: gemini | local | fake. model: a model id, or 'small' / 'big' (default big)."""
    if provider == "fake":
        from mcpagent.llm.fake import FakeModel

        return FakeModel()
    if provider == "gemini":
        from mcpagent.llm import gemini

        names = {"small": gemini.SMALL, "big": gemini.BIG}
        return gemini.GeminiModel(names.get(model or "big", model))
    if provider == "local":
        from mcpagent.llm import local

        names = {"small": local.SMALL, "big": local.BIG}
        return local.LocalModel(names.get(model or "big", model))
    raise ValueError(f"unknown provider {provider!r}: use gemini, local or fake")

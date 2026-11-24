"""One small interface for every model: chat(messages, tools) -> ChatResult.

Messages and tools use the OpenAI chat format (Gemini's OpenAI-compatible endpoint speaks it,
and the local Qwen chat template understands it too), so the agent loop never changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict  # already parsed from JSON; {} if the model sent invalid JSON
    raw_arguments: str = ""  # what the model really sent, kept for debugging


@dataclass(frozen=True)
class ChatResult:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0

    def as_message(self) -> dict:
        """The assistant turn to append to the history (OpenAI format)."""
        msg: dict = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                }
                for c in self.tool_calls
            ]
        return msg


class ChatModel(Protocol):
    name: str

    def chat(self, messages: list[dict], tools: list[dict]) -> ChatResult: ...


def parse_arguments(text: str) -> dict:
    try:
        value = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}

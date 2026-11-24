"""Gemini through its OpenAI-compatible endpoint (the project brief's setup).

    GEMINI_API_KEY=...   in .env  (free key from Google AI Studio)
    MCP_AGENT_PROVIDER=gemini   MCP_AGENT_MODEL=gemini-3.8-flash  (or gemini-3.5-flash-lite)

The `openai` package is pointed at Google's base URL, so the same client code would work for
any OpenAI-compatible provider. Free tier: limited requests per minute and per day, so the
evaluation pauses between calls (MCP_AGENT_SLEEP_S) and resumes from its saved results.
Free-tier prompts may be used by Google to improve its products: use sample data only.
"""

from __future__ import annotations

import os
import time

from mcpagent.llm.base import ChatResult, ToolCall, parse_arguments

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
SMALL, BIG = "gemini-3.5-flash-lite", "gemini-3.8-flash"


class GeminiModel:
    def __init__(self, name: str = BIG) -> None:
        from openai import OpenAI

        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set: put it in .env (see .env.example)")
        self.name = name
        self._client = OpenAI(api_key=key, base_url=BASE_URL)

    def chat(self, messages: list[dict], tools: list[dict]) -> ChatResult:
        start = time.perf_counter()
        resp = self._client.chat.completions.create(model=self.name, messages=messages, tools=tools)
        seconds = time.perf_counter() - start
        msg = resp.choices[0].message
        calls = [
            ToolCall(
                id=c.id,
                name=c.function.name,
                arguments=parse_arguments(c.function.arguments),
                raw_arguments=c.function.arguments or "",
            )
            for c in (msg.tool_calls or [])
        ]
        usage = resp.usage
        return ChatResult(
            content=msg.content or "",
            tool_calls=calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            seconds=seconds,
        )

"""An offline stand-in model for tests and CI. It never calls a network and is NOT intelligent.

Rules: a question with a GitHub repo name (owner/name) -> read_github_file; a question that
says "save"/"write a note" -> write_note; anything else -> search_notes with the last
meaningful word. After one tool result it answers with the first line of that result.
"""

from __future__ import annotations

import re

from mcpagent.llm.base import ChatResult, ToolCall

REPO = re.compile(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b")
STOP = {"what", "does", "my", "note", "notes", "on", "say", "about", "the", "a", "an", "of", "in"}


class FakeModel:
    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages: list[dict], tools: list[dict]) -> ChatResult:
        self.calls += 1
        last = messages[-1]
        if last["role"] == "tool":
            first = (last["content"] or "").splitlines()[0] if last["content"] else ""
            return ChatResult(content=f"From the tool: {first}", seconds=0.01)
        question = last["content"]
        repo = REPO.search(question)
        if repo:
            call = ToolCall("call_1", "read_github_file", {"repo": repo.group(1)})
        elif re.search(r"\b(save|write)\b.*\bnote\b", question, re.I):
            title = re.search(r"(?:called|named)\s+([\w-]+)", question)
            text = question.split(":", 1)[-1].strip()
            call = ToolCall(
                "call_1", "write_note", {"title": title.group(1) if title else "note", "text": text}
            )
        else:
            words = [w for w in re.findall(r"[A-Za-z]+", question.lower()) if w not in STOP]
            call = ToolCall("call_1", "search_notes", {"query": words[-1] if words else question})
        return ChatResult(content="", tool_calls=[call], seconds=0.01)

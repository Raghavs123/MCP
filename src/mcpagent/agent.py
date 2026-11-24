"""The agent: start the MCP server, list its tools, and loop model -> tools -> model.

It knows nothing about notes or GitHub: it only learns the tools from the server
(session.list_tools()). That is the point of MCP: swap the server, and the agent gets new tools.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcpagent.llm.base import ChatModel

ROOT = Path(__file__).resolve().parents[2]
SYSTEM = "Use the tools when they help. Answer briefly."
MAX_STEPS = 5  # hard stop, so a confused model can never loop forever


@dataclass
class ToolUse:
    name: str
    arguments: dict
    seconds: float
    result_preview: str


@dataclass
class AgentResult:
    answer: str
    tools_used: list[ToolUse] = field(default_factory=list)
    steps: int = 0  # model calls
    stopped: bool = False  # True if MAX_STEPS was reached without an answer
    seconds: float = 0.0  # whole question, wall clock
    llm_seconds: float = 0.0
    tool_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def server_params(notes_dir: Path | None = None) -> StdioServerParameters:
    """How to start our server as a child process (exactly what Claude Desktop does too)."""
    env = dict(os.environ)
    if notes_dir is not None:
        env["MCP_NOTES_DIR"] = str(notes_dir)
    return StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], env=env)


def mcp_tools_to_functions(mcp_tools) -> list[dict]:
    """MCP tool list -> the 'function' format chat models understand."""
    return [
        {
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.inputSchema},
        }
        for t in mcp_tools
    ]


async def run_agent(question: str, model: ChatModel, session: ClientSession) -> AgentResult:
    start = time.perf_counter()
    functions = mcp_tools_to_functions((await session.list_tools()).tools)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    res = AgentResult(answer="")
    for _ in range(MAX_STEPS):
        reply = model.chat(messages, functions)
        res.steps += 1
        res.llm_seconds += reply.seconds
        res.input_tokens += reply.input_tokens
        res.output_tokens += reply.output_tokens
        if not reply.tool_calls:
            res.answer = reply.content
            break
        messages.append(reply.as_message())
        for call in reply.tool_calls:
            t = time.perf_counter()
            out = await session.call_tool(call.name, call.arguments)
            text = out.content[0].text if out.content else ""
            res.tool_seconds += time.perf_counter() - t
            res.tools_used.append(ToolUse(call.name, call.arguments, time.perf_counter() - t, text[:200]))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": text})
    else:
        res.answer, res.stopped = f"Stopped after {MAX_STEPS} steps.", True
    res.seconds = time.perf_counter() - start
    return res


async def ask(question: str, model: ChatModel, notes_dir: Path | None = None) -> AgentResult:
    """One question with a freshly started server (the brief's agent.py does exactly this)."""
    async with stdio_client(server_params(notes_dir)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await run_agent(question, model, session)

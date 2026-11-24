"""The real MCP protocol: an in-memory client, the stdio server process, and the raw JSON client."""

import asyncio
import os

from mcp.shared.memory import create_connected_server_and_client_session

from mcpagent.agent import ROOT
from mcpagent.raw_client import handshake_and_call
from mcpagent.server import mcp


def test_server_lists_three_tools_with_schemas():
    async def run():
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            return (await session.list_tools()).tools

    tools = {t.name: t for t in asyncio.run(run())}
    assert set(tools) == {"search_notes", "read_github_file", "write_note"}
    assert tools["search_notes"].inputSchema["required"] == ["query"]
    assert "repo" in tools["read_github_file"].inputSchema["required"]


def test_tool_call_over_the_protocol_uses_the_notes_folder(tmp_path, monkeypatch):
    (tmp_path / "x.md").write_text("- Chunk size: 500 tokens\n", encoding="utf-8")
    monkeypatch.setenv("MCP_NOTES_DIR", str(tmp_path))

    async def run():
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            return await session.call_tool("search_notes", {"query": "chunk size"})

    out = asyncio.run(run())
    assert out.content[0].text == "x.md: - Chunk size: 500 tokens"


def test_hand_written_json_rpc_client_talks_to_the_stdio_server(tmp_path):
    (tmp_path / "x.md").write_text("- never print() in a stdio server\n", encoding="utf-8")
    env = dict(os.environ, MCP_NOTES_DIR=str(tmp_path))
    out = handshake_and_call(ROOT / "server.py", "search_notes", {"query": "print"}, env)
    assert out["server"]["name"] == "notes-and-github"
    assert out["tools"] == ["search_notes", "read_github_file", "write_note"]
    assert out["call"] == "x.md: - never print() in a stdio server"


def test_streamable_http_transport_serves_the_same_tools(tmp_path):
    """Stretch goal: the same server over HTTP, as a remote client would use it."""
    import socket
    import subprocess
    import sys
    import time

    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(os.environ, MCP_NOTES_DIR=str(tmp_path))
    (tmp_path / "x.md").write_text("- streamable HTTP for remote servers\n", encoding="utf-8")
    srv = subprocess.Popen(
        [sys.executable, str(ROOT / "server.py"), "--http", "--port", str(port)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    async def run():
        async with streamable_http_client(f"http://127.0.0.1:{port}/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = [t.name for t in (await session.list_tools()).tools]
                out = await session.call_tool("search_notes", {"query": "remote"})
                return names, out.content[0].text

    try:
        for _ in range(100):  # wait until the port answers
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.1)
        names, text = asyncio.run(run())
    finally:
        srv.terminate()
        srv.wait(timeout=10)
    assert names == ["search_notes", "read_github_file", "write_note"]
    assert text == "x.md: - streamable HTTP for remote servers"

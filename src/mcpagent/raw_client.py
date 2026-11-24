"""A second, completely different MCP client: plain JSON-RPC over stdio, no MCP SDK at all.

MCP's stdio transport is simply one JSON message per line on the server's stdin/stdout.
If this hand-written client can list and call our tools, the server speaks the standard
protocol, not something private to our agent. (Claude Desktop is a third client: see README.)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROTOCOL_VERSION = "2025-06-18"  # the client proposes a version; the server answers with its own


class RawStdioClient:
    def __init__(self, server: Path, env: dict | None = None) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, str(server)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # the server logs there; stdout is only for the protocol
            text=True,
            encoding="utf-8",
            env=env,
        )
        self._id = 0

    def request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})
        while True:  # skip notifications until our answer arrives
            msg = json.loads(self.proc.stdout.readline())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    def notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def _send(self, msg: dict) -> None:
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.wait(timeout=10)


def handshake_and_call(server: Path, tool: str, arguments: dict, env: dict | None = None) -> dict:
    c = RawStdioClient(server, env)
    try:
        init = c.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "raw-json-client", "version": "0.1"},
            },
        )
        c.notify("notifications/initialized")
        listed = c.request("tools/list")
        called = c.request("tools/call", {"name": tool, "arguments": arguments})
    finally:
        c.close()
    return {
        "server": init["serverInfo"],
        "protocolVersion": init["protocolVersion"],
        "tools": [t["name"] for t in listed["tools"]],
        "call": called["content"][0]["text"],
    }

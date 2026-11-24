"""The MCP server: three tools over stdio (default) or streamable HTTP.

    python server.py                   stdio: started by a client (the agent, Claude Desktop ...)
    python server.py --http            streamable HTTP on http://127.0.0.1:8000/mcp

Never print() in a stdio server: stdout carries the protocol messages. Log to stderr.
"""

from __future__ import annotations

import argparse
import logging
import sys

from mcp.server.fastmcp import FastMCP

from mcpagent import tools

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("mcp-agent-server")

mcp = FastMCP("notes-and-github")


@mcp.tool()
def search_notes(query: str) -> str:
    """Search my markdown notes for a keyword or short phrase. Returns matching lines with file names."""
    log.info("search_notes %r", query)
    return tools.search_notes(query)


@mcp.tool()
def read_github_file(repo: str, path: str = "README.md") -> str:
    """Read a file from a public GitHub repo, for example repo='rasbt/LLMs-from-scratch'.

    Returns the first 6000 characters.
    """
    log.info("read_github_file %s %s", repo, path)
    return tools.read_github_file(repo, path)


@mcp.tool()
def write_note(title: str, text: str) -> str:
    """Save a new markdown note with this title and text. Never overwrites an existing note."""
    log.info("write_note %r", title)
    return tools.write_note(title, text)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--http", action="store_true", help="streamable HTTP instead of stdio")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv)
    if args.http:
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
